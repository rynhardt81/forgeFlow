# Create PR — Review Loop and Merge Order Detail

Detail for `/create-pr review` (Step 6) and `/create-pr merge-order` (Step 7). The step sequence, triage buckets and gates are in SKILL.md.

## Step 6: fetch, feedback source, wait condition

- **Fetch per PR:** `gh pr view <N> --json number,title,headRefName,reviewDecision,mergeable,mergeStateStatus,statusCheckRollup,reviews,comments` + `gh api repos/{owner}/{repo}/pulls/<N>/comments` (inline comments).
- **Feedback source:** with `forge.reviewBot` set, look for that bot's actor (verify the actual bot login on first run — e.g. `chatgpt-codex-connector[bot]`; it may differ from the mention handle). Without a bot, triage human review comments + failing CI checks from `statusCheckRollup` — same buckets, same loop.
- **Wait condition:** bot configured but silent after ~2 min → suggest `/loop 5m /create-pr review <N>` (where the host Claude Code ships /loop) or a one-shot scheduled wakeup. No bot → CI status + human review state is the answer now; no waiting.

## Why re-run 3.7 on the fix diff

The fix itself is unreviewed code. A review bot (Codex et al.) re-scans every commit, so it catches regressions the fix introduced — a misleading comment, an orphaned route, a guard that broke a sibling. If the framework's own specialists only run once at the *original* 3.7 and then go silent through the whole review phase, every self-inflicted fix bug is left for the bot to find, which is exactly the round-trip this loop exists to avoid. Re-running 3.7 on the fix diff closes the seam: catch your own regressions with your own tooling before the bot has to. Skip only when the fix is a pure revert or a one-line typo with no runtime surface.

## Security re-review

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

## Step 7: Multi-PR merge order

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

## Gotchas

- **Codex findings arrive on three endpoints — poll all of them.** The bot
  (`chatgpt-codex-connector[bot]`; match `'codex' in login`, case-insensitive)
  posts to issue-comments (`issues/{n}/comments`), formal reviews
  (`pulls/{n}/reviews`, sometimes `state:COMMENTED` with an empty body), and inline
  review comments (`pulls/{n}/comments`, with P-badges). A finding can sit in one
  while the others are empty.
- **On re-push, codex re-anchors old inline findings to the new head** (line and
  `commit_id`), so a stale finding and a fresh clean verdict can share a commit and
  line. Read the newest entry by `created_at` for the current verdict.
