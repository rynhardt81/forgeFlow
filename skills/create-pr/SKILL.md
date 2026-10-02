---
name: create-pr
description: Creates pull requests with smart defaults. Infers target branch from branch name, adapts description detail to PR size, runs appropriate checks based on PR type (draft vs final), appends the configured review bot's mention (git config forge.reviewBot) when one is set, and offers a post-create review/merge-order loop for triaging review feedback across multiple open PRs. Use when shipping a branch as a PR, triaging review feedback on open PRs (`review`), or sequencing several ready PRs (`merge-order`).
hooks:
  Stop:
    - hooks:
        - type: command
          command: "python3 $CLAUDE_PROJECT_DIR/.claude/hooks/validators/skills/create_pr_format.py --final"
---

# Create PR Workflow

Opens a PR behind pre-push gates, then triages review feedback. Flow: Analyze → Target → Checks → **Pre-push gates** → Docs → Description → Create → Monitor → Merge-order.

## Index

| File or section | Read when… |
|-----------------|------------|
| `TEMPLATES.md` | Step 4 — PR body templates, size thresholds, Pre-flight notes |
| `GATES.md` | Review-bot setup; Step 3.7 plugin check + specialist table; Step 3.8 mechanics and rationale |
| `REVIEW.md` | Steps 6–7 — fetch commands, Codex endpoints, security re-review, merge-order procedure |
| `_shared/ci-failure-classifier.md` | Step 3.6 exits 3 — routing failures |
| `_shared/task-triage.md` | Deferring a finding as a follow-up task |

## Review bot configuration

`git config forge.reviewBot` (post-PR mention line) and `forge.localReview` (Step 3.8 command); set both ideally (GATES.md).

- **Set** — append the exact line to **every** PR body (draft or final) just before the Claude Code attribution; Step 6 reviews against that bot.
- **Unset** — no mention (never invent one); Step 6 triages human reviews + CI with the same buckets.

## Output rules

- **PR body** — shortest template that fits the size (TEMPLATES.md).
- **Chat output** — ONLY the PR URL, title, and `/create-pr review <N>` hint. Never echo the body.

## Untrusted values (every command)

Branch names (`git check-ref-format` permits `;`, `$(…)`, `&&`), commit topics, review findings and the `forge.reviewBot` line may hold shell metacharacters. **Never interpolate them into a command string.**

- **Pass values as separate arguments** (`gh pr view "$n" --json body`), never concatenated into one command string.
- **Prose goes through a file** (`--body-file`), never `--body "…<finding>…"` — it makes bot output inert and keeps @-mentions intact.

## Invocation

`/create-pr` (final PR, full checks) · `--draft` (draft PR) · `--preflight` (adds Step 3.6) · `review [PR#]` (triage review feedback, Step 6) · `merge-order` (merge sequence, Step 7). `review` and `merge-order` do NOT create PRs.

## Step 1: Analyze

Branch, commits since base, diff stats; PR type (`--draft`, or `wip`/`draft`/`poc` in branch/commits → suggest draft); size Small/Medium/Large (thresholds in TEMPLATES.md; conflicting signals → larger). Present for confirmation.

## Step 2: Determine Target

Infer target from branch name and **confirm with the user** before proceeding: `hotfix/*` → latest `release/*` if one exists, else `main`; everything else → `main`.

Title `<type>: <description>`, type from the branch prefix (`hotfix/*` → `fix`; else infer from commits). Link issue refs from the branch name (`feature/123-…` → `#123`) and `fixes|closes|resolves #N` commits. Branch not on remote (`git ls-remote --heads origin "<branch>"`, quoted) → push with `-u`.

## Step 3: Run Checks

| PR type | Tests | Types | Lint | On fail |
|---------|-------|-------|------|---------|
| Draft | run | skip | skip | proceed with warning, list failures in body |
| Final | must pass | must pass | must pass | **no PR** — fix, downgrade to draft, or abort |

Detect commands from project config; ask if unclear. Tests → types → lint, fail fast for final PRs. `--skip-checks` needs explicit confirmation and adds a "created without running checks" note.

## Step 3.6: Preflight CI mirror (when `--preflight`)

Runs the exact `run:` blocks of the PR-trigger jobs in `.github/workflows/*.yml` (`/preflight-ci`).

```bash
python3 .claude/scripts/preflight/preflight.py --project-root . --regenerate
```

| Exit | Behaviour |
|------|-----------|
| 0 (green) | Continue |
| 2 (drift) | Exit with `error: workflow drift — run /preflight-ci --regenerate first` |
| 3 (red) | **Block PR creation.** Per-job summary, route via `_shared/ci-failure-classifier.md`; user fixes or passes `--skip-checks` |
| 4 (degraded) | Warn `preflight degraded — continuing without local mirror`, continue |
| 5 (incomplete) | **Block PR creation.** Coverage did not run: `jobs_skipped` (infra absent → `docker compose up -d`, re-run) or `jobs_incomplete` (gating `uses:` step only CI can run — user decides). `--skip-checks` overrides. Stricter than the pre-push hook on purpose. |

## Step 3.7: Specialist Review (pre-flight fan-out)

**CI remains the gate of record.** Check `pr-review-toolkit` is installed (GATES.md). Absent → cross-check first (a skip verdict earns *more* scrutiny): if `pr-review-toolkit:code-reviewer` is available, run it. Else emit `Specialist review skipped (pr-review-toolkit not installed)` and continue — **do not block**.

Select specialists from the diff (table: GATES.md; `code-reviewer` always), fan out in one message. An `Intent:` line in the task body adds a compliance question — a diff that misses the intent's outcome or constraints is `MUST-FIX`. Buckets: `MUST-FIX` / `NICE-TO-HAVE` / `NO-ACTION`.

**Push gate:** unresolved MUST-FIX blocks PR creation. Fix (re-run checks + 3.7), defer (`forge task add` after applying `_shared/task-triage.md` — default `--epic E99`; schema/auth/money/security never deferred), or `--proceed-anyway` (reason in Pre-flight notes). NICE-TO-HAVE → Pre-flight notes, no gate.

## Step 3.8: Local review-bot gate (pre-push)

Runs `forge.localReview` (e.g. `codex review --base {base}`) before the push, so findings don't each cost an Actions run. **Unset → skip silently.** Mechanics: GATES.md.

- **Presence:** binary not on PATH (`command -v`) → emit `Local review skipped (<binary> not on PATH)`, continue. **Never block on a missing reviewer.**
- **No prompt argument:** `--base` cannot be used with a `[PROMPT]` argument (codex-cli 0.144.1); put review guidance in `AGENTS.md` at the repo root instead.
- **Resolve, then invoke — two steps, never one pipeline:** read `git config forge.localReview`; substitute `{base}` with the Step 2 target branch, **shell-quoted** (`git check-ref-format` permits `;`, `$(…)` and `&&` in branch names, so an unquoted branch can append a second command); show it, then run it as its own invocation — never piped to a shell or `eval`.
- **Run it in the background** (`run_in_background`) alongside 3.7; no polling. **Do not edit files while a review is in flight** — kill and re-run instead.
- Triage as in 3.7; ambiguous severity → MUST-FIX.
- **Push gate:** unresolved MUST-FIX blocks PR creation, exactly as in 3.7. Fix → re-run Step 3 checks → re-run this step. Background execution does **not** relax this: never create the PR while a review is still running.
- **Round cap:** stop after **3** local review rounds and hand back to the user. Never run it unattended, in a hook, or in a `/loop`.

## Step 3.9: Documentation Verification (final PRs only)

Invoke `/refresh-project-context` (README, API docs, CHANGELOG Unreleased, doc examples). Issues → present, offer to fix.

## Step 4: Generate Description

Size-matched template from TEMPLATES.md; see Output rules.

## Step 5: Create PR

1. Push the branch if needed.
2. **If `forge.reviewBot` is set:** the body MUST end with its line before the attribution. Create via `gh pr create --body-file`, then verify: `gh pr view <N> --json body --jq .body | grep -qF -- "$(git config forge.reviewBot)" || echo MISSING`. Missing → `gh pr edit --body-file`.
3. **If unset:** create via `gh pr create --body-file` with no bot mention.
4. Present the PR URL + the `/create-pr review <N>` hint.

## Step 6: Review Loop (`/create-pr review [PR#]`)

1. **Targets:** `<PR#>`, else all the user's open PRs. Fetch reviews, comments, inline comments, CI (REVIEW.md).
2. **Triage:** **MUST-FIX** (bug, security, broken test, regression) / **NICE-TO-HAVE** (style, small refactor) / **NO-ACTION**.
3. **Each MUST-FIX:** `gh pr checkout <N>` → fix → Step 3 checks → **re-run Step 3.7 on the fix diff** (skip only for a pure revert/typo) → commit `fix(review): address review feedback on <topic> (PR #<N>)` → push. **Same PR — never close-and-recreate.** Comment via `gh pr comment <N> --body-file <file>` (`Addressed in <sha>:` per finding, then the bot line); **never `--body "…"`**. Security finding → `security-boss` re-review first (REVIEW.md).
4. **NICE-TO-HAVE:** apply if cheap, else defer and note it in a PR comment.
5. **Status report (always emit, one line per PR, no prose):** `PR #<N> <title> — review:<status> ci:<status> | MUST:<n> NICE:<n> NO:<n> | <verdict>`. Verdicts: `safe-to-merge` / `re-review-pending` / `blocked`.
6. **Wait condition:** bot silent after ~2 min → suggest a `/loop` or scheduled wakeup (REVIEW.md). No bot → no waiting.

## Step 7: Multi-PR Merge Order (`/create-pr merge-order`)

Order `safe-to-merge` PRs by file overlap, risk and size (REVIEW.md). **Never auto-merge.**

## Key Rules

- Always confirm target branch before creating.
- Never create a final PR with failing checks (offer draft instead).
- Consult the review bot locally BEFORE pushing (Step 3.8): max 3 rounds, never unattended.
- Review fixes go to the SAME PR; re-mention the bot to retrigger review.
- Always include the Claude Code attribution. Never auto-merge.

---

**Project-specific overrides:** if `SKILL.local.md` exists in this directory, read it — it is consumer-owned, survives framework refresh, and **wins on conflict**. A sidecar that relaxes a gate defined above must state how to prove the gate is wrong in that case. Doctrine: `rules/framework-vs-project-root.md`.
