---
name: damage-control
description: Install, configure, and manage Claude Code security hooks. Blocks dangerous commands, protects sensitive files, and provides defense-in-depth protection via PreToolUse hooks. Use when user mentions damage control, security hooks, protected paths, blocked commands, or install security.
---

## Quick Scan

| | |
|---|---|
| **Purpose** | Install and manage security hooks for defense-in-depth protection |
| **Inputs** | Action (install/modify/test/list), optional path/command targets |
| **Output** | Configured hooks, patterns.yaml, protected paths/commands |
| **Flow** | Detect intent → Route to cookbook → Execute workflow |

---

# Damage Control Skill

Defense-in-depth protection system for Claude Code. Combines Claude Forge's allowlist approach with pattern-based blocking and path protection via PreToolUse hooks.

> **Attribution:** Based on [claude-code-damage-control](https://github.com/disler/claude-code-damage-control) by [IndyDevDan](https://github.com/disler). Adapted and integrated with Claude Forge's security model.

## Overview

This skill helps deploy and manage the Damage Control security system, which provides:

- **Allowlist Enforcement**: Only explicitly permitted commands can run (deny by default)
- **Pattern Blocking**: Regex patterns block dangerous commands even if base command is allowed
- **Ask Patterns**: Triggers confirmation dialog for risky-but-valid operations (`ask: true`)
- **Path Protection Levels**:
  - `zeroAccessPaths` - No access at all (secrets/credentials)
  - `readOnlyPaths` - Read allowed, modifications blocked
  - `noDeletePaths` - All operations except delete

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

## Skill Structure

```
skills/damage-control/           # In Claude Forge framework root
├── SKILL.md                     # This file
├── patterns.yaml                # Security patterns (single source of truth)
├── cookbook/
│   ├── install_damage_control.md
│   ├── modify_damage_control.md
│   ├── test_damage_control.md
│   └── list_damage_controls.md
├── hooks/
│   └── damage-control-python/   # Python/UV implementation
│       ├── bash-tool-damage-control.py
│       ├── edit-tool-damage-control.py
│       ├── write-tool-damage-control.py
│       └── settings-template.json
└── test-prompts/                # Test prompts for validation
    ├── README.md
    └── sentient.md
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

---

## Cookbook

This section defines the decision tree for handling user requests.

### Installation Pathway

**Trigger phrases**: "install damage control", "setup security hooks", "deploy damage control", "add protection", "/damage-control install"

**Workflow**: Read and execute [cookbook/install_damage_control.md](cookbook/install_damage_control.md)

### Modification Pathway

**Trigger phrases**: "help me modify damage control", "update protection", "change blocked paths", "add restricted directory"

**Workflow**: Read and execute [cookbook/modify_damage_control.md](cookbook/modify_damage_control.md)

### Testing Pathway

**Trigger phrases**: "test damage control", "run damage control tests", "verify hooks are working"

**Workflow**: Read and execute [cookbook/test_damage_control.md](cookbook/test_damage_control.md)

### List Configuration Pathway

**Trigger phrases**: "list damage control settings", "show protected paths", "what commands are blocked"

**Workflow**: Read and execute [cookbook/list_damage_controls.md](cookbook/list_damage_controls.md)

### Direct Command Pathway

**Trigger phrases**: "add ~/.secrets to zero access paths", "block command Y", "update allowlist"

**Action**: Execute immediately without prompts - the user knows the system.

---

## Quick Reference

### Path Protection Levels

| Type              | Read | Write | Edit | Delete | Use Case                |
| ----------------- | ---- | ----- | ---- | ------ | ----------------------- |
| `zeroAccessPaths` | No   | No    | No   | No     | Secrets, credentials    |
| `readOnlyPaths`   | Yes  | No    | No   | No     | System configs, locks   |
| `noDeletePaths`   | Yes  | Yes   | Yes  | No     | Important project files |

### Exit Codes

| Code | Meaning                              |
| ---- | ------------------------------------ |
| 0    | Allow operation                      |
| 0    | Ask (JSON output triggers dialog)    |
| 2    | Block operation                      |

### Runtime Requirements

| Implementation | Runtime     | Install Command                                    |
| -------------- | ----------- | -------------------------------------------------- |
| Python         | UV (Astral) | `curl -LsSf https://astral.sh/uv/install.sh \| sh` |

---

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

---

## Related Files

- [cookbook/install_damage_control.md](cookbook/install_damage_control.md) - Installation workflow
- [cookbook/modify_damage_control.md](cookbook/modify_damage_control.md) - Modification workflow
- [cookbook/test_damage_control.md](cookbook/test_damage_control.md) - Testing workflow
- [cookbook/list_damage_controls.md](cookbook/list_damage_controls.md) - List configuration
- [hooks/damage-control-python/](hooks/damage-control-python/) - Python implementation
- [reference/08-security-model.template.md](../../reference/08-security-model.template.md) - Security architecture

---

## See Also

- [security/README.md](../../security/README.md) - Security model overview
- [security/allowed-commands.md](../../security/allowed-commands.md) - Allowlist
- [security/command-validators.md](../../security/command-validators.md) - Validators
- [rules/security.md](../../rules/security.md) - Security rules
