# Config Flow

Handles `/reflect config` and `/reflect config <key> <value>`.

> Dispatch and intent config were removed in v4 (the forge registry + `/run-epic` is the one task system; skills are invoked explicitly). The `/reflect on|off` auto-reflection toggle (`.claude/memories/.reflect-status`) was also removed — nothing in hooks or scripts ever read it. Reflection is manual: `/reflect` with no args.

---

## `/reflect config`

Show current configuration — the `settings` block of `docs/tasks/registry.json` plus session defaults.

```markdown
## Reflect Configuration

### Task Management (registry `settings`)
| Setting | Value | Allowed | Description |
|---------|-------|---------|-------------|
| lockTimeoutSeconds | 3600 | 60-86400 | Seconds before a task lock is stale |
| allowManualUnlock | true | true, false | Allow /reflect unlock |
| maxParallelAgents | 3 | 1-10 | Max concurrent task locks |
| autoAssignNext | true | true, false | Auto-suggest next ready task |

### Session Management
| Setting | Value | Allowed | Description |
|---------|-------|---------|-------------|
| sessionStaleTimeout | 86400 | 3600-604800 | Seconds before a session is stale (cleanup) |
```

---

## `/reflect config <key> <value>`

Update a setting. Task-management keys live in the `settings` block of `docs/tasks/registry.json` — editing `settings.*` is sanctioned (it is configuration, not task state; task state stays forge-CLI-only). Validate against the allowed range, apply, confirm.

```
/reflect config lockTimeoutSeconds 1800
/reflect config maxParallelAgents 5
/reflect config autoAssignNext false
```
