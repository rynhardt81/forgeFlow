# PR Description Templates

## Size Detection

| Size | Files Changed | Lines Changed |
|------|---------------|---------------|
| Small | 1-3 | <100 |
| Medium | 4-10 | 100-500 |
| Large | 10+ | 500+ |

If files and lines suggest different sizes, use the larger size.

---

> **REVIEW-BOT LINE (config-aware):** when `git config forge.reviewBot` is set, every template ends with its configured mention line (e.g. `cc @codex — please review.`) BEFORE the Claude Code attribution — draft PRs included; this triggers the bot's review on PR open. When unset, omit the `[review-bot line]` placeholder entirely.
>
> **CONCISION:** see SKILL.md → Concision rules. Use the shortest template that fits. Omit any section whose content would be "None" or restated diff. Bullet caps are hard.

## Small PR Template

```markdown
[One sentence describing the change — title line covers the rest.]

[review-bot line — only if forge.reviewBot is set]

---
🤖 Generated with [Claude Code](https://claude.com/claude-code)
```

---

## Medium PR Template

```markdown
## Summary
[1-2 sentences — what changed and why. No restating the diff.]

## Changes
- [≤5 bullets, ≤12 words each]

[Optional — include ONLY if non-empty: ## Related Issues with closes #N lines]

[review-bot line — only if forge.reviewBot is set]

---
🤖 Generated with [Claude Code](https://claude.com/claude-code)
```

---

## Large PR Template

```markdown
## Summary
[2-3 sentences — purpose and scope. No prose padding.]

## Changes
- [≤8 bullets total across categories, ≤15 words each. Group with `### Category` headers only when ≥3 bullets in a category.]

## Test Plan
- [ ] [Concrete verification step]
- [ ] [Concrete verification step]

[Optional — include ONLY if non-empty: ## Related Issues]
[Optional — include ONLY if breaking change, migration required, or specific risk area: ## Notes for Reviewers — one paragraph max]

[review-bot line — only if forge.reviewBot is set. Append " Focus: <risk area>." ONLY if the PR has a specific risk area worth flagging.]

---
🤖 Generated with [Claude Code](https://claude.com/claude-code)
```

---

## Draft Prefix

Prepend to any template when creating a draft PR:

```markdown
> ⚠️ **Draft PR** - Work in progress, not ready for merge.
> Looking for feedback on: [specific area or question]

```

---

## Pre-flight notes

When `/create-pr` Step 3.7 surfaces NICE-TO-HAVE findings (or a `--proceed-anyway` override on MUST-FIX), capture them in the PR description as a `## Pre-flight notes` section, inserted immediately above the review-bot line (or above the attribution when no bot is configured).

```markdown
## Pre-flight notes

Specialist review (pr-review-toolkit):
- [code-reviewer] `path/to/file.ts:42` — naming inconsistency, deferred (low risk)
- [pr-test-analyzer] `tests/auth.test.ts:18` — edge case missing, follow-up T### opened

<!-- include this block ONLY if --proceed-anyway was used -->
**Override:** MUST-FIX bypassed via `--proceed-anyway`. Reason: <user-supplied reason>.
```

If Step 3.7 found nothing actionable (all `NO-ACTION`), omit the section entirely. The review-bot line (when configured) still goes at the very end of the PR body, before the attribution.

---

## Content Generation Rules

**Summary:** Analyze commit messages and diff to describe the overall change.

**Changes list:** Group by:
- Feature/component affected
- Type of change (add, modify, remove)

**Test plan:** For each significant change, describe how to verify it works.

**Related issues:** Extract from branch name and commit messages.

**Notes for reviewers:** Include if:
- Breaking changes exist
- Migration required
- Specific areas need careful review
