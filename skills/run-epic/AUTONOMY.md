# Run-Epic Autonomy Block

> **Scope: `/run-epic` only.** This file is read when the drain loop starts and is injected into every agent the loop spawns. It must never be loaded by an interactive session, and it does not belong in the framework `CLAUDE.md`, in `rules/`, or in any skill a human drives at the terminal. The reason is in the guide that supplies it: the block *"can also make the model less likely to ask about ambiguous requests"* — which is correct for an unattended drain and wrong for pair work, where asking is the point.

## Why run-epic needs it

`/run-epic` is the framework's one genuinely unattended skill: the human confirms the drain plan once at Step 1 and then leaves. Without this block the loop stalls the way Claude Fable 5.1's guide describes — the model *"sometimes describes what it would do next instead of doing it ('Next, I'll …') or stops to ask permission for a step the original request already covered ('Shall I apply this?')"*. In an attended session a human types "continue". In a drain there is nobody to type it, so the iteration burns and the epic does not move.

## The block

Injected verbatim at loop start and into every spawned agent's prompt. The opening sentence carries most of the effect and is kept exactly as the guide writes it:

```text
You are operating autonomously. The user is not watching in real time and cannot answer questions mid-task, so asking 'Want me to…?' or 'Shall I…?' will block the work. For reversible actions that follow from the original request, proceed without asking. Stop only for destructive actions or genuine scope changes the user must decide. Offering follow-ups after the task is done is fine; asking permission before doing the work is not.

Stop for these specifically — they are the scope changes and destructive actions this framework has already decided the user must see:
- Any escalation gate in GUARDRAILS.md §3 (a new ADR, a Tier 2 source-of-truth edit, a new dependency or CI change, a security-validation failure, a pre-existing breakage in main, a cross-session scope overlap). Halting on one of these is correct behaviour, not an unfinished turn.
- Any hard-floor domain: a schema or migration change, auth, a money path. These are never auto-proceeded however reversible the individual step looks.
- A task whose classification is genuinely ambiguous after reading its body and scope. Ask once, then cache the answer for similar tasks in this run.
- Either rate limiter in GUARDRAILS.md §4 (more than 5 new tasks in an iteration, or 30 in the run).

Before ending your turn, check your last paragraph. If it is a plan, an analysis, a question, a list of next steps, or a promise about work you have not done ('I'll…', 'let me know when…'), do that work now with tool calls. That includes retrying after errors and gathering missing information yourself. Do not stop because the context or session is long. End your turn only when the task is complete or you are blocked on input only the user can provide.

Before running a command that changes system state (such as restarts, deletes, or config edits), check that the evidence actually supports that specific action. A signal that pattern-matches to a known failure may have a different cause.
```

## What this block does not do

- **It does not relax a gate.** The framework's escalation gates, hard floors and rate limiters sit *above* it: the guide's own text says to stop for destructive actions and genuine scope changes, and the inserted list is what this framework has already decided those are. A halt on a gate is the loop working, not the block failing.
- **It does not replace the Step 1 confirmation.** The drain plan is still confirmed once with a human before the loop starts. The block governs iterations after that point.
- **It does not license skipping verification.** Every claim still needs its probe (`CLAUDE.md` → Operational rules), and a task still completes through `/create-pr` with evidence.
- **It omits the guide's "Exception" paragraph, deliberately.** The guide's block continues: *"when the user is describing a problem, asking a question, or thinking out loud rather than requesting a change, the deliverable is your assessment. Report your findings and stop. Don't apply a fix until they ask for one."* That is right for a conversation and wrong here — a `/run-epic` task *is* the standing request for the change, so a paragraph telling the loop to report and stop when it reads a problem description would stall every `/fix-bug` task in the epic. The block above is therefore the guide's first block **minus that paragraph**, plus the stop list.
- **It is not paired with the guide's second block.** Claude Fable 5.1's guide offers a companion "Delivering work" block defining the request as the scope of the deliverable. Claude Code already injects that text into its own system prompt, so adding it here would compound rather than help — see `CONTRIBUTING.md` on not duplicating the harness.

## Where it is injected

| Site | How |
|------|-----|
| The main drain loop | Read at Step 3 (loop start), held for the run |
| Every `--parallel` spawned agent | Included in the dispatch prompt ([PARALLEL.md](PARALLEL.md) step 4) — a background agent in a worktree is at least as unattended as the loop that spawned it |

## Source

Claude Fable 5.1 prompting guide, [Finish the whole task](https://platform.claude.com/docs/en/build-with-claude/prompt-engineering/prompting-claude-fable-5-1#finish-the-whole-task). The guide supplies two blocks and says to apply both, or the first alone if prompt length is a constraint: *"The first tells the model not to ask about work already requested and to carry out the next steps it has stated."* Here the first is used and the second deliberately omitted, for the reason above. The guide also says: *"If your product needs the model to stop for specific confirmations, add a sentence after it listing them."* The inserted stop list is that addition.
