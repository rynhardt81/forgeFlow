# Coding Style Rules

> Active directive. Discovered on-demand via the `rules/*.md` glob — read by `/audit-rules` and any agent reasoning about coding style. Treat as binding when encountered.

## File Size Limits

| Type | Max Lines | If Exceeded |
|------|-----------|-------------|
| Component | 300 | Split |
| Service | 400 | Extract |
| Utility | 200 | Break into modules |
| Test | 500 | Split by concern |

When a limit is hit, route through `/refactor` (Structural mode) — the skill picks the cleavage and runs `check_undefined_names.py` to catch slicing-bug regressions before they ship.

## Errors

The error-handling floor is canonical in **`rules/error-handling.md`** — specific error types, handle-at-boundaries, never swallow, structured API responses. Defer there.

## Project-specific extensions

Add project-specific examples, exceptions, and conventions to `rules/coding-style.local.md` alongside this file. Sidecar `*.local.md` files are excluded from framework refresh — they survive `install.sh --mode refresh-v3`. Readers (skills, agents, `/audit-rules`) pick up both via the `rules/*.md` glob.
