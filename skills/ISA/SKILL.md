---
name: ISA
description: Articulate the ideal state of a task or project as testable criteria. Invoked at Algorithm OBSERVE for non-trivial work; produces an ISA.md the rest of the run reads from and writes back to.
model: inherit
type: skill
---

# ISA — Ideal State Articulation

The ISA is the **system of record** for a non-trivial Algorithm run. A single document holding:

1. The ideal-state articulation (Problem / Vision / Goal)
2. The test surface (Criteria — atomic ISCs)
3. The verification trail (tool-probe evidence per ISC)
4. The done condition (every ISC `[x]` with evidence)
5. The persistence trail (Decisions + Changelog)

Created at OBSERVE, refined through pursuit, verified at VERIFY.

## Tiers (per `ALGORITHM/v1.2.0.md`)

- **E2** — inline criteria checklist in the reply; no ISA document.
- **E3/E4** — ISA document required. Two homes: **project ISA** at `<project>/ISA.md` (long-lived) or **task ISA** at `docs/tasks/<task-id>/ISA.md` (per-task; auto-created by `forge task add --isa`). Prefer extending the project ISA for project tasks; task ISA for ad-hoc work.

## When invoked

| Trigger | Action |
|---------|--------|
| Algorithm OBSERVE, E3+ | [Scaffold](Workflows/Scaffold.md) — create or extend the relevant ISA |
| Algorithm VERIFY | [CheckCompleteness](Workflows/CheckCompleteness.md) — gate `phase: complete` |
| OBSERVE at E3/E4, unresolved interdependent design decisions | [Interview](Workflows/Interview.md) — dependency-ordered design interview (optional, skippable) |
| `/ISA scaffold "..."` · `/ISA check <path>` · `/ISA interview <path>` | Same workflows, manual |

A plain `forge task add` carries no ISA — track + nudge, never enforce. `task lock` prints a non-blocking reminder; the consistency checker reports advisory `task-without-isa` findings. Attaching one stays your choice.

## The 12-section structure (locked order)

| # | Section | Role |
|---|---------|------|
| 1 | **Problem** | What's broken / missing / wanted — concrete, evidence-backed |
| 2 | **Vision** | The world once this is done |
| 3 | **Out of Scope** | Explicit cuts for this run |
| 4 | **Principles** | Inviolable rules framing every decision |
| 5 | **Constraints** | Inherited boundaries; references Tier 2 docs |
| 6 | **Goal** | One paragraph — the deliverable in concrete terms |
| 7 | **Criteria** | Atomic ISCs, each one nameable tool probe |
| 8 | **Test Strategy** | Per-ISC: type / check / threshold / tool |
| 9 | **Features** | Phased breakdown linking ISCs to delivery units |
| 10 | **Decisions** | Timestamped — chosen, why, rejected |
| 11 | **Changelog** | Conjecture/refutation pairs — how understanding evolved |
| 12 | **Verification** | Tool-probe evidence per `[x]` ISC — closes the loop |

## ISC quality gates

**Criterion count is judgment, not a quota** — enough that every deliverable, risk, and regression path has a probe; no more. Gate each criterion with the splitting test:

- **Granularity** — a single nameable tool probe (Read / Grep / Bash / curl / …)
- **Atomic** — one verifiable end-state; compound "and"/"with" → split
- **Independent failure** — A can pass while B fails → split
- **Scope words** — "all", "every", "complete" → enumerate
- **Domain boundary** — one ISC per UI / API / data boundary

Required regardless of size: **≥1 `Anti:` ISC** — what must NOT happen, making regression-prevention and out-of-scope probe-able. (Experiential goals also carry ≥1 `Antecedent:` ISC — the gate the user ultimately judges by.)

## Operating rules

- **ISC IDs are stable** — never renumber. Splits become `ISC-N.M`; drops become tombstones with a note.
- **`[x]` requires evidence in `## Verification`** — never just "tests pass" or "looks fine".
- **Tier 2 docs win on conflict** — `.claude/reference/02-architecture-and-tech-stack.md` is authoritative over `## Constraints` until reconciled via ADR.
- **`phase: complete` is gated** — CheckCompleteness must pass first.

## See also

- `.claude/ALGORITHM/v1.2.0.md` — phase doctrine that drives ISA usage (LATEST)
- `.claude/reference/06-architecture-decisions.md` — where significant Decisions land long-term as ADRs
- `.claude/scripts/forge/forge.py task add --isa "..."` — auto-creates the task ISA
