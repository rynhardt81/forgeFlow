# Install Damage Control Workflow

This workflow guides installation of the Damage Control security hooks.

## Prerequisites

1. **UV (Python runtime)** - Required for running the hooks
   ```bash
   curl -LsSf https://astral.sh/uv/install.sh | sh
   ```

## Installation Steps

### Step 1: Determine Installation Level

Use `AskUserQuestion` to determine where to install:

```
Question: "Where should I install the damage control hooks?"
Options:
  - "Project (Recommended)" - Install in current project's .claude/ directory
  - "Global" - Install in ~/.claude/ for all projects
  - "Project Personal" - Install in .claude/ but gitignored (settings.local.json)
```

### Step 2: Check for Existing Configuration

Check if settings already exist:
- **Project**: `.claude/settings.json`
- **Global**: `~/.claude/settings.json`
- **Personal**: `.claude/settings.local.json`

If exists, ask user how to proceed:
```
Question: "Existing settings found. How should I proceed?"
Options:
  - "Merge" - Add hooks to existing configuration
  - "Replace" - Replace entire hooks section
  - "Cancel" - Abort installation
```

### Step 3: Create Hooks Directory

Based on installation level:

**Project:**
```bash
mkdir -p .claude/hooks/damage-control
```

**Global:**
```bash
mkdir -p ~/.claude/hooks/damage-control
```

### Step 4: Copy Hook Files

Copy from skill directory to installation location:

```bash
# For project installation (skill is at root of Claude Forge framework):
cp skills/damage-control/hooks/damage-control-python/*.py .claude/hooks/damage-control/
cp skills/damage-control/patterns.yaml .claude/hooks/damage-control/
```

**Note:** The `skills/` directory is at the root of the Claude Forge framework. When the framework is installed, it becomes the project's `.claude/` directory.

### Step 5: Create/Update Settings

**For new installation (settings.json):**
```json
{
  "hooks": {
    "PreToolUse": [
      {
        "matcher": "Bash",
        "hooks": [{
          "type": "command",
          "command": "uv run \"$CLAUDE_PROJECT_DIR\"/.claude/hooks/damage-control/bash-tool-damage-control.py",
          "timeout": 5
        }]
      },
      {
        "matcher": "Edit",
        "hooks": [{
          "type": "command",
          "command": "uv run \"$CLAUDE_PROJECT_DIR\"/.claude/hooks/damage-control/edit-tool-damage-control.py",
          "timeout": 5
        }]
      },
      {
        "matcher": "Write",
        "hooks": [{
          "type": "command",
          "command": "uv run \"$CLAUDE_PROJECT_DIR\"/.claude/hooks/damage-control/write-tool-damage-control.py",
          "timeout": 5
        }]
      }
    ]
  }
}
```

**For global installation, replace `$CLAUDE_PROJECT_DIR` with `$HOME`:**
```json
"command": "uv run \"$HOME\"/.claude/hooks/damage-control/bash-tool-damage-control.py"
```

### Step 6: Verify Installation

1. Restart Claude Code for hooks to take effect
2. Test with a blocked command:
   ```
   rm -rf /tmp/test
   ```
   Should see: "SECURITY: Blocked: rm with recursive or force flags"

### Step 7: Report Success

```
Damage Control installed successfully!

Location: [project/global/personal]
Hooks installed:
  - bash-tool-damage-control.py (Bash commands)
  - edit-tool-damage-control.py (Edit tool)
  - write-tool-damage-control.py (Write tool)

Protected paths configured:
  - Zero-access: .env, ~/.ssh/, credentials files
  - Read-only: lock files, node_modules/, build artifacts
  - No-delete: .claude/, LICENSE, README.md

To test: Try running a dangerous command like "rm -rf /tmp"
To modify: Edit .claude/hooks/damage-control/patterns.yaml
```

## Troubleshooting

### "Hook not firing"
1. Restart Claude Code
2. Check `/hooks` command to verify registration
3. Validate JSON: `cat .claude/settings.json | jq .`

### "UV not found"
Install UV:
```bash
curl -LsSf https://astral.sh/uv/install.sh | sh
```

### "Permission denied"
Make hooks executable:
```bash
chmod +x .claude/hooks/damage-control/*.py
```
