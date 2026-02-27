"""FastAPI wrapper around the MCP server with optional API-key auth."""

from __future__ import annotations

import os
from contextlib import asynccontextmanager
from typing import Any, Awaitable, Callable, Dict, cast

from fastapi import Depends, FastAPI, Header, HTTPException, Request, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field

from server import (
    call_source_endpoint,
    datastore_search,
    get_dataset,
    get_resource,
    list_publishers,
    list_sources,
    mcp,
    memory_search,
    preview_resource,
    publisher_summary,
    search_datasets,
    vector_memory,
)

ToolCallable = Callable[..., Awaitable[Any]]


def _normalize_key(raw: str) -> str:
    # Accept escaped/local-dev variants while preserving the intended key pattern.
    return raw.replace("\\$", "$")


FASTAPI_API_KEY = _normalize_key(os.getenv("FASTAPI_API_KEY", "$$hrn&ali4KSA$$"))
MCP_PUBLIC_BASE_URL = os.getenv("MCP_PUBLIC_BASE_URL", "http://ksa-opendata-mcp.localhost:8000")
MCP_SERVER_NAME = os.getenv("MCP_SERVER_NAME", "KSA Open Data MCP")
MCP_SERVER_DESCRIPTION = os.getenv(
    "MCP_SERVER_DESCRIPTION",
    "National Saudi Open Data MCP with FastAPI and vector memory.",
)
MCP_ICON_URL = os.getenv(
    "MCP_ICON_URL",
    "http://ksa-opendata-mcp.localhost:8000/assets/ksa-mcp-icon-128.jpg",
)
MCP_API_KEY_REQUIRED = os.getenv("MCP_API_KEY_REQUIRED", "false").strip().lower() in {
    "1",
    "true",
    "yes",
    "on",
}

if MCP_API_KEY_REQUIRED and not FASTAPI_API_KEY.strip():
    raise RuntimeError("FASTAPI_API_KEY must be set and non-empty")

mcp_http_app = cast(Any, mcp).http_app(
    path="/",
    transport="streamable-http",
)

TOOLS: Dict[str, ToolCallable] = {
    "list_sources": list_sources,
    "list_publishers": list_publishers,
    "search_datasets": search_datasets,
    "get_dataset": get_dataset,
    "get_resource": get_resource,
    "preview_resource": preview_resource,
    "publisher_summary": publisher_summary,
    "datastore_search": datastore_search,
    "call_source_endpoint": call_source_endpoint,
    "memory_search": memory_search,
}

TOOL_BRIEFS: Dict[str, str] = {
    "list_sources": "List configured source connectors and endpoint capabilities.",
    "list_publishers": "Return publishers (organizations) with optional query filtering.",
    "search_datasets": "Search CKAN datasets with ranking metadata.",
    "get_dataset": "Fetch full dataset metadata and resources by id/name.",
    "get_resource": "Fetch CKAN resource metadata.",
    "preview_resource": "Preview CSV/JSON/XLSX resource rows with size limits.",
    "publisher_summary": "Aggregate publisher formats/tags from sampled datasets.",
    "datastore_search": "Query CKAN DataStore resources with filters.",
    "call_source_endpoint": "Call allowlisted ministry/authority REST endpoints.",
    "memory_search": "Semantic retrieval over stored MCP response memory.",
}


class ToolCallRequest(BaseModel):
    arguments: Dict[str, Any] = Field(default_factory=dict)


def _equivalent_keys(key: str) -> set[str]:
    normalized = _normalize_key(key)
    return {
        normalized,
        normalized.replace("$$", "$"),
        normalized.replace("$", "$$"),
    }


def require_api_key(x_api_key: str = Header("", alias="X-API-Key")) -> None:
    if not MCP_API_KEY_REQUIRED:
        return
    if _normalize_key(x_api_key) not in _equivalent_keys(FASTAPI_API_KEY):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid API key",
        )


@asynccontextmanager
async def app_lifespan(app: FastAPI) -> Any:
    await vector_memory.initialize()
    async with mcp_http_app.lifespan(app):
        yield


app = FastAPI(
    title="KSA Open Data MCP API",
    version="1.0.0",
    description=(
        "FastAPI wrapper around KSA Open Data MCP with mounted streamable MCP endpoint."
    ),
    lifespan=app_lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=False,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.mount("/mcp", mcp_http_app)
app.mount("/assets", StaticFiles(directory="assets"), name="assets")


@app.middleware("http")
async def auth_middleware(request: Request, call_next: Callable[..., Awaitable[Any]]) -> Any:
    if not MCP_API_KEY_REQUIRED:
        return await call_next(request)
    path = request.url.path
    is_protected = path.startswith("/api") or path.startswith("/mcp")
    is_open = path in {"/health", "/docs", "/openapi.json", "/redoc"}
    if is_protected and not is_open:
        api_key = request.headers.get("X-API-Key", "")
        if _normalize_key(api_key) not in _equivalent_keys(FASTAPI_API_KEY):
            return JSONResponse(
                status_code=status.HTTP_401_UNAUTHORIZED,
                content={"detail": "Invalid API key"},
            )
    return await call_next(request)


@app.get("/health")
async def health() -> Dict[str, str]:
    return {"status": "ok", "vector_memory": vector_memory.status}


@app.get("/api/welcome", dependencies=[Depends(require_api_key)])
async def api_welcome(request: Request) -> Dict[str, Any]:
    if MCP_PUBLIC_BASE_URL.strip().lower() == "auto" or not MCP_PUBLIC_BASE_URL.strip():
        effective_base = str(request.base_url).rstrip("/")
    else:
        effective_base = MCP_PUBLIC_BASE_URL.rstrip("/")
    icon_url = (
        f"{effective_base}/assets/ksa-mcp-icon-128.jpg"
        if MCP_ICON_URL.strip().lower() == "auto" or not MCP_ICON_URL.strip()
        else MCP_ICON_URL
    )
    auth_mode = "Custom header X-API-Key" if MCP_API_KEY_REQUIRED else "No auth (public mode)"
    return {
        "name": MCP_SERVER_NAME,
        "description": MCP_SERVER_DESCRIPTION,
        "icon_url": icon_url,
        "mcp_url": f"{effective_base}/mcp/",
        "tools_endpoint": f"{effective_base}/api/tools",
        "docs_url": f"{effective_base}/docs",
        "tool_count": len(TOOLS),
        "tool_briefs": TOOL_BRIEFS,
        "vector_memory": {"status": vector_memory.status},
        "chatgpt_mcp_setup": {
            "icon": icon_url,
            "name": MCP_SERVER_NAME,
            "description": MCP_SERVER_DESCRIPTION,
            "mcp_server_url": f"{effective_base}/mcp/",
            "authentication": auth_mode,
            "oauth": "Not required",
        },
    }


@app.get("/api/tools", dependencies=[Depends(require_api_key)])
async def list_tools_api() -> Dict[str, Any]:
    return {
        "count": len(TOOLS),
        "tools": [{"name": name, "brief": TOOL_BRIEFS[name]} for name in sorted(TOOLS)],
    }


@app.post("/api/tools/{tool_name}", dependencies=[Depends(require_api_key)])
async def call_tool_api(tool_name: str, request: ToolCallRequest) -> Dict[str, Any]:
    tool = TOOLS.get(tool_name)
    if tool is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Unknown tool '{tool_name}'",
        )
    try:
        result = await tool(**request.arguments)
    except TypeError as exc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Invalid arguments for tool '{tool_name}': {exc}",
        ) from exc
    except Exception as exc:  # noqa: BLE001
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Tool '{tool_name}' execution failed: {exc}",
        ) from exc
    return {"tool": tool_name, "result": result}
