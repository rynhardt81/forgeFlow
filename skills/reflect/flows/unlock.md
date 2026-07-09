# Unlock Flow

Handles `/reflect unlock T###` and `/reflect cleanup`.

---

## `/reflect unlock T###`

Force unlock a stale task.

1. **Inspect the lock:** `python3 .claude/scripts/forge/forge.py task show T###` — read `lock.session` and `lock.lockedAt`.

2. **Validate:**
   - `lock` is null → "Task T### is not locked."
   - Locked by current session → "You already have this task locked."
   - Locked by another session and NOT stale → warn and ask before force-unlocking (show task, holder, age, timeout). If the lock is past `settings.lockTimeoutSeconds`, the consistency-banner hook already clears it at SessionStart — manual unlock is for the not-yet-stale case.

3. **If stale or user confirms:**

   ```bash
   python3 .claude/scripts/forge/forge.py task unlock T### --to-status continuation
   ```

   Use `--to-status ready` if no progress was made. The CLI atomically clears the lock, sets the status, mirrors it into the task file's frontmatter, and recomputes `stats.tasks`.

4. **Confirm:** previous status → new status; "Resume with `/reflect resume T###`."

---

## `/reflect cleanup`

Clean up stale sessions from `active/`.

1. List `.claude/memories/sessions/active/`; parse timestamps from session IDs.
2. Identify sessions older than `sessionStaleTimeout` (default: 24h).
3. Present the stale list (ID, started, age, branch) and ask to confirm.
4. On confirmation: set each session's status to `abandoned`, move `active/` → `completed/`, append a summary to `progress-notes.md`.
