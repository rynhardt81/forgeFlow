# Shared Report Format

> Single source of truth for how completed work is handed back. Consumed by every framework agent, by `/run-epic --parallel` dispatch, and by any skill that reports a finished task. Update this file; consumers inherit.

A report is read by someone deciding what to do next. Four fields answer that: what the problem was, what was done, what happened, what to do about it. Anything else is prose competing with the evidence.

## When this fires

**Work happened.** A subagent returned, a skill finished, a task moved to `pr_pending`/`completed`, a fix was declared done.

**Not** for questions, discussion, mid-work narration, or a single-fact lookup. Those stay plain prose — a four-field scaffold with an empty Action line is output ceremony, and it pushes toward declaring completion early (`ALGORITHM/v1.2.0.md`).

## The four fields

| Field | Holds |
|-------|-------|
| **Problem/Task** | What was asked, or what broke. One statement, not a restatement of the whole ticket. |
| **Action** | What was actually done — files touched, commands run. Real tool calls only (Algorithm rule: no phantom capabilities). |
| **Result** | Outcome **plus an evidence pointer** — a test line, `file:line`, exit code, curl status, query result. |
| **Recommends** | Follow-ups worth someone's time, each with a next action. **Omit the whole field when empty** — never `Recommends: none`. |

## Levels

`medium` is the default. `low` and `high` are the same four fields at a different prose budget.

| Level | Budget |
|-------|--------|
| `low` | One line per field. |
| `medium` | 2–3 lines per field. |
| `high` | Uncapped, plus an appendix: full diff, full command output, full reasoning. |

**Levels cap prose, never evidence.** The Result field carries its evidence pointer at every level, `low` included. A level is a budget for explanation, not permission to assert an outcome without proof — `rules/agent-verification.md` still governs: a report's claim is an input to verification, not a substitute for it. A reader who cannot follow the pointer to ground truth has been given nothing, however short.

Filed artifacts (ISA `## Verification`, task notes, ADRs, PR bodies) are unaffected — the level governs the *report*, not the record.

## Written-document length (the canonical calibration)

A feedback level caps a *report*. It says nothing about the documents this framework writes to disk — task bodies, ISAs, ADRs, PRDs, PR descriptions, intents, epic files, specialist exports. Those need their own calibration, because the failure mode is different and current models lean into it: per the Claude Opus 5 prompting guide, *"Separate from conversational verbosity, files that Claude Opus 5 writes to disk (reports, Markdown documents, summaries) are often longer than on prior models. If your product includes Claude-authored documents, add explicit length calibration."*

The calibration, quoted from that guide, is the rule every prose template in `templates/` carries and the one to apply to any document this framework authors:

> Match the length of written documents to what the task needs: cover the substance, but do not pad with filler sections, redundant summaries, or boilerplate.

Length is set by substance, in both directions. It is not a brevity instruction: a document that drops required content to look tight has failed the same rule as one padded with boilerplate, and it fails harder where content is load-bearing — `skills/_shared/continuity-preservation.md`'s six categories, an ISA's `## Verification` evidence, a task's acceptance criteria. Cut the filler, never the substance.

## Setting the level

Convention, not code — the same shape as the `/e1`–`/e4` effort-tier override:

- **Project default:** a line in the project's `CLAUDE.md` (`Feedback level: low`). Absent → `medium`.
- **Session override:** the user types `/fb low|medium|high`. Holds until changed or the session ends.
- **Dispatch:** the level in force is passed to spawned agents in the prompt, so a subagent reports at the same budget as its parent.

## Anti

- A field padded to hit its budget. Under-budget is finished, not lazy.
- A `Result` reading "tests pass" / "works now" / "should be fine" with no pointer. That is the exact claim `rules/agent-verification.md` exists to reject.
- Reports on work that did not happen — see the no-phantom-capabilities rule.
- A written document padded to look thorough: a summary restating the section above it, a "Background" section the reader already has, a scaffold heading with nothing under it.
- A written document trimmed below its substance to look concise. Under-length is not a virtue when a required field goes missing with it.
