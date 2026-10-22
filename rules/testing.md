---
paths:
  - "**/tests/**"
  - "**/test/**"
  - "**/__tests__/**"
  - "**/e2e/**"
  - "**/*.{test,spec}.{ts,tsx,js,jsx,mjs,cjs}"
  - "**/test_*.py"
  - "**/*_test.{py,go}"
  - "**/conftest.py"
---

# Testing Rules

> **Loaded when Claude reads a file matching `paths:` above** — with the Read tool only, not at session start and not through Bash `cat`/`sed`. Binding. Keep it short: opt-in depth belongs in a skill or `reference/`. See CONTRIBUTING.md "The rules budget".

## What a good test is

Tests verify behavior through public interfaces, not implementation details. Code can change entirely; tests shouldn't. A good test reads like a specification: "user can checkout with valid cart" tells you exactly what capability exists, and it survives refactors because it doesn't care about internal structure. One logical assertion per test; the name describes WHAT, not HOW.

## Seams: where tests go

A **seam** is the public boundary you test at: the interface where you observe behavior without reaching inside (`/codebase-design` holds the vocabulary — module, interface, depth, seam). Tests live at seams, never against internals.

**Test only at pre-agreed seams.** Before writing tests for a feature, write down the seams under test, each with a one-line note on what it catches and what it misses, and confirm them with the user (or record them in the task ISA). You can't test everything; agreeing the seams up front is how testing effort lands on critical paths and complex logic instead of every edge case. Prefer existing seams to new ones, and the highest seam that works.

## Anti-patterns

- **Implementation-coupled**: mocks internal collaborators, tests private methods, asserts on call counts/order, or verifies through a side channel (querying the database instead of using the interface). The tell: the test breaks when you refactor but behavior hasn't changed.
- **Tautological**: the assertion recomputes the expected value the way the code does (`expect(add(a, b)).toBe(a + b)`, a snapshot derived by hand the same way, a constant asserted equal to itself), so it passes by construction and can never disagree with the code. Expected values must come from an independent source of truth: a known-good literal, a worked example, the spec.

  ```typescript
  // BAD: expected = items.reduce((sum, i) => sum + i.price, 0)
  // GOOD: expect(calculateTotal([{ price: 10 }, { price: 5 }])).toBe(15);
  ```

- **Horizontal slicing**: writing all tests first, then all implementation. Bulk tests verify _imagined_ behavior: you test the _shape_ of things rather than user-facing behavior, the tests go insensitive to real changes, and you commit to test structure before understanding the implementation. Work in **vertical slices** instead: one test → one implementation → repeat, each test a **tracer bullet** that responds to what the last cycle taught you.

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

Mock at **system boundaries** only: external APIs (payment, email), time and randomness, slow operations; databases and the file system only sometimes — prefer a test DB or an in-memory stand-in. **Don't mock** your own classes/modules, internal collaborators, or anything you control. At a boundary, accept the dependency as a parameter rather than constructing it inside, and prefer one function per external operation over a generic fetcher, so each mock returns one shape with no conditional logic in test setup.

<!-- Good-test, seams, anti-pattern and mocking sections adapted from mattpocock/skills tdd (MIT) — see THIRD-PARTY-NOTICES.md -->

## Project-specific extensions

`rules/testing.local.md` — survives refresh, wins on conflict.

## See also

- `agents/README.md` — `@quality-engineer` is the test-strategy agent
- `rules/error-handling.md` — error-path and edge-case coverage expectations
