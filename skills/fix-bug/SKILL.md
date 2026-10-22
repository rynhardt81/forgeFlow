---
name: fix-bug
description: Disciplined bug fixing — a tight feedback loop that goes red on this bug before any theory, minimised repro, ranked falsifiable hypotheses, root cause before fix, regression test always; production fast path included. Hands off to /create-pr. Use when fixing any bug, error, test failure or performance regression, or when the user says "diagnose" / "debug this".
hooks:
  Stop:
    - hooks:
        - type: command
          command: "python3 $CLAUDE_PROJECT_DIR/.claude/hooks/validators/skills/fix_bug_regression.py --final"
metadata:
  credits:
    skill: diagnosing-bugs
    author: Matt Pocock
    url: "https://github.com/mattpocock/skills"
    license: MIT
---

# Fix Bug

`/fix-bug <description>` — an error message, failing test name, or symptom.

This discipline governs whatever debugging plugins are installed. The two hard gates — a red reproduction first, and a regression test — are non-negotiable. (The prod fast path below defines exactly one permitted deferral shape for the regression test; nothing waives it.)

## Index

| File or section | Read when… |
|---|---|
| `_shared/domain-docs.md` | Before investigating — glossary terms + ADRs in the area |
| 1. Memory check · Redact | Before investigating |
| 2. Feedback loop + reproduce FIRST | Always — Gate A, the completion checklist, first confirmation stop |
| `FEEDBACK-LOOP.md` | Step 2 — the ten ways to build a loop, tightening it, flaky bugs, perf regressions, when no loop is possible |
| `scripts/hitl-loop.template.sh` | Step 2, last resort — **copy and edit** when a human must act |
| 3. Minimise · 4. Hypothesise and instrument | Before writing any fix |
| 5. Fix + regression test | Writing the fix; the correct-seam rule and optional test lock |
| 6. Verify and clean up · `FAN-OUT.md` | After the fix; `FAN-OUT.md` for the E2E / security dispatches |
| Production incident fast path · `INCIDENT.md` | The bug is live in production |
| `_shared/task-triage.md` | Fast path step 5 / no-seam finding — filing a follow-up |
| Debug doc · `DEBUG-DOC.md` | The investigation spans hypotheses or sessions |
| 7. Ship / Rules | Second confirmation stop, commit, `/create-pr` hand-off |

## 1. Memory check

If `docs/project-memory/bugs.md` exists, grep it for keywords from the bug description. Surface any prior art ("we hit this class of bug before, root cause was X") before investigating. Skip silently if the file doesn't exist.

**Redact:** this skill shows commands, outputs and captured artifacts. Write `<REDACTED>` in place of every secret first. Build loops against env vars, so the credential stays in the environment rather than in what you show. Captured artifacts carry auth headers: quote only the lines that carry the signal.

## 2. Feedback loop + reproduce FIRST (Algorithm Gate A)

Capture the failure **before any Read/Grep targets the suspect code path**. The capture is a **feedback loop**: one command that goes **red** on _this_ bug. Build it with `FEEDBACK-LOOP.md`. If you catch yourself reading code to build a theory before this command exists, **stop: jumping straight to a hypothesis is the exact failure this step prevents.**

Done when you can name **one command** (a script path, a test invocation, a curl) that you have **already run** — show the invocation and its output, redacted — and that is:

- [ ] **Red-capable**: it drives the actual bug code path and asserts the **user's exact symptom**, so it goes red on this bug and green once fixed. Not "runs without erroring".
- [ ] **Deterministic**: same verdict every run (flaky bugs: a pinned, high reproduction rate).
- [ ] **Fast**: seconds, not minutes.
- [ ] **Agent-runnable**: you can run it unattended; a human in the loop only via the HITL script.

The minimum evidence the loop shows, by symptom:

| Symptom | Required reproduction |
|---------|----------------------|
| Web/UI bug | Browser screenshot or network trace |
| HTTP failure | `curl -i` showing the broken response |
| CLI failure | Actual stdout/stderr |
| Test failure | The failing test output |
| Data inconsistency | `SELECT` showing the wrong value |

Confirm the loop produces the failure the **user** described, not a nearby one: wrong bug = wrong fix.

**Confirm with the user here** — "Reproduced: `<command>` goes red when [X]. Proceed?" This is the first of only two confirmation stops.

If no loop is possible (prod-only race, third-party outage), say so explicitly, list what you tried, and agree on the closest proxy probe or the access you need (`FEEDBACK-LOOP.md`) — never skip silently, never hypothesise without one.

## 3. Minimise

Once it's red, shrink the repro to the **smallest scenario that still goes red**. Cut inputs, callers, config, data, and steps **one at a time**, re-running the loop after each cut, and keep only what's load-bearing for the failure. Done when **every remaining element is load-bearing**: removing any one of them makes the loop go green.

## 4. Hypothesise and instrument

- Generate **3–5 ranked hypotheses** before testing any of them; a single hypothesis anchors on the first plausible idea. Each is **falsifiable**: "If <X> is the cause, then <changing Y> will make the bug disappear / <changing Z> will make it worse." If you cannot state the prediction, the hypothesis is a vibe: discard or sharpen it.
- **Show the ranked list to the user before testing** — they often re-rank instantly. Don't block on it; proceed if they're away.
- **Root-cause-at-ingestion:** rank highest where the bad state *enters* the system. Fixing there kills the bug class; patching the output side masks it. For UI bugs, trace display-down (correct), not database-up.
- Each probe maps to one prediction. **Change one variable at a time.** Prefer a debugger / REPL breakpoint, then targeted logs at the boundaries that distinguish hypotheses; never "log everything and grep".
- **Tag every debug log** with a unique prefix, e.g. `[DEBUG-a4f2]`. Cleanup at the end becomes a single grep. Untagged logs survive; tagged logs die.
- Do not touch the fix until a hypothesis is confirmed by evidence, not by plausibility. A fix that swallows the error instead of surfacing it is not a fix (`rules/error-handling.md`).

## 5. Fix + regression test

- Smallest fix that addresses the confirmed root cause. No scope creep, no drive-by refactoring — file follow-ups instead.
- **Regression test required:** a test that fails without the fix and passes with it, asserting on the failure path from step 2. The Stop-hook validator (`fix_bug_regression.py`) checks for it. Write it **before the fix**, at a **correct seam**: one where the test exercises the real bug pattern as it occurs at the call site. A seam too shallow to replicate the chain that triggered the bug gives false confidence — go up a level (integration, the step-2 loop itself) until it reproduces. If no seam at any level can, that itself is the finding: say so, agree it with the user like an impossible reproduction, and file it (`_shared/task-triage.md`) as an `/improve-codebase-architecture` candidate. It is not a way around the gate.
- Order: turn the minimised repro into the failing test → watch it fail (if you forced the red by mutating code or a fixture, `diff` against a pristine copy to prove the mutation landed) → apply the fix → watch it pass.
- **If the project installed the test-lock damage control** (the test-lock recipe in `/damage-control`): commit the failing test, then write its path into `.claude/.test-lock`. That makes the test unwritable while you fix the source — the escape this closes is editing the test until it passes. Skip silently if the hook isn't installed.

## 6. Verify and clean up

- **Clear the lock first if you set one:** `rm .claude/.test-lock` — a stale lock blocks the next session's test edits.
- [ ] Original repro no longer reproduces: re-run the step-2 loop against the original (un-minimised) scenario, shown with actual output.
- [ ] Regression test passes; the related suite shows no new failures.
- [ ] All `[DEBUG-...]` instrumentation removed — grep the prefix, zero hits.
- [ ] Throwaway harnesses deleted (or moved to a clearly-marked debug location).
- [ ] The hypothesis that turned out correct is stated in the commit / PR message, so the next debugger learns.
- UI / critical-flow bugs → E2E regression pass; security bugs → review of the fix. Dispatch blocks: `FAN-OUT.md`.

## Production incident fast path

Live in production (outage, data corruption, all-users breakage) → follow `INCIDENT.md`: speed over ceremony, never skipping verification. The regression test may be deferred **only** by filing the follow-up task before merging and naming it in the PR body. For full incident handling, use `/triage-incident`.

## Debug doc (gnarly bugs only)

When the investigation outlives a couple of hypotheses or spans sessions, keep a running `docs/debug/<slug>.md` (template: `DEBUG-DOC.md`) so context survives compaction and handoffs. Skip it for quick fixes.

## 7. Ship

**Confirm with the user before opening the PR** (second and last confirmation stop): fix summary, files touched, regression test name.

Commit as `fix: <description>`, then invoke `Skill("create-pr")`. Never use raw `gh pr create` — it bypasses the pre-flight review gates. If the user explicitly wants no PR, stop after the commit.

If the bug pattern is novel and worth remembering, offer `/remember bug "<title>"`.

## Rules

- A red feedback loop before any theory; the same loop goes green after the fix.
- Hypotheses ranked and falsifiable; root cause confirmed by evidence before any fix lands.
- Regression test always, at a seam that reproduces the real call-site pattern.
- Fix only this bug — discovered work becomes follow-up tasks.
- Confirm with the user at exactly two points: reproduction confirmed, and before the PR.

---

**Project-specific overrides:** if `SKILL.local.md` exists in this directory, read it — it is consumer-owned, survives framework refresh, and **wins on conflict**. A sidecar that relaxes a gate defined above must state how to prove the gate is wrong in that case. Doctrine: `rules/framework-vs-project-root.md`.
