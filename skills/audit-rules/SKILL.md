---
name: audit-rules
description: Audit CLAUDE.md and .claude/rules/*.md for stale, contradictory, or over-prompting rules. Surfaces rules untouched for 6+ months and rules that constrain rather than help on current model capability. Outputs a review report — never modifies governance files directly. Trigger keywords — audit rules, audit governance, review CLAUDE.md, prune rules, stale rules, over-prompting check, BitterPill, BPE.
allowed-tools: Read, Glob, Grep, Bash, Write, TodoWrite
---

## Quick Scan

| | |
|---|---|
| **Purpose** | Surface rules that are stale, redundant, or constrain rather than help the current model. |
| **Inputs** | `CLAUDE.md` (project root) + every file in `.claude/rules/*.md` |
| **Output** | `memories/rules-audit-{YYYY-MM-DD}.md` — categorized findings + recommendations |
| **Mutates** | Nothing. Findings are advisory; user applies them manually. |
| **Flow** | Inventory rules → score each → categorize → write report |

---

# audit-rules Workflow

## When to use

- **Quarterly governance review** — Anthropic's large-codebase post recommends every 3–6 months. Rules that helped older models can constrain newer ones.
- **After a major model upgrade** — old prompts often become dead weight when the underlying model gets smarter.
- **When CLAUDE.md feels bloated** — slow sessions, ignored rules, contradictory guidance.
- **Before a refresh-v3 / framework upgrade** — clear the dead weight first so the refresh doesn't preserve obsolete instructions.

## Invocation

```
/audit-rules                 # Default scope: CLAUDE.md + .claude/rules/*.md
/audit-rules --stale-months 6  # Rules with no git activity in N months get flagged (default 6)
/audit-rules --include-skills  # Also audit .claude/skills/*/SKILL.md frontmatter descriptions
/audit-rules --output PATH     # Custom output path (default: memories/rules-audit-{date}.md)
```

---

## Step 1: Inventory

List every governance file:

```bash
find CLAUDE.md .claude/rules/ -name "*.md" 2>/dev/null
```

For each file, record:
- Path
- Size (lines, characters)
- Last git activity (`git log -1 --format='%ai' -- <file>`)
- Whether it was last touched manually or by a refresh/install script

Build the inventory table — used downstream as the audit's working set.

## Step 2: Score each rule file

For each rule file, evaluate against the five-question test (the same one BitterPillEngineering applies in PAI):

1. **Does the model already do this without being told?**
   _Example: "Always use proper variable names" — modern Claude does this by default; the rule is dead weight._
2. **Does this rule contradict another rule in the same file or elsewhere?**
   _Example: a CLAUDE.md that says "be concise" and a rule file saying "explain every step verbosely".  Pick one._
3. **Is this rule redundant — same instruction stated twice in different words?**
   _Example: "Use Read tool for files" and "Don't use cat for files" — same rule, two surfaces._
4. **Was this rule written for a specific incident that's now resolved?**
   _Example: a rule that says "never use library X" because of a 2024 CVE that was patched in 2025._
5. **Is this rule vague enough that the model can't act on it?**
   _Example: "Write clean code" — no action surface; cut or sharpen with a specific DO/DON'T pair._

A YES to any question is a hit. Multiple hits = stronger recommendation to cut/rewrite.

## Step 3: Categorize

Each rule lands in one of these buckets:

| Verdict | Meaning |
|---|---|
| **KEEP** | Rule is specific, current, non-redundant, and reflects a real constraint or learning the model wouldn't infer. |
| **SHARPEN** | The intent is good but the wording is vague. Rewrite with concrete DO/DON'T or a worked example. |
| **MERGE** | Rule overlaps with another rule. Combine into one canonical statement; delete the others. |
| **CUT** | Rule fails three or more of the five questions, or covers behavior current models do without being told. |
| **MOVE** | Rule is in the wrong file (e.g., a per-skill convention sitting in root CLAUDE.md). Relocate. |

## Step 4: Surface contradictions

Beyond per-rule scoring, run a global pass:

- Does any rule in `.claude/rules/A.md` contradict a rule in `.claude/rules/B.md`?
- Does any rule contradict the project's `ISA.md` constraints?
- Does any rule reference deprecated tooling, retired model IDs, or removed dependencies?

These cross-file findings go in their own report section — they often produce the highest-value edits.

## Step 5: Write the report

Output path: `memories/rules-audit-{YYYY-MM-DD}.md` (or `--output`).

Format:

```markdown
# Rules Audit — {ISO date}

## Inventory

| File | Lines | Last touched | Verdict count |
|---|--:|---|---|
| CLAUDE.md | 312 | 2025-11-12 (6+ months stale) | KEEP: 4 / SHARPEN: 2 / CUT: 1 |
| rules/testing.md | 87 | 2026-04-10 | KEEP: 6 / SHARPEN: 1 |
| ...

## High-priority findings

### CUT
- **CLAUDE.md L42-L46**: rule about manually escaping shell arguments — modern Claude does this by default.
  > Quote the rule verbatim.
- ...

### SHARPEN
- **rules/security.md L18**: "always be careful with secrets" — too vague. Rewrite as DO/DON'T:
  > DO: read secrets from env vars at session start.
  > DON'T: paste a secret value into chat or commit it.
- ...

### MERGE
- **rules/git-workflow.md L9** and **CLAUDE.md L88** both say "create a PR per task". Consolidate in git-workflow.md; cite from CLAUDE.md.

### MOVE
- ...

## Contradictions detected

- **CLAUDE.md L120** says "prefer Bash for git ops" but **rules/git-workflow.md L24** says "use forge.py for all git state changes". Pick one.

## Stale-but-keep notes

Rules that haven't been touched in 6+ months but still pass the five-question test. Listed for awareness, not action.

## Recommended next steps

1. Apply CUT findings (lowest risk, highest token savings)
2. Resolve contradictions (one decision per contradiction)
3. SHARPEN flagged rules in order of how often the session references them
4. MERGE round to consolidate the surface

Estimated rule reduction: N lines (~M tokens per session).
```

## Step 6: Surface and stop

Print a one-paragraph summary to the session: how many findings of each kind, where the report lives, what the user should do next. Then exit. **Never edit CLAUDE.md or rules/ files directly** — the user reviews and applies recommendations on their own schedule.

## When NOT to use

- Right after a `refresh-v3` upgrade. Refresh re-installs framework rules; let them settle for a few sessions before auditing.
- During an active feature or bug session. The audit is a focused activity; don't interleave with implementation work.
- When `.claude/rules/` is empty. The audit needs material; it has nothing to say about a clean install.

## See also

- `skills/refresh-project-context/SKILL.md` — refresh the *content* of CLAUDE.md; this skill audits the *quality* of its rules.
- `skills/audit-code-map/SKILL.md` — pairs naturally: audit the rules, then regenerate the code map so the rules and codebase reality are both fresh.
- Anthropic, "How Claude Code works in large codebases" — the source advice for the 3–6 month config refresh cadence.
