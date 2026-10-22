---
name: improve-codebase-architecture
description: Scans a codebase for deepening opportunities — shallow modules whose interface is nearly as complex as their implementation — and presents them as a visual HTML report with before/after diagrams, then grills through whichever one the user picks. Advisory: it changes no code; a chosen candidate leaves through /intent or /refactor. Use when the user wants an architecture review, asks what to restructure, wants the codebase easier for agents to navigate or test, or has a spare moment for codebase health. NOT FOR executing a refactor already chosen (/refactor).
disable-model-invocation: true
metadata:
  credits:
    skill: improve-codebase-architecture
    author: Matt Pocock
    url: "https://github.com/mattpocock/skills"
    license: MIT
---

# Improve Codebase Architecture

Surface architectural friction and propose **deepening opportunities**: refactors that turn shallow modules into deep ones. The aim is testability and AI-navigability.

This command is _informed_ by the project's domain model and built on a shared design vocabulary:

- Use `/codebase-design` for the architecture vocabulary (**module**, **interface**, **depth**, **seam**, **adapter**, **leverage**, **locality**) and its principles (the deletion test, "the interface is the test surface", "one adapter = hypothetical seam, two = real"). Use these terms exactly in every suggestion, and don't drift into "component," "service," "API," or "boundary."
- The domain language in `GLOSSARY.md` gives names to good seams; ADRs in `reference/06` record decisions this command should not re-litigate.

## Index

| File or section | Read when… |
|---|---|
| 1. Explore | Every run — scoping by hot spots, the friction questions, the deletion test |
| 2. Present candidates | Writing the report |
| `HTML-REPORT.md` | Step 2 — the scaffold, card layout, diagram patterns, tone |
| 3. Grilling loop | After the user picks a candidate |
| 4. Leave the survey | Handing a chosen candidate into Forge |
| `_shared/domain-docs.md` | Step 1 — reading the project glossary and the ADRs in reference/06 |
| `_shared/model-routing.md` | Dispatching the exploration sub-agent |

## Process

### 1. Explore

**Scope before you scan: YAGNI.** Deepening a module pays off by making future changes to it easier, so put extra weight on the parts of the codebase that have recently changed. Decide *where* to look before you look:

- If the user named a direction (a module, a subsystem, a pain point), take it, and skip the inference below.
- Otherwise, walk back a good stretch of the commit history (`git log --oneline`) to find the codebase's hot spots, the files and areas that keep coming up, and let those paths pull your attention first. If the changes are scattered with no clear hot spot, widen the net.

Read the project's domain glossary (`GLOSSARY.md`) and any ADRs in the area you're touching first.

Then spawn a sub-agent to walk the codebase (read-only exploration: the `Explore` agent, per `_shared/model-routing.md`). Don't follow rigid heuristics; explore organically and note where you experience friction:

- Where does understanding one concept require bouncing between many small modules?
- Where are modules **shallow**, with an interface nearly as complex as the implementation?
- Where have pure functions been extracted just for testability, but the real bugs hide in how they're called (no **locality**)?
- Where do tightly-coupled modules leak across their seams?
- Which parts of the codebase are untested, or hard to test through their current interface?

Apply the **deletion test** to anything you suspect is shallow: would deleting it concentrate complexity, or just move it? A "yes, concentrates" is the signal you want.

### 2. Present candidates as an HTML report

Write a self-contained HTML file to the OS temp directory so nothing lands in the repo. Resolve the temp dir from `$TMPDIR`, falling back to `/tmp` (or `%TEMP%` on Windows), and write to `<tmpdir>/architecture-review-<timestamp>.html` so each run gets a fresh file. Open it for the user (`xdg-open <path>` on Linux, `open <path>` on macOS, `start <path>` on Windows) and tell them the absolute path.

The report uses **Tailwind via CDN** for layout and styling, and **Mermaid via CDN** for diagrams where a graph/flow/sequence reliably communicates the structure. Mix Mermaid with hand-crafted CSS/SVG visuals: use Mermaid when relationships are graph-shaped (call graphs, dependencies, sequences), and hand-built divs/SVG when you want something more editorial (mass diagrams, cross-sections, collapse animations). Each candidate gets a **before/after visualisation**. Be visual.

For each candidate, render a card with:

- **Files**: which files/modules are involved
- **Problem**: why the current architecture is causing friction
- **Solution**: plain English description of what would change
- **Benefits**: explained in terms of locality and leverage, and how tests would improve
- **Before / After diagram**: side-by-side, custom-drawn, illustrating the shallowness and the deepening
- **Recommendation strength**: one of `Strong`, `Worth exploring`, `Speculative`, rendered as a badge

End the report with a **Top recommendation** section: which candidate you'd tackle first and why.

**Use GLOSSARY.md vocabulary for the domain, and the `/codebase-design` vocabulary for the architecture.** If `GLOSSARY.md` defines "Order," talk about "the Order intake module," not "the FooBarHandler," and not "the Order service."

**ADR conflicts**: if a candidate contradicts an existing ADR, only surface it when the friction is real enough to warrant revisiting the ADR. Mark it clearly in the card (e.g. a warning callout: _"contradicts ADR-0007, but worth reopening because…"_). Don't list every theoretical refactor an ADR forbids.

See `HTML-REPORT.md` for the full HTML scaffold, diagram patterns, and styling guidance.

Do NOT propose interfaces yet. After the file is written, ask the user: "Which of these would you like to explore?"

### 3. Grilling loop

Once the user picks a candidate, run `/grilling` to walk the decision tree with them: constraints, dependencies, the shape of the deepened module, what sits behind the seam, what tests survive.

Side effects happen inline as decisions crystallize; run `/domain-modeling` alongside it to keep the domain model current as you go:

- **Naming a deepened module after a concept not in `GLOSSARY.md`?** Add the term to `GLOSSARY.md`. Create the file lazily if it doesn't exist.
- **Sharpening a fuzzy term during the conversation?** Update `GLOSSARY.md` right there.
- **User rejects the candidate with a load-bearing reason?** Offer an ADR in `reference/06`, framed as: _"Want me to record this as an ADR so future architecture reviews don't re-suggest it?"_ Only offer when the reason would actually be needed by a future explorer to avoid re-suggesting the same thing; skip ephemeral reasons ("not worth it right now") and self-evident ones.
- **Want to explore alternative interfaces for the deepened module?** Use `/codebase-design` and its design-it-twice parallel sub-agent pattern.

### 4. Leave the survey

The survey changes no code. When the grilling settles a candidate, it leaves through Forge's front door: `/intent` when someone else must accept it or its scope is still large, `/refactor` when it is small, clear, and the engineer is at the terminal. Carry the decisions from the grilling into the intent or the refactor's scope doc, by reference to the glossary and ADR entries they produced.

---

**Project-specific overrides:** if `SKILL.local.md` exists in this directory, read it — it is consumer-owned, survives framework refresh, and **wins on conflict**. A sidecar that relaxes a gate defined above must state how to prove the gate is wrong in that case. Doctrine: `rules/framework-vs-project-root.md`.
