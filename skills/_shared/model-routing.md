# Shared Model-Routing Policy

> Single source of truth for per-task model selection when a skill dispatches subagents. Consumed by `/run-epic --parallel` (background task agents) and available to any skill that spawns Task-tool agents. Update this file; consumers inherit.

The main session stays on the session model. Subagents doing bounded work often don't need it — routing smaller models to simpler tasks cuts cost and latency. Quality gates never scale down: verification evidence rules are identical whatever model executed.

## Mechanisms (all generally available in Claude Code, any session model)

| Mechanism | Where | Scope |
|-----------|-------|-------|
| `model` parameter on the Task/Agent tool call | per invocation | one dispatch |
| `model:` frontmatter (`haiku` \| `sonnet` \| `opus` \| full ID \| `inherit`) | `.claude/agents/<name>.md` | that agent, every invocation |
| `CLAUDE_CODE_SUBAGENT_MODEL` env var | environment | all subagents |

Resolution order: env var → per-invocation parameter → agent frontmatter → session model. On a harness that lacks the `model` parameter, omit it — dispatch proceeds at the session model, everything else unchanged.

## Routing table

Classify the task with the framework's effort-tier vocabulary (CLAUDE.md → Modes), judged from the task body + declared scope at dispatch time:

| Tier | Task shape | Route |
|------|-----------|-------|
| E1 | Mechanical: typo, rename, doc sync, config bump, single obvious one-file fix | `haiku` |
| E2 | Single-domain substantial: isolated bug with a clear repro, single-module feature, test backfill | `sonnet` |
| E3 | Multi-file, needs planning | inherit (session model) |
| E4 | Architectural, cross-cutting | do not dispatch — main loop only (matches PARALLEL.md selection rules) |

## Hard floors — route at the session model regardless of tier

- Tasks touching gate domains: schema/migrations, auth, money paths (`rules/migrations.md`, Algorithm gates).
- Security-review work of any size.
- Tasks whose body or ISA declares E3+/gate applicability, even when the diff looks small.

## Failure escalation

If a down-routed (E1/E2) agent fails its task: release the lock and tick the failure counter exactly as PARALLEL.md prescribes, and record that this task routes at the session model on its next pick. One escalation per task; a failure at the session model is a real failure.

## Heavy fan-out: Workflows ("ultracode")

Claude Code also ships a deterministic multi-agent Workflow tool — script-driven `agent()` / `parallel()` / `pipeline()` orchestration, 16 concurrent agents, 1000-agent/run cap. Generally available on paid plans with any session model; opt in with the `ultracode` keyword (or `/effort ultracode`). Prefer `/run-epic --parallel` for registry work (locks, heartbeats, guardrails are already wired); reach for a Workflow for read/analyze fan-out — audits, sweeps, research — that doesn't need task locks.

## External executors (ChatGPT / Codex CLI, etc.) — opt-in only

Claude Code has no native cross-vendor routing. Shelling out to another vendor's CLI is possible for an isolated, bounded task, but only with explicit user opt-in per run, a hard cap on invocations, and never inside an unattended loop — any billable AI CLI spawned in a loop is a runaway-cost hazard. Treat its output as an untrusted diff: same review and verification as any other change. No framework skill wires this by default; keep it that way.
