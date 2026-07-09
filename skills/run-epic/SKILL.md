---
name: run-epic
description: Autonomously drain every open task in a single epic. Pulls ready tasks via the forge CLI, executes the work in-context using the matching discipline (fix-bug / new-feature / refactor), files newly-discovered work back into the same epic silently, opens a PR per completed task via /create-pr, and repeats until the epic has zero ready/in-progress/pending tasks. Use when the user says `/run-epic E##`, "run epic autonomously", "finish all remaining tasks for epic X", or "drive epic X to completion".
---

## Quick Scan

| | |
|---|---|
| **Purpose** | Drive a single epic to zero open tasks autonomously |
| **Inputs** | Epic ID (`E##`), optional flags (`--max-iter`, `--dry-run`, `--no-pr`, `--resume`, `--parallel`) |
| **Output** | Completed tasks, opened PRs, new tasks filed for discovered work |
| **Flow** | Init → Loop(pick → execute → verify → PR → file follow-ups) → Halt |

# Run Epic

`/run-epic` takes a named epic and drains it to zero open tasks without human ping-pong between every task. The skill runs the work itself — it follows the discipline of `/fix-bug`, `/new-feature`, or `/refactor` inline in the same context rather than spawning them as sub-skills, which would lose the epic-level context (queued tasks, files already touched, follow-ups already filed).

The distinguishing capability is the **self-feeding loop**: when execution surfaces a bug, a missing prerequisite, or a task too coarse to finish in one go, `/run-epic` files a new forge task into the same epic and continues. The epic grows until reality stops surprising it; then it shrinks to zero. It works directly on the forge task registry (`docs/tasks/registry.json`) via `forge task ...` — the only sanctioned mutation path.

## Invocation

```
/run-epic E37 [--max-iter=20] [--dry-run] [--no-pr] [--resume] [--parallel [--max-agents=3]]
```

- `E##` — required; the single epic to drain.
- `--max-iter=<n>` — hard cap on iterations this run. Default: 50.
- `--dry-run` — list what would be done (next task, discipline, projected parallel groups); no mutations.
- `--no-pr` — skip `/create-pr` per task; `forge task complete` and continue (batched-PR workflows).
- `--resume` — explicitly opt in to picking up interrupted (`in_progress`/`pr_pending`) tasks.
- `--parallel` — spawn background agents in isolated worktrees for scope-disjoint ready tasks while the main loop drives the primary task; each agent runs on a model matched to its task's effort tier (`skills/_shared/model-routing.md`). See [PARALLEL.md](PARALLEL.md).
- `--max-agents=<n>` — ceiling on concurrent background agents. Default: 3.

## Step 0: Map the surface

Read `docs/code-map.md` (auto-regenerated each SessionStart). For an autonomous run the map is non-negotiable — without per-file symbol info the loop re-discovers the same code structure every task. Missing → run `/audit-code-map` first. **Refuse to start without it.**

## Step 1: Validate the epic

1. `forge task ls --epic <E##> --json` — confirm the epic exists.
2. Compute the work surface: `ready`, `in_progress`, `pr_pending`, `pending` counts.
3. **Refuse to start** if all four are 0 — nothing to do.
4. **Refuse to start** if `in_progress > 0` without `--resume` — interrupted runs deserve a human glance before clobbering.
5. Print the drain plan (counts + cap) and confirm once with the user.

## Step 2: Session start

Generate a session ID and declare scope — the union of `scope-dirs` across the epic's tasks. Same conflict-scan protocol as any `/reflect` session.

## Step 3: Run the loop

The per-iteration body — pick, lock, classify, execute, verify, file follow-ups, PR — is defined in [LOOP.md](LOOP.md). With `--parallel`, each iteration also spawns background agents per [PARALLEL.md](PARALLEL.md).

The loop terminates when any of these is true:

- `forge task ls --epic E## --status ready,in_progress,pending --json` returns `[]`
- Iteration count hits `--max-iter`
- **Three consecutive iterations fail** ([GUARDRAILS.md](GUARDRAILS.md))
- A task trips an escalation gate ([GUARDRAILS.md](GUARDRAILS.md) — halts, not failures)

## Step 4: Loop end

Print the halt summary (format in [GUARDRAILS.md](GUARDRAILS.md)): completed, PRs opened, new tasks filed, remaining, reason for halt. On `--max-iter` or `consecutive-failure`, surface the next-task suggestion explicitly; on `escalation`, surface the specific blocker.

## Hard rules

- **Never silently mutate registry.json** — all state changes via `forge task ...`.
- **Never skip `/create-pr` failures** — a PR failure halts on that task; don't move on with uncommitted work.
- **Never run forever** — `--max-iter` is the ceiling; consecutive-failure is the circuit breaker.
- **Never auto-file outside the current epic** — out-of-epic discoveries are surfaced at end-of-run, not filed elsewhere.
- **Never resume `in_progress` tasks without `--resume`.**

## See also

- [LOOP.md](LOOP.md) — the per-iteration body
- [GUARDRAILS.md](GUARDRAILS.md) — caps, circuit breaker, escalation gates, halt format
- [TASK-CREATION.md](TASK-CREATION.md) — auto-file rules and task shapes
- [PARALLEL.md](PARALLEL.md) — `--parallel` worktree mode
- `skills/fix-bug/SKILL.md`, `skills/new-feature/PHASES.md`, `skills/refactor/SKILL.md` — the disciplines the loop follows inline
- `skills/create-pr/SKILL.md` — invoked per task at the PR step

## Gotchas

- **Single-epic by design.** Two epics → run it twice. Cross-epic dependencies resolve via `pending → ready` transitions, not by the skill.
- **`--resume` is opt-in for a reason.** Auto-resuming `in_progress` tasks has clobbered uncommitted work in the past.
- **Classification is judgment, asked once.** Classify each task as bug/feature/refactor from its name + body. When genuinely ambiguous, pause and ask once; cache the answer for similar tasks in the run.
- **`/create-pr` may itself surface follow-up work** (DRY hotspots, review findings) — those land in the same epic under the same auto-file rules.
- **Code-map staleness is the silent killer.** A map older than the newest commit routes fixes to outdated locations. Do not relax the Step 0 gate.
