# Modify Damage Control Workflow

This workflow guides modifications to the Damage Control security configuration.

## Modification Types

### 1. Add Zero-Access Path

**User says:** "Add ~/.secrets to zero access paths", "Block access to credentials.json"

**Action:**
1. Open `.claude/hooks/damage-control/patterns.yaml`
2. Add path to `zeroAccessPaths` section:
   ```yaml
   zeroAccessPaths:
     # ... existing paths ...
     - "~/.secrets/"
     - "credentials.json"
   ```

### 2. Add Read-Only Path

**User says:** "Make config/ read-only", "Don't let Claude modify the migrations folder"

**Action:**
1. Open `.claude/hooks/damage-control/patterns.yaml`
2. Add path to `readOnlyPaths` section:
   ```yaml
   readOnlyPaths:
     # ... existing paths ...
     - config/
     - migrations/
   ```

### 3. Add No-Delete Path

**User says:** "Protect the database folder from deletion", "Don't delete anything in data/"

**Action:**
1. Open `.claude/hooks/damage-control/patterns.yaml`
2. Add path to `noDeletePaths` section:
   ```yaml
   noDeletePaths:
     # ... existing paths ...
     - database/
     - data/
   ```

### 4. Add Blocked Command Pattern

**User says:** "Block the heroku command", "Don't allow npm publish"

**Action:**
1. Open `.claude/hooks/damage-control/patterns.yaml`
2. Add pattern to `bashToolPatterns` section:
   ```yaml
   bashToolPatterns:
     # ... existing patterns ...
     - pattern: '\bheroku\s+'
       reason: heroku commands blocked

     - pattern: '\bnpm\s+publish\b'
       reason: npm publish blocked
   ```

### 5. Add Ask Pattern (Confirmation Required)

**User says:** "Ask before running database migrations", "Confirm before npm run build"

**Action:**
1. Open `.claude/hooks/damage-control/patterns.yaml`
2. Add pattern with `ask: true`:
   ```yaml
   bashToolPatterns:
     # ... existing patterns ...
     - pattern: '\bnpm\s+run\s+migrate\b'
       reason: Database migration requires confirmation
       ask: true

     - pattern: '\bnpm\s+run\s+build\b'
       reason: Build command requires confirmation
       ask: true
   ```

### 6. Add Allowed Command

**User says:** "Allow the terraform command", "I need to use kubectl"

**Action:**
1. Open `.claude/hooks/damage-control/patterns.yaml`
2. Add command to `allowedCommands` section:
   ```yaml
   allowedCommands:
     # ... existing commands ...
     - terraform
     - kubectl
   ```

**Important:** Consider adding appropriate patterns to block dangerous subcommands:
```yaml
bashToolPatterns:
  - pattern: '\bterraform\s+destroy\b'
    reason: terraform destroy requires manual execution

  - pattern: '\bkubectl\s+delete\s+namespace\b'
    reason: namespace deletion blocked
```

### 7. Add Special Validator Process

**User says:** "Allow pkill for postgres", "Let me kill docker processes"

**Action:**
1. Open `.claude/hooks/damage-control/patterns.yaml`
2. Add to `specialValidators.pkill.allowedProcesses`:
   ```yaml
   specialValidators:
     pkill:
       allowedProcesses:
         # ... existing processes ...
         - postgres
         - docker
   ```

## Path Pattern Syntax

### Literal Paths
```yaml
- ~/.ssh/           # Directory (trailing slash)
- /etc/passwd       # Specific file
- .env              # File in any directory
```

### Glob Patterns
```yaml
- "*.pem"           # All .pem files
- ".env.*"          # All .env.* files
- "*-secret.yaml"   # Files ending in -secret.yaml
```

## Regex Pattern Syntax

Patterns use Python regex. Common elements:
- `\b` - Word boundary
- `\s+` - One or more whitespace
- `.*` - Any characters
- `(?!...)` - Negative lookahead

**Examples:**
```yaml
# Block rm -rf but allow rm
- pattern: '\brm\s+-[rRf]'
  reason: rm with dangerous flags

# Block git push --force but allow --force-with-lease
- pattern: '\bgit\s+push\s+.*--force(?!-with-lease)'
  reason: force push blocked (use --force-with-lease)

# Block DELETE without WHERE
- pattern: 'DELETE\s+FROM\s+\w+\s*;'
  reason: DELETE without WHERE clause
```

## After Modification

Changes take effect immediately - no restart required.

Test your changes:
```bash
# For command patterns:
echo '{"tool_name":"Bash","tool_input":{"command":"your-test-command"}}' | \
  uv run .claude/hooks/damage-control/bash-tool-damage-control.py

# For path protection:
echo '{"tool_name":"Edit","tool_input":{"file_path":"/path/to/test"}}' | \
  uv run .claude/hooks/damage-control/edit-tool-damage-control.py
```
