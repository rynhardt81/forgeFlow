# Manual Reflection Flow

Handles `/reflect` (no arguments) — session end and learning capture.

---

## `/reflect`

1. **Complete the Session End Protocol** (below)
2. Scan the conversation for learnings: corrections from the user, repeated failures and their fixes, preferences stated, approaches that worked
3. Identify skills used this session; categorize findings by confidence (High/Medium/Low)
4. Match each learning to the relevant skill (append to its `## Learned Preferences`, dated) or to `.claude/memories/general.md`
5. Present a batch review of proposed changes; apply on approval — dedup first, flag contradictions instead of replacing (see SKILL.md Key Rules)
6. Commit with a descriptive message (e.g. `reflect: session YYYY-MM-DD with N learnings`)

---

## Session End Protocol

### 1. Update the session file
Fill in Ended/Duration/Status, the Completed list (with commit hashes), and Handoff Notes (what's next, blockers).

### 2. Move the session file

```bash
mv .claude/memories/sessions/active/session-{id}.md \
   .claude/memories/sessions/completed/session-{id}.md
```

### 3. Append to progress notes

**Append only** — never overwrite `progress-notes.md`. One block per session: ID, date, branch, scope, status, completed items, key decisions, handoff.

### 4. Update latest.md

**Only if no other active sessions exist:** point `sessions/latest.md` at the completed session file with a 3-line quick summary (branch, tasks completed, ready-for).
