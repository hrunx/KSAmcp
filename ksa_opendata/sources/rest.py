"""REST source adapters for ministry enterprise APIs."""

from __future__ import annotations

import os
from typing import Any, Dict

import httpx

from ksa_opendata.errors import SourceConfigError
from ksa_opendata.registry import Source
from ksa_opendata.sources.base import SourceAdapter


class RestSourceAdapter(SourceAdapter):
    def __init__(self, source: Source) -> None:
        super().__init__(source)
        self._client = httpx.AsyncClient(
            timeout=30.0,
            headers={"User-Agent": "ksa-opendata-mcp/0.1"},
            follow_redirects=True,
        )

    async def close(self) -> None:
        await self._client.aclose()

    async def call_endpoint(self, endpoint_name: str, params: Dict[str, Any] | None = None) -> Any:
        endpoint = self.validate_endpoint(endpoint_name)
        method = (endpoint.get("method") or "GET").upper()
        path = endpoint.get("path") or ""
        url = f"{self.source.base_url.rstrip('/')}{path}"

        headers = {}
        if self.source.type == "rest_api_key":
            auth = self.source.auth or {}
            header_key = auth.get("header")
            env_key = auth.get("env")
            if not header_key or not env_key:
                raise SourceConfigError(f"Source '{self.source.id}' missing auth.header/auth.env")
            api_key = os.environ.get(env_key)
            if not api_key:
                raise SourceConfigError(
                    f"Missing required env var '{env_key}' for '{self.source.id}'"
                )
            headers[header_key] = api_key

        response = await self._client.request(method, url, params=params or {}, headers=headers)
        self._raise_for_status(response.status_code)
        try:
            return response.json()
        except ValueError:
            return {"text": response.text}
