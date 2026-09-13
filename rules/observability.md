# Observability Rules

> **Loaded at every session start** — all of `.claude/rules/*.md` is. Binding. Keep it short: opt-in depth belongs in a skill or `reference/`. See CONTRIBUTING.md "The rules budget".

## Concrete DO/DON'T

- **DO** emit structured logs (JSON, one event per line) with a request/correlation ID on every line. **DON'T** `print`/`console.log` prose into stdout as the production logging strategy.
- **DO NOT log PII or secrets** — never passwords, tokens, full PANs, or personal data. Redact at the logging boundary. (Intersects `rules/security.md` — logs are a common leak surface.)
- **DO** alert on thresholds that map to user-visible pain (error rate, p95 latency). **DON'T** alert on vanity counts. Per-project targets live in the `reference/05` Monitoring table.
- **DO** route unhandled exceptions to an error tracker with the correlation ID attached. For a small single-service app, structured logs + error tracking may be enough; add tracing when you cross a service boundary — make it a *decision*, not an omission.

## Project-specific extensions

`rules/observability.local.md` — survives refresh, wins on conflict.
