# Run-Epic Guardrails

Autonomy without limits is reckless. Four guardrails define when the loop is allowed to keep running and when it must halt.

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
  Failed:         3 (T315, T316, T317 — see below)
  Open tasks:     T314, T318, T319 (pending deps)
  Next:           [specific suggestion]
```

If `Failed > 0`, list each failure with a one-line summary (the verification message, the PR error, the classification ambiguity). The user should be able to scan the halt block and immediately know what's salvageable and what isn't.
