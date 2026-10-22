# Verification fan-out

> Dispatch blocks for SKILL.md step 6.

If the bug affected UI or critical user flows, fan out an E2E regression pass:

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
