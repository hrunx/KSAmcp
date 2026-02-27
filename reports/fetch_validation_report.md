# Fetch and Validation Evidence Report

Generated at (UTC): `2026-02-27T04:07:07Z`

This report captures concrete evidence that the repository is pulling real data and that the current implementation passes runtime checks.

## 1) GOV.SA Directory Crawl Evidence

Source endpoints used:

- `https://www.my.gov.sa/en/agencies`
- `https://www.my.gov.sa/ar/agencies`

Generated registry artifacts:

- `reports/govsa_entity_registry.json`
- `reports/govsa_ministries_registry.json`
- `reports/govsa_entity_registry.md`

Observed crawl statistics (from generated artifact):

- Official total rows reported by GOV.SA: `363`
- Raw rows collected across crawl strategies: `1452`
- Unique entity IDs captured: `360`
- Ministry entity IDs captured: `27`
- Category taxonomy count: `14`
- Crawl strategy variants executed: `56`

## 2) Real Sample Records Pulled

Sample ministries from `reports/govsa_ministries_registry.json`:

1. `17330` — Ministry of Sports — `https://www.gsa.gov.sa/en/Pages/default.aspx`
2. `17342` — Ministry of National Guard Health Affairs (MNGHA) — `http://www.mngha.med.sa/English/Pages/Default.aspx`
3. `17396` — Ministry of Investment — `https://www.misa.gov.sa/en`
4. `17399` — Ministry of Tourism — `https://mt.gov.sa/en/Pages/default.aspx`
5. `17597` — Ministry of Communications and Information Technology — `https://www.mcit.gov.sa/en/node`
6. `17600` — Ministry of Economy and Planning — `https://www.mep.gov.sa/en`
7. `17603` — Ministry of Energy — `https://www.moenergy.gov.sa/ar`
8. `17606` — Ministry of Commerce — `https://mc.gov.sa/`

Sample entity records from `reports/govsa_entity_registry.json`:

1. `17219` — Emirates — Emirate Of Eastern Province
2. `17222` — Emirates — Emirate Of Al-Baaha Province
3. `17225` — Emirates — Emirate Of Al-Jowf Province
4. `17228` — Emirates — Emirate Of Northern Borders Province
5. `17231` — Emirates — Emirate Of Riyadh Province
6. `17234` — Emirates — Emirate Of Al-Qasim Province
7. `17237` — Emirates — Emirate Of Madinah Province
8. `17240` — Emirates — Emirate Of Tabouk Province

## 3) Live API Fetch Evidence (MOH HDP)

Live request executed:

- `GET https://hdp.moh.gov.sa/api/v1/Dataset/search/public`
- Query: `search=الهيئات&pageNumber=1&pageSize=3`

Observed response:

- HTTP status: `200`
- Response code field: `200`
- `totalRowsCount`: `2`

Returned sample dataset names:

1. `79e7b8f0-0fe6-4c08-90c4-9a69e08e9de2` — عدد الهيئات الصحية الشرعية وعدد قضايا الأخطاء الطبية المعروضة عليها  حسب المنطقة الصحية لعام 2022م.
2. `8052b7b2-1cec-4d5c-bf9d-7526f7ec3ba1` — الحالات التي أرسلت للعلاج بالخارج من قبل الهيئات الطبية حسب الدولة والحالة الطبية عام  2023م.

## 4) Test and Quality Evidence

Executed verification command:

```bash
PYTHONPATH=. .venv/bin/ruff check . && PYTHONPATH=. .venv/bin/pytest -q
```

Observed output:

- `All checks passed!`
- `15 passed in 0.41s`

## 5) Contributor Backlog Evidence

Generated contributor scaffolds:

- `contrib/entities/*.yaml`: `360` files (one file per captured unique entity ID)
- `contrib/ministries/README.md`: ministry-first pick list for contributors

This confirms the repository can be presented with concrete fetch/test evidence and real pull results.

## 6) FastAPI + MCP Gateway Smoke Evidence

Container runtime validation (`./ksa-mcp.sh rebuild`):

- Docker rebuild completed successfully.
- `/health` returned `200`.
- `/api/welcome` returned `200` with `X-API-Key`.
- `/api/tools` returned `401` without key and `200` with key.
- `/mcp` returned `401` without key.

MCP over FastAPI validation:

- MCP client connected to `http://ksa-opendata-mcp.localhost:8000/mcp/`.
- Tool call `list_sources` succeeded.
- Source count observed: `7`.

FastAPI tool execution validation:

- `POST /api/tools/call_source_endpoint` with source `moh_hdp_api` + endpoint `dataset_search_public` succeeded.
- Response `code`: `200`, `totalRowsCount`: `196`, `pageSize`: `2`.

## 7) Known External Constraint (Catalog API)

The Saudi Open Data CKAN endpoint (`open.data.gov.sa/api/3/action/*`) is currently returning a WAF HTML rejection from this network environment.

- The MCP now surfaces this condition clearly as a diagnostic error (non-JSON CKAN response), instead of a generic JSON parsing failure.
- Ministry/API-first connectors (example: MOH HDP) continue to work and were validated above.
