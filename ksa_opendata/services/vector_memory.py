"""Lightweight pgvector-backed memory for MCP tool responses."""

from __future__ import annotations

import asyncio
import hashlib
import json
import logging
import math
import re
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from typing import Any, Dict, List

import psycopg
from psycopg.types.json import Jsonb

logger = logging.getLogger(__name__)

_ARABIC_DIACRITICS_RE = re.compile(r"[\u0610-\u061A\u064B-\u065F\u0670\u06D6-\u06ED]")
_SPACE_RE = re.compile(r"\s+")


def _normalize_text(value: str) -> str:
    """Normalize mixed Arabic/English text for stable embeddings."""
    normalized = value.strip().lower()
    normalized = (
        normalized.replace("أ", "ا")
        .replace("إ", "ا")
        .replace("آ", "ا")
        .replace("ؤ", "و")
        .replace("ئ", "ي")
        .replace("ى", "ي")
        .replace("ة", "ه")
        .replace("ـ", "")
    )
    normalized = _ARABIC_DIACRITICS_RE.sub("", normalized)
    return _SPACE_RE.sub(" ", normalized)


def _vector_literal(values: List[float]) -> str:
    return "[" + ",".join(f"{item:.8f}" for item in values) + "]"


@dataclass(frozen=True)
class MemoryMatch:
    tool_name: str
    score: float
    updated_at: str
    request: Dict[str, Any]
    response: Any


class VectorMemoryService:
    """A tiny Arabic-friendly vector memory built on char n-gram hashing."""

    def __init__(
        self,
        *,
        database_url: str | None,
        enabled: bool,
        ttl_seconds: int = 60 * 60 * 24 * 7,
        max_text_chars: int = 6000,
        embedding_dim: int = 256,
        model_name: str = "arabic-hash-ngram-v1",
    ) -> None:
        self.database_url = database_url
        self.enabled = enabled and bool(database_url)
        self.ttl_seconds = max(300, ttl_seconds)
        self.max_text_chars = max(512, max_text_chars)
        self.embedding_dim = max(64, embedding_dim)
        self.model_name = model_name

        self._initialized = False
        self._initializing_lock = asyncio.Lock()

    @property
    def status(self) -> str:
        if not self.enabled:
            return "disabled"
        if self._initialized:
            return "ready"
        return "initializing"

    def _database_url(self) -> str:
        if not self.database_url:
            raise RuntimeError("Vector memory database URL is not configured")
        return self.database_url

    async def initialize(self) -> None:
        if not self.enabled or self._initialized:
            return
        async with self._initializing_lock:
            if self._initialized or not self.enabled:
                return
            try:
                conn = await psycopg.AsyncConnection.connect(
                    self._database_url(),
                    autocommit=True,
                )
                async with conn.cursor() as cur:
                    await cur.execute("CREATE EXTENSION IF NOT EXISTS vector")
                    await cur.execute(
                        f"""
                        CREATE TABLE IF NOT EXISTS mcp_vector_memory (
                            id BIGSERIAL PRIMARY KEY,
                            tool_name TEXT NOT NULL,
                            request_hash TEXT NOT NULL UNIQUE,
                            request_json JSONB NOT NULL,
                            response_json JSONB NOT NULL,
                            response_text TEXT NOT NULL,
                            embedding VECTOR({self.embedding_dim}) NOT NULL,
                            hit_count INTEGER NOT NULL DEFAULT 0,
                            created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
                            updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
                            expires_at TIMESTAMPTZ NOT NULL
                        )
                        """
                    )
                    await cur.execute(
                        """
                        CREATE INDEX IF NOT EXISTS idx_mcp_vector_memory_expires
                        ON mcp_vector_memory (expires_at)
                        """
                    )
                    await cur.execute(
                        """
                        CREATE INDEX IF NOT EXISTS idx_mcp_vector_memory_tool
                        ON mcp_vector_memory (tool_name)
                        """
                    )
                    await cur.execute(
                        """
                        DELETE FROM mcp_vector_memory
                        WHERE expires_at <= NOW()
                        """
                    )
                await conn.close()
                self._initialized = True
            except Exception:  # noqa: BLE001
                logger.exception("Failed to initialize vector memory; disabling memory runtime")
                self.enabled = False

    @staticmethod
    def _canonical_json(value: Any) -> tuple[str, Any]:
        text = json.dumps(value, ensure_ascii=False, sort_keys=True, default=str)
        return text, json.loads(text)

    @staticmethod
    def _request_hash(tool_name: str, request_payload: Dict[str, Any]) -> str:
        canonical = json.dumps(
            request_payload,
            ensure_ascii=False,
            sort_keys=True,
            default=str,
        )
        return hashlib.sha256(f"{tool_name}:{canonical}".encode("utf-8")).hexdigest()

    def _embed(self, value: str) -> List[float]:
        text = _normalize_text(value)[: self.max_text_chars]
        if not text:
            text = "empty"
        bins = [0.0] * self.embedding_dim
        wrapped = f" {text} "

        for gram_size in (2, 3, 4):
            if len(wrapped) < gram_size:
                continue
            for idx in range(len(wrapped) - gram_size + 1):
                gram = wrapped[idx : idx + gram_size]
                if gram.isspace():
                    continue
                digest = hashlib.blake2b(gram.encode("utf-8"), digest_size=8).digest()
                bucket = int.from_bytes(digest, byteorder="big") % self.embedding_dim
                bins[bucket] += 1.0

        norm = math.sqrt(sum(value * value for value in bins))
        if norm <= 0.0:
            return bins
        return [value / norm for value in bins]

    async def get_cached(self, tool_name: str, request_payload: Dict[str, Any]) -> Any | None:
        await self.initialize()
        if not self.enabled:
            return None
        request_hash = self._request_hash(tool_name, request_payload)
        conn = await psycopg.AsyncConnection.connect(self._database_url(), autocommit=True)
        try:
            async with conn.cursor() as cur:
                await cur.execute(
                    """
                    SELECT response_json
                    FROM mcp_vector_memory
                    WHERE tool_name = %s
                      AND request_hash = %s
                      AND expires_at > NOW()
                    LIMIT 1
                    """,
                    (tool_name, request_hash),
                )
                row = await cur.fetchone()
                if row is None:
                    return None
                await cur.execute(
                    """
                    UPDATE mcp_vector_memory
                    SET hit_count = hit_count + 1,
                        updated_at = NOW()
                    WHERE tool_name = %s
                      AND request_hash = %s
                    """,
                    (tool_name, request_hash),
                )
                return row[0]
        finally:
            await conn.close()

    async def store(
        self,
        tool_name: str,
        request_payload: Dict[str, Any],
        response_payload: Any,
    ) -> None:
        await self.initialize()
        if not self.enabled:
            return

        request_hash = self._request_hash(tool_name, request_payload)
        response_text, response_json = self._canonical_json(response_payload)
        _, request_json = self._canonical_json(request_payload)
        embedding = self._embed(response_text)
        expires_at = datetime.now(timezone.utc) + timedelta(seconds=self.ttl_seconds)

        conn = await psycopg.AsyncConnection.connect(self._database_url(), autocommit=True)
        try:
            async with conn.cursor() as cur:
                await cur.execute(
                    """
                    INSERT INTO mcp_vector_memory (
                        tool_name,
                        request_hash,
                        request_json,
                        response_json,
                        response_text,
                        embedding,
                        expires_at
                    )
                    VALUES (%s, %s, %s, %s, %s, %s::vector, %s)
                    ON CONFLICT (request_hash) DO UPDATE
                    SET request_json = EXCLUDED.request_json,
                        response_json = EXCLUDED.response_json,
                        response_text = EXCLUDED.response_text,
                        embedding = EXCLUDED.embedding,
                        expires_at = EXCLUDED.expires_at,
                        updated_at = NOW()
                    """,
                    (
                        tool_name,
                        request_hash,
                        Jsonb(request_json),
                        Jsonb(response_json),
                        response_text[: self.max_text_chars],
                        _vector_literal(embedding),
                        expires_at,
                    ),
                )
                await cur.execute(
                    """
                    DELETE FROM mcp_vector_memory
                    WHERE expires_at <= NOW()
                    """,
                )
        finally:
            await conn.close()

    async def search(self, query: str, limit: int = 5) -> Dict[str, Any]:
        await self.initialize()
        if not self.enabled:
            return {"query": query, "model": self.model_name, "matches": []}

        query_embedding = self._embed(query)
        safe_limit = max(1, min(limit, 20))
        conn = await psycopg.AsyncConnection.connect(self._database_url(), autocommit=True)
        try:
            async with conn.cursor() as cur:
                await cur.execute(
                    """
                    SELECT
                        tool_name,
                        request_json,
                        response_json,
                        updated_at,
                        (1 - (embedding <=> %s::vector)) AS score
                    FROM mcp_vector_memory
                    WHERE expires_at > NOW()
                    ORDER BY embedding <=> %s::vector
                    LIMIT %s
                    """,
                    (
                        _vector_literal(query_embedding),
                        _vector_literal(query_embedding),
                        safe_limit,
                    ),
                )
                rows = await cur.fetchall()
        finally:
            await conn.close()

        matches: List[MemoryMatch] = []
        for row in rows:
            updated_at = row[3]
            updated_iso = (
                updated_at.astimezone(timezone.utc).isoformat()
                if isinstance(updated_at, datetime)
                else str(updated_at)
            )
            matches.append(
                MemoryMatch(
                    tool_name=str(row[0]),
                    request=row[1] if isinstance(row[1], dict) else {},
                    response=row[2],
                    updated_at=updated_iso,
                    score=float(row[4] or 0.0),
                )
            )

        return {
            "query": query,
            "model": self.model_name,
            "embedding_dim": self.embedding_dim,
            "match_count": len(matches),
            "matches": [
                {
                    "tool_name": match.tool_name,
                    "score": round(match.score, 4),
                    "updated_at": match.updated_at,
                    "request": match.request,
                    "response_preview": json.dumps(
                        match.response,
                        ensure_ascii=False,
                        default=str,
                    )[:500],
                    "response": match.response,
                }
                for match in matches
            ],
        }
