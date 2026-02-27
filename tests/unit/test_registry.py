from pathlib import Path

import pytest

from ksa_opendata.errors import SourceConfigError
from ksa_opendata.registry import Source, SourceRegistry


def test_source_registry_loads(tmp_path: Path):
    cfg = tmp_path / "sources.yaml"
    cfg.write_text(
        """
        sources:
          - id: test
            type: ckan
            title: Test Source
            base_url: https://test.example
        """
    )

    registry = SourceRegistry(cfg)
    registry.load()

    source = registry.get("test")
    assert isinstance(source, Source)
    assert source.title == "Test Source"
    assert source.base_url == "https://test.example"


def test_unknown_source_raises(tmp_path: Path):
    cfg = tmp_path / "sources.yaml"
    cfg.write_text("sources: []")

    registry = SourceRegistry(cfg)
    registry.load()

    with pytest.raises(SourceConfigError):
        registry.get("missing")
