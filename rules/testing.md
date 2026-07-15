# Testing Rules

> Active directive. Discovered on-demand via the `rules/*.md` glob — read by `/audit-rules` and any agent reasoning about testing. Treat as binding when encountered.

## Coverage priorities

Critical paths — auth, payments, validation, error handling, API endpoints — get the deepest coverage. Test the failure modes, not just the happy path. Coverage-gap findings are surfaced advisorily by `quality_coverage.py` on `@quality-engineer` writes.

## Adversarial floor (not just conformity)

"Test the failure modes" above is aspirational until it names a floor. The floor: **every function on a critical path gets at least one adversarial case — a degenerate input the happy-path test never sends.** A suite that only proves the function works on well-formed input is conformity testing; it passes green while the function is still broken on the inputs that actually reach production. This is the builder's blind spot — you test the case you were thinking about when you wrote it.

Degenerate inputs to reach for, by argument type:

- **Collections** — empty, single element, duplicates, all-identical, already-sorted / reverse-sorted.
- **Strings** — empty, whitespace-only, unicode, very long, embedded delimiters/quotes.
- **Numbers** — 0, negative, boundary (min/max), off-by-one around limits, non-integer where integer assumed.
- **Nullable / optional** — null/None/undefined, missing key, wrong type.
- **State** — same operation applied twice (idempotency), on an already-deleted / tombstoned record, on self (self-reference, self-deactivation), concurrent/interleaved.
- **Money & security paths** — get the widest adversarial set, no exceptions: overflow, rounding, unauthorized caller, replayed request.

Not a per-function suite mandate — one runnable adversarial case per critical-path function, chosen for the input class most likely to break it. Trivial pure one-liners are exempt (YAGNI applies to tests too). Project-specific degenerate-input lists go in `rules/testing.local.md`.

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
