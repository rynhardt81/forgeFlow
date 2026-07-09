---
name: refresh-project-context
description: Updates CLAUDE.md project sections while keeping it lean. Adds detailed content to CHEATSHEET.md. Use after framework upgrades, when project context has drifted, or when the user says "update project docs", "refresh context", "CLAUDE.md is outdated", or "sync documentation".
allowed-tools: Read, Write, Edit, Bash, Glob, Grep, Task, TodoWrite, AskUserQuestion
---

## Quick Scan

| | |
|---|---|
| **Purpose** | Refresh CLAUDE.md project context (keep lean, defer to CHEATSHEET) |
| **Inputs** | Existing codebase, optional flags (--quick, --prd, --full) |
| **Output** | Filled `## Project context` skeleton in root CLAUDE.md (lean), updated CHEATSHEET.md (detailed) |
| **Flow** | Analyze → Fill the root CLAUDE.md project-context skeleton (lean) → Update CHEATSHEET.md (detailed) |

---

# Refresh Project Context Skill

> **CRITICAL PRINCIPLE:** Keep CLAUDE.md LEAN (~100 lines max for framework content).
> Add detailed reference content to CHEATSHEET.md instead.

---

## Key Principles

1. **CLAUDE.md = Index** - Minimal framework instructions + project overview
2. **CHEATSHEET.md = Reference** - All detailed tables, examples, workflows
3. **On-demand loading** - Reference files in `.claude/reference/` not inlined
4. **Token optimization** - Every line in CLAUDE.md costs context window

## Invocation

```
/refresh-project-context           # Update project sections in CLAUDE.md
/refresh-project-context --quick   # CLAUDE.md project sections only
/refresh-project-context --prd     # Include PRD update
/refresh-project-context --full    # Full refresh with @project-manager re-interview
```

---

## Phase 1: Analyze Current Project State

### 1.1 Discover Project Structure

Check for:
- `package.json`, `requirements.txt`, `go.mod`, `Cargo.toml`
- Project structure (src/, app/, lib/)
- Available commands (npm scripts, Makefile targets)

### 1.2 Read Current Files

Read:
- `CLAUDE.md` - current project sections
- `CHEATSHEET.md` - current reference content
- Dependency files for tech stack

### 1.3 Present Findings

Show discovered vs documented state. Confirm before updating.

---

## Phase 2: Fill the root CLAUDE.md "Project context" skeleton (KEEP LEAN)

`install.sh --mode refresh-v3` scaffolds an empty **project-context** skeleton in
the consumer's **root** `CLAUDE.md` (below the `<!-- forge-flow:framework-import -->`
import, under a `<!-- forge-flow:project-context -->` sentinel). This skill's job
is to **populate that exact skeleton** — never to invent a parallel section. Write
to the headers below verbatim; do NOT create a `## PROJECT OVERVIEW` or any other
heading, or you'll leave the real skeleton empty beside a duplicate.

### 2.1 Target — the canonical project-context section

The skeleton (in the root `CLAUDE.md`) is exactly:

```markdown
<!-- forge-flow:project-context -->
## Project context

### Identity
### Why it exists
### Architecture (deviations only)
### Version quirks & pins
### Global invariants & anti-patterns
### See also
```

Locate the `<!-- forge-flow:project-context -->` sentinel and edit the headers
underneath it in place (replace the `<!-- ... -->` placeholder comment in each
section with real content). If the sentinel is absent (older install, or a
project that pre-dates the scaffold), the user should re-run the refresh first —
or insert the skeleton manually before filling it.

### 2.2 What goes in each header — LEAN, document only the non-inferable

Keep every section to **1–3 lines**. The rule (same as the skeleton's own
guidance): **document only what Claude cannot infer from the code.** Depth lives
in Tier-2, not here.

| Header | Content | Length |
|--------|---------|--------|
| **Identity** | One line: what the project is, plain terms. | 1 line |
| **Why it exists** | The problem it solves / value delivered — the strategic *why*, not visible in code. | 2–3 lines |
| **Architecture (deviations only)** | ONLY the parts that depart from convention. Skip anything a reader infers from structure. Often empty — that's fine. | 0–3 lines |
| **Version quirks & pins** | "This library version behaves this way / is real, don't reinvent it." Tribal knowledge (e.g. a framework's new middleware file Claude would otherwise deny exists). | 0–4 lines |
| **Global invariants & anti-patterns** | Verifiable hard rules: "never bypass `getOrCreateX`", "all auth errors route through Y", "parameterize all SQL". | 0–5 lines |
| **See also** | Pointer line(s): `- Full intent & architecture: .claude/reference/01-system-overview.md` and `- CHEATSHEET.md` for command/agent tables. | 1–2 lines |

### 2.3 DO NOT

- Do NOT create `## PROJECT OVERVIEW` or any heading outside the skeleton.
- Do NOT duplicate full intent prose that belongs in `reference/01-system-overview.md` — summarize + point.
- Do NOT add verbose examples, full routing tables, detailed workflows, or code snippets (those go in CHEATSHEET.md).
- Do NOT overwrite a section the user has already filled with real content unless they ask — only replace remaining `<!-- ... -->` placeholders by default.

### 2.4 Link to references (the See also line)

The `### See also` header must point at the authoritative sources rather than
inline them:
- `.claude/reference/01-system-overview.md` — full intent & architecture (Tier-2 source-of-truth)
- `CHEATSHEET.md` — full command/agent tables and examples

---

## Phase 3: Update CHEATSHEET.md

Move any detailed content to CHEATSHEET.md:
- Full command list with examples
- Full agent list with descriptions
- Full best practices list
- Detailed workflows
- Session protocol steps

---

## Phase 4: Documentation Audit (Optional)

If not `--quick`:

```
Self-perform (this skill IS the v3 documentation audit; v2 used a `@doc-updater` agent which was cut). Focus:

1. Framework files in `.claude/reference/` (NOT docs/)
2. Task registry at `docs/tasks/registry.json`
3. Project memory at `docs/project-memory/`

Note: Architecture and development docs are in `.claude/reference/`, not `docs/`.
```

---

## Phase 5: Summary

Append to `.claude/memories/progress-notes.md`:

```markdown
## Project Context Refresh - [DATE]

- CLAUDE.md: Filled root `## Project context` skeleton (kept lean)
- CHEATSHEET.md: Added detailed references
- Framework alignment verified
```

---

## Error Handling

| Issue | Action |
|-------|--------|
| No CLAUDE.md | Run `/new-project --current` |
| No `<!-- forge-flow:project-context -->` sentinel in root CLAUDE.md | Re-run `install.sh --mode refresh-v3` to scaffold the skeleton, then fill it |
| CLAUDE.md bloated (>150 lines) | Move content to CHEATSHEET.md |
| Missing `.claude/reference/` | Framework not initialized properly |

---

## Key Paths (Framework)

| Type | Location |
|------|----------|
| Reference docs | `.claude/reference/` |
| Rules | `.claude/rules/` |
| Agents | `.claude/agents/` |
| Sessions | `.claude/memories/sessions/` |
| Tasks | `docs/tasks/registry.json` |
| Project memory | `docs/project-memory/` |

**Note:** Architecture, development standards, and framework docs are in `.claude/reference/`, NOT in a separate `docs/` directory.
