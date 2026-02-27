"""Shared source adapter base types."""

from __future__ import annotations

from abc import ABC, abstractmethod
from http import HTTPStatus
from typing import Any, Dict

from ksa_opendata.registry import Source


class SourceAdapter(ABC):
    def __init__(self, source: Source) -> None:
        self.source = source

    @abstractmethod
    async def call_endpoint(self, endpoint_name: str, params: Dict[str, Any] | None = None) -> Any:
        """Call a configured endpoint for this source."""

    def validate_endpoint(self, endpoint_name: str) -> Dict[str, Any]:
        endpoints = self.source.endpoints or []
        for e in endpoints:
            if e.get("name") == endpoint_name:
                return e
        raise ValueError(f"Endpoint '{endpoint_name}' not found for source '{self.source.id}'")

    def _raise_for_status(self, status_code: int) -> None:
        if status_code >= HTTPStatus.INTERNAL_SERVER_ERROR:
            raise RuntimeError(f"Upstream error ({status_code}) from {self.source.id}")
