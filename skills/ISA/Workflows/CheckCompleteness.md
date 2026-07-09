# Workflow: CheckCompleteness

> Score an existing ISA against the completeness gates. Reports gaps; never modifies the ISA. The Algorithm's `phase: complete` transition is gated on this passing.

## Inputs

| Input | Required | Default |
|-------|----------|---------|
| `path` | yes | — path to the ISA to score |

## Gates

Walk all gates in order — don't short-circuit on the first failure; the caller needs the full picture. Record pass/fail with a one-line reason each.

1. **Frontmatter parses** — YAML between the leading `---` markers, with keys `project`, `task`, `slug`, `effort`, `phase`, `progress`, `started`, `updated` (other keys allowed).
2. **All 12 sections present in order** — `## Problem`, `## Vision`, `## Out of Scope`, `## Principles`, `## Constraints`, `## Goal`, `## Criteria`, `## Test Strategy`, `## Features`, `## Decisions`, `## Changelog`, `## Verification` (case-sensitive; out-of-order fails with a note).
3. **Coverage** — every deliverable and named risk in `## Goal` maps to ≥1 ISC in `## Criteria`, and every ISC has a nameable single-tool probe in `## Test Strategy`. This is a judgment gate, not a count: list any deliverable without a probe as a gap. Tombstoned ISCs don't count as coverage.
4. **≥1 `Anti:` ISC** present in `## Criteria`.
5. **`Antecedent:` ISC if experiential** — if `## Goal` describes user experience/perception ("user", "feel", "delight", "smooth"), require ≥1 `Antecedent:` ISC; otherwise auto-pass with a note.
6. **Every `[x]` ISC has a Verification entry** — a corresponding `ISC-N` entry in `## Verification` with a non-trivial body (actual probe evidence, not "done"). Missing entries are gaps.
7. **No empty/placeholder sections at phase ≥ build** — `_(open — fill at THINK)_`-style bodies are gaps once `phase: build` or later; at observe/think/plan they warn, not fail.

## Report

```
## ISA Completeness — <path>
**Phase**: <observe..complete>   **Progress**: <x>/<n>

### Gates
- [✓|✗] <gate> — <one-line reason>

### Gaps
- <what's missing, where — file-line referenced when possible>

### Verdict
<READY-FOR-NEXT-PHASE | BLOCKED — see gaps>
```

Exit 0 if every gate passes; exit 1 otherwise (callers fail fast on it).

## Anti-criteria for this workflow

- Anti: does NOT modify the ISA (read-only, idempotent).
- Anti: does NOT short-circuit — reports all gates every run.
- Anti: does NOT auto-fix gaps — that belongs to the next Algorithm phase or the user.
