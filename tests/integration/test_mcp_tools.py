import pytest

from ksa_opendata.registry import SourceRegistry
from ksa_opendata.services.catalog import CatalogService


class DummyCKANClient:
    def __init__(self, *args, **kwargs):
        pass

    async def call(self, action, params=None):
        if action == "organization_list":
            return [{"id": "n", "name": "ministry", "title": "Ministry"}]
        if action == "package_search":
            return {
                "count": 1,
                "results": [
                    {
                        "id": "ds",
                        "name": "demo",
                        "title": "Demo",
                        "tags": [],
                        "resources": [],
                    }
                ],
            }
        if action == "package_show":
            return {
                "id": "ds",
                "name": "demo",
                "title": "Demo",
                "tags": [],
                "groups": [],
                "resources": [],
            }
        if action == "resource_show":
            return {"id": "r", "name": "resource"}
        raise RuntimeError("unexpected action")

    async def close(self):
        return None


@pytest.mark.asyncio
async def test_catalog_service_search(monkeypatch, tmp_path):
    cfg = tmp_path / "sources.yaml"
    cfg.write_text(
        """
        sources:
          - id: ksa_open_data_platform
            type: ckan
            title: Demo
            base_url: https://example.com
            api_path: /api/3/action
        """
    )
    registry = SourceRegistry(cfg)
    registry.load()
    monkeypatch.setattr("ksa_opendata.services.catalog.CKANClient", DummyCKANClient)
    catalog = CatalogService(registry)
    result = await catalog.search_datasets(
        "ksa_open_data_platform",
        "demo",
        None,
        None,
        None,
        10,
        0,
        "score desc",
    )
    assert result["count"] == 1
    assert result["datasets"][0]["title"] == "Demo"


