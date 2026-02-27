## Security & Compliance Posture

- **Read-only by design:** MCP tools never mutate or accept user uploads; only retrieval operations exist.
- **Allowlisted sources/endpoints:** Every integration lives in `sources.yaml`, validated at startup by `SourceRegistry`.
- **Rate limiting:** Critical tools (`preview_resource`, `search_datasets`, `call_source_endpoint`, etc.) enforce in-memory quotas via `cachetools.TTLCache`.
- **Host allowlisting:** Preview and REST adapters check `urllib.parse.urlparse` against the approved host set defined in `server.py`.
- **Bounded previews:** Previews cap downloads to 2 MB with row limits (CSV/JSON/XLSX) and rely on cached results.
- **Audit logs:** Each tool emits structured events (`tool_event <name>`) with timestamp, status, and metadata.
- **Vector memory controls:** pgvector memory is bounded by TTL and text size limits from environment configuration.
- **Configurable auth posture:** API key requirement is controlled by `MCP_API_KEY_REQUIRED` for `/api/*` and `/mcp/`.
- **Environment policy:** runtime keys are supplied through environment variables. This public rollout may version a public `.env`; move sensitive keys to private secret stores for hardened production.
- **Quality controls:** `pyproject.toml` integrates `ruff`, `mypy`, and `pytest` to keep checks automated.

For production deployment, pair this server with an API gateway, TLS, and observability pipeline (tracing + metrics) for auditability.
