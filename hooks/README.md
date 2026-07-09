# Claude Code Hooks

Claude Forge hooks are helper scripts that provide context and useful reminders. They never block operations.

> **Cross-Platform:** All hooks are written in Python for compatibility with Windows, macOS, and Linux.

## Philosophy

Hooks are **purely informational**. They:
- Provide session status on startup
- Inject active session/skill/agent context on UserPromptSubmit
- Auto-fix registry/task drift on every Write/Edit
- Capture conversation context on SessionEnd and PreCompact (memory pipeline)
- Warn on suspicious Bash commands and edits to sensitive files
- Never return exit code 2 (never block)

## Directory Structure

```
hooks/
├── session/                # Session lifecycle
│   ├── session-context.py      # SessionStart context (informational)
│   └── session-end-cleanup.py  # Final cleanup at SessionEnd
│
├── context/                # Context management
│   └── user-prompt-submit.py   # Inject session/skill/agent context per prompt
│
├── validation/             # PreToolUse warnings (never block)
│   ├── validate-edit.py        # Sensitive-file edit warnings (Write|Edit)
│   └── pr-skill-reminder.py    # Reminder to use /create-pr for PR ops (Bash)
│
├── validators/             # Domain validators bound via agent/skill frontmatter
│   ├── base.py                 # Base validator class (PostToolUse → additionalContext)
│   ├── agents/                 # Agent-bound validators
│   │   ├── security_secrets.py     # Secret detection
│   │   ├── architect_adr.py        # ADR format
│   │   ├── quality_coverage.py     # Test coverage
│   │   ├── tdd_aaa.py              # AAA pattern
│   │   └── build_deps.py           # Dependency validation
│   └── skills/                 # Skill-bound validators
│       ├── fix_bug_regression.py   # Regression test check
│       ├── create_pr_format.py     # PR description format
│       ├── diagnose_ci_format.py   # /diagnose-ci diagnosis-only contract
│       └── new_project_prd.py      # PRD completeness
│
├── config/                 # Configuration
│   ├── secret-patterns.yaml    # Secret detection patterns
│   └── README.md               # Config documentation
│
├── forge/                  # Framework integrity
│   ├── consistency-banner.py   # Wrapper around scripts/forge/check_consistency.py
│   ├── isa-reflection-emit.py  # Reflection skeleton on ISA phase: complete
│   └── checkpoint-nudge.py     # Checkpoint reminders for worktree agents
│
├── settings.json           # Default settings template (the only runtime wiring)
└── README.md               # This documentation
```

**Hard rule:** no hook spawns an LLM subprocess. Hooks are deterministic scripts. Knowledge capture is manual and intentional (`/remember`); rule reflection is `/audit-rules`, run by a human.

## Installation

Copy the settings template to your project:

```bash
cp .claude/hooks/settings.json .claude/settings.json
```

**Requirements:**
- Python 3.6+ (`python3` on macOS/Linux, `python` on Windows)

## Active Hooks

### session-context.py

**Runs on SessionStart.** Displays compact session status (~100 tokens):

```
=== FORGE ===
S:20240115-143022-a7x9    # Session ID (or NONE)
T:5/20|R3|A1              # Task status
===
```

### user-prompt-submit.py (context/)

**Runs on every UserPromptSubmit.** Inspects the active session file (`.claude/memories/sessions/active/session-*.md`) and the task registry. If an active skill or agent is recorded, it injects a one-line reminder so the model knows to re-invoke or reload context. Silent when there's nothing to surface.

### validate-edit.py (validation/)

**Runs on PreToolUse Write|Edit.** Warns when editing sensitive files (`.env`, `.env.local`, `.env.production`, `package-lock.json`, `yarn.lock`, `pnpm-lock.yaml`, `.git/`, `node_modules/`). Informational only — never blocks.

### pr-skill-reminder.py (validation/)

**Runs on PreToolUse Bash.** Detects ad-hoc `gh pr {create|merge|ready|checks}` invocations and emits a one-line reminder to route through `/create-pr` instead. Each subcommand gets a tailored message:

| Detected | Reminder gist |
|----------|---------------|
| `gh pr create` (without `--body-file`) | `/create-pr` adds Step 3.7 pr-review-toolkit pre-flight + mandatory `@codex` mention + size-aware description |
| `gh pr merge` | Run `/create-pr review <PR#>` first to verify codex + MUST-FIX resolution |
| `gh pr ready` | `/create-pr` ensures Step 3.7 pre-flight runs before reviewers see the PR |
| `gh pr checks` | `/create-pr review <PR#>` aggregates CI + codex + Step 3.7 in one verdict |

**Self-suppression:** detects the `--body-file` flag on `gh pr create` and stays silent — the `/create-pr` skill itself uses `--body-file` in Step 5, so the reminder doesn't echo during legitimate skill execution.

**Skipped subcommands:** `gh pr review` (the skill calls `gh pr review --json` in its review loop — reminding there is noise) and `gh pr edit` / `gh pr view` (low-level surgery the skill isn't the right wrapper for).

Never blocks — informational stderr only, exit 0 always.

### consistency-banner.py (forge/)

**Runs on SessionStart and PostToolUse (Write|Edit).** Wraps
`scripts/forge/check_consistency.py` to detect and auto-fix drift between
`docs/tasks/registry.json` and the task files on disk.

What gets auto-fixed silently (4 classes — registry-as-truth direction):
- `registry.stats` recompute when counts disagree (drift #4)
- `pending → ready` flip when all dependencies are done (drift #5)
- task file frontmatter `status:` rewrite to match registry (drift #6)
- stale `lock` cleanup on `in_progress` tasks past `lockTimeoutSeconds` (drift #7)
- task file frontmatter `name:` rewrite to match registry (drift #8)

What's surfaced as a banner (max 300 chars, silent on clean — 3 classes blocking):
- task file on disk missing from registry (drift #1)
- epic dir on disk missing from registry (drift #2)
- `completedAt < createdAt` monotonicity violations (drift #3)

For drift #1 (orphan task files), the recovery path is `forge task reconcile-from-files` — an opt-in command that seeds registry entries from the orphan files' frontmatter. Useful for v2 → v3 migrations where task files predate the v3 registry schema.

The PostToolUse hook self-filters to only run when the touched path
matches `registry.json` or a task file, and uses an env-var recursion
guard so the auto-fix's own registry write doesn't re-trigger the hook.

#### Optional: PreToolUse commit gate

Not enabled by default. Add this manually to `.claude/settings.json` to
block `git commit` when blocking drift remains:

```json
{
  "hooks": {
    "PreToolUse": [
      {
        "matcher": "Bash",
        "hooks": [{
          "type": "command",
          "command": "python3 \"$CLAUDE_PROJECT_DIR/.claude/hooks/forge/consistency-banner.py\" --strict",
          "timeout": 10
        }]
      }
    ]
  }
}
```

The hook self-filters on `git commit` substring match, so it doesn't
slow other Bash calls. Off by default because workflows vary; enable per-
project if you want a hard gate.

## Configuration

Hooks are configured in `.claude/settings.json`:

```json
{
  "hooks": {
    "SessionStart": [
      { "matcher": "startup", "hooks": [{ "type": "command", "command": "python3 .claude/hooks/session/session-context.py" }] }
    ],
    "SessionEnd": [
      { "matcher": "", "hooks": [{ "type": "command", "command": "python3 .claude/hooks/session/session-end-cleanup.py" }] }
    ]
  }
}
```

## Validators

Domain validators in `validators/` provide helpful suggestions but never block.

### Exit Codes

| Exit Code | Meaning |
|-----------|---------|
| 0 | Success (always) |

Validators may print warnings to stderr for informational purposes.

## Disabling Hooks

Create `.claude/settings.local.json`:

```json
{
  "hooks": {}
}
```

## Creating Custom Hooks

### Hook Input

Hooks receive JSON via stdin:

```json
{
  "session_id": "abc123",
  "hook_event_name": "SessionStart"
}
```

### Hook Output

- Print to stdout for context
- Print to stderr for warnings
- Always exit 0 (never block)

### Environment Variables

Available to all hooks:
- `CLAUDE_PROJECT_DIR` - Absolute path to project root

## Token Optimization

Keep output minimal to preserve context:

```python
# Good - minimal output
print("Session: active")

# Bad - verbose output
print("Session check complete. Session found at /path/to/session-abc123.md")
```
