---
name: triage-incident
description: Production incident triage — from "something is broken for users" to fixed, verified, and learned-from. Pulls the error signal (Sentry/logs/user report), reproduces before touching code, routes the fix through /fix-bug's prod fast path, and closes with a postmortem entry. Trigger phrases — production is down, users are reporting, crash spike, incident, Sentry alert, it broke in prod. NOT FOR bugs found in development (use /fix-bug directly) or CI failures (use /diagnose-ci).
---

## Quick Scan

| | |
|---|---|
| **Purpose** | Structured path from production incident to verified fix + recorded learning |
| **Inputs** | An error signal: Sentry issue, log excerpt, user report, crash-rate alert |
| **Output** | Fix shipped via prod fast path + postmortem entry + follow-up tasks filed |
| **Flow** | Assess → Stabilize → Reproduce → Fix → Verify in prod → Postmortem |

# Triage Incident

## Step 1: Assess — how bad, how many, since when

Pull the actual signal before theorizing:
- **Sentry available:** issue frequency, first-seen, affected-user count, release tag, stack trace. First-seen aligned with a release/flag flip is your prime suspect.
- **No Sentry:** platform logs (Supabase logs, store vitals/ANR dashboard, server logs) — get ONE concrete failing event with a timestamp.
- Severity call: data loss or security exposure → **stop, stabilize first** (Step 2 now); degraded-but-safe → normal flow.

## Step 2: Stabilize — stop the bleeding before root-causing

Fastest reversible mitigation FIRST when users are actively harmed:
- Last release suspect → roll back (`rules/release-engineering.md` — the rollback command you verified at release time)
- Flag-flip suspect → flip it back
- Runaway job / abusive traffic → pause the job / rate-limit

Record what you did and when — it's the first postmortem timeline entry. If mitigation isn't possible, say so and continue; do not silently skip.

## Step 3: Reproduce — Gate A applies, prod edition

No fix until the failure is captured (ALGORITHM REPRODUCE-FIRST): the failing request as `curl -i`, the `SELECT` showing bad state, the crash reproduced on a local build pointed at staging. If truly unreproducible, capture the full evidence chain (trace + logs + affected rows) and treat the hypothesis as unconfirmed — the fix must then include instrumentation that would confirm it.

## Step 4: Fix — hand off to `/fix-bug` prod fast path

Minimal-diff hotfix shipped via `/create-pr` — regression test in the same PR when it can be written quickly, otherwise filed as a forge task before merge and named in the PR body (the fast path's one permitted deferral shape). Schema involved → Gate E (`rules/migrations.md`). Security involved → `/security-review` on the fix before shipping.

## Step 5: Verify in production

The incident is not over when the fix merges — probe the live surface: the failing request now succeeds (`curl -i`), Sentry issue stops accruing new events on the fixed release, crash-free rate recovers. Name the number you watched and what it showed.

## Step 6: Postmortem — small, honest, filed

Write `docs/debug/incident-YYYY-MM-DD-<slug>.md` (≤1 page): timeline, impact (users × duration), root cause, why it wasn't caught earlier, what prevents the class (not just the instance). Then:
- `/remember bug "<one-line root cause>"` → project memory
- File prevention follow-ups as real tasks: `python3 .claude/scripts/forge/forge.py task add ...`
- If the root cause implicates doctrine (a gate that should have fired), surface it — that's a `doctrine` learning per ALGORITHM LEARN.

## Key Rules

- Mitigate before root-causing when users are actively harmed — but never call mitigation the fix.
- No fix without reproduction or an explicitly-marked unconfirmed hypothesis + instrumentation.
- Production verification is a probe, not a deploy log.
- Every incident produces exactly one postmortem file and ≥0 prevention tasks — an incident with zero learnings is a claim, not an outcome.
