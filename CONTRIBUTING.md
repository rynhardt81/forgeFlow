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

## Style

- Read the existing code before adding more. Forge Flow prefers fewer, sharper primitives over feature accretion.
- No emojis in framework files unless an existing file already uses them.
- Markdown for content; HTML only where markdown can't express the structure.
- Never hand-edit `docs/tasks/registry.json` — use the `forge` CLI.

## Acknowledgments

**[Daniel Miessler](https://github.com/danielmiessler)** — creator of the [Personal AI Infrastructure (PAI)](https://github.com/danielmiessler/PAI) system.

Forge Flow was already designed when PAI entered the picture, but PAI's primitives — its Algorithm doctrine, ISA articulation, skill model, and bias toward deterministic scaffolding over model improvisation — directly inspired the fine-tuning that shaped Forge Flow's current form: more structured, more direct in its functionality, and more disciplined in how it separates source-of-truth docs from operational scaffolds. The conceptual debt is real and worth naming.

If you build on Forge Flow, consider looking at PAI as well — much of what makes Forge Flow opinionated about *how* AI-assisted development should be scaffolded traces back to ideas Daniel articulated first.
