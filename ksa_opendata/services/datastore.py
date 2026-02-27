"""Optional CKAN Datastore access helpers."""

from __future__ import annotations

from typing import Any, Dict, List, cast

from ksa_opendata.errors import SourceConfigError
from ksa_opendata.registry import SourceRegistry
from ksa_opendata.services.fallback_catalog import fallback_datastore_search
from ksa_opendata.sources.ckan import CKANClient, CKANConfig


class DatastoreService:
    def __init__(self, registry: SourceRegistry) -> None:
        self.registry = registry

    def _make_client(self, source_id: str) -> CKANClient:
        source = self.registry.get(source_id)
        if source.type != "ckan" or not source.api_path:
            raise SourceConfigError(f"Source '{source_id}' does not expose a CKAN datastore")
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

    async def search(
        self,
        source_id: str,
        resource_id: str,
        filters: List[Dict[str, Any]] | None = None,
        limit: int = 20,
        offset: int = 0,
    ) -> Dict[str, Any]:
        client = self._make_client(source_id)
        params: Dict[str, Any] = {
            "resource_id": resource_id,
            "limit": max(1, min(limit, 100)),
            "offset": max(0, offset),
        }
        if filters:
            params["filters"] = filters
        try:
            return cast(Dict[str, Any], await client.call("datastore_search", params))
        except Exception as exc:
            if self._is_upstream_unavailable(exc):
                return fallback_datastore_search(
                    resource_id=resource_id,
                    limit=limit,
                    offset=offset,
                )
            raise
        finally:
            await client.close()
