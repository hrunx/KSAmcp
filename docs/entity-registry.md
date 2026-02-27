# GOV.SA Entity Registry

This project ships a generator that builds a contributor backlog from the official GOV.SA agencies directory payload.

## Why this exists

- Contributors need a clean, non-fabricated list of entities to claim.
- The source is official (`my.gov.sa`) and read-only.
- Generated files provide one scaffold per entity to standardize contributions.

## Generator

Run:

```bash
PYTHONPATH=. .venv/bin/python scripts/generate_entity_registry.py
```

Artifacts:

- `reports/govsa_entity_registry.json`
- `reports/govsa_ministries_registry.json`
- `reports/govsa_entity_registry.md`
- `contrib/entities/*.yaml`
- `contrib/entities/README.md`
- `contrib/ministries/README.md`

## Data quality policy

- No ministry/entity names are manually invented.
- Category mapping comes from GOV.SA taxonomy IDs.
- Raw observation count and unique ID count are both preserved for auditability.
