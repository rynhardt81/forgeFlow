# Run-Epic Parallel Mode

`--parallel` makes the loop spawn background agents for non-conflicting ready tasks while the main loop drives the primary task. Spawning is plain Task-tool worktree dispatch — no separate dispatch infrastructure.

## Per-iteration shape

1. **Reap finished agents first.** Integrate results from agents spawned in prior iterations: their `pr_pending` flips, the follow-up tasks they filed, lock release. A failed agent run ticks the consecutive-failure counter.
2. **Select parallelizable tasks.** From the current ready set, pick tasks whose `scope-dirs`/`scope-files` overlap neither the primary task nor each other. Tasks without scope declarations are treated as conflicting with everything — they stay in the main loop. While selecting, classify each task's effort tier (E1–E4) from its body + scope — it feeds the model route below.
3. **Cap** the batch at `--max-agents` (default 3). The cap is a ceiling, not a target.
4. **Spawn each** as a background agent in an isolated worktree:

   ```
   Task tool:
   - subagent_type: "general-purpose"
   - description: "T### : <task name>"
   - isolation: "worktree"
   - run_in_background: true
   - model: per the tier → model table in skills/_shared/model-routing.md
     (E1 → haiku, E2 → sonnet, E3 → inherit; hard floors override —
     gate-domain tasks always run at the session model)
   - prompt: task body + scope declaration + the matching discipline
     (bug/feature/refactor, same inline rules as LOOP.md) + the epic's
     session ID + instruction to follow Background Agent Checkpoint
     Discipline (ALGORITHM v1.2.0) and finish via Skill("create-pr")
   ```

   Then `forge task lock <T###> --session <session-id>-agent-<n>` so the registry shows who owns what.
5. **Main loop continues** with the primary task using the standard [LOOP.md](LOOP.md) body.

## Checkpoint Discipline (binding for every spawned agent)

Per `ALGORITHM/v1.2.0.md` — background agents have no commit safety net; the git history is the only truthful record:

- Gate D fires on entry: commit `wip(checkpoint): observe start` before any tool action; periodic `wip:` checkpoints every ~5 min / ~10 tool actions; checkpoint before long operations.
- The parent reads progress via `python3 .claude/scripts/forge/forge.py agent heartbeat <branch> [--json]` — never the agent's transcript (context overflow). Heartbeat over commit log is the contract.
- No-commit-no-reap: cleanup refuses to delete a dirty worktree; forced cleanup promotes state to `wip(reaped): ...` first.
- Before signalling completion, the agent's `git status --porcelain` must be empty.

## Reaping and integration

At the start of every iteration the parent scans:

```bash
forge task ls --epic <E##> --status pr_pending --json          # completed agents
forge task ls --epic <E##> --locked-by <session-id>-agent-* --json  # still running / stalled
```

plus the heartbeat per active agent branch. Completed → integrate (their auto-filed follow-ups already sit in the same epic). Failed or stalled-past-heartbeat → tick the consecutive-failure counter, release the lock, do not retry automatically. One exception on routing: when the failed agent was down-routed (E1/E2 model per [model-routing](../_shared/model-routing.md)), the task re-enters the ready set flagged to run at the session model on its next pick — the counter still ticks, and a session-model failure is final.

## When to use / when to skip

**Use** when the epic has many small scope-disjoint tasks with clean `scope-dirs` declarations (isolated bug fixes, parallel CRUD endpoints, per-component UI work) and you're running unattended.

**Skip** when tasks make cross-cutting changes (shared interfaces, refactor cascades), when most tasks lack scope declarations (selection yields nothing), or when early-stage architecture wants a single brain in the room.

## Guardrail interactions

[GUARDRAILS.md](GUARDRAILS.md) caps apply with these clarifications:

- **`--max-iter`** counts main-loop iterations, not agent spawns.
- **Consecutive-failure counter** ticks on either a main-loop failure or an agent failure; three across the run → halt.
- **Auto-file rate limit:** the 5/iteration cap is per-agent; the 30/run cap is total across all agents.
- **Escalation gates** trigger from any agent — an agent hitting one halts the entire run, not just itself; the parent reaps it, surfaces the escalation, and stops.
