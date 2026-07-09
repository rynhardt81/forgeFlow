# Run-Epic Auto-File Rules

When an iteration discovers new work, the loop files it back into the same epic silently. This file defines *when* that happens, *what shape* the new task takes, and *what limits* apply.

## When to auto-file

File a new task when execution surfaces:

| Discovery | Example | New task type |
|-----------|---------|---------------|
| **Bug found mid-fix** | Patching X reveals Y is also broken | `bug` |
| **Missing prerequisite** | Task needs an API client that doesn't exist yet | `feature` (the prereq) + dependency added to current task |
| **Sub-task too large** | Estimated 1 hour, after 30 min realize it's 4 hours | Split: keep current task scoped to the chunk done, file remainder as new task |
| **Duplicate logic discovered** | DRY hotspot that should be extracted | `refactor` (separate task; don't expand current scope) |
| **Test gap exposed** | Fix landed but coverage is now < threshold | `bug` if regression-prevention; `feature` if new test surface |
| **`/create-pr` pre-flight finding** | The review pre-flight raises an issue we won't fix in this PR | task with the specific finding + dep on current task's PR |
| **Architecture decision needed** | Pattern question, no clear precedent | **ESCALATE** (see [GUARDRAILS.md](GUARDRAILS.md)) — do NOT auto-file |

## When NOT to auto-file

Do not auto-file when:

- The discovery is in scope of the current task — fix it inline, don't fragment.
- The discovery is in a different epic — surface to the user at end-of-run, do not file outside the current epic.
- The discovery is a Tier 2 source-of-truth doc gap — escalate (architecture-level).
- The discovery is a hypothesis ("might be a problem") rather than a confirmed gap — file only when verified.

## What shape the new task takes

```bash
python3 .claude/scripts/forge/forge.py task add T### \
    --epic <current-epic> \
    --name "<concise actionable name>" \
    --deps <T### of triggering task, when relevant> \
    --scope-dirs <paths>
```

The task *type* (bug/feature/refactor) is not a CLI flag — it lives in the name prefix (next section) and is re-derived at classification time when the task is picked.

**Naming convention** for auto-filed tasks: prefix with the trigger context.

| Trigger | Name template |
|---------|---------------|
| Bug found mid-fix | `Bug: <one-line symptom> (surfaced by T###)` |
| Missing prereq | `Prereq: <one-line need> (blocking T###)` |
| Split-off remainder | `Continuation: <name> (split from T###)` |
| DRY hotspot | `Refactor: extract <thing> (DRY hotspot from T###)` |
| Test gap | `Test: cover <thing> (gap from T###)` |
| Review finding | `Followup: <reviewer finding> (from T### PR review)` |

The "(from T###)" suffix makes the lineage explicit and survives `forge task ls`. A future human reading the registry can trace the auto-filed task back to its trigger without reading commit history.

## Dependency wiring

- **Continuation tasks** (split-offs) depend on the parent — `--deps T<parent>`.
- **Bug-found-mid-fix** tasks do NOT depend on the parent — they're parallel work, not sequential.
- **Prereq** tasks invert the dependency — the *current* task gets `--deps T<new>` added retroactively. The current task transitions from `in_progress` back to `pending` and the new prereq task becomes `ready`.
- **DRY refactor** tasks do NOT block the current PR. The current task ships, the refactor task lands in a later iteration.

## Limits (also in GUARDRAILS.md)

- **5 per iteration max.** More than 5 means the iteration was wrongly scoped — halt with `escalation: scope-explosion`.
- **30 per run max.** More than 30 means the epic's scope is fundamentally larger than originally planned — halt and let the human re-plan.

## Logging

Every auto-file emits a single line to the iteration's progress output:

```
+ Filed T315: Bug: null check missing in WidgetSerializer (surfaced by T312)
+ Filed T316: Continuation: WidgetSerializer round-trip (split from T312)
```

These show up in the halt-summary's "New tasks filed" count and are listed by ID at the bottom of the run summary so the user can review what the autonomy decided was worth tracking.
