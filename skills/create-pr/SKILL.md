---
name: create-pr
description: Creates pull requests with smart defaults. Infers target branch from branch name, adapts description detail to PR size, runs appropriate checks based on PR type (draft vs final), appends the configured review bot's mention (git config forge.reviewBot) when one is set, and offers a post-create review/merge-order loop for triaging review feedback across multiple open PRs.
hooks:
  Stop:
    - hooks:
        - type: command
          command: "python3 $CLAUDE_PROJECT_DIR/.claude/hooks/validators/skills/create_pr_format.py --final"
---

## Quick Scan

| | |
|---|---|
| **Purpose** | Create PRs with smart defaults + config-aware review-bot mention + post-create monitoring + merge-order guidance |
| **Inputs** | Optional `--draft`, or `review [PR#]`, or `merge-order` |
| **Output** | PR created (with bot mention when configured); or review-feedback triage; or recommended merge sequence |
| **Flow** | Analyze → Target → Checks → **Local review** → Docs → Description → Create → Monitor → Merge-order |

---

## Review bot configuration (detect once per repo)

```bash
git config forge.reviewBot    # e.g. "cc @codex — please review."  (post-PR mention)
git config forge.localReview  # e.g. "codex review --base {base}"  (pre-push gate, Step 3.8)
```

The two are independent and complementary: `localReview` runs the reviewer on your machine before the branch is pushed, `reviewBot` mentions it on the PR afterwards. Setting both is the intended configuration — the local pass absorbs the fix rounds that would otherwise each trigger CI.

- **Set** — the value is the exact mention line. Append it to **every** PR body (draft or final) immediately before the Claude Code attribution, and run the Step 6 review loop against that bot.
- **Unset** — skip the mention entirely; Step 6 falls back to triaging human reviews + CI feedback with the same buckets. Never invent a bot mention on a repo that hasn't configured one.

To enable on a repo with a Codex-style reviewer installed: `git config forge.reviewBot "cc @codex — please review."`

---

## Concision rules (apply to ALL output this skill produces)

These rules govern PR bodies, status reports, merge-order output, and chat messages emitted while this skill runs. Verbose output here bloats both the PR page AND the calling agent's context window when `/status` re-reads recent activity.

- **PR body** — use the shortest template that fits the size (see TEMPLATES.md). Do not upgrade a Small PR to Medium just because there are 3 changes; bullets are cheap, prose is expensive.
- **No analysis prose** — facts only. The diff already shows the code; the body says *what* and *why*, not *how I thought about it*.
- **No restating the diff** — "Added X, modified Y, removed Z" is line-by-line narration; collapse into one sentence of intent.
- **No motivational/justification padding** — drop "This change improves...", "This is important because...", "I went with this approach because..." unless the *why* is genuinely non-obvious from the title.
- **No section headers for empty sections** — if Related Issues is "None", omit the header. If there's no Test Plan because tests are in the diff, omit the header.
- **Bullet caps** — Small: 0 bullets (one sentence only). Medium: ≤5 bullets, ≤12 words each. Large: ≤8 bullets across all categories, ≤15 words each.
- **Chat output to the calling agent** — after PR creation, emit ONLY: PR URL, one-line title, the `/create-pr review <N>` follow-up hint. Do not echo the PR body back into chat. Do not summarize what was created — the URL is the summary.
- **Status reports (Step 6) and merge-order output (Step 7)** — use the compact shapes shown in those sections verbatim; do not add commentary.
- **`gh pr create` body must not contain agent reasoning** — the PR body is read by humans + Codex, not by an agent re-reading its own work. Strip "I noticed", "It looks like", "After investigating".

If in doubt, cut. A reviewer would rather read a 2-line PR with a clear title than a 30-line PR they have to skim.

---

## Untrusted values (apply to EVERY command this skill runs)

Almost every value this skill handles arrives from somewhere that permits shell metacharacters, and most of them end up inside a command:

| Value | Comes from |
|-------|-----------|
| branch name | `git check-ref-format` permits `;`, `$(…)`, backticks, `&&`, `\|` |
| PR title / commit topic | commit messages on the branch — authored by whoever opened the PR |
| review findings | the review bot's output — external text, quoted back into a comment |
| bot mention line | `git config forge.reviewBot`, never validated |

**Never interpolate any of them into a command string.** Two rules cover every case in this skill:

- **Pass values as separate arguments**, never inside a double-quoted string built by concatenation. `gh pr view "$n" --json body` — not `gh pr view $n ...` assembled into one line.
- **Prose goes through a file.** `--body-file` / `--title` reading from a file, never `--body "…<finding>…"`. This is already mandated for `gh pr create` because HEREDOC bodies mangle @-mentions; the same mechanism is what makes bot output inert, so use it everywhere prose flows into a command.

The reason this is easy to get wrong: every ordinary branch name, title and finding works fine. Nothing in normal use ever exposes it, so the omission ships and sits there until the one input that isn't ordinary arrives. Quote and file-pass unconditionally rather than deciding case by case — you cannot tell by looking.

---

# Create PR Workflow

## Invocation

| Form | Purpose |
|------|---------|
| `/create-pr` | Create final PR with full checks |
| `/create-pr --draft` | Create draft PR for early feedback |
| `/create-pr review [PR#]` | Poll open PRs for review feedback, triage, report safe-to-merge or fixes-needed |
| `/create-pr merge-order` | Across all ready-to-merge PRs, output a recommended merge sequence |

`review` and `merge-order` do NOT create PRs — they're follow-up loops.

## Step 1: Analyze

1. Current branch + commits since diverging from base; diff stats (files, lines).
2. PR type: `--draft` flag, or branch/commits containing `wip`/`draft`/`poc`/`WIP` → suggest draft; otherwise final.
3. Size (drives the template — see TEMPLATES.md): Small 1–3 files & <100 lines · Medium 4–10 files & 100–500 · Large 10+ files or 500+. Conflicting signals → the larger size.
4. Present analysis for confirmation.

## Step 2: Determine Target

Infer target from branch name and **confirm with the user** before proceeding:

- `hotfix/*` → latest `release/*` if one exists, else `main`.
- Everything else (`feature/*`, `feat/*`, `fix/*`, `bugfix/*`, `refactor/*`, `docs/*`, `chore/*`, `release/*`, `dependabot/*`, unmatched) → `main`.

Title: `<type>: <description>` with the type prefix from the branch pattern (`feat`, `fix`, `refactor`, `docs`, `chore`; `hotfix/*` → `fix`; otherwise infer from commits). Extract issue refs from branch name (`feature/123-…` → `#123`) and commit keywords (`fixes|closes|resolves #N`) into the body. If the branch isn't on the remote (`git ls-remote --heads origin "<branch>"` — quoted, see Untrusted values), push with `-u` first.

## Step 3: Run Checks

| PR type | Tests | Types | Lint | On fail |
|---------|-------|-------|------|---------|
| Draft | run | skip | skip | proceed with warning, list failures in body |
| Final | must pass | must pass | must pass | **no PR** — fix and retry, downgrade to draft, or abort |

Detect commands from project config (`package.json` scripts, `Makefile` targets, `pyproject.toml` tools, project CLAUDE.md); ask if unclear. Run tests → types → lint, failing fast for final PRs. `--skip-checks` requires explicit confirmation and adds a "created without running checks" note to the PR description.

## Step 3.6: Preflight CI mirror (when `--preflight`)

Step 3 runs generic project checks; this runs the **workflow-derived** matrix — the exact `run:` blocks `.github/workflows/*.yml` declares for PR-trigger jobs. Green preflight ≈ green CI; red preflight saves the Actions minutes.

```bash
python3 .claude/scripts/preflight/preflight.py --project-root . --regenerate
```

| Exit | Behaviour |
|------|-----------|
| 0 (green) | Continue |
| 2 (drift) | Exit with `error: workflow drift — run /preflight-ci --regenerate first` |
| 3 (red) | **Block PR creation.** Per-job summary, route via `skills/_shared/ci-failure-classifier.md`; user fixes or passes `--skip-checks` |
| 4 (degraded) | Warn `preflight degraded — continuing without local mirror`, continue |
| 5 (incomplete) | **Block PR creation.** Coverage did not run — not a green. Two causes, both in the JSON: `jobs_skipped` (job self-skipped, infra absent → tell the user to bring it up with `docker compose up -d` and re-run) and `jobs_incomplete` (job ran but a gating `uses:` step can't be mirrored locally, e.g. the trivy scan — that one only CI can settle, so note it and let the user decide). `--skip-checks` overrides. Deliberately stricter than the pre-push hook, which waves 5 through so an absent local stack never blocks a push — a PR gate is cheap to re-run. |

Opt-in flag because not every project has workflows.

## Step 3.7: Specialist Review (pre-flight fan-out)

Catches review-class issues *before* the push instead of burning CI minutes on fix-and-retry. **CI remains the gate of record** — this is additive.

**Plugin presence check first:**

```bash
python3 -c "import json,sys,os; d=json.load(open(os.path.expanduser('~/.claude/plugins/installed_plugins.json'))); sys.exit(0 if any(k.split('@',1)[0]=='pr-review-toolkit' for k in d.get('plugins',{})) else 1)" 2>/dev/null
```

Matches the plugin by its name-portion regardless of `@marketplace` suffix — the `installed_plugins.json` (schema v2) key is `pr-review-toolkit@claude-plugins-official`, never the bare name, so a `grep '"pr-review-toolkit"'` would never match. Missing file / bad JSON → non-zero exit → treated as absent (safe default).

Plugin absent → **cross-check before trusting it** (agent-verification.md: an "already-correct / nothing-to-do" verdict — which "absent, skip review" is — earns *more* scrutiny). If a `pr-review-toolkit:code-reviewer` agent is actually available, the check is wrong; run the review. Otherwise emit `Specialist review skipped (pr-review-toolkit not installed)` and continue to Step 3.5. **Do not block** — bare installs proceed on Step 3 checks + CI.

**Agent selection** (deterministic — walk once against the changed files, accumulate matches):

| Diff pattern | Specialist (`pr-review-toolkit:` prefix) |
|--------------|------------------------------------------|
| Any code file (always) | `code-reviewer` |
| Test files (`*test*`, `*spec*`, `tests/`, `__tests__/`) | `pr-test-analyzer` |
| New types (`interface`, `type`, `class`, dataclass/Pydantic in diff) | `type-design-analyzer` |
| Error handling (`try/except`, `try/catch`, `.catch(`, `raise`) | `silent-failure-hunter` |
| Comments/docstrings touched | `comment-analyzer` |
| Final pass after MUST-FIX cleared (on request) | `code-simplifier` |

**Fan-out:** single message, multiple Task tool uses — one per matched agent. Each gets the diff + changed-file list and returns findings as `MUST-FIX` (bug, security, broken test, regression) / `NICE-TO-HAVE` (style, naming, small refactor) / `NO-ACTION`. Aggregate into a compact per-agent count table + MUST-FIX detail lines.

**Push gate:** cannot create the PR with unresolved MUST-FIX. Options: fix it (re-run checks + 3.7 on the new diff), defer (file a follow-up via `forge task add`, document in the PR body), or `--proceed-anyway` (override reason recorded in the body's Pre-flight notes). NICE-TO-HAVE → Pre-flight notes section (TEMPLATES.md), doesn't gate. NO-ACTION → dropped.

## Step 3.8: Local review-bot gate (pre-push)

Same idea as 3.7, aimed at the one reviewer that otherwise costs CI minutes to consult. The configured review bot only ever sees the code **after** the PR exists, so every finding it raises is paid for with a full Actions run: fix → push → the whole matrix re-runs → the bot re-scans → repeat. A PR that takes 19 review rounds burns 19 matrices. Running the same reviewer locally, before the branch is pushed, moves that loop off Actions entirely.

**Config (per repo, mirrors `forge.reviewBot`):**

```bash
git config forge.localReview 'codex review --base {base}'
```

`{base}` is substituted with the Step 2 target branch. The value is a full command, so any reviewer CLI works — nothing here is specific to one vendor. **Unset → skip this step silently** and continue to 3.5; bare installs are unaffected.

**Presence check before running:** resolve the command's binary with `command -v`. Absent → emit `Local review skipped (<binary> not on PATH)` and continue. **Never block on a missing reviewer** — same default as 3.7.

**Resolve, then invoke — two steps, never one pipeline:**

1. Read the configured command: `git config forge.localReview`
2. Substitute `{base}` with the Step 2 target branch, **shell-quoted**.
3. Run the resolved command as its own invocation, and show it before you do.

**Quote the branch — this string is executed.** `git check-ref-format` permits
`;`, `$(…)`, backticks, `&&` and `|` in a branch name, so `release/foo;id` is a
legal branch, and substituting it raw appends a second command to whatever the
reviewer was supposed to run. Verified: a branch named `release/foo;touch PWNED`
creates the file when substituted bare, and does not when quoted.

```
--base 'release/foo;touch PWNED'      # inert: one argument
--base release/foo;touch PWNED        # two commands
```

Most branch names need no quoting, which is exactly why this is easy to miss —
you cannot tell by looking at the usual case. Quote unconditionally.

Piping the config value straight into a shell interpreter is the wrong shape and will be blocked outright on any machine running a defensive hook — it is the same pattern as the notorious download-and-execute one-liner, and the text being piped comes from config. `eval` is no better. Resolving first also means the exact command is visible in the transcript before it executes, which is what you want from something whose contents come out of config rather than out of this file.

**Run it in the background.** A review over a real diff takes long enough that a blocking call is a frozen turn of unknown length. Launch it detached (`run_in_background`) and let the harness re-invoke you when it exits — do **not** sit in a polling loop, which burns turns to learn nothing the completion notification would have told you.

The point of running it detached is that it overlaps **Step 3.7**: the specialist fan-out and this review read the same diff and do not depend on each other, so both proceed at once and the gate waits for the pair. That is the whole of the concurrency — see the gate note below.

**Do not edit files while a review is in flight.** The reviewer reads the working tree. Editing underneath it means it reviews a mix of old and new state and reports findings against code that no longer exists — a phantom MUST-FIX that costs more to disprove than the review saved. If a fix cannot wait, kill the review and re-run it after the edit.

Triage the output into the same three buckets as 3.7 and Step 6: **MUST-FIX** / **NICE-TO-HAVE** / **NO-ACTION**. The reviewer emits prose, not structured findings, so this is a judgement call on free text — when a finding's severity is genuinely ambiguous, treat it as MUST-FIX and let the fix or the explicit deferral be the record.

**Push gate:** unresolved MUST-FIX blocks PR creation, exactly as in 3.7. Fix → re-run Step 3 checks → re-run this step on the new diff.

Background execution does **not** relax this. Step 5 must never create the PR while a review is still running — that defeats the gate entirely and leaves you paying for the post-PR rounds this step exists to remove. The concurrency is with 3.7 only; everything after the gate waits.

**Round cap — read this before looping.** Stop after **3** local review rounds and hand back to the user with what is still outstanding. Do not run the reviewer in an unattended loop, and never wire it into a hook or a `/loop`. This is the same failure shape as any LLM CLI invoked in a loop: a subscription meant for interactive use, billed by a process that never gets tired. Three rounds catches the ordinary case; a fourth means the change needs a human read, not another review pass.

**What this does not change:** the `forge.reviewBot` mention still goes in the PR body (Step 5) and Step 6 still runs. The bot gets a second pass over the assembled PR with full context, which the local diff review does not have. The difference is that it should now come back `NO-ACTION` or close to it — one Actions run instead of nineteen.

**Feedback signal:** if Step 6 surfaces a MUST-FIX that this step could have caught on the same diff, say so in the status report. Either the local invocation needs different instructions, or that finding class genuinely needs full-PR context — both worth knowing, and neither is visible unless it is named.

## Step 3.5: Documentation Verification (final PRs only)

Invoke `/refresh-project-context`: README matches new features/config, API docs current, CHANGELOG has Unreleased entries, doc examples still work. Issues found → present list, offer to fix before proceeding.

## Step 4: Generate Description

Use the size-matched template from [TEMPLATES.md](TEMPLATES.md). Concision rules apply.

## Step 5: Create PR

1. Push the branch if needed.
2. **If `forge.reviewBot` is set:** the PR body MUST end with the configured mention line before the Claude Code attribution — draft or final. Create via `gh pr create --body-file` (HEREDOC bodies sometimes mangle @-mentions), then verify post-create: `gh pr view <N> --json body --jq .body | grep -qF -- "$(git config forge.reviewBot)" || echo MISSING`. If missing, fix immediately via `gh pr edit --body-file`.
3. **If unset:** create via `gh pr create --body-file` with no bot mention.
4. Present the PR URL + the `/create-pr review <N>` follow-up hint (bot-configured repos: feedback usually lands in 2–10 min).

## Step 6: Review Loop (`/create-pr review [PR#]`)

Post-create monitoring: is this PR (or every open PR) safe to merge?

1. **Targets:** `<PR#>` if given, else all open PRs authored by the user.
2. **Fetch per PR:** `gh pr view <N> --json number,title,headRefName,reviewDecision,mergeable,mergeStateStatus,statusCheckRollup,reviews,comments` + `gh api repos/{owner}/{repo}/pulls/<N>/comments` (inline comments).
3. **Feedback source:** with `forge.reviewBot` set, look for that bot's actor (verify the actual bot login on first run — e.g. `chatgpt-codex-connector[bot]`; it may differ from the mention handle). Without a bot, triage human review comments + failing CI checks from `statusCheckRollup` — same buckets, same loop.
4. **Triage every finding:** **MUST-FIX** (actual bug, security gap, broken test, regression) / **NICE-TO-HAVE** (style, naming, docstring, small refactor) / **NO-ACTION** (nothing found, or acknowledgment only).
5. **For each MUST-FIX:** `gh pr checkout <N>` → apply fix → re-run Step 3 checks → **re-run Step 3.7 specialists on the fix diff** (`git diff` of the fix commit — same fan-out, same MUST-FIX push gate) → commit `fix(review): address review feedback on <topic> (PR #<N>)` → push. **Same PR number — never close-and-recreate.** Then comment via `gh pr comment <N> --body-file <file>` — write the body (`Addressed in <sha>:`, one line per finding, then the bot mention line if configured, whose re-mention retriggers the re-scan) to a file first. **Never `--body "…"`**: those lines quote review-bot output straight back into a command. For human reviewers, request re-review via `gh pr edit --add-reviewer` or the comment.

   **Why re-run 3.7 here:** the fix itself is unreviewed code. A review bot (Codex et al.) re-scans every commit, so it catches regressions the fix introduced — a misleading comment, an orphaned route, a guard that broke a sibling. If the framework's own specialists only run once at the *original* 3.7 and then go silent through the whole review phase, every self-inflicted fix bug is left for the bot to find, which is exactly the round-trip this loop exists to avoid. Re-running 3.7 on the fix diff closes the seam: catch your own regressions with your own tooling before the bot has to. Skip only when the fix is a pure revert or a one-line typo with no runtime surface.
6. **NICE-TO-HAVE:** apply if cheap, else defer to a follow-up task; note the deferral in a PR comment.
7. **Status report (always emit, one line per PR, no prose):**

   ```
   PR #<N> <title> — review:<status> ci:<status> | MUST:<n> NICE:<n> NO:<n> | <verdict>
   ```

   Verdicts: `safe-to-merge` / `re-review-pending` / `blocked`. Expand to per-finding detail only when MUST > 0 and the user asks.
8. **Wait condition:** bot configured but silent after ~2 min → suggest `/loop 5m /create-pr review <N>` (where the host Claude Code ships /loop) or a one-shot scheduled wakeup. No bot → CI status + human review state is the answer now; no waiting.

If a security finding surfaces in review, re-review the fix before re-requesting:

```
Use the Task tool:
- subagent_type: "security-boss"
- description: "Re-review <PR#> fix for the flagged security finding"
- prompt: |
    PR: <#>. Finding: <quote>. Fix commit: <hash>. Files: <list>.
    Re-review the fix against the finding: mitigation correct and complete,
    no new attack surface. Defer to reference/03 + reference/08.
    Output feeds the comment that re-requests review.
```

## Step 7: Multi-PR Merge Order (`/create-pr merge-order`)

1. Gather open PRs with verdict `safe-to-merge` from Step 6.
2. File-overlap matrix: `gh pr diff <N> --name-only` per PR, intersect pairs — overlap means the later PR rebases after the earlier merges.
3. Score: risk band (infra/docs low < backend non-runtime med < backend runtime/security/migration high ≈ frontend behavior high), prefer smaller diffs first, flag deploy-affecting changes (migrations, routes) for a separate window.
4. Output — one line per PR in merge order; append Deploy/Conflict lines only if non-empty:

   ```
   Merge order:
   1. PR #X — <title> — risk:low +N/-M
   2. PR #Y — <title> — risk:med +N/-M — rebase after #X

   Conflicts: PR #Y ↔ PR #Z on <file>
   ```

5. **Never auto-merge.** Hand the order to the user.

## Key Rules

- Always confirm target branch before creating.
- Never create a final PR with failing checks (offer draft instead).
- Review-bot mention is config-driven: `forge.reviewBot` set → its line on every PR body, verified post-create; unset → no mention, Step 6 triages human + CI feedback.
- **Consult the review bot locally BEFORE pushing** (`forge.localReview`, Step 3.8). Its post-PR findings cost a full Actions run each; its pre-push findings cost nothing. Capped at 3 rounds, never unattended, never in a hook or `/loop`.
- After review feedback, push fixes to the SAME PR (never close-and-recreate); re-mention the bot in a comment to retrigger its review.
- Always include the Claude Code attribution; extract and link related issues.
- For multi-PR sequences, present a merge order; never auto-merge without explicit instruction.

## Learned Preferences

- **2026-07-16 — Poll ALL THREE codex surfaces, not just issue-comments.** Codex
  (`chatgpt-codex-connector[bot]`, match `'codex' in login` case-insensitively)
  files findings across three endpoints in the same PR: top-level issue-comments
  (`issues/{n}/comments`), formal reviews (`pulls/{n}/reviews`, sometimes
  `state:COMMENTED` with an EMPTY body), AND inline review comments
  (`pulls/{n}/comments`, with P-badges). A poll that checks only one endpoint will
  miss a real P2 (happened this session — the finding was under inline comments
  while the top-level comment list was empty). Fetch all three.
- **2026-07-16 — On re-push, codex re-anchors an old inline finding's line# AND
  `commit_id` to the new head commit** — so the stale P2 and the fresh "clean"
  verdict can both show the same commit/line. Sort by `created_at` and read the
  NEWEST entry for the current verdict; do not judge by line proximity or commit id.

---

**Project-specific overrides:** if `SKILL.local.md` exists in this directory, read it — it is consumer-owned, survives framework refresh, and **wins on conflict**. A sidecar that relaxes a gate defined above must state how to prove the gate is wrong in that case. Doctrine: `rules/framework-vs-project-root.md`.
