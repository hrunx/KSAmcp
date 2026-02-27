"""Typed configuration for the MCP server."""

from __future__ import annotations

from pathlib import Path

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    sources_path: Path = Field(default=Path("sources.yaml"), alias="KSA_MCP_SOURCES")
    mcit_api_key: str | None = Field(default=None, alias="MCIT_API_KEY")
    fastapi_api_key: str | None = Field(default=None, alias="FASTAPI_API_KEY")
    mcp_api_key_required: bool | None = Field(default=None, alias="MCP_API_KEY_REQUIRED")
    mcp_public_base_url: str | None = Field(default=None, alias="MCP_PUBLIC_BASE_URL")
    mcp_server_name: str | None = Field(default=None, alias="MCP_SERVER_NAME")
    mcp_server_description: str | None = Field(default=None, alias="MCP_SERVER_DESCRIPTION")
    mcp_icon_url: str | None = Field(default=None, alias="MCP_ICON_URL")
    postgres_db: str | None = Field(default=None, alias="POSTGRES_DB")
    postgres_user: str | None = Field(default=None, alias="POSTGRES_USER")
    postgres_password: str | None = Field(default=None, alias="POSTGRES_PASSWORD")
    database_url: str | None = Field(default=None, alias="DATABASE_URL")
    vector_memory_enabled: bool = Field(default=True, alias="VECTOR_MEMORY_ENABLED")
    vector_memory_ttl_seconds: int = Field(default=604800, alias="VECTOR_MEMORY_TTL_SECONDS")
    vector_memory_max_text_chars: int = Field(default=6000, alias="VECTOR_MEMORY_MAX_TEXT_CHARS")
    embedding_model_name: str = Field(default="arabic-hash-ngram-v1", alias="EMBEDDING_MODEL_NAME")
    embedding_dim: int = Field(default=256, alias="EMBEDDING_DIM")

    model_config = SettingsConfigDict(
        env_file=".env",
        extra="forbid",
        populate_by_name=True,
    )


settings = Settings()
