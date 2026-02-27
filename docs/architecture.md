# Architecture Overview

KSA Open Data MCP runs as a single deployment unit with two core services:

- `ksa-opendata-mcp` (FastAPI + mounted MCP streamable HTTP)
- `ksa-mcp-postgres` (Postgres + `pgvector` memory)

## Layered Design

### 1) Source Registry Layer

- `sources.yaml` is the single allowlist control-plane for integrations.
- `ksa_opendata/registry.py` validates and loads source contracts.
- Supported source types:
  - `ckan`
  - `rest`
  - `rest_api_key`

### 2) Source Adapters + Domain Services

- CKAN adapter: `ksa_opendata/sources/ckan.py`
- REST adapter: `ksa_opendata/sources/rest.py`
- Catalog service: `ksa_opendata/services/catalog.py`
- Datastore service: `ksa_opendata/services/datastore.py`
- Preview service: `ksa_opendata/services/preview.py`
- Ranking service: `ksa_opendata/services/ranking.py`
- Vector memory service: `ksa_opendata/services/vector_memory.py`

### 3) MCP Tool Layer

- `server.py` defines MCP tools and enforces:
  - rate limiting
  - host allowlisting
  - audit logging
  - response memory read/write hooks

### 4) API Gateway Layer

- `fastapi_app.py` exposes:
  - `/mcp/` (streamable MCP endpoint)
  - `/api/*` tool gateway
  - `/health` operational health
  - `/assets/*` static icon

## Data and Memory Flow

1. Client calls MCP tool or `/api/tools/{tool}`.
2. Request is checked against rate limits and allowlists.
3. Vector memory checks for exact request replay cache.
4. If no memory hit, source adapters call upstream ministry/catalog APIs.
5. Response is returned and also persisted into pgvector memory.
6. `memory_search` enables semantic recall over stored responses.

## Deployment and Operations

- `docker-compose.yml` starts both app and Postgres with health checks.
- `ksa-mcp.sh` orchestrates:
  - environment bootstrap
  - build/up lifecycle
  - smoke tests
  - local integration config generation (`.cursor/mcp.json`, `reports/chatgpt_mcp_setup.json`)

## Reference Docs

- Full API contract: `docs/api/API_REFERENCE_FULL.md`
- Source onboarding: `docs/sources.md`
- Security controls: `docs/security.md`
