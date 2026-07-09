# Observability Rules

> Active directive. Discovered on-demand via the `rules/*.md` glob — read by `/audit-rules` and any agent reasoning about observability. Treat as binding when encountered.

## Not the same as `forge dashboard`

`forge dashboard` views *framework artifacts* (tasks, code-map, ISAs) at dev time. That is **not** application observability. This rule is about the running app in production — its logs, metrics, and traces once real users hit it. Forge does not instrument your app; it makes the discipline a standing expectation.

## Concrete DO/DON'T

- **DO** emit structured logs (JSON, one event per line) with a request/correlation ID on every line. **DON'T** `print`/`console.log` prose into stdout as the production logging strategy.
- **DO NOT log PII or secrets** — never passwords, tokens, full PANs, or personal data. Redact at the logging boundary. (Intersects `rules/security.md` — logs are a common leak surface.)
- **DO** alert on thresholds that map to user-visible pain (error rate, p95 latency). **DON'T** alert on vanity counts. Per-project targets live in the `reference/05` Monitoring table.
- **DO** route unhandled exceptions to an error tracker with the correlation ID attached. For a small single-service app, structured logs + error tracking may be enough; add tracing when you cross a service boundary — make it a *decision*, not an omission.

## What this rule is NOT

Not an Algorithm probe mandate — Forge deliberately does not force a logging ISC onto every task. Observability is verified at the `/build` production checklist and by `@devops` review.

## Project-specific extensions

Add your stack's concrete choices (log shipper, metrics backend, trace exporter, dashboards, alert routing) to `rules/observability.local.md` alongside this file. Sidecar `*.local.md` files survive `install.sh --mode refresh-v3`; readers pick up both via the `rules/*.md` glob.
