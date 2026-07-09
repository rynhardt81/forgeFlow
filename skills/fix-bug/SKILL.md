---
name: fix-bug
description: Disciplined bug fixing — reproduce first, root-cause before fix, regression test always. Includes a production-incident fast path and a debug-doc artifact for gnarly bugs. Hands off to /create-pr. Use when fixing any bug, error, or test failure.
hooks:
  Stop:
    - hooks:
        - type: command
          command: "python3 $CLAUDE_PROJECT_DIR/.claude/hooks/validators/skills/fix_bug_regression.py --final"
---

# Fix Bug

`/fix-bug <description>` — an error message, failing test name, or symptom.

If the superpowers plugin is installed, its systematic-debugging skill governs the investigation; otherwise follow the inline discipline below. Either way the two hard gates — reproduce-first and regression-test — are non-negotiable. (The prod fast path below defines exactly one permitted deferral shape for the regression test; nothing waives it.)

## 1. Memory check

If `docs/project-memory/bugs.md` exists, grep it for keywords from the bug description. Surface any prior art ("we hit this class of bug before, root cause was X") before investigating. Skip silently if the file doesn't exist.

## 2. Reproduce FIRST (Algorithm Gate A)

Capture the failure **before any Read/Grep targets the suspect code path**. A bug you can't reproduce is a bug you can't verify fixed.

| Symptom | Required reproduction |
|---------|----------------------|
| Web/UI bug | Browser screenshot or network trace |
| HTTP failure | `curl -i` showing the broken response |
| CLI failure | Actual stdout/stderr |
| Test failure | The failing test output |
| Data inconsistency | `SELECT` showing the wrong value |

Note whether it's consistent or intermittent. **Confirm with the user here** — "Reproduced: triggers when [X]. Proceed to root-cause?" This is the first of only two confirmation stops.

If reproduction is genuinely impossible (prod-only race, third-party outage), say so explicitly and agree on the closest proxy probe before continuing — never skip silently.

## 3. Root cause before fix

- Form the plausible hypotheses; test the cheapest-to-check first (targeted logging, a debugger, a scratch test). Record what each probe ruled out.
- **Root-cause-at-ingestion:** ask where the bad state *enters* the system. Fixing at the ingestion point kills the whole bug class; patching the output side masks it. For UI bugs, trace display-down (correct), not database-up.
- Do not touch the fix until the root cause is confirmed by evidence, not by plausibility.
- A fix that swallows the error instead of surfacing it is not a fix (`rules/error-handling.md` — surface, don't hide).

## 4. Fix + regression test

- Smallest fix that addresses the confirmed root cause. No scope creep, no drive-by refactoring — file follow-ups instead.
- **Regression test required:** a test that fails without the fix and passes with it, asserting on the failure path from step 2. The Stop-hook validator (`fix_bug_regression.py`) checks for it.

## 5. Verify

- Re-run the step-2 reproduction probe — the original failure must now pass, shown with actual output.
- Run the related test suite; no new failures.
- If the bug affected UI or critical user flows, fan out an E2E regression pass:

```
Use the Task tool:
- subagent_type: "quality-engineer"
- description: "E2E regression for <bug>"
- prompt: |
    Bug: <one-line summary>. Regression test (now passing): <path::name>.
    UI flows touched: <list>. Run E2E scoped to those flows; capture
    screenshots/traces for failures; distinguish flaky from real.
```

For security-related bugs, have a review of the fix before shipping:

```
Use the Task tool:
- subagent_type: "security-boss"
- description: "Security review of <bug> fix"
- prompt: |
    Bug: <summary>. Fix commit: <hash>. Files: <list>.
    Review the fix for completeness and new attack surface.
```

## Production incident fast path

When the bug is live in production (outage, data corruption, all-users breakage), compress the flow — speed over ceremony, but never skip verification:

1. Branch `hotfix/<slug>` from the deployed tag/branch.
2. Assess blast radius; if rollback or a feature flag mitigates faster than a fix, do that first.
3. Minimal diff — the smallest change that stops the bleeding.
4. Verify with a live probe against the affected environment (the step-2 table applies).
5. The regression test ships in the hotfix PR when it can be written quickly (the reproduction from step 4 usually IS the test). If shipping speed genuinely can't wait, file the follow-up task via `forge task add` BEFORE merging and name it in the PR body — an unfiled deferral is a dropped gate, not a fast path.
6. Ship, then note the backport to main in the PR body. Deep root-causing lands in the same follow-up task.

For full incident handling (stabilize → postmortem → prevention tasks), use `/triage-incident`.

## Debug doc (gnarly bugs only)

When the investigation outlives a couple of hypotheses or spans sessions, keep a running artifact at `docs/debug/<slug>.md` so context survives compaction and handoffs:

```markdown
# Debug: <title>          Status: In Progress | Resolved
## Error          <exact output>
## Reproduction   <steps, consistent/intermittent, environment>
## Hypotheses     <each with probe + confirmed/ruled-out + evidence>
## Root cause     <confirmed cause>
## Fix            <files, change, regression test>
## Verification   <probe output showing resolution>
```

Update it as you go; reference it from the commit/PR. Skip it for quick fixes.

## 6. Ship

**Confirm with the user before opening the PR** (second and last confirmation stop): fix summary, files touched, regression test name.

Commit as `fix: <description>`, then invoke `Skill("create-pr")`. Never use raw `gh pr create` — it bypasses the pre-flight review gates. If the user explicitly wants no PR, stop after the commit.

If the bug pattern is novel and worth remembering, offer `/remember bug "<title>"`.

## Rules

- Reproduce before reading suspect code; verify with the same probe after fixing.
- Root cause confirmed by evidence before any fix lands.
- Regression test always; it asserts on the failure path, not just the happy path.
- Fix only this bug — discovered work becomes follow-up tasks.
- Confirm with the user at exactly two points: reproduction confirmed, and before the PR.
