# Run-Epic Loop Body

One iteration of the loop = one task taken from `ready` to `complete` (or `pr_pending` on `--no-pr`).

## Pick

```bash
python3 .claude/scripts/forge/forge.py task ls --epic <E##> --ready --json | jq -r '.[0].id'
```

Highest-priority ready task wins; tie-break lowest ID (oldest first). `null` → no ready tasks → exit the loop.

## Lock

```bash
python3 .claude/scripts/forge/forge.py task lock <T###> --session <session-id>
```

Lock conflict (another session holds overlapping `scope-dirs`) → skip and pick the next ready task. Three consecutive lock conflicts on different tasks → halt with `escalation: lock-conflict`.

## Classify

Read the task body (`forge task show <T###> --json | jq -r '.file'`). Classify as **bug**, **feature**, or **refactor** from the task name and first paragraph — this is native judgment, not keyword matching. If genuinely ambiguous, surface a single ask ("T### classifies ambiguously — treat as bug | feature | refactor?") and cache the answer for similar cases this run.

## Execute

Follow the matching discipline **inline**, in this context:

- `bug` → `skills/fix-bug/SKILL.md`
- `feature` → `skills/new-feature/PHASES.md`
- `refactor` → `skills/refactor/SKILL.md`

Inline means: read the discipline file and follow its phases here — do not invoke the skill via `Skill(...)`. Spawning a sub-skill loses the epic-level context (queued tasks, files touched in earlier iterations, follow-ups already filed). The loop is the orchestrator; the discipline files are how-to guides. The skills' user-confirmation stops are replaced by this loop's guardrails — that's the autonomy trade the user accepted by invoking `/run-epic`.

## Verify

Per `ALGORITHM/LATEST` (v1.2.0): every ISC/criterion for the task flips `[x]` only with tool-verified evidence in the same block. Forbidden language: "should work", "looks fine", "tests pass" without the actual output.

Verification failure → the iteration is a failure; see [GUARDRAILS.md](GUARDRAILS.md) for the circuit breaker.

## File follow-ups

New work discovered (bug found mid-fix, missing prerequisite, oversized sub-task) → file each as a new forge task in the same epic, silently. Rules and shapes: [TASK-CREATION.md](TASK-CREATION.md).

## PR

Unless `--no-pr`: invoke `Skill("create-pr")`. It runs its own pre-flight gates; on success it flips the task to `pr_pending` via `forge task pr <T###>`. If PR creation fails, the iteration fails — do not move on with uncommitted work. Completion happens externally on merge.

## Complete (only on `--no-pr`)

```bash
python3 .claude/scripts/forge/forge.py task complete <T###>
```

This unblocks downstream tasks (`pending → ready`); the next iteration picks one up.

## Iteration end

Increment the counter. Loop back to **Pick**.
