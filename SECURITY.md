# Security Policy - KSA Open Data MCP

KSA Open Data MCP is designed for high-trust deployments. Security is a core project requirement, not an optional enhancement.

## Supported Versions

Security fixes are prioritized for:

- the latest release line, and
- the current default branch.

Older versions may not receive patches.

## Reporting a Vulnerability

Do **not** open public issues for suspected vulnerabilities.

Use private reporting channels:

1. GitHub Security Advisory (preferred when enabled), or
2. direct maintainer contact through private channels.

Please include:

- vulnerability description,
- reproduction steps,
- impact assessment (for example SSRF, data exposure, RCE),
- proposed mitigation (if available).

We will acknowledge reports and coordinate responsible disclosure.

## Security Design Constraints (Project-Wide)

All contributions must preserve:

- read-only tool behavior,
- explicit source and endpoint allowlisting,
- no arbitrary URL fetch surface in public tools,
- strict output bounds for preview-like operations,
- no secrets in code, logs, or repository history,
- deterministic, audit-friendly output contracts.

## Implemented Controls (Current Repository State)

The current codebase already enforces:

- source allowlisting through `sources.yaml`,
- typed environment-backed settings via `ksa_opendata/config.py`,
- explicit config strictness (`extra = "forbid"` in settings),
- centralized source loading/validation in `ksa_opendata/registry.py`,
- runtime tool rate-limiting controls in `server.py`,
- preview host allowlist checks in `server.py`,
- bounded preview fetch size and row limits via `ksa_opendata/services/preview.py`,
- adapter-level HTTP timeout defaults in CKAN and REST clients.

## Planned Controls (Roadmap Scope)

Planned controls are tracked in the architecture plan and include:

- strict outbound request timeouts across adapters,
- bounded row/byte limits for previews,
- stronger SSRF defenses at tool/transport boundaries,
- expanded contract and integration test coverage.

These controls should not be claimed as complete until implemented and tested.

## Common Risk Areas

- SSRF from user-controlled network targets
- unbounded data exfiltration from preview endpoints
- secret leakage through logs and trace payloads
- dependency/supply-chain risk from unnecessary packages
- missing timeout/retry limits on upstream requests

## Security Review Expectations for PRs

Security-relevant changes should include:

- threat statement (what risk is addressed),
- control statement (what guardrail is added or changed),
- validation statement (how the behavior was tested).

## Disclosure Process

If a report is confirmed:

1. a fix is prepared privately when feasible,
2. release timing is coordinated to reduce exposure,
3. a security advisory is published as appropriate,
4. reporter credit is provided when requested and suitable.

Thank you for helping keep KSA Open Data MCP secure.
