# KSA Open Data MCP - Full API Reference

This document is the complete runtime contract for the KSA Open Data MCP gateway.

## 1) Runtime Topology

The stack started by `./ksa-mcp.sh` runs:

- `ksa-opendata-mcp` (FastAPI + mounted MCP streamable HTTP server)
- `ksa-mcp-postgres` (PostgreSQL with `pgvector`)

Primary local URL (stable and non-IP style):

- `http://ksa-opendata-mcp.localhost:8000`

Additional container-network URL (for service-to-service access):

- `http://ksa-opendata-mcp:8000`

## 2) Startup Contract

`./ksa-mcp.sh` performs:

1. Ensures `.env` exists with ready defaults.
2. Generates local integration files:
   - `.cursor/mcp.json`
   - `reports/chatgpt_mcp_setup.json`
3. Builds Docker image.
4. Starts Postgres + MCP containers.
5. Waits for `/health`.
6. Runs API smoke checks.
7. Prints all links, auth mode, and tools.

## 3) Health and Platform Endpoints

### `GET /health`

Returns service readiness and vector-memory state.

Example response:

```json
{
  "status": "ok",
  "vector_memory": "ready"
}
```

### `GET /docs`

FastAPI interactive docs.

### `GET /openapi.json`

OpenAPI schema for FastAPI wrapper routes.

### `GET /assets/ksa-mcp-icon-128.jpg`

MCP icon asset (128x128, under 10 KB).

## 4) Authentication Model

Configured via `.env`:

- `MCP_API_KEY_REQUIRED=true|false`
- `FASTAPI_API_KEY=<value>`

When `MCP_API_KEY_REQUIRED=true`:

- `/api/*` and `/mcp/` require header `X-API-Key`.

When `MCP_API_KEY_REQUIRED=false`:

- `/api/*` and `/mcp/` are public in runtime.

## 5) FastAPI Wrapper Endpoints

## `GET /api/welcome`

Returns integration metadata for ChatGPT/Cursor and runtime links.

Important fields:

- `mcp_url`
- `tools_endpoint`
- `docs_url`
- `tool_count`
- `tool_briefs`
- `chatgpt_mcp_setup`
- `vector_memory.status`

## `GET /api/tools`

Lists all tool names and briefs exposed by this gateway.

Response:

- `count`
- `tools[]` (`name`, `brief`)

## `POST /api/tools/{tool_name}`

Calls a tool using JSON payload:

```json
{
  "arguments": {
    "...": "..."
  }
}
```

Success shape:

```json
{
  "tool": "<tool_name>",
  "result": { "...": "..." }
}
```

Error codes:

- `400`: invalid tool arguments
- `404`: unknown tool
- `500`: tool execution failed

## 6) MCP Endpoint

### `POST /mcp/` (Streamable HTTP MCP transport)

Use this endpoint for MCP clients (Cursor, ChatGPT custom MCP, and other agents).

- Transport: `streamable-http`
- URL should include trailing slash: `/mcp/`

## 7) MCP Tool Reference

The following tools are available:

1. `list_sources`
2. `list_publishers`
3. `search_datasets`
4. `get_dataset`
5. `get_resource`
6. `preview_resource`
7. `publisher_summary`
8. `datastore_search`
9. `call_source_endpoint`
10. `memory_search`

### `list_sources`

- Args: none
- Returns configured source metadata including allowed endpoint names.

### `list_publishers`

- Args:
  - `source_id` (default: `ksa_open_data_platform`)
  - `query` (optional filter)
  - `limit` (default: 200)

### `search_datasets`

- Args:
  - `source_id`
  - `query`
  - `publisher`
  - `tag`
  - `group`
  - `rows`
  - `start`
  - `sort`
- Returns dataset search + ranking output.

### `get_dataset`

- Args:
  - `source_id`
  - `dataset_id_or_name`
- Returns dataset metadata and resources.

### `get_resource`

- Args:
  - `source_id`
  - `resource_id`
- Returns resource metadata.

### `preview_resource`

- Args:
  - `source_id`
  - `resource_id` (preferred) or `url`
  - `rows`
  - `max_bytes`
- Returns bounded preview for JSON/CSV/XLSX.

### `publisher_summary`

- Args:
  - `source_id`
  - `publisher`
  - `sample_rows`
- Returns top formats/tags and publisher dataset summary.

### `datastore_search`

- Args:
  - `source_id`
  - `resource_id`
  - `filters`
  - `limit`
  - `offset`
- Returns CKAN datastore records.

### `call_source_endpoint`

- Args:
  - `source_id`
  - `endpoint`
  - `params`
- Calls allowlisted ministry endpoints from `sources.yaml`.

### `memory_search`

- Args:
  - `query`
  - `limit`
- Returns semantic matches from stored MCP memory entries.

## 8) Vector Memory (pgvector)

Vector memory automatically stores tool responses for reuse.

Implementation:

- Backend: Postgres + pgvector.
- Table: `mcp_vector_memory`.
- Embedding strategy: tiny local Arabic-friendly hashed n-gram model.
- Model identifier: `arabic-hash-ngram-v1`.
- Dimension default: `256`.

Controls:

- `VECTOR_MEMORY_ENABLED`
- `VECTOR_MEMORY_TTL_SECONDS`
- `VECTOR_MEMORY_MAX_TEXT_CHARS`
- `EMBEDDING_MODEL_NAME`
- `EMBEDDING_DIM`

Behavior:

- Exact request replay cache by tool + canonical argument hash.
- Semantic recall using cosine similarity for `memory_search`.
- Expired rows are pruned automatically.

## 9) Sources and Ministry APIs

Configured in `sources.yaml`:

- `ksa_open_data_platform` (CKAN)
- `shc_open_data_apis`
- `moh_hdp_api`
- `mcit_open_api`
- `sama_open_data_api`
- `cchi_odata`
- `gastat_api`

Each REST source is endpoint-allowlisted. Unlisted endpoints are rejected.

## 10) ChatGPT Custom MCP Setup

Use values from `reports/chatgpt_mcp_setup.json` (auto-generated by `./ksa-mcp.sh`).

In the ChatGPT MCP form:

- **Icon**: use the `icon` URL from setup file
- **Name**: `KSA Open Data MCP`
- **Description**: from setup file
- **MCP Server URL**: `.../mcp/`
- **Authentication**:
  - if `MCP_API_KEY_REQUIRED=true`, provide `X-API-Key`
  - otherwise use public/no-auth mode
- **OAuth**: not required

## 11) Cursor MCP Setup

`./ksa-mcp.sh` generates `.cursor/mcp.json` automatically.

The generated server id:

- `ksa-opendata-mcp`

Transport:

- `streamable-http`

URL:

- `http://ksa-opendata-mcp.localhost:8000/mcp/`

## 12) URL Reality and Reachability

Important behavior:

- `http://ksa-opendata-mcp.localhost:8000` is stable and local-machine friendly.
- `http://ksa-opendata-mcp:8000` works in container-network contexts.
- For internet/global reachability, deploy behind a stable public domain/reverse proxy.

## 13) Troubleshooting

### `Request Rejected` from CKAN source

`open.data.gov.sa` may return WAF HTML from some networks. The server now surfaces clear diagnostics for non-JSON CKAN responses.

### API key mismatch due `$` signs

Use exact value from `.env` and quote headers in shell:

```bash
curl -H 'X-API-Key: $$hrn&ali4KSA$$' ...
```

### Vector memory not ready

Check:

- `docker compose ps`
- `GET /health` for `vector_memory`
- Postgres container logs
