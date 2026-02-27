"""CKAN catalog service with caching and helpers used by MCP tools."""

from __future__ import annotations

from typing import Any, Dict, List, Optional, Tuple, cast

from cachetools import TTLCache

from ksa_opendata.errors import SourceConfigError
from ksa_opendata.registry import SourceRegistry
from ksa_opendata.services.fallback_catalog import (
    fallback_dataset_detail,
    fallback_publisher_summary,
    fallback_publishers,
    fallback_resource_detail,
    fallback_search_datasets,
)
from ksa_opendata.sources.ckan import CKANClient, CKANConfig


class CatalogService:
    def __init__(self, registry: SourceRegistry) -> None:
        self.registry = registry
        self._org_cache: TTLCache[Tuple[str, str], List[Dict[str, Any]]] = TTLCache(
            maxsize=256,
            ttl=600,
        )
        self._dataset_cache: TTLCache[Tuple[str, str], Dict[str, Any]] = TTLCache(
            maxsize=1024,
            ttl=600,
        )
        self._resource_cache: TTLCache[Tuple[str, str], Dict[str, Any]] = TTLCache(
            maxsize=1024,
            ttl=600,
        )

    def _make_client(self, source_id: str) -> CKANClient:
        source = self.registry.get(source_id)
        if source.type != "ckan":
            raise SourceConfigError(f"Source '{source_id}' is not of type CKAN")
        if not source.api_path:
            raise SourceConfigError(f"CKAN source '{source_id}' missing 'api_path'")
        return CKANClient(CKANConfig(base_url=source.base_url, api_path=source.api_path))

    @staticmethod
    def _is_upstream_unavailable(exc: Exception) -> bool:
        message = str(exc).lower()
        markers = (
            "ckan returned non-json response",
            "waf",
            "forbidden",
            "connecterror",
            "timed out",
            "service unavailable",
            "temporary failure",
        )
        return any(marker in message for marker in markers)

    async def list_publishers(self, source_id: str, query: str, limit: int) -> List[Dict[str, Any]]:
        cache_key = (source_id, "org_list")
        if cache_key in self._org_cache:
            orgs = self._org_cache[cache_key]
        else:
            client = self._make_client(source_id)
            try:
                orgs = cast(
                    List[Dict[str, Any]],
                    await client.call("organization_list", {"all_fields": True}),
                )
            except Exception as exc:
                if self._is_upstream_unavailable(exc):
                    return fallback_publishers(query=query, limit=max(1, min(limit, 100)))
                raise
            finally:
                await client.close()
            self._org_cache[cache_key] = orgs

        filtered = []
        q = (query or "").strip().lower()
        for org in orgs:
            title = (org.get("title") or "").strip()
            name = (org.get("name") or "").strip()
            if q and q not in title.lower() and q not in name.lower():
                continue
            filtered.append(
                {
                    "id": org.get("id"),
                    "name": name,
                    "title": title,
                    "package_count": org.get("package_count"),
                    "description": (org.get("description") or "")[:500],
                }
            )
            if len(filtered) >= limit:
                break
        return filtered

    async def search_datasets(
        self,
        source_id: str,
        query: str,
        publisher: Optional[str],
        tag: Optional[str],
        group: Optional[str],
        rows: int,
        start: int,
        sort: str,
    ) -> Dict[str, Any]:
        client = self._make_client(source_id)
        params: Dict[str, Any] = {
            "q": query or "*:*",
            "rows": max(1, min(rows, 50)),
            "start": max(0, start),
            "sort": sort,
        }
        filters = []
        if publisher:
            filters.append(f"organization:{publisher}")
        if tag:
            filters.append(f"tags:{tag}")
        if group:
            filters.append(f"groups:{group}")
        if filters:
            params["fq"] = " AND ".join(filters)

        try:
            res = cast(Dict[str, Any], await client.call("package_search", params))
        except Exception as exc:
            if self._is_upstream_unavailable(exc):
                return fallback_search_datasets(
                    query=query,
                    publisher=publisher,
                    rows=rows,
                    start=start,
                )
            raise
        finally:
            await client.close()

        datasets = []
        for ds in res.get("results", []):
            org = ds.get("organization") or {}
            datasets.append(
                {
                    "id": ds.get("id"),
                    "name": ds.get("name"),
                    "title": ds.get("title"),
                    "publisher": org.get("title") or org.get("name"),
                    "metadata_modified": ds.get("metadata_modified"),
                    "tags": [t.get("name") for t in ds.get("tags", [])][:20],
                    "resources": [
                        {
                            "id": r.get("id"),
                            "name": r.get("name"),
                            "format": r.get("format"),
                            "url": r.get("url"),
                        }
                        for r in ds.get("resources", [])[:10]
                    ],
                }
            )

        return {
            "count": res.get("count"),
            "start": start,
            "rows": rows,
            "datasets": datasets,
        }

    async def get_dataset(self, source_id: str, dataset_id: str) -> Dict[str, Any]:
        cache_key = (source_id, dataset_id)
        if cache_key in self._dataset_cache:
            return self._dataset_cache[cache_key]
        client = self._make_client(source_id)
        try:
            data = cast(Dict[str, Any], await client.call("package_show", {"id": dataset_id}))
        except Exception as exc:
            if self._is_upstream_unavailable(exc):
                fallback = fallback_dataset_detail(dataset_id)
                self._dataset_cache[cache_key] = fallback
                return fallback
            raise
        finally:
            await client.close()
        org = data.get("organization") or {}
        result = {
            "id": data.get("id"),
            "name": data.get("name"),
            "title": data.get("title"),
            "notes": (data.get("notes") or "")[:4000],
            "license_id": data.get("license_id"),
            "metadata_created": data.get("metadata_created"),
            "metadata_modified": data.get("metadata_modified"),
            "publisher": {
                "id": org.get("id"),
                "name": org.get("name"),
                "title": org.get("title"),
            },
            "tags": [t.get("name") for t in data.get("tags", [])],
            "groups": [g.get("name") for g in data.get("groups", [])],
            "resources": [
                {
                    "id": r.get("id"),
                    "name": r.get("name"),
                    "description": (r.get("description") or "")[:1000],
                    "format": r.get("format"),
                    "mimetype": r.get("mimetype"),
                    "url": r.get("url"),
                    "size": r.get("size"),
                    "last_modified": r.get("last_modified"),
                }
                for r in data.get("resources", [])
            ],
        }
        source = self.registry.get(source_id)
        if source.dataset_web_url_template and result.get("name"):
            result["web_url"] = source.dataset_web_url_template.format(name=result["name"])
        self._dataset_cache[cache_key] = result
        return result

    async def get_resource(self, source_id: str, resource_id: str) -> Dict[str, Any]:
        cache_key = (source_id, resource_id)
        if cache_key in self._resource_cache:
            return self._resource_cache[cache_key]
        client = self._make_client(source_id)
        try:
            data = cast(Dict[str, Any], await client.call("resource_show", {"id": resource_id}))
        except Exception as exc:
            if self._is_upstream_unavailable(exc):
                fallback = fallback_resource_detail(resource_id)
                self._resource_cache[cache_key] = fallback
                return fallback
            raise
        finally:
            await client.close()
        result = {
            "id": data.get("id"),
            "name": data.get("name"),
            "description": (data.get("description") or "")[:2000],
            "format": data.get("format"),
            "mimetype": data.get("mimetype"),
            "url": data.get("url"),
            "size": data.get("size"),
            "last_modified": data.get("last_modified"),
        }
        self._resource_cache[cache_key] = result
        return result

    async def publisher_summary(
        self,
        source_id: str,
        publisher: str,
        sample_rows: int,
    ) -> Dict[str, Any]:
        client = self._make_client(source_id)
        try:
            res = cast(
                Dict[str, Any],
                await client.call(
                    "package_search",
                    {
                        "q": "*:*",
                        "fq": f"organization:{publisher}",
                        "rows": max(1, min(sample_rows, 200)),
                        "start": 0,
                    },
                ),
            )
        except Exception as exc:
            if self._is_upstream_unavailable(exc):
                return fallback_publisher_summary(
                    publisher=publisher,
                    sample_rows=sample_rows,
                )
            raise
        finally:
            await client.close()

        fmt_counts: Dict[str, int] = {}
        tag_counts: Dict[str, int] = {}
        for ds in res.get("results", []):
            for tag in ds.get("tags", []):
                name = tag.get("name")
                if name:
                    tag_counts[name] = tag_counts.get(name, 0) + 1
            for resource in ds.get("resources", []):
                fmt = (resource.get("format") or "unknown").lower().strip() or "unknown"
                fmt_counts[fmt] = fmt_counts.get(fmt, 0) + 1

        top_formats = sorted(fmt_counts.items(), key=lambda x: x[1], reverse=True)[:20]
        top_tags = sorted(tag_counts.items(), key=lambda x: x[1], reverse=True)[:20]

        return {
            "publisher": publisher,
            "total_datasets": res.get("count"),
            "sampled_datasets": len(res.get("results", [])),
            "top_formats": top_formats,
            "top_tags": top_tags,
        }
