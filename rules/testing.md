# Testing Rules

> Active directive. Discovered on-demand via the `rules/*.md` glob — read by `/audit-rules` and any agent reasoning about testing. Treat as binding when encountered.

## Coverage priorities

Critical paths — auth, payments, validation, error handling, API endpoints — get the deepest coverage. Test the failure modes, not just the happy path. Coverage-gap findings are surfaced advisorily by `quality_coverage.py` on `@quality-engineer` writes.

## Test Organization

```
tests/
├── unit/          # Fast, isolated
├── integration/   # Component interaction
└── e2e/           # End-to-end flows
```

## Naming Pattern

`should [expected] when [condition]`

```
should return user when credentials valid
should throw AuthError when password incorrect
```

## Mocking

**Mock:** External services, time, random, slow operations.
**Don't mock:** The code being tested, simple utilities.

## Project-specific extensions

Add project-specific examples, exceptions, and conventions to `rules/testing.local.md` alongside this file. Sidecar `*.local.md` files are excluded from framework refresh — they survive `install.sh --mode refresh-v3`. Readers (skills, agents, `/audit-rules`) pick up both via the `rules/*.md` glob.

## See also

- `agents/README.md` — `@quality-engineer` is the test-strategy agent
- `rules/error-handling.md` — error-path and edge-case coverage expectations
