# Manual Reflection Flow

Handles `/reflect` (no arguments) — session end and learning capture.

---

## `/reflect`

1. **Complete the Session End Protocol** (below)
2. Scan the conversation for learnings: corrections from the user, repeated failures and their fixes, preferences stated, approaches that worked. Also look for improvements to the agent's **environment**, not the code:
   - **Navigation**: did finding the right file take long? Is there a hidden dependency a **navigation pointer** would make obvious?
   - **Automated checks**: did the agent make a mistake a lint, type check, test or filesystem check could have caught? Read the repo's own check commands (its lint/check scripts, its CI workflow) first, so a check that exists but sits unwired or silently broken is the finding, not a reinvention. A repo with no **guardrail** at all (no pre-commit hook and no CI job running its lint/typecheck/test command) is itself a finding.
   - **Coding standards**: should the reviewer be given a new rule, or an existing one removed or clarified?
   - **Tool economy**: an expensive tool call that could be streamlined, or token-inefficient custom tooling.
   - **No-ops**: steering instructions that don't change the agent's behaviour.
   - **Information access**: a crucial fact the agent couldn't reach (dev-server logs, read-only access to a service).
3. Identify skills used this session; categorize findings by confidence (High/Medium/Low)
4. **Classify each finding before writing anything.** A **mechanical** one — a fixed syntactic pattern, a banned API, an import shape, a file-location rule — gets a deterministic check, full stop: a rule in the repo's own linter, a pre-commit hook, a CI job, or a forge validator, whichever the repo's existing guardrail makes cheapest. Default to building the check over writing the rule: propose where it lives and what it matches, and file it as a task (`forge task add`, after applying `_shared/task-triage.md`) — not prose in a sidecar. Only **judgement calls** (cross-file consistency, "matches the surrounding style", anything no check could ever substitute for) become written learnings. Standards belong with the reviewer, not the implementer: the review stage has the least context pressure (it receives a diff), so a standard enforced there costs the implementation agent nothing.
   Match each judgement-call learning to the relevant skill (append to its `SKILL.local.md` sidecar, dated — never the framework `SKILL.md`, which refresh overwrites) or to `.claude/memories/general.md`
5. Present a batch review of proposed changes; apply on approval — dedup first, flag contradictions instead of replacing (see SKILL.md Key Rules)
6. Commit with a descriptive message (e.g. `reflect: session YYYY-MM-DD with N learnings`)

<!-- Environment categories and the mechanical-vs-judgement split adapted from mattpocock/skills retro (MIT) — see THIRD-PARTY-NOTICES.md -->

---

## Session End Protocol

### 1. Update the session file
Fill in Ended/Duration/Status, the Completed list (with commit hashes), and Handoff Notes — all 7 fields, under the preservation contract in `skills/_shared/continuity-preservation.md`. This is the session's compaction boundary: constraints stated exactly, counts re-derived from a live probe rather than copied forward.

### 2. Move the session file

```bash
mv .claude/memories/sessions/active/session-{id}.md \
   .claude/memories/sessions/completed/session-{id}.md
```

### 3. Append to progress notes

**Append only** — never overwrite `progress-notes.md`. One block per session: ID, date, branch, scope, status, completed items, key decisions, handoff.

### 4. Update latest.md

**Only if no other active sessions exist:** point `sessions/latest.md` at the completed session file with a 3-line quick summary (branch, tasks completed, ready-for).
