# Contributing to Forge Flow

Thanks for considering a contribution. Forge Flow is a deterministic spine for AI-assisted software development, and the bar for changes is correctness, clarity, and respect for the framework's primitives (phase-disciplined Algorithm, ISA articulation, atomic task-state CLI, 4-tier documentation governance).

## Getting started

1. Read [README.md](README.md) for what the framework is and how it's structured.
2. Run the test suite: `python3 -m pytest tests/` (suites: `forge/`, `wiring/`, `dashboard/`, `preflight/`).
3. Make a scoped change, add/update tests, and open a PR.

> **A note on paths.** This is the framework *source* repo, so the framework lives at the repo root: `reference/`, `agents/`, `skills/`, `rules/`, etc. When the framework is *installed* into a consumer project it lives under `.claude/` — so docs that reference `.claude/reference/…` or `.claude/agents/…` describe the **installed** layout. In this source checkout, drop the `.claude/` prefix.

## How to contribute

- **Issues** — open one before non-trivial PRs so design intent gets discussed before code lands.
- **PRs** — keep them scoped; one logical change per PR. Reference any related task IDs and ADRs.
- **Tests** — changes touching framework behavior (skills, hooks, the forge CLI, Algorithm doctrine) must include or update tests under `tests/`.
- **Docs** — if a change alters runtime behavior, update the relevant Tier 2 source-of-truth file under `.claude/reference/` in the same PR. Operational scaffolds (`templates/`, `CLAUDE.md`) and source-of-truth docs are different categories — see `CLAUDE.md` "Three kinds of documents".
- **Specialist agents** — user-owned specialists live in `.claude/agents/specialists/` and are never modified by framework refresh; framework agents under `.claude/agents/` are.

## Don't duplicate the harness

Claude Code injects a substantial system prompt of its own before any framework file is read. Re-stating an instruction it already gives makes behaviour **worse**, not better: both current prompting guides name compounding as a real cost, and the Claude Opus 5 guide is explicit that such instructions "compound with the model's own behavior and add cost without improving results."

So a framework file's job is what the harness does *not* say — the forge CLI's mutation discipline, the ISA verification trail, the gate domains, the task-triage defaults. Not a second copy of general good behaviour.

**Already injected by the harness — do not add these to framework files:**

| Already there | Don't re-add |
|---|---|
| A "Delivering work" block: the request sets the scope, don't quietly narrow or widen it, make routine judgment calls yourself, finish the whole task, stop short of what's clearly beyond the ask | A framework restatement of scope discipline |
| A corrections limiter: only correct an earlier statement when the error changes the user's code, conclusions, or decisions | "Don't over-apologise", "don't narrate mistakes" |
| Subagent delegation guidance, and deterministic caps as environment variables | A framework rule telling the model when to delegate in general (per-tier *routing* in `skills/_shared/model-routing.md` is different — it says which model and effort, not whether to delegate at all) |
| A parallel-tool-call nudge: make independent calls in the same block | "Batch your tool calls" |
| Context-management guidance for long sessions | "Wrap up early", "hand off before you run out" |

**Named as harmful by the guides — do not add, and remove on sight:**

- **Anti-formatting rules** — "no bullets", "avoid bold", "minimal formatting". Current models already under-format rather than over-format; Claude Fable 5.1's guide: *"If your prompt contains anti-formatting language, remove it or replace it with a rule that says when specific formatting is appropriate."*
- **"Hold all findings for the final response"** — written for models that over-narrated. It now suppresses the progress updates users need during long tool chains.
- **Self-re-verification scaffolding** — "double-check your answer", "re-verify before responding", "include a final verification step for any non-trivial task", "use a subagent to verify your own work". Claude Opus 5's guide: *"Avoid instructing re-checks it already performs ... these compound with the model's own behavior and add cost without improving results."*

### The one boundary this section must not be used to cross

**"No claim without a probe" is not self-re-verification, and it stays.** The distinction is exact and worth stating because the two look alike:

- What the guides tell you to delete is an instruction to *do the work again* — a second pass, an extra verification step, a subagent whose job is to re-check the first one. That is redundant, because the model already does it.
- What this framework requires is that a claim *cite what established it*. That is a rule about evidence, not about extra passes. It costs one sentence, it does not re-run anything, and nothing in the harness supplies it.

`CLAUDE.md`'s Operational rules mark that rule load-bearing and say never to relax it on the grounds that a newer model does it natively. This section does not license doing so, and a PR that cites "don't duplicate the harness" while deleting an evidence requirement is out of scope for it.

### Audit an incoming framework, plugin, or skill pack

Run this before enabling anything written for an older model, and read every hit — some are legitimate (a re-check after a repair action is not self-re-verification):

```bash
rg -il "no bullet|avoid bullet|minimal formatting|no bold|hold all findings|double.?check|re-?verify|subagent.{0,40}verif" <dir> --glob '*.md'
```

A hit is a question, not a verdict. Check what the line is actually doing before removing it.

## Style

- Read the existing code before adding more. Forge Flow prefers fewer, sharper primitives over feature accretion.
- No emojis in framework files unless an existing file already uses them.
- Markdown for content; HTML only where markdown can't express the structure.
- Never hand-edit `docs/tasks/registry.json` — use the `forge` CLI.

## Acknowledgments

**[Daniel Miessler](https://github.com/danielmiessler)** — creator of the [Personal AI Infrastructure (PAI)](https://github.com/danielmiessler/PAI) system.

Forge Flow was already designed when PAI entered the picture, but PAI's primitives — its Algorithm doctrine, ISA articulation, skill model, and bias toward deterministic scaffolding over model improvisation — directly inspired the fine-tuning that shaped Forge Flow's current form: more structured, more direct in its functionality, and more disciplined in how it separates source-of-truth docs from operational scaffolds. The conceptual debt is real and worth naming.

If you build on Forge Flow, consider looking at PAI as well — much of what makes Forge Flow opinionated about *how* AI-assisted development should be scaffolded traces back to ideas Daniel articulated first.
