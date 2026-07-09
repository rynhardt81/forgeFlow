# List Damage Controls Workflow

This workflow displays the current damage control configuration.

## Display Configuration

Read and parse `.claude/hooks/damage-control/patterns.yaml` and present:

### 1. Allowed Commands

```markdown
## Allowed Commands (Allowlist)

Commands that can be executed (all others blocked):

**File Operations:** ls, cat, head, tail, wc, grep, find, cp, mkdir, chmod, mv, rm, touch
**Node.js:** npm, npx, pnpm, bun, node, tsx, ts-node
**Python:** python, python3, pip, pip3, uv, poetry, pytest
**Git:** git
**Containers:** docker, docker-compose
**Process:** ps, lsof, sleep, kill, pkill
**Network:** curl
**Build:** make, vite, webpack, esbuild, rollup
**Testing:** jest, vitest, mocha
**Linting:** eslint, prettier, tsc, biome
```

### 2. Blocked Patterns

```markdown
## Blocked Command Patterns

Even allowed commands are blocked if they match these patterns:

| Pattern | Reason | Action |
|---------|--------|--------|
| `rm -rf`, `rm -r` | Recursive deletion | BLOCK |
| `git reset --hard` | Destroys uncommitted changes | BLOCK |
| `git push --force` | Overwrites remote history | BLOCK |
| `chmod 777` | World writable permissions | BLOCK |
| `terraform destroy` | Infrastructure destruction | BLOCK |
| `DROP TABLE`, `DROP DATABASE` | Database destruction | BLOCK |
| `git stash drop` | Deletes stash | ASK |
| `git branch -D` | Force delete branch | ASK |
| `DELETE FROM ... WHERE id=` | Targeted deletion | ASK |
```

### 3. Protected Paths

```markdown
## Path Protection

### Zero-Access (No Operations Allowed)
These files/directories cannot be read, written, edited, or deleted:

- `.env`, `.env.*` - Environment files with secrets
- `~/.ssh/` - SSH keys
- `~/.aws/`, `~/.config/gcloud/`, `~/.azure/` - Cloud credentials
- `*.pem`, `*.key` - SSL/TLS certificates
- `*.tfstate` - Terraform state (contains secrets)
- `~/.npmrc`, `~/.pypirc` - Package manager auth

### Read-Only (Read Allowed, No Modifications)
These can be read but not modified:

- `/etc/`, `/usr/`, `/bin/` - System directories
- `~/.bashrc`, `~/.zshrc` - Shell config
- `package-lock.json`, `yarn.lock`, `*.lock` - Lock files
- `node_modules/`, `dist/`, `build/` - Generated directories
- `.git/` - Git internals

### No-Delete (Read/Write Allowed, No Delete)
These can be modified but not deleted:

- `.claude/`, `CLAUDE.md` - Framework files
- `docs/tasks/`, `docs/epics/` - Task management
- `LICENSE`, `README.md` - Documentation
- `.github/`, `.gitignore` - Git/CI configuration
- `Dockerfile`, `docker-compose.yml` - Container config
- `security/` - Security configuration
```

### 4. Special Validators

```markdown
## Special Validators

### pkill
Only these processes can be killed:
- node, npm, npx, pnpm
- vite, next, webpack
- jest, vitest, pytest

### chmod
Only these modes allowed:
- `+x`, `u+x`, `g+x`, `a+x` (make executable)

### curl
Blocked:
- `file://` protocol
- `--upload-file`, `-T` flags
```

## Output Format

When user asks "list damage control settings", output the above sections formatted as markdown tables where appropriate.

## Configuration File Location

Report where the configuration is loaded from:
- Project: `.claude/hooks/damage-control/patterns.yaml`
- Global: `~/.claude/hooks/damage-control/patterns.yaml`
- Skill (development): `.claude/skills/damage-control/patterns.yaml`
