"""Streamable HTTP MCP server for the Saudi national open data MCP."""

from __future__ import annotations

import logging
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional, cast
from urllib.parse import urlparse

from cachetools import TTLCache
from fastmcp import FastMCP

from ksa_opendata.config import settings
from ksa_opendata.logging import configure_logging
from ksa_opendata.registry import load_registry
from ksa_opendata.services.catalog import CatalogService
from ksa_opendata.services.datastore import DatastoreService
from ksa_opendata.services.preview import fetch_bytes, preview_csv, preview_json, preview_xlsx
from ksa_opendata.services.ranking import rank_datasets
from ksa_opendata.services.vector_memory import VectorMemoryService
from ksa_opendata.sources.rest import RestSourceAdapter

configure_logging()

logger = logging.getLogger(__name__)

ALLOWED_HOSTS: frozenset[str] = frozenset(
    [
        "open.data.gov.sa",
        "services.shc.gov.sa",
        "hdp.moh.gov.sa",
        "api.mcit.gov.sa",
        "data.sama.gov.sa",
        "opendata.cchi.gov.sa",
        "api.stats.gov.sa",
        "localhost",
        "127.0.0.1",
    ]
)

RATE_LIMIT_WINDOW = 60
RATE_LIMITS: TTLCache[str, int] = TTLCache(maxsize=512, ttl=RATE_LIMIT_WINDOW)
RATE_LIMITS_PER_TOOL: Dict[str, int] = {
    "preview_resource": 10,
    "search_datasets": 100,
    "list_publishers": 20,
    "list_sources": 15,
    "get_dataset": 40,
    "get_resource": 40,
    "publisher_summary": 20,
    "datastore_search": 20,
    "call_source_endpoint": 20,
    "memory_search": 40,
}


def enforce_rate_limit(tool_name: str) -> None:
    limit = RATE_LIMITS_PER_TOOL.get(tool_name, 60)
    count = RATE_LIMITS.get(tool_name, 0)
    if count >= limit:
        raise RuntimeError(f"Rate limit reached for {tool_name}")
    RATE_LIMITS[tool_name] = count + 1


def audit_tool(tool_name: str, status: str, details: Dict[str, Any] | None = None) -> None:
    logger.info(
        f"tool_event {tool_name}",
        extra={
            "tool": tool_name,
            "status": status,
            "details": details or {},
            "timestamp": datetime.now(timezone.utc).isoformat(),
        },
    )


def ensure_allowed_host(url: str) -> None:
    parsed = urlparse(url)
    host = parsed.hostname
    if not host:
        raise ValueError("URL does not have a hostname")
    if host not in ALLOWED_HOSTS:
        raise RuntimeError(f"Host '{host}' is not allowlisted")

mcp = FastMCP("KSA Open Data MCP")
registry = load_registry()
catalog_service = CatalogService(registry)
datastore_service = DatastoreService(registry)
_preview_cache: TTLCache[str, Dict[str, Any]] = TTLCache(maxsize=4096, ttl=600)
vector_memory = VectorMemoryService(
    database_url=settings.database_url,
    enabled=settings.vector_memory_enabled,
    ttl_seconds=settings.vector_memory_ttl_seconds,
    max_text_chars=settings.vector_memory_max_text_chars,
    embedding_dim=settings.embedding_dim,
    model_name=settings.embedding_model_name,
)


def _memory_request(**kwargs: Any) -> Dict[str, Any]:
    return {key: value for key, value in kwargs.items() if value is not None}


async def _memory_get(tool_name: str, request_payload: Dict[str, Any]) -> Any | None:
    try:
        return await vector_memory.get_cached(tool_name, request_payload)
    except Exception:  # noqa: BLE001
        logger.exception("vector_memory_get_failed", extra={"tool": tool_name})
        return None


async def _memory_store(tool_name: str, request_payload: Dict[str, Any], response: Any) -> None:
    try:
        await vector_memory.store(tool_name, request_payload, response)
    except Exception:  # noqa: BLE001
        logger.exception("vector_memory_store_failed", extra={"tool": tool_name})


@mcp.tool()
async def list_sources() -> List[Dict[str, Any]]:
    enforce_rate_limit("list_sources")
    request_payload = _memory_request()
    cached = await _memory_get("list_sources", request_payload)
    if isinstance(cached, list):
        result = cast(List[Dict[str, Any]], cached)
        audit_tool("list_sources", "success", {"count": len(result), "memory_hit": True})
        return result
    result = [
        {
            "id": source.id,
            "type": source.type,
            "title": source.title,
            "base_url": source.base_url,
            "requires_auth": bool(source.auth),
            "endpoints": [e.get("name") for e in source.endpoints],
        }
        for source in registry.list()
    ]
    await _memory_store("list_sources", request_payload, result)
    audit_tool("list_sources", "success", {"count": len(result)})
    return result


@mcp.tool()
async def list_publishers(
    source_id: str = "ksa_open_data_platform",
    query: str = "",
    limit: int = 200,
) -> List[Dict[str, Any]]:
    enforce_rate_limit("list_publishers")
    request_payload = _memory_request(source_id=source_id, query=query, limit=limit)
    cached = await _memory_get("list_publishers", request_payload)
    if isinstance(cached, list):
        result = cast(List[Dict[str, Any]], cached)
        audit_tool("list_publishers", "success", {"count": len(result), "memory_hit": True})
        return result
    result = await catalog_service.list_publishers(source_id, query, limit)
    await _memory_store("list_publishers", request_payload, result)
    audit_tool("list_publishers", "success", {"count": len(result)})
    return result


@mcp.tool()
async def search_datasets(
    source_id: str = "ksa_open_data_platform",
    query: str = "",
    publisher: Optional[str] = None,
    tag: Optional[str] = None,
    group: Optional[str] = None,
    rows: int = 10,
    start: int = 0,
    sort: str = "score desc, metadata_modified desc",
) -> Dict[str, Any]:
    enforce_rate_limit("search_datasets")
    request_payload = _memory_request(
        source_id=source_id,
        query=query,
        publisher=publisher,
        tag=tag,
        group=group,
        rows=rows,
        start=start,
        sort=sort,
    )
    cached = await _memory_get("search_datasets", request_payload)
    if isinstance(cached, dict):
        result = cast(Dict[str, Any], cached)
        audit_tool("search_datasets", "success", {"count": result.get("count"), "memory_hit": True})
        return result
    search_results = await catalog_service.search_datasets(
        source_id,
        query,
        publisher,
        tag,
        group,
        rows,
        start,
        sort,
    )
    ranked = rank_datasets(search_results.get("datasets", []), query)
    search_results["ranked_datasets"] = ranked
    await _memory_store("search_datasets", request_payload, search_results)
    audit_tool("search_datasets", "success", {"count": search_results.get("count")})
    return search_results


@mcp.tool()
async def get_dataset(
    source_id: str = "ksa_open_data_platform",
    dataset_id_or_name: str = "",
) -> Dict[str, Any]:
    enforce_rate_limit("get_dataset")
    request_payload = _memory_request(source_id=source_id, dataset_id_or_name=dataset_id_or_name)
    cached = await _memory_get("get_dataset", request_payload)
    if isinstance(cached, dict):
        result = cast(Dict[str, Any], cached)
        audit_tool("get_dataset", "success", {"dataset": result.get("id"), "memory_hit": True})
        return result
    result = await catalog_service.get_dataset(source_id, dataset_id_or_name)
    await _memory_store("get_dataset", request_payload, result)
    audit_tool("get_dataset", "success", {"dataset": result.get("id")})
    return result


@mcp.tool()
async def get_resource(
    source_id: str = "ksa_open_data_platform",
    resource_id: str = "",
) -> Dict[str, Any]:
    enforce_rate_limit("get_resource")
    request_payload = _memory_request(source_id=source_id, resource_id=resource_id)
    cached = await _memory_get("get_resource", request_payload)
    if isinstance(cached, dict):
        result = cast(Dict[str, Any], cached)
        audit_tool("get_resource", "success", {"resource": result.get("id"), "memory_hit": True})
        return result
    result = await catalog_service.get_resource(source_id, resource_id)
    await _memory_store("get_resource", request_payload, result)
    audit_tool("get_resource", "success", {"resource": result.get("id")})
    return result


@mcp.tool()
async def preview_resource(
    source_id: str = "ksa_open_data_platform",
    resource_id: Optional[str] = None,
    url: Optional[str] = None,
    rows: int = 20,
    max_bytes: int = 2_000_000,
) -> Dict[str, Any]:
    enforce_rate_limit("preview_resource")
    request_payload = _memory_request(
        source_id=source_id,
        resource_id=resource_id,
        url=url,
        rows=rows,
        max_bytes=max_bytes,
    )
    cached = await _memory_get("preview_resource", request_payload)
    if isinstance(cached, dict):
        result = cast(Dict[str, Any], cached)
        audit_tool("preview_resource", "success", {"memory_hit": True})
        return result
    if resource_id:
        resource = await catalog_service.get_resource(source_id, resource_id)
        resolved_url = resource.get("url")
        if not resolved_url:
            raise ValueError("Resource metadata is missing a URL")
    elif url:
        resolved_url = url
    else:
        raise ValueError("Provide either resource_id or url")
    cache_key = f"{resolved_url}-{rows}-{max_bytes}"
    if cache_key in _preview_cache:
        return _preview_cache[cache_key]

    content, headers = await fetch_bytes(resolved_url, max_bytes=max_bytes)
    ct = headers.get("content-type", "")
    fmt = (
        "json"
        if "json" in ct
        else "csv"
        if "csv" in ct
        else "xlsx"
        if "spreadsheet" in ct or "excel" in ct
        else "unknown"
    )
    try:
        if fmt == "csv":
            preview = preview_csv(content, rows=rows)
        elif fmt == "xlsx":
            preview = preview_xlsx(content, rows=rows)
        else:
            preview = preview_json(content, rows=rows)
    except Exception as exc:
        preview = {"error": str(exc)}

    ensure_allowed_host(resolved_url)
    result = {"url": resolved_url, "format_guess": fmt, "headers": headers, "preview": preview}
    _preview_cache[cache_key] = result
    await _memory_store("preview_resource", request_payload, result)
    audit_tool("preview_resource", "success", {"format": fmt})
    return result


@mcp.tool()
async def publisher_summary(
    source_id: str = "ksa_open_data_platform",
    publisher: str = "",
    sample_rows: int = 50,
) -> Dict[str, Any]:
    enforce_rate_limit("publisher_summary")
    request_payload = _memory_request(
        source_id=source_id,
        publisher=publisher,
        sample_rows=sample_rows,
    )
    cached = await _memory_get("publisher_summary", request_payload)
    if isinstance(cached, dict):
        result = cast(Dict[str, Any], cached)
        audit_tool("publisher_summary", "success", {"publisher": publisher, "memory_hit": True})
        return result
    result = await catalog_service.publisher_summary(source_id, publisher, sample_rows)
    await _memory_store("publisher_summary", request_payload, result)
    audit_tool("publisher_summary", "success", {"publisher": publisher})
    return result


@mcp.tool()
async def datastore_search(
    source_id: str = "ksa_open_data_platform",
    resource_id: str = "",
    filters: Optional[List[Dict[str, Any]]] = None,
    limit: int = 20,
    offset: int = 0,
) -> Dict[str, Any]:
    enforce_rate_limit("datastore_search")
    request_payload = _memory_request(
        source_id=source_id,
        resource_id=resource_id,
        filters=filters,
        limit=limit,
        offset=offset,
    )
    cached = await _memory_get("datastore_search", request_payload)
    if isinstance(cached, dict):
        result = cast(Dict[str, Any], cached)
        audit_tool("datastore_search", "success", {"resource": resource_id, "memory_hit": True})
        return result
    result = await datastore_service.search(source_id, resource_id, filters, limit, offset)
    await _memory_store("datastore_search", request_payload, result)
    audit_tool("datastore_search", "success", {"resource": resource_id})
    return result


@mcp.tool()
async def call_source_endpoint(
    source_id: str,
    endpoint: str,
    params: Optional[Dict[str, Any]] = None,
) -> Any:
    enforce_rate_limit("call_source_endpoint")
    request_payload = _memory_request(source_id=source_id, endpoint=endpoint, params=params or {})
    cached = await _memory_get("call_source_endpoint", request_payload)
    if cached is not None:
        audit_tool(
            "call_source_endpoint",
            "success",
            {"source": source_id, "endpoint": endpoint, "memory_hit": True},
        )
        return cached
    source = registry.get(source_id)
    adapter = RestSourceAdapter(source)
    endpoint_meta = adapter.validate_endpoint(endpoint)
    endpoint_url = f"{source.base_url.rstrip('/')}{endpoint_meta.get('path', '')}"
    ensure_allowed_host(endpoint_url)
    try:
        result = await adapter.call_endpoint(endpoint, params)
        await _memory_store("call_source_endpoint", request_payload, result)
        audit_tool("call_source_endpoint", "success", {"source": source_id, "endpoint": endpoint})
        return result
    finally:
        await adapter.close()


@mcp.tool()
async def memory_search(query: str, limit: int = 5) -> Dict[str, Any]:
    enforce_rate_limit("memory_search")
    result = await vector_memory.search(query=query, limit=limit)
    audit_tool("memory_search", "success", {"count": result.get("match_count", 0)})
    return result


if __name__ == "__main__":
    mcp.run(
        transport="streamable-http",
        host="0.0.0.0",
        port=8000,
    )
