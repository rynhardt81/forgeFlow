# Shared Continuity-Preservation Contract

> Single source of truth for what a continuity artifact must carry across a context boundary. Consumed by `/reflect handoff` (the projected brief), `/reflect resume` (the Continuation Context it writes on pause or failure), and the `## Handoff Notes` / `## Continuation Context` sections of `templates/session.md`. Update this file; consumers inherit.

## Why this exists

`/reflect handoff` and the Continuation Context are Forge Flow's **client-side compaction**: a long session is discarded and a short artifact stands in for it. What the artifact drops is gone — the next session does not know it is missing and re-derives it, wrongly or not at all. The failure is silent by construction, which is why it needs a written floor rather than judgment.

The observed cost is category (6) below. A brief that carries a stale count — "39 ready", "3 of 8 done" — is worse than one twice as long, because the next session acts on the number instead of re-deriving it.

## The six categories — binding on every continuity artifact

From the Claude Fable 5.1 prompting guide, [Tell the model what to preserve in compaction summaries](https://platform.claude.com/docs/en/build-with-claude/prompt-engineering/prompting-claude-fable-5-1#tell-the-model-what-to-preserve-in-compaction-summaries). Quoted as written; the guide's instruction is the contract:

> Include relevant information in the summary such that this conversation will be continued by a new context window without needing to redo work or be reprovided with relevant constraints or context. Be sure to preserve: (1) any difficulties or problems that came up, and how they were handled or resolved; (2) any possibilities, options, or approaches that were raised, tried, or set aside, and why; (3) anything that was asked for, decided, agreed, ruled out, or established as a preference, constraint, or boundary — stated exactly; (4) exactly where things stand now — what has been covered, settled, or completed so far; (5) anything still open, unresolved, promised, or expected to happen next; (6) specific details that would be hard to reconstruct — names, numbers, dates, exact wording, links or references — kept exactly. Be complete on these even at the cost of length; keep everything else concise. Weight the two voices differently: keep what the user said, asked for, shared, or established carefully and close to their own words; your own explanations and reasoning can be condensed much further, to what they concluded or produced — as long as nothing in the six items above is dropped.

**Completeness on the six outranks the brevity budget.** Every other cap in this framework — the handoff field caps, a `/fb low` feedback level, the "this is a brief, not a dump" rule — governs prose. None of them licenses dropping a category. When a field cannot hold a category inside its cap, the cap yields.

## Where each category lands in the 7-field schema

| Category | Field |
|---|---|
| (4) where things stand | **Goal**, **Current Progress** |
| (1) problems and how resolved, (2) options tried or set aside and why | **What Worked**, **What Didn't Work** |
| (3) asked / decided / agreed / ruled out — stated exactly | **Constraints & Decisions** |
| (5) open, unresolved, promised, expected next | **Next Steps** |
| (6) hard-to-reconstruct specifics — kept exactly | **Specifics** |

Fields (3) and (6) exist because the original 5-field schema had nowhere to put them, and a category with nowhere to go is a category that gets dropped.

## Counts are re-derived, never carried forward

Category (6) says keep numbers exactly. That is a rule about **provenance**, not about copying: a number is preserved exactly *from the probe that produced it*, never from a prior summary.

- Any count that a live probe can produce — ready tasks, epic progress, open PRs, test totals — is **re-run at projection time**, not read out of the previous brief. `/reflect handoff` already re-queries `forge task ls --ready`; that query is the source, and the brief is downstream of it.
- A number that cannot be re-derived (a measurement, a benchmark, a figure the user stated) is carried verbatim **with its date and how it was obtained**, so the next reader can tell a fact from a fossil.
- A bare number with no provenance is the defect this rule exists to prevent. Write `39 ready (forge task ls --ready, 2026-09-12)`, never `39 ready`.

## Anti

- **Anti:** a continuity artifact that paraphrases a constraint the user stated exactly. Category (3) says *stated exactly* — a reworded constraint has already lost the boundary it was setting.
- **Anti:** a count copied from a prior brief rather than re-derived from its probe.
- **Anti:** a category dropped to stay inside a field's length budget. The budget yields; the category does not.
- **Anti:** the assistant's own reasoning preserved at the same weight as the user's words. The guide weights them differently on purpose — condense your own explanations hard, keep theirs close to verbatim.
