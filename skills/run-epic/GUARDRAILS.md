# Run-Epic Guardrails

Autonomy without limits is reckless. Five guardrails define when the loop is allowed to keep running and when it must halt.

## 1. Iteration cap (`--max-iter`)

Default: **50**. Hard ceiling. The loop never runs more than this many iterations in a single invocation, regardless of how many tasks are still open.

When the cap is hit:
- Print remaining open task count.
- Suggest: `/run-epic <E##>` to continue (a fresh invocation, fresh cap).
- Do not auto-restart.

This exists for two reasons. First, a runaway loop spawning new tasks faster than it completes them needs a hard stop. Second, an explicit re-invoke is a natural human checkpoint — the user can glance at what was filed and what's queued before authorizing more autonomy.

## 2. Consecutive-failure circuit breaker

If **three iterations in a row** fail (verification fails, PR fails to open, classification ambiguity, etc.), halt with `escalation: consecutive-failure` and surface the three failure summaries. Do not silently move on.

A "failure" is any iteration that did not reach a successful PR (or `forge task complete` under `--no-pr`). A skipped iteration (lock conflict, deferred task) is not a failure.

The threshold is intentionally low. The pattern this catches is a class of related tasks all hitting the same underlying blocker — better to surface it once after three than to burn 20 tasks all failing the same way.

## 3. Escalation gates (immediate halt, not a failure)

Some discoveries are worth a human glance before continuing. The loop halts cleanly with `reason: escalation` when:

| Trigger | Why escalate |
|---------|--------------|
| Task surfaces an architecture decision (new ADR needed) | ADRs are a `@architect` call, not autonomy |
| Task touches Tier 2 source-of-truth docs (`reference/01-09.md`) | Source-of-truth changes deserve human review |
| Task adds a dependency or modifies CI config | Supply-chain/build changes — never silent |
| Task fails security validation (`security-boss` flag) | Security findings always get a human eye |
| Task reveals a pre-existing breakage in `main` | Means earlier work was wrongly marked complete — halt to investigate |
| Task's required `scope-dirs` overlap an in-progress sibling task across sessions | Cross-session conflict — already protected by lock, but surface it explicitly |

When escalating, file (or update) a follow-up task with the specific decision needed and the context, then halt the loop. The follow-up sits in the epic until a human resumes it.

## 4. Task-creation rate limiter

Auto-filing follow-up tasks is the loop's most powerful capability and its most dangerous one. The rate limiter:

- **Per-iteration cap: 5 new tasks.** A single iteration that wants to file more than five follow-ups is a sign the work was wrongly scoped — halt with `escalation: scope-explosion` instead of filing.
- **Per-run cap: 30 new tasks.** A run that has filed 30 new tasks total has effectively rewritten the epic's scope on the fly — halt and let the human re-plan.

These are aggressive caps by design. The autonomy is for *draining* an epic, not *expanding* it indefinitely.

## 5. Spawn budget (`--parallel` only)

`--max-agents` caps a *batch*. It does not cap a *run*. A long drain spawns up to `--max-agents` per iteration across many iterations, and those accumulate: the defaults alone project `3 × 50 = 150` agent spawns for one invocation. Nothing in the loop counted them, so a run that exhausted an environment's subagent budget discovered it mid-epic — the failure mode being a half-drained epic and a "finish the remaining work directly" message, which is the worst moment to learn about a ceiling.

The loop counts its own spawns and checks headroom **before** the batch, not after the refusal.

**At init (Step 1, with `--parallel`), project and report:**

```
Spawn projection:  --max-agents 3 x --max-iter 50 = up to 150 agent spawns
Environment caps:  concurrent=6 (set)  depth=1 (set)  per-session=40 (set)
```

Read each cap from the environment rather than assuming a default — `echo "${CLAUDE_CODE_MAX_CONCURRENT_SUBAGENTS:-unset}"` and the same for `CLAUDE_CODE_MAX_SUBAGENT_SPAWN_DEPTH`. `unset` means the documented default applies (see `skills/_shared/model-routing.md`), not that no cap exists.

**Before each batch:**

- Clamp `--max-agents` to the concurrency cap when the environment sets one lower. A `--max-agents` above it is not an error; it is a ceiling that can never be reached, and silently pretending otherwise hides the real parallelism from the halt summary.
- Keep a running `spawned` count for the invocation and print it in the halt summary.
- Where the environment declares a per-session total, warn as soon as `spawned + --max-agents` would exceed it, and **degrade to serial** — drop to the main-loop-only body and keep draining — rather than spawning into a refusal. A degraded run is slower; a refused one is a halt with work in flight.

**Anti:** a guardrail whose only trigger is a per-session environment variable existing. That variable is environment-specific and outside the documented cap set (see `model-routing.md`), so the projection and the `spawned` count must be reported whether or not it is set. Their value is that the human sees the number 150 before the run, not that any particular variable catches it.

## Halt summary format

Every halt — clean or otherwise — prints a single block:

```
Run-epic halted.
  Epic:           E37
  Reason:         epic-empty | --max-iter | consecutive-failure | escalation:<gate>
  Iterations:     14 / 50
  Completed:      11
  PRs opened:     11
  New tasks:      6
  Agents spawned: 27 / 150 projected (--parallel runs only)
  Failed:         3 (T315, T316, T317 — see below)
  Open tasks:     T314, T318, T319 (pending deps)
  Next:           [specific suggestion]
```

If `Failed > 0`, list each failure with a one-line summary (the verification message, the PR error, the classification ambiguity). The user should be able to scan the halt block and immediately know what's salvageable and what isn't.
