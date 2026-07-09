---
name: refactor
description: Disciplined refactoring with risk-scaled process, scope boundaries, and behavior-preservation verification. Restructures existing code without changing behavior — extract, split, rename, reorganize, simplify, optimize. NOT FOR bug fixes (use /fix-bug), new features (use /new-feature), or framework migration (use /migrate).
---

# Refactor

`/refactor <description>` — what to change and where.

Refactoring changes structure, never behavior. If the work requires new behavior, that's a feature — handle it separately.

## 1. Classify by risk

| Risk | Signals | Process |
|------|---------|---------|
| **Low** | Rename/extract/inline within 1–2 files, no interface change | Confirm plan inline → refactor → verify |
| **Medium** | Rename across 3+ files, widely-used symbol, or performance change (identical behavior, measurable surface) | Scope boundary + coverage check first |
| **High** | Structural: files move, module boundaries shift, import paths change codebase-wide | Written scope doc + coverage check + manual review of the moves |

Risk scales with **rename scope** (how many files see the symbol) and **behavior surface** (how much runtime behavior could shift if you get it wrong). When uncertain, classify up. Present classification + intended process to the user before starting.

For Medium/High, write the boundary down (a short scope doc at `docs/refactors/<date>-<slug>.md` or inline in the conversation): files in scope, explicitly out-of-scope items with reasons, success criteria. Refactoring has a gravity problem — adjacent improvements pull scope outward; the written boundary is the reference point that catches drift.

## 2. Establish the baseline

Run the test suite **before touching anything**. You cannot prove "behavior unchanged" without a green starting point.

- Tests failing before you start → stop and surface it.
- Medium/High: check the code you're about to change is actually covered. Gaps in high-risk areas → flag and ask whether to write tests first.
- Performance refactors: record benchmark numbers now (response time, memory, query count).

## 3. Refactor

- **One logical change at a time, tests between changes** — a 15-file one-shot that then fails is far harder to bisect than a break caught immediately.
- **Out-of-scope temptations get logged** (Deferred Improvements), not acted on. Crossing the boundary requires asking: "I need to modify `[file]`, which is outside scope. Expand?"
- Structural moves: create new locations first, move code, update every reference (imports, type refs, test fixtures, **and config files** — build configs, CI, dynamic imports, lazy loading — the references that don't fail until runtime), then remove old locations only after tests pass on the new paths.
- Performance: profile before optimizing; if a change shows no measurable improvement, revert it rather than stacking optimizations.

## 4. Verify behavior preserved

- Full test suite green — same results as the baseline, no semantic diff.
- Performance: re-run benchmarks, present before/after numbers.
- **Structural refactors (Python): run the undefined-name check** before opening the PR:

```bash
python3 .claude/skills/refactor/Tools/check_undefined_names.py <new-file-1> <new-file-2> ...
```

Structural splits produce a bug class where a module-local helper lands in one new file but is called from another — a runtime `NameError` that a broad `try/except` silently swallows. The script wraps pyflakes (host → `python -m pyflakes` → `docker exec $REFACTOR_CHECK_CONTAINER`) and surfaces only undefined-name findings. Exit codes: `0` safe, `1` slicing bug — fix before merge (missing import, or extract the helper to a shared module), `2` pyflakes unavailable — note in the PR that the gate didn't run. TypeScript/JS projects get equivalent protection from the type-checker; this gate no-ops there.

After structural changes, refresh `docs/code-map.md` via `/audit-code-map`.

## 5. Ship

Commit as `refactor: <description>` (reference the scope doc for Medium/High). Present the commit message for approval, then invoke `Skill("create-pr")` — never raw `gh pr create`; the pre-flight review (Step 3.7) is what catches behavior drift across moved/renamed symbols. Deeper code-smell or pattern review afterwards: Task tool with `subagent_type: "quality-engineer"`.

Present the deferred-improvements list at the end — the user decides what becomes follow-up tasks.

## Principles

- **Green baseline first** — "unchanged" needs a definition of "before".
- **Scope boundaries** — without one, a refactor expands until it's a rewrite; log the temptation, defer it, keep moving.
- **Incremental with test runs** — catch the break at the change that caused it.
- **No new functionality** — mixing refactor and feature makes both harder to review and revert.
