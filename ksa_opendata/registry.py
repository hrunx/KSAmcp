"""Source registry that drives MCP tool allowlists."""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, List, Optional

import yaml

from ksa_opendata.config import settings
from ksa_opendata.errors import SourceConfigError


@dataclass(frozen=True)
class Source:
    id: str
    type: str
    title: str
    base_url: str
    api_path: Optional[str] = None
    dataset_web_url_template: Optional[str] = None
    endpoints: List[Dict[str, Any]] = field(default_factory=list)
    auth: Dict[str, Any] = field(default_factory=dict)


class SourceRegistry:
    def __init__(self, sources_path: Path) -> None:
        self.sources_path = sources_path
        self._sources: Dict[str, Source] = {}

    def load(self) -> None:
        if not self.sources_path.exists():
            raise SourceConfigError(f"Sources config not found: {self.sources_path}")

        raw = yaml.safe_load(self.sources_path.read_text(encoding="utf-8")) or {}
        sources = raw.get("sources", [])
        parsed: Dict[str, Source] = {}
        for entry in sources:
            try:
                src = Source(
                    id=entry["id"],
                    type=entry["type"],
                    title=entry.get("title", entry["id"]),
                    base_url=entry["base_url"].rstrip("/"),
                    api_path=entry.get("api_path"),
                    dataset_web_url_template=entry.get("dataset_web_url_template"),
                    endpoints=entry.get("endpoints") or [],
                    auth=entry.get("auth") or {},
                )
            except KeyError as exc:
                raise SourceConfigError(f"Invalid source definition: {entry}") from exc
            parsed[src.id] = src

        self._sources = parsed

    def get(self, source_id: str) -> Source:
        if source_id not in self._sources:
            raise SourceConfigError(f"Unknown source_id={source_id}")
        return self._sources[source_id]

    def list(self) -> List[Source]:
        return list(self._sources.values())


def load_registry() -> SourceRegistry:
    registry = SourceRegistry(settings.sources_path)
    registry.load()
    return registry
