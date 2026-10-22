# Production incident fast path

> The compressed flow SKILL.md routes to when the bug is live in production. The gates in SKILL.md still apply.

When the bug is live in production (outage, data corruption, all-users breakage), compress the flow — speed over ceremony, but never skip verification:

1. Branch `hotfix/<slug>` from the deployed tag/branch.
2. Assess blast radius; if rollback or a feature flag mitigates faster than a fix, do that first.
3. Minimal diff — the smallest change that stops the bleeding.
4. Verify with a live probe against the affected environment (step 2's evidence applies).
5. The regression test ships in the hotfix PR when it can be written quickly (the reproduction from step 4 usually IS the test). If shipping speed genuinely can't wait, file the follow-up task via `forge task add` BEFORE merging and name it in the PR body — an unfiled deferral is a dropped gate, not a fast path. **Before filing, apply `skills/_shared/task-triage.md`** — Deferred is the default (`--epic E99`); hard floors (schema/auth/money/security) are never deferred.
6. Ship, then note the backport to main in the PR body. Deep root-causing lands in the same follow-up task.

For full incident handling (stabilize → postmortem → prevention tasks), use `/triage-incident`.
