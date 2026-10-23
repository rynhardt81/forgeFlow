# Orchestrated development

## Contents

- The ask — once, before work starts
- Roles
- 1. Dispatch the implementer
- 2. Handle the report
- 3. Review the task
- 4. The fix loop
- 5. Complete the task
- Where it plugs in

The main agent is the **orchestrator**: it plans, dispatches, verifies and keeps the registry. **Subagents implement and review.** A fresh subagent per task, a task review (spec + quality) after it, and the broad review once at `/create-pr` keeps quality high and the orchestrator's context clean for coordination. Used by `/run-epic` and `/new-feature`; it is their default, behind one question.

## The ask — once, before work starts

Ask exactly once, at the skill's existing confirmation point (`/run-epic` Step 1.6, `/new-feature` Step 1), never mid-run:

> **Subagent-driven development?** I orchestrate; a fresh subagent implements each task and another reviews it (spec + quality) before I verify and commit. Costs two extra subagents per task, keeps my context clear across long runs. **yes** (default) / **no** (I implement inline, as before).

Record the answer in the session file's Scope Declaration (`orchestrated: yes|no`) so `/reflect resume` restores it. **No** → the skill's inline path, unchanged. An E1 task under `/new-feature` may be done inline even on yes — say so in one line; dispatch overhead is larger than the change.

## Roles

- **Orchestrator** (main loop): never edits source files in this mode, and **never fixes findings itself** — controller fixes skip review. It owns locks, the task-file ledger, verification and the PR hand-off.
- **Implementer**: one task, one fresh subagent. Never dispatches subagents of its own — not helpers, and never a reviewer. Review arrives from the orchestrator, after the report.
- **Reviewer**: fresh, read-only, sees the diff — not the implementer's reasoning.

Routing is `_shared/model-routing.md`, named at dispatch: implementer by the task's tier (E1 `worker-e1`, E2 `worker-e2`, E3 `general-purpose` inheriting; E4 stays in the main loop and is not dispatched). The reviewer is at least the implementer's tier. Hard-floor tasks (schema, auth, money paths, security) run both at the session model.

## 1. Dispatch the implementer

Record BASE (`git rev-parse HEAD`) before dispatching — the review diff and fix-round diffs need it; never `HEAD~1`, which silently drops all but the last commit of a multi-commit task.

The **task body is the brief** (`forge task show <T###> --json` → `file`, plus its ISA when one exists). The dispatch contains:
1. one line on where this task fits in the epic;
2. the brief path, introduced as "read this first — it is your requirements, with the exact values to use verbatim";
3. interfaces and decisions from earlier tasks the brief cannot know;
4. your resolution of any ambiguity you noticed in the brief;
5. the discipline file to follow (`skills/fix-bug/SKILL.md`, `skills/new-feature/PHASES.md` Implementation + Verification, or `skills/refactor/SKILL.md`), the autonomy block when inside `/run-epic`, "commit, do not push";
6. the report contract: status (`DONE` / `DONE_WITH_CONCERNS` / `NEEDS_CONTEXT` / `BLOCKED`), commits, the test command run and its output, concerns — in the four fields of `_shared/report-format.md`.

A dispatch describes one task, not the session's history: never paste prior-task summaries into later dispatches. Record the implementer's agent identity — fix rounds 1–3 resume it. Never dispatch two implementers in parallel on overlapping scope; scope-disjoint tasks go to worktrees exactly as `/run-epic --parallel` already does.

## 2. Handle the report

- **DONE** → review (step 3).
- **DONE_WITH_CONCERNS** → read the concerns first. About correctness or scope: address them before review. Observations ("this file is getting large"): note and proceed.
- **NEEDS_CONTEXT** → provide the missing context and re-dispatch.
- **BLOCKED** → assess: a context problem → more context, same model; needs more reasoning → one tier up; too large → split it (`forge task add`, `_shared/task-triage.md`); the plan itself is wrong → rule on the correction, ledger it, re-dispatch with the ruling.

**Never** ignore an escalation or force the same model to retry without changes. If the implementer said it's stuck, something needs to change.

## 3. Review the task

Never skip the task review, and never accept a report missing either verdict — **spec compliance AND quality** are both required. Implementer self-review never replaces it.

- Hand the reviewer its diff as a file: `git log --oneline BASE..HEAD`, `git diff --stat BASE..HEAD` and `git diff -U10 BASE..HEAD` redirected to one uniquely named scratch file. It never enters your own context; the reviewer reads it in one call.
- Reviewer inputs: the brief path, the implementer's report, the diff file, and the binding constraints copied verbatim (exact values, formats, stated relationships). It returns findings as `MUST-FIX` / `NICE-TO-HAVE` / `NO-ACTION` with a spec verdict, plus "⚠️ cannot verify from diff" items.
- Do not ask the reviewer to re-run tests the implementer already ran on the same code. Do not pre-judge findings: if the prompt you are writing contains "do not flag", "don't treat X as a defect" or "the plan chose" — stop: you are pre-judging, usually to spare yourself a review loop.
- Resolve every ⚠️ item yourself before completion — you hold the cross-task context. A confirmed gap is a failed spec review.

## 4. The fix loop

Triggers on a failed spec verdict, any `MUST-FIX`, or a confirmed ⚠️ gap. `NICE-TO-HAVE` findings never enter it: ledger them (`<T###>: minor (deferred): <one-liner>`) and point `/create-pr` at that list. A round is one fix dispatch plus one scoped re-review; **five rounds maximum**.

- **Rounds 1–3 — resume the original implementer** (`SendMessage`) with the open findings verbatim. If it can't be resumed, dispatch a fresh one with the brief, report and findings.
- **Rounds 4–5 — a fresh implementer one tier up**, framed: "A prior implementer attempted this task N times; you own it now. Read the report for what was tried." A loop that survives three resumes usually means the implementer cannot see its own problem.
- Every round: the implementer fixes, re-runs the covering tests, reports command + output; the re-review sees only FIX_BASE..HEAD and verdicts each finding ADDRESSED / NOT ADDRESSED. New breakage in the fix diff joins the open list.
- **The breaker** — round 5 still open: adjudicate each finding yourself. Reviewer wrong, or real but nothing builds on it → park with a ruling. Real and load-bearing → rule on the smallest unblocking change and carry it into the next dispatch. Adjudicate only at the cap; every adjudication is a ledger line — a silent discard is forbidden. Inside `/run-epic` a tripped breaker counts as an iteration failure for its circuit breaker.

## 5. Complete the task

Delegated output and green tests are inputs to verification, not proof (`rules/agent-verification.md`): before completion, **run the covering tests yourself** and check each ISA criterion's evidence. Then ledger `<T###>: complete (commits <base7>..<head7>, review clean | K parked)` in the task file's Notes and continue the calling skill's flow (`/create-pr`, or `forge task complete` on `--no-pr`). Never move on while a `MUST-FIX` is neither fixed nor parked-with-ruling at the cap.

## Where it plugs in

- `/run-epic`: the ask at Step 1.6; LOOP.md → Execute dispatches instead of following the discipline inline.
- `/new-feature`: the ask at Step 1; PHASES.md → Implementation dispatches the implementer, Verification and Review become the task review above. Design and Planning stay with the orchestrator.

<!-- Task loop (implementer statuses, task review, five-round fix loop with resume-then-escalate, the breaker) adapted from obra/superpowers subagent-driven-development (MIT, © 2025 Jesse Vincent) — see THIRD-PARTY-NOTICES.md -->
