# Task Management

> **This content moved.** Task management in Forge Flow is now handled by the deterministic forge CLI rather than a markdown protocol document. The CLI's atomicity guarantees are the trust boundary, and the consistency-banner hook surfaces any drift automatically.

## See instead

| Topic | Authoritative source |
|-------|---------------------|
| Task states + transitions (`pending → ready → in_progress → pr_pending → completed`) | `python3 .claude/scripts/forge/forge.py task --help` |
| Atomic state mutation (registry + file frontmatter in lockstep) | `.claude/scripts/forge/forge.py` (B2.1) |
| Registry-disk drift detection + auto-fix | `.claude/hooks/forge/consistency-banner.py` (B3.2) — fires SessionStart + PostToolUse |
| File-scope conflict detection at lock time | `forge task lock T### --session <id>` — fails on overlap |
| Dependency model (`--deps T###,T###`) | `forge task add --help` |
| Listing / filtering / showing | `forge task ls`, `forge task show T###` |
| Spec link (`isa` field) + spec nudge on lock | This file, "Task ↔ ISA link" below |
| Multi-session cooperation (broader than registry locks) | `reference/10-parallel-sessions.md` |

## Task ↔ ISA link

A task may carry an optional **`isa`** field on its registry record — the project-relative path to its per-task spec (`docs/tasks/<id>/ISA.md`). It is set automatically when a task is created with `forge task add T### ... --isa`, and is otherwise absent.

The link is **tracked and nudged, never enforced** (matching the "hooks are informational, never blocking" doctrine):

- **On lock** — `forge task lock` prints a non-blocking reminder if the task being started has no ISA (resolved from the `isa` field OR a `docs/tasks/<id>/ISA.md` on disk). It never changes the exit code or blocks the lock.
- **In the consistency checker** — `check_task_without_isa` reports an advisory `task-without-isa` finding (`severity=info`, `auto_fixable=false`) for any **in_progress** task with no ISA. It is **report-only**: the framework never auto-scaffolds an ISA (that would create empty stubs).

ISA creation stays **opt-in** — the nudge tells you a spec is missing; attaching one (`forge task add ... --isa` or `/ISA scaffold`) is always your choice. The two spec systems (PRD → epic → task vs the ISA) remain deliberately separate; this field only makes a task's spec-state *visible* rather than silent.

## Why this collapsed

In v2, `13-task-management.md` documented 399 lines of task-state semantics, transition rules, and locking conventions. Most of that is now enforced by code in `forge.py` + `registry_ops.py` + the consistency-banner hook. Repeating it in markdown invites drift between doc and behavior.

The forge CLI is self-documenting via `--help` on every subcommand. The hooks fire automatically. The atomicity guarantees are tested in `tests/forge/test_registry_ops.py`. There's no longer a separate document layer to keep in sync.

## When to read this file

- You're investigating an unfamiliar `task ...` subcommand → `forge task <action> --help`
- You suspect registry drift → consistency-banner reports it on the next Write/Edit
- You're wiring a new skill flow that needs to mutate task state → use the CLI, never hand-edit `docs/tasks/registry.json`

For multi-session conflict-coordination details (which span beyond single-task atomic mutation), see `10-parallel-sessions.md`.
