---
name: preflight-ci
description: Mirrors GitHub Actions CI locally before push. Derives gating jobs from `.github/workflows/*.yml`, generates committed bash scripts at `.forge/preflight/<job>.sh`, executes them, and routes failures to the same `pr-review-toolkit` specialists `/diagnose-ci` uses. Proactive twin of `/diagnose-ci` — exists to keep failing pushes from burning Actions minutes. Local execution only — never pushes, commits, or invokes `gh run rerun`. Use when about to push or open a PR on a repo with GitHub Actions workflows, or after changing a workflow (`--regenerate`). NOT FOR diagnosing a CI run that already failed (/diagnose-ci).
---

# /preflight-ci

Runs the gating-CI matrix locally before push to spare Actions minutes. The mirror is **workflow-derived, not hand-maintained**: whatever `.github/workflows/*.yml` declares as `run:` steps for PR-trigger jobs runs locally, and drift between workflow and mirror is detected. Flow: derive gating jobs → generate scripts → drift-check → execute → route failures → report.

## Index

| File or section | Read when… |
|-----------------|------------|
| `GENERATION.md` | Why this exists; Step 2 — script shape, refused steps, project shims, Compose port/password rewrites and `.env` discovery, `pyproject.toml` overrides, step `if:` translation, gotchas |
| `REPORT.md` | Step 6 — report template; how self-skipped and `INCOMPLETE` jobs are shown in `--quick`, full and `--json` output |
| `_shared/ci-failure-classifier.md` | Step 5 — classifying a red job and the specialist dispatch prompt |
| Exit codes (below) | A caller needs to act on the result |

## Exit codes

| Code | Meaning |
|------|---------|
| `0` | All green; safe to push |
| `2` | Drift detected; refused to execute stale scripts |
| `3` | At least one gating job failed |
| `4` | Degraded (no workflows, `pr-review-toolkit` missing, etc.) |
| `5` | Nothing failed, but a job self-skipped or ran without a gating `uses:` step — that coverage did NOT run locally |

`5` is never folded into `0`: machine consumers read only the exit code. The **pre-push hook waves `5` through** with a warning (an absent local stack must not block a push; CI still runs the job); **`/create-pr --preflight` blocks on it** (a PR gate is cheap to re-run).

## Security: this runs the checked-out branch's shell

> **Running `/preflight-ci` on a branch you did not author is a code-execution path.** A `run:` step is arbitrary shell, executed on your machine with your `.env` files exported.

Refused destructive steps are a text filter, not a sandbox, and `CI`/`GITHUB_ACTIONS` guards inside a `run:` body are not a control (the workflow sets them). Before running on someone else's branch, read `git diff origin/main -- .github/workflows/` — that is the whole attack surface. Detail: GENERATION.md.

## Invocation

| Form | Behaviour |
|------|-----------|
| `/preflight-ci` | Run the gating matrix against the current working tree |
| `/preflight-ci --regenerate` | Re-derive scripts from workflows (run after a workflow change) |
| `/preflight-ci --only typecheck` | Run a single named job |
| `/preflight-ci --with-act` | (Opt-in, future) execute via `act` instead of scripted parity |
| `/preflight-ci --quick` | Terse output mode used by the pre-push hook |
| `/preflight-ci --keep-going` | Run all jobs even after the first failure |

## Step 1: Locate gating jobs

Read `.github/workflows/*.yml`. Keep workflows whose `on:` declares `pull_request` targeting the default branch.

If the repo has GitHub branch-protection rules (`gh api repos/:owner/:repo/branches/<default>/protection` returns required-check names), narrow the gating job list to that intersection. If `gh` is absent, unauthenticated, or returns 404, fall back to the full PR-trigger job set — no protection rules required.

Output (under the hood, not surfaced to user by default): `.forge/preflight/gating-jobs.json`.

## Step 2: Generate or refresh local scripts

For each gating job, write `.forge/preflight/<job>.sh` (banner, env exports, one block per `run:` step; shape in GENERATION.md). `uses:` steps are emitted as `# Skipped step:` comments — scripted parity does not emulate composite actions. A `drift.lock` with the SHA-256 of each workflow file is written alongside. These files **are committed** for diff-reviewability.

- **Refused steps (gate):** a step whose `run:` body holds a workstation-destructive command (volume prune, compose `down` with volumes, recursive delete of `/`) is not written at all, and the **whole job is skipped** — its script emits `FORGE_SKIP: job not mirrored locally — …` and exits 0, so it reports SKIPPED, never a pass. Steps CI never runs (`if: false`, untranslatable conditions) are excluded from this scan.
- **Project shims:** every script sources `_local_shims.sh` (ships empty; idempotent project-local portability helpers). It survives `install.sh --mode refresh` and `--regenerate`: the generator seeds it only when absent and never overwrites a copy that differs. Commit it.
- **Compose-aware rewrites:** CI `localhost` ports and empty `*_PASSWORD` defaults are rewritten to match the local Compose stack, and every discovered `.env` layer is sourced. Discovery order and `[tool.forge.preflight]` overrides: GENERATION.md.
- **Step `if:` conditions:** `always()`/`failure()` keep GHA semantics; change-detection gates run anyway; anything mentioning `github.` or `false` is **not emitted** (table: GENERATION.md).
- **Templates:** `${{ secrets|env|vars|inputs.X }}` become `${X:-}`; export them locally before running.

## Step 3: Drift check

Compute SHA-256 of each `.github/workflows/*.yml` and compare against `drift.lock`. On any change (new, modified, removed workflow), emit:

```
⚠️ Preflight drift detected — local scripts are stale
   changed: ci.yml
   run: /preflight-ci --regenerate
```

Exit code 2. Refuses to execute stale scripts unless `--regenerate` was passed. First run (no `drift.lock`) writes scripts + lockfile, then executes.

## Step 4: Execute

For each gating job (or just `--only <name>`), run `bash .forge/preflight/<job>.sh` from project root. Capture stdout/stderr per job. Stop at first failure unless `--keep-going` is set.

## Step 5: Route failures

For any red job, classify the stderr tail against `skills/_shared/ci-failure-classifier.md` and dispatch the matching `pr-review-toolkit` specialist via the Task tool. Use the shared dispatch prompt template from that file.

**Graceful degradation**: if `pr-review-toolkit` is not installed, fall back to printing the first 80 lines of the failing job's stderr and exit non-zero (4 — degraded).

## Step 6: Report

Per-job ✅/❌/⏭️ summary with branch, job count, duration and drift; specialist diagnosis appended when red (template: REPORT.md).

- **Self-skipped job** — ran, found its infra absent, printed `FORGE_SKIP: <reason>` and exited 0. Reported as SKIPPED, never green; **the "safe to push" line is withheld whenever anything skipped**; exit `5`. To actually run it, bring the dependency up (`docker compose up -d`) and re-run.
- **Hollowed job (`INCOMPLETE`)** — its `run:` steps passed but a dropped `uses:` step is not on `LOCALLY_INERT_ACTIONS` (`script_generator.py`; a denylist of inert actions, so an unknown action counts as lost work). Exit `5`.

## Integration points

| Caller | How it invokes |
|--------|----------------|
| Direct (user) | `/preflight-ci` in any chat — runs against current branch |
| `/create-pr` | Step 3.6 (when `--preflight` flag is on) — runs preflight before specialist diff-review |
| Pre-push hook | `.git/hooks/pre-push` — runs only when a locked in-progress task has `preflight_required: true` |

## Pre-push hook lifecycle

| Command | Behaviour |
|---------|-----------|
| `forge preflight enable-git-hook` | Install `.git/hooks/pre-push` (idempotent; refuses to clobber a non-Forge hook unless `--force`) |
| `forge preflight disable-git-hook` | Remove the Forge hook if present (idempotent; refuses to remove a non-Forge hook) |

The hook is installed by default during `install.sh --mode refresh-v3`. It reads `forge task ls --in-progress --json`; no in-progress task → preflight runs as the safe default; every in-progress task `preflight_required: false` → exits 0 silently. Tasks declare it at creation: `forge task add … --preflight {auto|required|skip}` (auto: any non-doc scope path → required). Bypass: `FORGE_SKIP_PREFLIGHT=1 git push` (rare, for emergencies).

## Key rules

- **No pushes.** This skill never invokes `git push`, `gh run rerun`, `gh pr create`, or `gh pr edit`. It runs CI locally and reports. The user decides what to push.
- **Running this on a branch you did not author executes that branch's shell.** Read the workflow diff first — `git diff origin/main -- .github/workflows/`.
- **Workflow files are source of truth.** No hand-maintained mirror config; drift between `.github/workflows/` and `.forge/preflight/` is detected.
- **Shared classifier with `/diagnose-ci`.** Failure routing lives in `skills/_shared/ci-failure-classifier.md`. Both skills `@see` it; neither embeds its own copy.
- **Generated scripts are committed.** `.forge/preflight/*.sh` lives in the repo so the parity layer is diff-reviewable.
- **Hook is opt-out per task, not per repo.** Tasks declare `preflight_required` at creation; doc-only commits push silently.
- **Green is "very likely green on CI", not guaranteed** — `uses:` steps don't mirror and macOS/Ubuntu tooling differs (GENERATION.md → Gotchas).

---

**Project-specific overrides:** if `SKILL.local.md` exists in this directory, read it — it is consumer-owned, survives framework refresh, and **wins on conflict**. A sidecar that relaxes a gate defined above must state how to prove the gate is wrong in that case. Doctrine: `rules/framework-vs-project-root.md`.
