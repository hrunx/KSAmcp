## Source Registry and Onboarding

Every MCP source lives in `sources.yaml`. The registry schema supports:

- `id`: unique identifier referenced by MCP tools.
- `type`: either `ckan`, `rest`, or `rest_api_key`.
- `title`: human-friendly name.
- `base_url`: root host used by the adapter.
- `api_path`: CKAN-specific path.
- `dataset_web_url_template`: optional link template for dataset discovery.
- `endpoints`: allowlisted REST endpoints (name, method, path, optional query parameters).
- `auth`: configuration for API keys (`header` + `env`).

### Adding a Source

1. Update `sources.yaml` with a guarded definition.
2. Run `python -m pytest tests/unit/test_registry.py` to ensure validation still passes.
3. Add targeted tests that cover any new adapter behavior (e.g., new auth mode).
4. Document the source in `docs/sources.md` describing purpose, owner, and usage.

### Example Sources

| Source ID | Type | Auth | Highlights |
|---|---|---|---|
| `ksa_open_data_platform` | `ckan` | none | CKAN catalog that backs list/search/dataset tools. |
| `mcit_open_api` | `rest_api_key` | API key in header `apiKey` | Telecom + digital indicators. |
| `shc_open_data_apis` | `rest` | none | Health Council budgets, tenders, and workforce data. |
| `moh_hdp_api` | `rest` | none | MOH public dataset search APIs. |
| `sama_open_data_api` | `rest` | none | Financial and payment indicators. |
| `cchi_odata` | `rest` | none | Health insurance open data endpoints. |
| `gastat_api` | `rest` | none | Statistics and demographic indicator endpoints. |

## Runtime URL Model

This project uses fixed non-IP local URLs for cleaner MCP integration:

- `http://ksa-opendata-mcp.localhost:8000` (host machine)
- `http://ksa-opendata-mcp:8000` (container-network)

Both resolve to the same runtime service in their respective network context.
