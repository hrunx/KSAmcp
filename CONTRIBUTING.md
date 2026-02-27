# Contributing to KSA Open Data MCP

KSA Open Data MCP is a government-grade, open-source MCP server intended to unify Saudi Arabia's open data ecosystem behind a safe, read-only interface.

Contributions are welcome from engineers and domain experts who prioritize security, correctness, clarity, and long-term maintainability.

## Table of Contents

- [Quality Bar](#quality-bar)
- [What We Accept](#what-we-accept)
- [Non-Negotiables (Hard Requirements)](#non-negotiables-hard-requirements)
- [Current Status vs Roadmap](#current-status-vs-roadmap)
- [Before You Start](#before-you-start)
- [Local Development](#local-development)
- [Adding a New Source (Checklist)](#adding-a-new-source-checklist)
- [Pull Request Standards](#pull-request-standards)
- [Maintainer Authority](#maintainer-authority)

## Quality Bar

Contributions are expected to be production quality:

- clear rationale and scope,
- consistent design with existing modules,
- tests for non-trivial logic,
- documentation updates when behavior changes.

## What We Accept

### 1) New Data Sources (Preferred)

- Official ministry or authority open-data APIs
- Catalog sources compatible with CKAN-style APIs
- Standards-based protocols such as OData only when official and stable

### 2) Core Improvements

- Metadata normalization and schema consistency
- Safety hardening for source handling and request boundaries
- Caching, resiliency, and observability improvements
- Tool contract hardening and integration coverage

### 3) Developer Experience

- Better setup and local testing workflows
- Cleaner docs and examples focused on real usage
- Improvements to lint/type/test ergonomics

## Non-Negotiables (Hard Requirements)

1. **Read-only only**
   - No mutation endpoints or write-side tools.

2. **Allowlisted sources only**
   - All sources must be explicitly defined in `sources.yaml`.
   - No "fetch any URL" behavior in public tool surfaces.

3. **No unofficial scraping by default**
   - Prefer official APIs and documented catalog interfaces.

4. **Bounded and safe outputs**
   - Enforce strict size/time constraints in any preview-style functionality.

5. **No secrets in repository**
   - Never commit API keys, credentials, or sensitive endpoints.
   - Use environment variables documented in `.env.example`.

6. **Stable public contracts**
   - MCP tool names and response schemas are treated as stable contracts.
   - Breaking changes require explicit proposal and versioning strategy.

## Current Status vs Roadmap

To keep contributions accurate:

- **Implemented now:** MCP server runtime (`server.py`), source registry/config model, CKAN and REST adapters, preview/datastore/ranking services, and inventory script.
- **Planned next:** deeper contract testing, stronger operational hardening, and expanded connector coverage.

Avoid describing roadmap items as already implemented in PR descriptions.

## Before You Start

For non-trivial changes, open an issue first and include:

- official source/doc links,
- intended tool behavior and constraints,
- auth/rate-limit characteristics,
- licensing/terms considerations where relevant.

Small docs fixes and typo-only updates can go directly to PR.

## Local Development

### Prerequisites

- Python 3.11+
- A virtual environment (recommended)

### Setup

```bash
python -m venv .venv
source .venv/bin/activate
pip install -e ".[dev]"
```

### Typical Validation Commands

```bash
ruff check .
mypy .
pytest
```

If you touched behavior exposed by MCP tools, include at least one tool-level validation note in the PR description.

If your contribution changes docs only, run at least markdown spell/consistency checks locally if available.

## Adding a New Source (Checklist)

### A) Source Definition (`sources.yaml`)

Add a new source entry with:

- `id` (stable snake_case),
- `type` (`ckan`, `rest`, `rest_api_key`, or approved equivalent),
- `title`,
- `base_url`,
- `api_path` when required,
- `endpoints` allowlist for REST-style sources,
- `auth` block when required.

Also include official source documentation links in the PR.

### B) Config and Secrets

- Use environment variables only for secrets.
- Keep `.env.example` updated when introducing new required keys.
- Existing keys include `MCIT_API_KEY` and `KSA_MCP_SOURCES`.

### C) Implementation

- Validate inputs strictly.
- Use deterministic output shapes.
- Handle upstream failures with explicit, actionable errors.

### D) Tests

- Add unit tests for parser/normalizer/validation logic.
- Add integration tests for tool-facing behavior when applicable.
- For source connectors, prefer mocked upstream responses over live network dependencies.

### E) Documentation

- Update `README.md` and architecture/security docs if behavior changes.

## Pull Request Standards

### PR Title Examples

- `[source] add <authority> connector`
- `[core] harden source registry validation`
- `[docs] clarify source onboarding`

### PR Must Include

- concise summary,
- rationale for fit with KSA MCP goals,
- safety implications and controls,
- testing notes (what ran and results).

### Review Expectations

- At least one maintainer approval required.
- Security-sensitive changes may require additional review depth.

## Maintainer Authority

Maintainers may request refactors or reject changes that:

- add unstable/unofficial sources,
- weaken safety guarantees,
- increase ambiguity in public tool contracts.

Project direction prioritizes long-term trustworthiness over short-term feature volume.
