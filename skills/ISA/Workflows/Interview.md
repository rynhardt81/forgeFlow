# Workflow: Interview

> Deepen an ISA through a **dependency-ordered** design interview: build the graph of unresolved design decisions, topologically order it, and resolve each decision with the user only after the decisions it depends on are settled. The output is a *deepened ISA*, never a new document.

The one non-redundant capability here is the ordering — any capable model asks clarifying questions; an undirected interview reliably settles decisions before their prerequisites. Scope boundaries:

- **Design-tree interviewing only** — resolving *how* the work should be shaped.
- **NOT idea-vetting** — go/no-go is `/vet-idea`, not this.
- **NOT a premortem** — failure-mode enumeration belongs to Algorithm THINK; the interview runs at OBSERVE and feeds the design sections.

## When invoked

| Trigger | Action |
|---------|--------|
| Algorithm OBSERVE, **E3/E4 only**, after Scaffold and before ISCs freeze | Optional deepening pass — offered, never forced |
| `/ISA interview <path>` | Run directly against an existing ISA |
| `/new-feature` Phase 1 discovery | Same workflow, no external-plugin dependency |

**Hard gate: never auto-fire at E1/E2** — an unbounded interview on a small task is pure friction.

## Inputs

`path` (required; the ISA to deepen — refuse and point to Scaffold if it doesn't exist), `tier` (refuse below E3), `focus` (optional — one section to deepen; default all open decisions).

## Steps

1. **Enumerate open design decisions.** Read the ISA; collect every place the build could go more than one way with no choice recorded in `## Decisions`: sections marked `_(open — fill at THINK)_`, ISCs whose phrasing hides a choice ("store X" — where? "validate Y" — at which boundary?), constraints that leave two designs viable. Write each as one line: `D#: <the choice to make>`.

2. **Build the dependency graph and topologically sort.** For each decision, name which other decisions change its askable options (e.g. an offline-first constraint reshapes the storage options). Resolve a decision only after its dependencies. Mutual dependency (a cycle) → surface it and ask the user to break it; don't guess.

3. **Walk the order, one decision at a time.** For each: state why it's live now, present the realistic options with trade-offs and the implicit assumption behind each, ask the user to choose or defer. **Write back immediately** — chosen → `## Decisions` (`YYYY-MM-DD: chose X because …; rejected Y because …`); deferred → `## Out of Scope` with the reason; new constraints/principles → their sections, then **re-check the graph** (a new constraint can create new dependencies — re-sort if so). Stop when the graph is drained: complete the graph, don't ask forever.

4. **Reconcile ISCs without renumbering.** New ISCs get fresh IDs; splits become `ISC-N.M`; drops become tombstones. ISC IDs are stable — deepening must not churn the ID space.

5. **Verify and report.** Every walked decision appears in `## Decisions` or `## Out of Scope`; no ID renumbered; 12 headers still in locked order; only `path` was edited. Report decisions resolved/deferred, constraints/principles captured, ISC splits/tombstones, next phase: THINK.

## Anti-criteria for this workflow

- Anti: does NOT auto-fire at E1/E2 — E3/E4 only, skippable even then.
- Anti: does NOT create a new document — writes back into the existing ISA only.
- Anti: does NOT emit a go/no-go verdict (that's `/vet-idea`) or re-litigate premortem (that's THINK).
- Anti: does NOT resolve a decision before its dependencies — the topological order is the point.
- Anti: does NOT renumber existing ISC IDs.
