---
name: setup-review-bot
description: Configure this repo's AI code reviewers — the post-PR mention bot and the pre-push local reviewer — and write the AGENTS.md the reviewers read. Interviews the user for what the reviewer should weight, then sets git config forge.reviewBot / forge.localReview and populates AGENTS.md at the project root. Use when a repo has no reviewer configured, when review findings are consistently off-target, or when onboarding a new project.
---

## Quick Scan

| | |
|---|---|
| **Purpose** | Wire up review bots and give them repo-specific direction |
| **Inputs** | None — interviews the user |
| **Output** | `git config forge.reviewBot` / `forge.localReview` + a populated `AGENTS.md` |
| **Flow** | Detect what's already set → choose reviewers → interview → write config → write AGENTS.md |

---

# /setup-review-bot

## Why this exists

Two reviewers run against a PR, at different moments and different cost:

- **Pre-push** (`forge.localReview`, create-pr Step 3.8) — runs on your machine before the branch exists remotely. Findings here cost nothing.
- **Post-PR** (`forge.reviewBot`) — mentioned in the PR body, reviews the assembled PR. Every finding it raises costs a CI run to fix, because the fix pushes a commit.

Both read `AGENTS.md` from the repo root. A reviewer without it applies a generic severity model to a codebase with specific rules, which is how you get confident findings about deliberate decisions and silence about the thing that actually matters. The interview below exists to make that file worth reading.

## Step 1: Detect current state

```bash
git config forge.reviewBot     # post-PR mention line, e.g. "cc @codex — please review."
git config forge.localReview   # pre-push command, e.g. "codex review --base {base}"
test -f AGENTS.md && echo "AGENTS.md present" || echo "AGENTS.md absent"
```

Report what is already configured before asking anything — if all three are set, say so and ask whether the user wants to revise `AGENTS.md` rather than starting from scratch.

## Step 2: Choose the reviewers

Ask which reviewer this repo uses. Nothing here is vendor-specific: `forge.reviewBot` is a free-text mention line and `forge.localReview` is a command template, so any reviewer that has a GitHub handle, a CLI, or both fits.

For a CLI reviewer, confirm the binary resolves (`command -v <binary>`) before writing the config — a command that isn't installed turns Step 3.8 into a silent skip, which reads as "the gate passed".

**The `{base}` placeholder** is substituted with the target branch, shell-quoted. **Do not add a prompt argument to the command** — with codex-cli, `--base <BRANCH>` and a prompt are mutually exclusive, and the error's own usage line advertises the combination it refuses. Review direction goes in `AGENTS.md`, which is the point of this skill.

## Step 3: Interview for AGENTS.md

Four questions, each aimed at something a reviewer cannot infer from the code. Ask them one at a time and keep the answers concrete — a vague answer here produces a file that changes nothing.

1. **Which documents are authoritative?** When the code and a doc disagree, which wins? A reviewer that doesn't know this argues from the wrong source.
2. **What counts as MUST-FIX in this repo?** Not "bugs" — the specific failure classes that matter here. "A write path that can drop a record without erroring" is useful; "correctness issues" is not.
3. **What should it skip?** Generated files, vendored code, a module mid-rewrite, a convention that looks wrong and isn't. Include *why*, or the next review re-reports it.
4. **Which conventions differ from the obvious default?** Anything the code alone would teach wrongly — the deliberate pattern a reviewer would otherwise flag as a mistake.

If the user has nothing for a section, leave its heading with a comment rather than inventing content. An empty section is honest; a fabricated one sends the reviewer after things nobody cares about.

## Step 4: Write the config

```bash
git config forge.reviewBot   "<mention line>"
git config forge.localReview "<command with {base}>"
```

Repo-local by design — different projects use different reviewers, and these values ride with the repo rather than the machine.

## Step 5: Write AGENTS.md

`AGENTS.md` lives at the **project root**, not under `.claude/`. It is project data: a framework refresh never overwrites it (`rules/framework-vs-project-root.md`).

- **Absent** → create it from `templates/AGENTS.template.md`, with the interview answers filled in.
- **Present** → never overwrite. Show the user the sections you would add and append only what is missing. An existing `AGENTS.md` is often hand-written and load-bearing for a cloud reviewer already.

Commit it — it is shared direction, not personal configuration. That is the whole advantage over passing a prompt on the command line: it is versioned, reviewed with the code, and steers the cloud review too.

## Step 6: Report

```
reviewers: post-PR <handle or none> · pre-push <command or none>
AGENTS.md: <created | appended N sections | unchanged>
next: /create-pr runs the pre-push review at Step 3.8
```

## Key rules

- **Never overwrite an existing `AGENTS.md`.** Append, or show and ask.
- **Never invent repo direction.** An unanswered section stays a comment; fabricated guidance is worse than none, because it is followed.
- **Never add a prompt argument to `forge.localReview`.** It conflicts with `--base`, and `AGENTS.md` is the supported channel.
- **Verify the CLI exists** before writing `forge.localReview`, so a missing binary fails loudly at setup rather than silently at the gate.

---

**Project-specific overrides:** if `SKILL.local.md` exists in this directory, read it — it is consumer-owned, survives framework refresh, and **wins on conflict**. A sidecar that relaxes a gate defined above must state how to prove the gate is wrong in that case. Doctrine: `rules/framework-vs-project-root.md`.
