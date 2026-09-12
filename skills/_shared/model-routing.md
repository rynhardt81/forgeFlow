# Shared Model-Routing Policy

> Single source of truth for per-task model selection. **Binding on every subagent dispatch** — `/run-epic --parallel`, any skill that spawns Task-tool agents, and ad-hoc `Agent` calls from the main loop alike. Update this file; consumers inherit.

**A route is a pair: model *and* effort.** Naming only the model is half a route. Both current prompting guides put effort first — Claude Opus 5: *"use `low` and `medium` liberally as your primary control for token cost and response time wherever quality holds, and step up to `xhigh` for demanding coding and agentic work."* Claude Fable 5.1: *"Effort is the primary control for trading off intelligence, latency, and cost."* A bigger model at low effort is frequently cheaper **and** better than a smaller model at default effort, which is the trade a model-only table cannot express.

**At dispatch, name the tier, the model, and the effort.** One line before the call — "E2 → sonnet @ medium" — so an unjustified route is visible rather than silent. Routing up *by default* is the failure this file exists to prevent: a bigger model on a mechanical task costs more, is slower, and buys nothing. Route down to the tier, and up only for a hard floor below or a stated reason.

The main session stays on the session model. Subagents doing bounded work often don't need it — routing smaller models to simpler tasks cuts cost and latency. Quality gates never scale down: verification evidence rules are identical whatever model executed.

## Mechanisms (all generally available in Claude Code, any session model)

| Mechanism | Sets | Where | Scope |
|-----------|------|-------|-------|
| `model` parameter on the Task/Agent tool call | model | per invocation | one dispatch |
| `model:` frontmatter (`haiku` \| `sonnet` \| `opus` \| `fable` \| full ID \| `inherit`) | model | `.claude/agents/<name>.md` | that agent, every invocation |
| `effort:` frontmatter (`low` \| `medium` \| `high` \| `xhigh` \| `max` \| a number) | effort | `.claude/agents/<name>.md` | that agent, every invocation |
| `CLAUDE_CODE_SUBAGENT_MODEL` env var | model | environment | all subagents |

Resolution order: env var → per-invocation parameter → agent frontmatter → session model. On a harness that lacks the `model` parameter, omit it — dispatch proceeds at the session model, everything else unchanged.

> **Effort is not settable per dispatch.** The Agent tool call accepts `model`; it has no effort input. Effort comes from the agent's definition — `effort:` in `.claude/agents/<name>.md` frontmatter, or the `effort` field of an SDK `AgentDefinition` — and a subagent otherwise inherits the session's thinking configuration. Two consequences bind the table below:
>
> - An **ad-hoc dispatch** (`subagent_type: "general-purpose"` plus a model) can set the model half of a route and nothing else. Its effort is the session's.
> - To route a tier at a **lower effort than the session's**, the dispatch must go through a **named agent** carrying that `effort:` in its frontmatter. A tier whose value comes mostly from the effort half is a reason to define an agent rather than hand-roll the call.
>
> Verified against the Claude Code subagents reference, which lists `effort` among the supported `.claude/agents/*.md` frontmatter fields — *"Effort level when this subagent is active. Overrides the session effort level. Default: inherits from session. Options: `low`, `medium`, `high`, `xhigh`, `max`; available levels depend on the model"* — the SDK `AgentDefinition` reference, which carries the same field, and the Agent tool's own input schema, which exposes `model` and no effort input. Do not write an effort argument into a dispatch; it is silently nothing.

## Routing table

Classify the task with the framework's effort-tier vocabulary (CLAUDE.md → Modes), judged from the task body + declared scope at dispatch time:

| Tier | Task shape | Model | Effort | Sweep against |
|------|-----------|-------|--------|---------------|
| E1 | Mechanical: typo, rename, doc sync, config bump, single obvious one-file fix | `haiku` | `low` | `fable` @ `low` |
| E2 | Single-domain substantial: isolated bug with a clear repro, single-module feature, test backfill | `sonnet` | `low`–`medium` | `fable` @ `low` |
| E3 | Multi-file, needs planning | inherit (session model) | `medium`–`high` | inherit @ `medium` before inherit @ `high` |
| E4 | Architectural, cross-cutting | do not dispatch — main loop only (matches PARALLEL.md selection rules) | — | — |

**This table is a starting point, not a measurement.** Neither column has been swept on this framework's own tasks. Both guides say the same thing about that, and it is the reason the "Sweep against" column exists rather than a rewritten model column.

## Why Fable is a candidate at every down-routed tier

Claude Fable 5.1's guide: *"At `low`, Claude Fable 5.1 is often competitive with Claude Opus and Claude Sonnet models on cost per task while scoring higher, so include it in the comparison wherever you'd otherwise run a smaller model at a higher effort level."*

E1 and E2 are precisely "a smaller model at a higher effort level" — `haiku` and `sonnet` at whatever effort the session happens to carry. So the guide's instruction lands on both rows. It says *include it in the comparison*, which is what the column does; promoting Fable into the model column is a claim about measured cost-per-task on this framework's tasks, and no such measurement exists yet. Run the sweep, then move it.

## Effort names do not transfer between models

Standing caveat, from both guides. Claude Fable 5.1: *"Re-run the sweep even if you already ran one on Claude Fable 5: effort level names don't correspond to the same amount of thinking across models."* Claude Opus 5: *"If you carried effort defaults over from a prior model, re-run an effort sweep on your own evals."*

`medium` on one model is not `medium` on another. Consequences for this file:

- A route carried over from a previous model is **unverified**, not inherited. Re-sweep it; do not assume it transfers.
- When the session model changes, every effort value above is stale until re-swept — including a value that was measured.
- A sweep result is worth recording where it will be read: a `model-routing.local.md` sidecar in the consumer project, which survives framework refresh.

## Hard floors — route at the session model, and never below `high` effort, regardless of tier

- Tasks touching gate domains: schema/migrations, auth, money paths (`rules/migrations.md`, Algorithm gates).
- Security-review work of any size.
- Tasks whose body or ISA declares E3+/gate applicability, even when the diff looks small.

The floor binds **both** halves of the route. Down-routing effort on a floor task is the same defect as down-routing the model, and it is the easier one to do by accident — effort has no per-dispatch argument, so a floor task handed to a named agent carrying `effort: low` inherits that agent's effort silently. Never point a floor task at a down-routed agent definition.

## Failure escalation

If a down-routed (E1/E2) agent fails its task: release the lock and tick the failure counter exactly as PARALLEL.md prescribes, and record that this task routes at the session model on its next pick. One escalation per task; a failure at the session model is a real failure.

## Heavy fan-out: Workflows ("ultracode")

Claude Code also ships a deterministic multi-agent Workflow tool — script-driven `agent()` / `parallel()` / `pipeline()` orchestration, 16 concurrent agents, 1000-agent/run cap. Generally available on paid plans with any session model; opt in with the `ultracode` keyword (or `/effort ultracode`). Prefer `/run-epic --parallel` for registry work (locks, heartbeats, guardrails are already wired); reach for a Workflow for read/analyze fan-out — audits, sweeps, research — that doesn't need task locks.

## External executors (ChatGPT / Codex CLI, etc.) — opt-in only

Claude Code has no native cross-vendor routing. Shelling out to another vendor's CLI is possible for an isolated, bounded task, but only with explicit user opt-in per run, a hard cap on invocations, and never inside an unattended loop — any billable AI CLI spawned in a loop is a runaway-cost hazard. Treat its output as an untrusted diff: same review and verification as any other change. No framework skill wires this by default; keep it that way.

---

**Project-specific overrides:** if `model-routing.local.md` exists in this directory, read it — it is consumer-owned, survives framework refresh, and **wins on conflict**. Sweep results belong there: a measured route beats this file's starting point, and a sidecar that overrides a route should record the sweep that justifies it.
