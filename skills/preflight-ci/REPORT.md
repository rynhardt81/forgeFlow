# Preflight CI — Report, Skips and Incomplete Jobs

The Step 6 report format and how self-skipped and hollowed (`INCOMPLETE`) jobs are reported. Exit codes and the consumer contract are in SKILL.md.

## Contents

- Report format
- Self-skipped jobs
- Hollowed jobs (`INCOMPLETE`)

## Report format

```markdown
### Preflight summary

**Branch:** <branch>
**Jobs run:** <count> (<duration>)
**Result:** ✅ all green · safe to push    | ❌ <N> failed
**Drift:** <none | <files>>

#### Per-job
- ✅ typecheck (3.2s)
- ❌ test (8.1s)
- ⏭️ lint (skipped — fail-fast)
- ⏭️ test (0.04s) — SKIPPED
     postgres not reachable (compose stack down) — …

#### Specialist diagnosis (only when red)
<output from the matched pr-review-toolkit specialist>
```

## Self-skipped jobs

Distinct from the fail-fast skip above (a job never *started* because an earlier
one failed). A **self-skip** is a job that ran, found its infra dependency
absent, announced `SKIP: <reason>` on stderr and exited 0 — the pg-reachability
guard is the built-in case.

Exit 0 is deliberate: an absent local stack must not block a push, and CI runs
the real thing. But exit 0 alone is indistinguishable from a pass, so the runner
detects the marker and reports it explicitly:

- `--quick` → `⚠️  preflight: 1 job(s) DID NOT RUN (test); 3 passed` — never
  "✓ … green", because this is the line that scrolls past during `git push`.
- full → the `⏭️ … — SKIPPED` block above, and the summary line becomes
  `✓ no gating job failed — but 1 SKIPPED (test); that coverage did NOT run`.
  **The "safe to push" line is withheld whenever anything skipped.**
- `--json` → `jobs_skipped: ["test"]`, plus `skip_reason` on each job entry.
- **exit code `5`**, not `0` — the machine consumers (the pre-push hook,
  `/create-pr --preflight`) read only the exit code, so folding this into `0`
  would leave them seeing the plain green this mechanism exists to remove.

Consumers differ deliberately: the **pre-push hook waves `5` through** with a
warning (an absent local stack must not block a push, and CI still runs
the job), while **`/create-pr` blocks on it** (a PR gate is cheap to re-run).

To actually run a skipped job, bring its dependency up (`docker compose up -d`)
and re-run.

The marker is `FORGE_SKIP: `, namespaced so it cannot collide with the ordinary
`SKIP:`/`SKIPPED` chatter that third-party tools write to stderr.

## Hollowed jobs (`INCOMPLETE`)

The sibling case. `uses:` steps can't be mirrored locally, so they're emitted as
inert comments — usually harmless, because most of them are `actions/checkout`
or `setup-python`. But when a job's *actual gating work* is a `uses:` step, the
job still runs its `run:` steps, exits 0, and reports a clean green having
proved nothing. `image-scan` built two Docker images and scanned neither.

A job is reported `INCOMPLETE` when a dropped `uses:` step is **not** on
`LOCALLY_INERT_ACTIONS` (`script_generator.py`). That list is a **denylist of
inert actions**, not an allowlist of dangerous ones, so an unrecognised action
counts as lost work — over-warning is recoverable, under-warning is the bug.
Inert means it prepares the environment (checkout, toolchain setup, cache,
buildx) or ships results *out* of CI (artifact/coverage upload). Anything that
brings data *in* that later steps consume, or performs the check itself, is not.

```
⚠️  image-scan  (6.8s) — INCOMPLETE
   2 gating step(s) cannot run locally; CI still runs them:
     · Scan Control Plane image (aquasecurity/trivy-action)
     · Scan Portal image (aquasecurity/trivy-action)
```

Same exit code `5` and the same consumer contract as a self-skip — both mean
"green overstates what was proved". `--json` exposes `jobs_incomplete` plus
per-job `dropped_steps`. Classification reads the generated script's existing
`# Skipped step:` comments, so it needs no regeneration to take effect.
