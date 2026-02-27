
import pytest

from ksa_opendata.errors import SourceConfigError
from ksa_opendata.registry import Source
from ksa_opendata.sources.rest import RestSourceAdapter


class DummyResponse:
    def __init__(self, status_code: int, body: dict[str, any]):
        self.status_code = status_code
        self._body = body

    def raise_for_status(self) -> None:
        if self.status_code >= 400:
            raise SourceConfigError("bad response")

    def json(self) -> dict[str, any]:
        return self._body

    @property
    def text(self) -> str:
        return str(self._body)


@pytest.mark.asyncio
async def test_rest_adapter_api_key_header(monkeypatch, mocker):
    source = Source(
        id="test",
        type="rest_api_key",
        title="Test",
        base_url="https://api.test",
        auth={"header": "apiKey", "env": "TEST_KEY"},
        endpoints=[{"name": "dummy", "path": "/"}],
    )
    monkeypatch.setenv("TEST_KEY", "secret")
    adapter = RestSourceAdapter(source)

    async def fake_request(method, url, params=None, headers=None):
        assert headers and headers.get("apiKey") == "secret"
        return DummyResponse(200, {"ok": True})

    mocker.patch.object(adapter._client, "request", fake_request)
    result = await adapter.call_endpoint("dummy")
    await adapter.close()
    assert result == {"ok": True}


@pytest.mark.asyncio
async def test_rest_adapter_missing_env(monkeypatch):
    monkeypatch.delenv("MISSING_KEY", raising=False)
    source = Source(
        id="test",
        type="rest_api_key",
        title="Test",
        base_url="https://api.test",
        auth={"header": "apiKey", "env": "MISSING_KEY"},
        endpoints=[{"name": "dummy", "path": "/"}],
    )
    adapter = RestSourceAdapter(source)
    with pytest.raises(SourceConfigError):
        await adapter.call_endpoint("dummy")
