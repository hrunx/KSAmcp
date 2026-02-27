from __future__ import annotations

import importlib
import os
import sys
from typing import Any

from fastapi.testclient import TestClient


def _load_module() -> Any:
    os.environ["FASTAPI_API_KEY"] = "$$hrn&ali4KSA$$"
    os.environ["MCP_API_KEY_REQUIRED"] = "true"
    if "fastapi_app" in sys.modules:
        del sys.modules["fastapi_app"]
    module = importlib.import_module("fastapi_app")
    return importlib.reload(module)


def test_health_endpoint_is_public() -> None:
    module = _load_module()
    client = TestClient(module.app)
    response = client.get("/health")
    assert response.status_code == 200
    assert response.json()["status"] == "ok"


def test_api_requires_key() -> None:
    module = _load_module()
    client = TestClient(module.app)
    response = client.get("/api/welcome")
    assert response.status_code == 401


def test_api_welcome_and_tool_call_with_key() -> None:
    module = _load_module()
    client = TestClient(module.app)
    headers = {"X-API-Key": "$$hrn&ali4KSA$$"}

    welcome = client.get("/api/welcome", headers=headers)
    assert welcome.status_code == 200
    payload = welcome.json()
    assert payload["tool_count"] >= 1
    assert "list_sources" in payload["tool_briefs"]

    tools = client.get("/api/tools", headers=headers)
    assert tools.status_code == 200
    tool_names = {item["name"] for item in tools.json()["tools"]}
    assert "list_sources" in tool_names

    call = client.post(
        "/api/tools/list_sources",
        headers=headers,
        json={"arguments": {}},
    )
    assert call.status_code == 200
    result = call.json()["result"]
    assert isinstance(result, list)


def test_public_mode_allows_requests_without_api_key() -> None:
    os.environ["FASTAPI_API_KEY"] = "$$hrn&ali4KSA$$"
    os.environ["MCP_API_KEY_REQUIRED"] = "false"
    if "fastapi_app" in sys.modules:
        del sys.modules["fastapi_app"]
    module = importlib.import_module("fastapi_app")
    module = importlib.reload(module)

    client = TestClient(module.app)
    response = client.get("/api/tools")
    assert response.status_code == 200
