# Damage Control — Architecture

## Contents
- Security Philosophy: Defense in Depth, How It Works
- After Installation: Project Hooks, Global Hooks
- Integration with Claude Forge

## Security Philosophy

### Defense in Depth

```
Layer 1: Command Allowlist
         ↓ (only allowed commands pass)
Layer 2: Pattern Blocking (bashToolPatterns)
         ↓ (dangerous patterns blocked)
Layer 3: Path Protection
         ↓ (zeroAccess, readOnly, noDelete)
Layer 4: Special Validators
         ↓ (pkill, chmod, rm, curl, git)
Layer 5: Claude Code Sandbox
```

### How It Works

```
┌─────────────────────────────────────────────────────────────────────┐
│                   Claude Code Tool Call                              │
└─────────────────────────────────────────────────────────────────────┘
                                │
          ┌─────────────────────┼─────────────────────┐
          ▼                     ▼                     ▼
    ┌───────────┐         ┌───────────┐         ┌───────────┐
    │   Bash    │         │   Edit    │         │   Write   │
    │   Tool    │         │   Tool    │         │   Tool    │
    └─────┬─────┘         └─────┬─────┘         └─────┬─────┘
          │                     │                     │
          ▼                     ▼                     ▼
┌─────────────────┐   ┌─────────────────┐   ┌─────────────────┐
│ bash-tool-      │   │ edit-tool-      │   │ write-tool-     │
│ damage-control  │   │ damage-control  │   │ damage-control  │
│                 │   │                 │   │                 │
│ • Allowlist     │   │ • zeroAccess-   │   │ • zeroAccess-   │
│ • bashTool-     │   │   Paths         │   │   Paths         │
│   Patterns      │   │ • readOnlyPaths │   │ • readOnlyPaths │
│ • zeroAccess-   │   │                 │   │                 │
│   Paths         │   │                 │   │                 │
│ • readOnlyPaths │   │                 │   │                 │
│ • noDeletePaths │   │                 │   │                 │
│ • Validators    │   │                 │   │                 │
└────────┬────────┘   └────────┬────────┘   └────────┬────────┘
         │                     │                     │
         ▼                     ▼                     ▼
   exit 0 = allow        exit 0 = allow        exit 0 = allow
   exit 2 = BLOCK        exit 2 = BLOCK        exit 2 = BLOCK
   JSON   = ASK
```

## After Installation

### Project Hooks (Recommended)
```
<project-root>/
└── .claude/
    ├── settings.json            # Hook configuration (shared with team)
    └── hooks/
        └── damage-control/
            ├── patterns.yaml
            ├── bash-tool-damage-control.py
            ├── edit-tool-damage-control.py
            └── write-tool-damage-control.py
```

### Global Hooks (All Projects)
```
~/.claude/
├── settings.json                # Hook configuration
└── hooks/
    └── damage-control/
        ├── patterns.yaml
        ├── bash-tool-damage-control.py
        ├── edit-tool-damage-control.py
        └── write-tool-damage-control.py
```

## Integration with Claude Forge

### Complements Existing Security

This skill extends Claude Forge's existing security model:

- **`security/python/security.py`** - SDK-based allowlist (async Python)
- **`security/allowed-commands.md`** - Command allowlist documentation
- **`security/command-validators.md`** - Validator rules documentation
- **`rules/security.md`** - Quick reference rules

Damage Control adds:
- **PreToolUse hooks** - Real-time enforcement before tool execution
- **Pattern-based blocking** - Catch dangerous patterns within allowed commands
- **Path protection** - File-level access control

### Claude Forge-Specific Protections

The patterns.yaml includes protection for:
- `.claude/` directory (framework configuration)
- `docs/tasks/` and `docs/epics/` (task management)
- Session files and progress notes
- `registry.json` (task registry)
