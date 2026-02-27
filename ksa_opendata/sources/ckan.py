"""CKAN helpers for the KSA open data catalog."""

from __future__ import annotations

from dataclasses import dataclass
from json import JSONDecodeError
from typing import Any, Dict

import httpx


@dataclass(frozen=True)
class CKANConfig:
    base_url: str
    api_path: str
    user_agent: str = "ksa-opendata-mcp/0.1 (read-only)"
    timeout: float = 30.0

    @property
    def action_base(self) -> str:
        return f"{self.base_url.rstrip('/')}/{self.api_path.strip('/')}"


class CKANClient:
    def __init__(self, config: CKANConfig) -> None:
        self.config = config
        self._client = httpx.AsyncClient(
            timeout=config.timeout,
            headers={
                "User-Agent": config.user_agent,
                "Accept": "application/json",
            },
            follow_redirects=True,
        )

    async def close(self) -> None:
        await self._client.aclose()

    async def call(self, action: str, params: Dict[str, Any] | None = None) -> Any:
        url = f"{self.config.action_base}/{action}"
        response = await self._client.get(url, params=params or {})
        response.raise_for_status()
        try:
            data = response.json()
        except JSONDecodeError as exc:
            snippet = response.text[:300].replace("\n", " ").strip()
            raise RuntimeError(
                "CKAN returned non-JSON response "
                f"(action={action}, status={response.status_code}): {snippet}"
            ) from exc
        if not isinstance(data, dict) or data.get("success") is not True:
            raise RuntimeError(f"CKAN call failed: action={action} error={data.get('error')}")
        return data["result"]
