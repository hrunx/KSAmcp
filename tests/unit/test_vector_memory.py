from __future__ import annotations

import math

import pytest

from ksa_opendata.services.vector_memory import VectorMemoryService, _normalize_text


def test_normalize_text_handles_arabic_forms() -> None:
    raw = "إِحصَاءاتُ وزارةِ الصِّحةِ السُّعُودِيَّة"
    normalized = _normalize_text(raw)
    assert "وزاره" in normalized
    assert "الصحه" in normalized
    assert "ّ" not in normalized


def test_embedder_returns_normalized_vector() -> None:
    memory = VectorMemoryService(
        database_url=None,
        enabled=False,
        embedding_dim=64,
        max_text_chars=2000,
    )
    vector = memory._embed("وزارة الصحة السعودية Health Open Data 2026")
    assert len(vector) == 64
    norm = math.sqrt(sum(value * value for value in vector))
    assert abs(norm - 1.0) < 1e-6


@pytest.mark.asyncio
async def test_disabled_memory_search_returns_empty() -> None:
    memory = VectorMemoryService(database_url=None, enabled=False)
    result = await memory.search("القطاع الصحي")
    assert result["matches"] == []


@pytest.mark.asyncio
async def test_disabled_memory_get_and_store_noop() -> None:
    memory = VectorMemoryService(database_url=None, enabled=False)
    await memory.store("list_sources", {}, [{"id": "a"}])
    cached = await memory.get_cached("list_sources", {})
    assert cached is None
