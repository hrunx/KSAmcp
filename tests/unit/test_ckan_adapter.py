import pytest

from ksa_opendata.sources.ckan import CKANClient, CKANConfig


class DummyResponse:
    def __init__(self, payload):
        self.payload = payload
        self.status_code = 200

    def raise_for_status(self) -> None:
        return None

    def json(self):
        return self.payload


@pytest.mark.asyncio
async def test_ckan_call_success(monkeypatch):
    payload = {"success": True, "result": {"id": "demo"}}
    async def fake_get(self, url, params=None, **kwargs):
        assert "package_search" in url
        return DummyResponse(payload)

    monkeypatch.setattr("httpx.AsyncClient.get", fake_get)
    client = CKANClient(CKANConfig(base_url="https://open.data.gov.sa", api_path="/api/3/action"))
    result = await client.call("package_search", {"rows": 1})
    await client.close()
    assert result == {"id": "demo"}
