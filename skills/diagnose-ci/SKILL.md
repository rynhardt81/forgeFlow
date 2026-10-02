---
name: diagnose-ci
description: Diagnoses a failed GitHub Actions run locally and routes to the correct pr-review-toolkit specialist agent. Reads run logs via `gh run view --log-failed`, classifies the failure, dispatches the matching specialist, and outputs a proposed fix plan. Does not push, commit, or modify files without explicit user approval — diagnosis is advisory. Use when a GitHub Actions run has failed and the cause needs diagnosing before another push. NOT FOR pre-push CI mirroring (/preflight-ci) or production incidents (/triage-incident).
hooks:
  Stop:
    - hooks:
        - type: command
          command: "python3 $CLAUDE_PROJECT_DIR/.claude/hooks/validators/skills/diagnose_ci_format.py --final"
---

# Diagnose CI Workflow

Diagnoses a failed CI run locally and proposes a fix path via pr-review-toolkit specialists, without burning more Actions minutes on blind retries. Input is an optional `<run-id>` (default: latest failed run on the current branch); output is a failure classification, the specialist(s) consulted, and a proposed fix plan. No files are modified.

## Index

| File or section | Read when… |
|---|---|
| Why this exists / Invocation | Deciding whether to run it; the no-failed-run exit |
| Steps 1–2 | Locating the run and fetching its failed logs |
| `_shared/ci-failure-classifier.md` | Step 3 — the routing table, degradation rules, dispatch prompt |
| Step 4: Dispatch the specialist | Fanning out to matched specialists |
| Steps 5–6 | The fix-plan format and the user-approval gate |
| Key Rules / Gotchas | Always — diagnosis only, no re-run, large matrix logs |

## Why this exists

GitHub Actions paid plans cap monthly minutes. Every fix-and-retry on a CI failure burns more minutes. This skill replaces the blind-retry loop with a local diagnosis: read the failed logs, classify the failure, route to the specialist that knows that failure class, and output a proposed fix plan **before** any code change. The user authorises the next push.

This skill is the post-failure companion to `/create-pr` Step 3.7 (pre-flight specialist review). Together they cover both leak points: prevention before push, and diagnosis after CI fails.

## Invocation

| Form | Behaviour |
|------|-----------|
| `/diagnose-ci` | Diagnose the latest failed run on the current branch |
| `/diagnose-ci <run-id>` | Diagnose a specific run by ID |

If no failed run is found, the skill emits `No failed runs to diagnose on <branch>` and exits cleanly — never an error.

## Step 1: Locate the failed run

If `<run-id>` is supplied, use it. Otherwise:

```bash
gh run list --branch "$(git rev-parse --abbrev-ref HEAD)" --status failure --limit 1 --json databaseId,name,conclusion,headSha
```

Capture the `databaseId` as `<run-id>`. If the list is empty, exit with the no-failure message above.

## Step 2: Fetch failed logs

```bash
gh run view <run-id> --log-failed
```

Capture the output. This is the single source of truth for classification — do not re-run jobs.

**Output: proposed fix plan** is written **before any modification** of project files. The skill never edits, commits, or pushes during diagnosis.

## Step 3: Classify the failure

**@see** `skills/_shared/ci-failure-classifier.md` for the routing table, graceful-degradation rules, and dispatch prompt template. Use that table top-to-bottom; first match wins; multiple distinct matches → parallel fan-out. The shared file is the single source of truth for both `/diagnose-ci` and `/preflight-ci` so updates land once.

## Step 4: Dispatch the specialist

For each matched specialist, invoke via the Task tool:

```
Task(
  subagent_type="pr-review-toolkit:<name>",
  description="Diagnose CI failure on run <run-id>",
  prompt="""
    Failed CI run: <run-id>
    Branch: <branch>
    Failure class: <classification>

    Failed-log excerpt (first 200 lines):
    <log excerpt>

    Diff context (files changed since base):
    <gh pr diff or git diff --stat>

    Read the failed log and the diff. Identify:
    1. Root cause of the failure (one sentence).
    2. The minimal change that fixes it (file:line).
    3. Whether this points to a wider issue in the diff (yes/no + one sentence).

    Do not propose pushes or commits — output is advisory only.
  """
)
```

Multiple matched specialists fan out in parallel — single message, multiple Task tool calls.

## Step 5: Output the proposed fix plan

```markdown
### Diagnosis — run <run-id>

**Branch:** <branch>
**Failure class:** <classification>
**Specialist(s) consulted:** <list>

#### Root cause
<one sentence>

#### Proposed fix
- File: `<path>:<line>`
- Change: <description>
- Wider issue: <yes/no + sentence>

#### Next step
Apply the proposed fix locally, run the relevant local check (`/preflight-ci` mirrors each CI job),
then push. Do NOT push without re-running the local check that mirrors the CI job.
```

## Step 6: User-approval gate

The skill does **not** apply, commit, or push the fix. The user reads the plan and decides:

- "Apply it" → user runs the implementation themselves or re-invokes a fix-applying skill (e.g. `/fix-bug`).
- "Defer" → no action taken; plan stays in conversation context.
- "Wrong" → user redirects; re-dispatch with new prompt.

## Key Rules

- **Diagnosis only.** No `git commit`, `git push`, or `gh pr edit` runs from this skill. The validator (`diagnose_ci_format.py`) enforces this on the Stop hook.
- **Plan output before any modification.** Step 5 fires before any tool call that could change project state.
- **Graceful degradation.** When `pr-review-toolkit` is absent, fall back to log summary; do not error.
- **No re-run of CI.** This skill exists to *avoid* spending more Actions minutes — it never invokes `gh run rerun`.
- **One source of truth.** `gh run view --log-failed` is the only log source; do not stitch from multiple endpoints.

## Gotchas

- `gh run view --log-failed` output is large for matrix builds. If it exceeds ~500 lines, send the specialist the head + tail and a grep for the failure marker, not the full log.
- `gh run list --status failure` returns only completed-with-failure runs. In-progress failing runs need `--status in_progress` + log polling — out of scope here; rerun the skill once the run completes.
- The bot login that posts the codex review may differ from `@codex` — see `/create-pr` Step 6 for the canonical detection. This skill does not read codex output.

---

**Project-specific overrides:** if `SKILL.local.md` exists in this directory, read it — it is consumer-owned, survives framework refresh, and **wins on conflict**. A sidecar that relaxes a gate defined above must state how to prove the gate is wrong in that case. Doctrine: `rules/framework-vs-project-root.md`.
