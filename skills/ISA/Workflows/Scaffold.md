# Workflow: Scaffold

> Generate a fresh ISA from a one-line prompt + tier. Idempotent — refuses to clobber an existing ISA at the target path.

## Inputs

| Input | Required | Default |
|-------|----------|---------|
| `prompt` | yes | — one-sentence description of the task or project |
| `tier` | yes | — E3 / E4 (E2 gets an inline checklist in the reply, not a document; E1 gets nothing) |
| `path` | no | inferred (project root → `<project>/ISA.md`; task ID present → `docs/tasks/<id>/ISA.md`) |
| `mode` | no | `interactive` (pause for clarifications) or `autonomous` (sensible defaults) |

## Steps

### 1. Refuse to clobber

If the target ISA exists, **stop**. Offer: (a) extend it via another workflow, (b) overwrite with explicit confirmation, (c) different path. Never silently overwrite.

### 2. Resolve target path

Explicit `--path` → task ID in prompt/environment → project root → else fail with a path-required error. Create parent directories as needed.

### 3. Detect project context

Read what exists, note gaps in `## Decisions`: the project ISA (when creating a task ISA), `.claude/reference/01-system-overview.md` (Vision/Goal grounding), `02-architecture-and-tech-stack.md` (Constraints), `06-architecture-decisions.md` (Decisions context), `07-non-functional-requirements.md` (NFR-derived ISCs).

### 4. Write frontmatter

```yaml
---
project: <name>
task: <one-line restatement>
slug: <kebab-case>
effort: <E3|E4>
effort_source: <explicit|heuristic>
phase: observe
progress: 0/<criterion count>
mode: <interactive|autonomous>
started: <ISO-8601 UTC>
updated: <ISO-8601 UTC>
---
```

### 5. Populate the 12 sections in locked order

Populate from the prompt + project context where signal exists; mark the rest `_(open — fill at THINK)_`. Constraints reference Tier 2 docs by path. Features stays empty until PLAN; Changelog and Verification stay empty until EXECUTE/VERIFY.

**Criteria: scaffold only criteria that name real deliverables or risks.** No placeholder ISCs, no padding to a count — criterion count is judgment (see SKILL.md quality gates). Include ≥1 `Anti:` ISC; for experiential goals, ≥1 `Antecedent:` ISC. All ISCs ship as `[ ]`.

### 6. Apply the splitting test to every ISC

Gate every ISC with SKILL.md's *ISC quality gates* (granularity, atomic, independent failure, scope words, domain boundary); no nameable probe → rewrite or split. Splits become `ISC-N.M` — never renumber existing IDs; drops become tombstones.

### 7. Verify the output

- File exists at the target path; frontmatter parses; 12 section headers present in order.
- Every deliverable and named risk in `## Goal` maps to ≥1 ISC; every ISC has a nameable single-tool probe.
- ≥1 `Anti:` ISC; `Antecedent:` present if the goal is experiential.

Fix in place if any check fails; if unfixable, surface the gap and stop.

### 8. Report

Target path, tier, criterion count, sections populated vs left open, next phase: THINK (per `ALGORITHM/v1.2.0.md`).

## Anti-criteria for this workflow

- Anti: does NOT clobber an existing ISA without explicit confirmation.
- Anti: does NOT generate placeholder ISCs to hit a count — every scaffolded ISC names a real deliverable or risk.
- Anti: does NOT renumber existing ISC IDs on a re-run.
- Anti: does NOT mark any ISC `[x]` during scaffold.
- Anti: does NOT silently skip sections — open sections are explicitly marked.
