# 09-autonomous-development.md

**Autonomous Development Patterns**

> **Audience:** Developers, Architects, Claude Code
> **Authority:** Development Standards (Tier 2)
> **Purpose:** Define patterns for long-running autonomous agent development

---

## 1. Purpose of This Document

This document defines **patterns for autonomous development** — AI agents implementing work with minimal human intervention, over sessions long enough that state, quality, and safety cannot live in one context window.

It answers:
* How do agents drain work autonomously, and what stops them?
* How is state preserved across sessions and context compaction?
* How do agents hand off work?
* How is quality maintained while nobody is watching?

This document does NOT cover:
* Application security model (see `08-security-model.md`)
* Application architecture (see `02-architecture-and-tech-stack.md`)
* Deployment procedures (see `05-operational-and-lifecycle.md`)

---

## 2. Key Principles

1. **Incremental progress:** one task at a time, committed after each — the git history is the only truthful record of work.
2. **Quality gates:** verification before completion; a task is not done until its ISA's criteria probe green.
3. **Bounded autonomy:** every loop has a hard iteration cap and halt conditions — runaway loops are a design failure, not a tuning problem.
4. **State persistence:** git + the task registry + progress notes — never "the agent remembers".
5. **Escalate, don't improvise:** decisions above the autonomy gate stop the loop and surface to the human.

---

## 3. The Autonomous Loop — `/run-epic`

The framework's sanctioned long-running loop is `/run-epic E##`: autonomously drain every open task in a single epic — inline work, discovered follow-ups auto-filed as new tasks into the same epic, a PR per task.

```
Get next ready task from registry
      │
      ▼
Lock (forge task lock) → implement → verify → /create-pr
      │
      ├─ surfaced a bug / missing prerequisite / too-coarse task?
      │       → file a new forge task into the same epic, continue
      │
      ▼
Repeat until: epic empty | --max-iter | consecutive-failure | escalation
```

### Guardrails (see `skills/run-epic/GUARDRAILS.md` for the full set)

| Guardrail | Behavior |
|-----------|----------|
| `--max-iter=<n>` | Hard cap on tasks executed per run (default 50). Prevents runaway loops. |
| Consecutive-failure circuit | Repeated task failures halt the loop instead of burning through the epic. |
| Escalation gates | A task that fails the autonomy gate (irreversible action, ambiguous requirement, security-sensitive decision) halts with the specific blocker surfaced — an escalation, not a failure. |
| PR discipline | A `/create-pr` failure halts the loop on that task; the loop never moves on with uncommitted work. |
| Halt report | Every termination states its reason (`epic empty` / `--max-iter` / `consecutive-failure` / `escalation`) plus a next-task suggestion. |

---

## 4. State Persistence — three bridges

```
┌───────────────────┬─────────────────┬──────────────────┐
│  Task Registry    │   Git Commits   │  Progress Notes  │
│                   │                 │                  │
│ • Which tasks are │ • All code      │ • Session logs   │
│   done/locked     │   changes       │ • Decisions      │
│ • Dependencies    │ • Task IDs in   │ • Blockers       │
│ • Scope claims    │   messages      │ • Human context  │
└───────────────────┴─────────────────┴──────────────────┘
```

* **Task registry** (`docs/tasks/registry.json`): mutated only via the forge CLI (`forge task add/lock/pr/complete`); the consistency-banner hook auto-fixes drift. Never hand-edited.
* **Git:** one commit (or PR) per task, task ID in the message body. Background worktree agents additionally follow the **Checkpoint Discipline** in `ALGORITHM/v1.2.0.md` — periodic `wip:` commits, checkpoint before long operations, final commit before completion — so a reaped worktree never loses work.
* **Progress notes** (`.claude/memories/progress-notes.md`): append-only session summaries and handoff context. See `reference/10-parallel-sessions.md`.

---

## 5. Session Management

**Session start:** the SessionStart hook auto-creates the session file; the agent reads progress notes, checks the registry for locked/in-progress tasks, and reviews recent commits before touching code.

**Session end / handoff:** completed work, key decisions, and the next ready task are appended to progress notes:

```markdown
## Session: YYYY-MM-DD HH:MM

### Summary
- Tasks: T046–T055 completed (PRs opened)
- Epic: E04 — 55/92 tasks done

### Next
T056 — locked by no one, deps satisfied

### Notes
- Chose Zustand for cart state (ADR-012)
- Dev server on port 3000
```

**Resume:** `/reflect resume` — reads the session file and progress notes, re-checks registry state and `git status`, and continues from the recorded checkpoint rather than from memory.

**Crash recovery:** check `git status` for uncommitted work, clear stale task locks, review progress notes, resume normally. For background worktree agents, forced cleanup promotes dirty state to a `wip(reaped):` commit first (no-commit-no-reap — `ALGORITHM/v1.2.0.md`).

---

## 6. Quality Assurance While Autonomous

* **Regression before progress:** verify previously-passing behavior still passes before building the next unit; a detected regression stops new work until fixed.
* **Verification per task:** lint + type-check + tests appropriate to the change, plus the task ISA's criteria probes. Evidence goes into the ISA `## Verification` table — "should work" is not a state.
* **Retry budget:** a failing task gets a bounded number of fix attempts (default 3); then it is skipped with the blocker logged as a new task, and the loop continues.
* **Commit strategy:** one commit per task, imperative message, task ID in the body — never batch multiple tasks into one commit.

---

## 7. Escalation Gates

Autonomy stops and a human decides when a task requires:

* An irreversible or destructive action (data deletion, force push, production deploy)
* A security-sensitive decision (auth model, payment flow, secrets)
* An ambiguous requirement that materially changes scope
* Spending money or calling paid external services beyond configured limits

The loop surfaces the specific blocker and the state it halted in. Everything below the gate proceeds without asking.

---

## 8. Best Practices

**Do:** complete tasks atomically; commit after each; run regression checks; update progress notes in real time; respect halt conditions.

**Don't:** batch tasks into one commit; leave tasks locked at session end; force through blockers that belong above the escalation gate; ignore failing verification to "keep velocity".

---

## 9. See Also

- `skills/run-epic/SKILL.md` + `skills/run-epic/GUARDRAILS.md` — the autonomous loop and its termination conditions
- `ALGORITHM/v1.2.0.md` → "Background Agent Checkpoint Discipline" — commit contract for background worktree agents
- `reference/10-parallel-sessions.md` — session files, conflict matrix, lock rules
- `reference/13-task-management.md` — forge CLI task lifecycle
- `08-security-model.md` — application threat model (agent command safety: `/damage-control`)
