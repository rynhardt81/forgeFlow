# PR Description Templates

> The Summary / Evidence / Merge Danger shape is adapted from mattpocock/skills `pr` (MIT), itself credited to HumanLayer's `show-me` skill (MIT) — see `THIRD-PARTY-NOTICES.md`.

## Contents

- Title and issue links
- Size Detection
- Small / Medium / Large PR Template
- Summary visuals
- Evidence and Merge Danger
- Draft Prefix
- Pre-flight notes
- Content Generation Rules

## Title and issue links

Title `<type>: <description>`, type from the branch prefix (`hotfix/*` → `fix`; else infer from commits). Link issue refs from the branch name (`feature/123-…` → `#123`) and `fixes|closes|resolves #N` commits.

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
> **CONCISION:** see SKILL.md → Output rules. Use the shortest template that fits; readers are reviewers and the review bot, who want what changed and why, not the diff restated. Omit any section whose content would be "None" or restated diff.

## Small PR Template

```markdown
[One sentence describing the change — title line covers the rest.]

**Door:** [one-way | two-way] · **Blast radius:** [one word]

[review-bot line — only if forge.reviewBot is set]

---
🤖 Generated with [Claude Code](https://claude.com/claude-code)
```

---

## Medium PR Template

```markdown
## Summary
[The smallest visual that makes the key point clear (see Summary visuals), plus one line on why. No restating the diff.]

## Changes
- [One bullet per reviewable change, each a single short line — a reviewer scans this list before opening the diff]

## Evidence
- **Before:** [screenshot / output / failing test run]
  **After:** [screenshot / output / passing test run]

## Merge Danger
**Door:** [one-way | two-way] · **Blast Radius:** [one word]

[Optional — include ONLY if non-empty: ## Related Issues with closes #N lines]

[review-bot line — only if forge.reviewBot is set]

---
🤖 Generated with [Claude Code](https://claude.com/claude-code)
```

---

## Large PR Template

```markdown
## Summary
[The smallest visual (or two) that shows purpose and scope, for a reviewer deciding where to look first — see Summary visuals. No prose padding.]

## Changes
- [One bullet per reviewable change, each a single short line. Group under `### Category` headers when a category holds several bullets.]

## Evidence
- **Before:** [screenshot / output / failing test run]
  **After:** [screenshot / output / passing test run]
- [Repeat per significant change. Anything not yet verified is a `- [ ]` step a reviewer can run.]

## Merge Danger
**Door:** [one-way | two-way]

[optional: why — destructive actions, data or schema changes, hard-to-reverse decisions]

**Blast Radius:** [one-word description]

[optional: potential ramifications of merge]

[Optional — include ONLY if non-empty: ## Related Issues]
[Optional — include ONLY if breaking change, migration required, or specific risk area: ## Notes for Reviewers — only what a reviewer must know before approving]

[review-bot line — only if forge.reviewBot is set. Append " Focus: <risk area>." ONLY if the PR has a specific risk area worth flagging.]

---
🤖 Generated with [Claude Code](https://claude.com/claude-code)
```

---

## Summary visuals

Pick the smallest view that makes the key point clear. Skip preambles and keep prose brief; name things in the project's glossary terms (`GLOSSARY.md`).

- Logic or an algorithm → pseudocode:

```text
on(save)
  if content is unchanged
    return cached result
  write new content
  return fresh result
```

- Runtime control flow → a call tree:

```text
submitForm
  createSession
    persistPrompt
    launchAgent
  navigateToSession
```

- UI structure → a component tree, including state and module boundaries that matter:

```text
<SessionPage> (apps/example/src/routes/session.tsx)
  useSessionEvents()
  <SessionToolbar>
    <RunSkillButton> (packages/ui)
```

- File responsibility or a broad refactor → a shallow file tree:

```text
src/
├── commands/       # parses user actions
├── sessions/       # owns session state
└── transport/      # sends API requests
```

- Component interaction, control flow, or data flow → Mermaid (a `sequenceDiagram` or `flowchart`).

- What changes, when the surrounding shape already exists → a `diff`, shaped to the topic (component tree, file layout, call tree, or state/control flow):

```diff
 submitForm
   createSession
     persistPrompt
+    expandSkillMention
     launchAgent
-  navigateToSession
+  navigateToSession
+    subscribeToEvents
```

- The whole block, when most of it is new, when omitted context would hide ownership or order, or when the reader needs a copyable target shape.

Place each visual next to the short text it supports. Keep only the calls, files, props, states, and boundaries needed to make the point. You may use one of these, you may use several; it is unlikely you will use all of them.

---

## Evidence and Merge Danger

**Evidence** is concrete proof the change works: a before and an after. Screenshots are S-tier — when the environment is set up for it and the change is visual. Execution-based evidence is A-tier: test results, console output. Show the exact test that now fails-then-passes, using pseudocode where the full test is noise.

**Merge Danger** says whether the PR is a one-way or two-way door. You can walk back through two-way doors, but not one-way doors. A PR that is cheap to roll back is lower risk. Changes that involve destructive actions or hard-to-reverse decisions — schema migrations, data deletion, published releases, external sends — are one-way doors. The **blast radius** is the potential impact or scope of the change: consider all possibilities — layout shift, breakages for consumers, mobile responsiveness, CI, other projects that vendor this one.

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

Specialist review (pr-review-toolkit) and the two axes:
- [code-reviewer] `path/to/file.ts:42` — naming inconsistency, deferred (low risk)
- [pr-test-analyzer] `tests/auth.test.ts:18` — edge case missing, follow-up T### opened
- [standards] `src/pricing.ts:88` — possible Feature Envy (judgement call), deferred
- [spec] scope creep: retry wrapper not asked for by T###, kept (two-way door)

<!-- include this block ONLY if --proceed-anyway was used -->
**Override:** MUST-FIX bypassed via `--proceed-anyway`. Reason: <user-supplied reason>.
```

If Step 3.7 found nothing actionable (all `NO-ACTION`), omit the section entirely. The review-bot line (when configured) still goes at the very end of the PR body, before the attribution.

---

## Content Generation Rules

**Changes list:** Group by:
- Feature/component affected
- Type of change (add, modify, remove)

**Evidence:** For each significant change, the before/after that proves it works; anything unverified becomes a checklist step.

**Merge Danger:** Every Medium/Large PR states its door and blast radius; Small PRs carry the one-line version.

**Related issues:** as in *Title and issue links* above.

**Notes for reviewers:** Include if:
- Breaking changes exist
- Migration required
- Specific areas need careful review
