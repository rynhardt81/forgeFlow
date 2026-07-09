# 00-documentation-governance.md

**Documentation Governance & Source-of-Truth Contract**

> **Audience:** Claude Code, architects, senior engineers
> **Authority:** **Highest** – governs *all* documentation
> **Purpose:** Define how documentation is created, updated, referenced, and trusted

---

## 1. Purpose

This document defines the **governance rules** for all documentation in this repository: what documents are authoritative, how they may be created or modified, how supporting documentation is processed and referenced, and how Claude and humans resolve conflicts.

**This is the highest-authority documentation file.** All other documents must comply with it.

---

## 2. Documentation Authority Model — four tiers

| Tier | Documents | Role |
|------|-----------|------|
| **Tier 1 — Governance** | `00-documentation-governance.md` (this document) | Rules for how docs work; highest authority |
| **Tier 2 — Master Source-of-Truth** | `01-system-overview.md`, `02-architecture-and-tech-stack.md`, `03-security-auth-and-access.md`, `04-development-standards-and-structure.md`, `05-operational-and-lifecycle.md`, `06-architecture-decisions.md`, `07-non-functional-requirements.md`, `08-security-model.md`, `09-autonomous-development.md` | Define the authoritative truth of the system |
| **Tier 3 — Processed Supporting** | `docs/processed/` | Evidence and background; read-only; must be explicitly referenced by master documents |
| **Tier 4 — Execution & Raw** | `CLAUDE.md`, `.claude/*`, inline comments, notes, drafts | Guide execution; do **not** define truth |

---

## 3. Master Document Rules

All master documents (01–09) must:

* Follow this governance file
* Declare their **scope and non-goals**
* Avoid duplicating content from other master documents
* Reference supporting documents instead of embedding them
* Remain concise and stable

Master documents are living documents, but changes must be intentional, traceable, and consistent with declared scope.

---

## 4. Docs Folder Processing Rules

### `docs/` (active source pool)

Contains unprocessed documentation, eligible for use.

### `docs/processed/` (evidence archive)

Contains documentation already used. Must **not** be re-processed automatically; may only be consulted when explicitly referenced. Organized by category (e.g. `architecture/`, `business/`, `operations/`).

### Processing rules

When a document is used by a master document:

1. Relevant sections are extracted
2. The document path and sections are recorded in the master document's reference table
3. The document is moved to `docs/processed/` (preserving folder structure)
4. The master document references it explicitly using the format below

Unused or obsolete documents in `docs/` are flagged for review and may be removed after user confirmation.

### Reference format standard

```markdown
| Source Document | Sections Used | Summary |
|-----------------|---------------|---------|
| `architecture/system-overview.md` | §2, §3.1 | High-level components, key characteristics |
```

* Path is relative to `docs/processed/`
* Sections identify specific headings or numbered sections used
* Summary is a brief (5–15 word) description of extracted content
* The same processed doc MAY be referenced by multiple master documents — each master records only the sections IT uses; no content is duplicated between masters. The processed doc is the shared detailed drill-down.

---

## 5. Modification & Evolution Rules

Claude **is allowed** to read, append to, and modify master documents.

Claude **must not**:

* Delete master documents
* Change a document's authority level
* Remove governance constraints
* Rewrite intent without explicit justification

All modifications must stay within declared scope, preserve intent unless explicitly superseded, and be traceable (what changed and why).

### Change workflow

```
1. Write detailed documentation in docs/ (active source pool)
2. Identify affected master documents (which 01-09 docs need updates)
3. Extract relevant content to the masters, within their declared scope
4. Move the detailed doc to docs/processed/{category}/
5. Update the master's reference table with the sections used
```

Typical triggers: new feature (detailed doc → extract to masters), architecture change (update 02, possibly 06/ADR), security change (update 03/08), new operational procedure (update 05), performance work (update 07), bug fix with design impact (relevant master + 06 if a decision was made).

### Version bumping (naming convention)

When master documents are updated:

* **Patch** (x.x.1): clarifications, typo fixes, reference updates
* **Minor** (x.1.0): new sections, expanded content, new references
* **Major** (1.0.0): structural changes, scope changes, breaking updates

---

## 6. Conflict Resolution

When conflicts arise, precedence is:

1. `00-documentation-governance.md` wins
2. Relevant master document wins
3. Referenced processed documentation wins
4. Execution guidance (`CLAUDE.md`) loses

If conflicts exist **between** master documents, they must be recorded in `06-architecture-decisions.md` or explicitly resolved with user input.

---

## 7. Final Statement

This governance model ensures documentation remains authoritative and coherent, architectural knowledge is preserved, Claude can safely evolve documentation, and humans and AI share a single source of truth.

**All documentation work begins here.**
