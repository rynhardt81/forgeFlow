---
name: intent
description: Capture a change request as a committed intent.md that a non-engineer can author, then promote an accepted intent into a forge epic and tasks. Use when someone describes a problem or wish for the product ("we need", "users keep", "it should"), when a product owner wants to file work without the task CLI, or when an accepted intent is ready to enter the queue. NOT for vetting whether to build it (/vet-idea) or for project bootstrap (/new-project).
allowed-tools: Read, Glob, Grep, Bash, Write, Edit
---

## Quick Scan

| | |
|---|---|
| **Purpose** | Turn a conversation into a version-controlled intent, then turn an accepted intent into queue state |
| **Inputs** | `/intent "<problem>"` or `/intent promote intent/<slug>.md [--epic E0X]` |
| **Output** | `intent/<slug>.md` (capture); an epic + tasks in the forge registry (promote) |
| **Flow** | Brainstorm → write intent → author corrects → commit ‖ read accepted intent → epic + tasks → mark promoted |

---

# /intent

The entry point to the artifact chain: **intent → PRD/ISA → tasks → PR**. The originator does not need the forge CLI, the Algorithm, or a task id. They need to describe a problem well enough that the next person can act on it. This skill gets them there and stops.

## Capture: `/intent "<problem>"`

1. **Brainstorm until concrete.** Ask only what the template cannot be filled without: who feels this, what "fixed" looks like, what must not break. Three to five questions is normal. If the description already answers something, do not re-ask.
2. **Write `intent/<slug>.md`** from `templates/intent.md`. Slug is kebab-case from the title. Status `draft`, author from `git config user.name`, date today. Symptoms in Problem, checkable outcome in Proposed outcome, unknowns in Open questions — never invent answers to fill a section.
3. **Show the file and let the author correct it.** Their words win over yours.
4. **Commit it** as `intent: <title>` on the current branch. The commit is the audit trail: who asked, when, what was decided. Do not open a PR — acceptance is a status edit by the product owner, not a merge.

Do not design the solution, estimate it, or file tasks here. That is what promote is for, and only after someone with authority has set `Status: accepted`.

## Promote: `/intent promote intent/<slug>.md [--epic E0X]`

Preconditions: file exists, `Status: accepted`. Anything else — stop and say which precondition failed. A `draft` intent is not queue-eligible; a `rejected` one never is.

1. **Read the intent and the project ISA** (`ISA.md`) if present, so tasks inherit the project's constraints.
2. **Choose the epic.** With `--epic`, use it (must exist — `forge epic add` first if not). Without, create one from the intent title:

   ```bash
   python3 .claude/scripts/forge/forge.py epic add E0X --name "<intent title>" \
     --description "From intent/<slug>.md"
   ```

3. **Draft tasks** — the smallest sequence that reaches Proposed outcome. Each task names files or directories it will touch (`--scope-dirs` / `--scope-files`) and gets `--isa` when it is E3 or above. Open questions in the intent that block a task become `--deps` on a spike task that answers them, not silent assumptions.
4. **Show the epic and task list; confirm before filing.** One confirmation, then file every task through the CLI. Never hand-edit `docs/tasks/registry.json`.
5. **Mark the intent** `Status: promoted → E0X` and commit both changes together as `intent: promote <slug> → E0X`. The intent stays in `intent/` — it is what `/create-pr`'s reviewer and the task ISA are checked against.

## Where it sits

| Question | Skill |
|----------|-------|
| Should we do this at all? | `/vet-idea` |
| What does the requester want? | **`/intent`** (this) |
| How will we know it is done? | ISA (`/new-feature` scaffolds it at E3+) |
| Do it | `/run-epic E0X` |

Derived work discovered while promoting follows `skills/_shared/task-triage.md` — an intent is not a licence to file everything it reminds you of.

---

**Project-specific overrides:** if `SKILL.local.md` exists in this directory, read it — it is consumer-owned, survives framework refresh, and **wins on conflict**. A sidecar that relaxes a gate defined above must state how to prove the gate is wrong in that case. Doctrine: `rules/framework-vs-project-root.md`.
