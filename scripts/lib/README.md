# Shared Script Library

This directory contains reusable bash functions for Claude Forge scripts.

## common.sh

The `common.sh` library provides standardized functions for bash scripts.

### Usage

Source it at the beginning of your scripts:

```bash
#!/bin/bash
source "$(dirname "${BASH_SOURCE[0]}")/../lib/common.sh"
```

Or with auto-detection for flexible paths:

```bash
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
source "$SCRIPT_DIR/../lib/common.sh" 2>/dev/null || source "$SCRIPT_DIR/lib/common.sh"
```

---

## Available Functions

### Colors

| Variable | Color |
|----------|-------|
| `$RED` | Red |
| `$GREEN` | Green |
| `$YELLOW` | Yellow |
| `$BLUE` | Blue |
| `$CYAN` | Cyan |
| `$MAGENTA` | Magenta |
| `$WHITE` | White (bold) |
| `$BOLD` | Bold |
| `$DIM` | Dim |
| `$NC` | No color (reset) |

```bash
echo -e "${RED}Error${NC}"
echo -e "${GREEN}Success${NC}"
echo -e "${BOLD}Important${NC}"
```

### Logging

```bash
log_debug "Debug message"    # Only shown when LOG_LEVEL=0
log_info "Info message"      # Standard info (blue)
log_warn "Warning message"   # Warning to stderr (yellow)
log_error "Error message"    # Error to stderr (red)
log_success "Done!"          # Success with checkmark (green)
log_step "Processing..."     # Step indicator with arrow (cyan)
```

Control verbosity with `LOG_LEVEL`:
- `0` = DEBUG (all messages)
- `1` = INFO (default)
- `2` = WARN
- `3` = ERROR

### Dry-Run Support

All `safe_*` functions respect dry-run mode:

```bash
# Enable dry-run
DRY_RUN=1 ./my-script.sh
./my-script.sh --dry-run

# In scripts
parse_common_args "$@"  # Sets DRY_RUN from --dry-run flag

if is_dry_run; then
    echo "Would do something"
fi

# Safe file operations
safe_cp "$src" "$dst"        # Copy file
safe_mv "$src" "$dst"        # Move file
safe_rm "$target"            # Remove file/directory
safe_mkdir "$dir"            # Create directory
run_cmd some_command args    # Run arbitrary command
```

### Argument Parsing

```bash
parse_common_args "$@"

# Sets these variables:
# - DRY_RUN: 1 if --dry-run or -n passed
# - VERBOSE: 1 if --verbose or -v passed
# - QUIET: 1 if --quiet or -q passed
# - HELP: 1 if --help or -h passed
# - ARGS: array of remaining arguments
```

### Path Utilities

```bash
# Find Claude Forge root directory
FORGE_ROOT=$(find_forge_root)
CLAUDE_DIR=$(get_claude_dir)

# Resolve to absolute path
abs_path=$(resolve_path "./relative/path")
```

### JSON Utilities

Requires `jq` to be installed:

```bash
# Check if jq available
if has_jq; then
    # Extract from JSON string
    value=$(json_get "$json_string" ".path.to.value" "default")

    # Extract from JSON file
    version=$(json_file_get "package.json" ".version" "0.0.0")
fi
```

### Git Utilities

```bash
# Check if in git repo
if is_git_repo; then
    branch=$(git_branch)
    task_id=$(extract_task_from_branch)      # T015 from feat/T015-description
    ticket=$(extract_ticket_from_branch)     # PROJ-123 from feat/PROJ-123-desc
fi
```

### Platform Detection

```bash
# Get OS type
os=$(get_os)  # darwin, linux, windows

# Platform-safe sed in-place edit
sed_inplace "$file" "s/old/new/g"
```

### Validation

```bash
# Require commands
require_commands git jq python3 || exit 1

# Require files/directories
require_file "package.json" "Package file" || exit 1
require_dir ".claude" "Claude directory" || exit 1
```

### Backup Utilities

```bash
# Create timestamped backup
backup_path=$(create_backup ".claude" "./backups")
echo "Backup at: $backup_path"
```

### User Interaction

```bash
# Confirm with user (skipped in dry-run mode)
if confirm "Continue?" "y"; then
    echo "Proceeding..."
fi
```

### Formatting

```bash
# Print styled banner
print_banner "Claude Forge v2.0.0"

# Print section header
print_section "Step 1: Installing"
```

---

## Example Script

```bash
#!/bin/bash
set -e

source "$(dirname "${BASH_SOURCE[0]}")/../lib/common.sh"

# Parse arguments
parse_common_args "$@"

if [[ "$HELP" == "1" ]]; then
    echo "Usage: $(basename "$0") [options]"
    exit 0
fi

# Banner
print_banner "My Script v1.0"

if is_dry_run; then
    echo -e "${YELLOW}DRY RUN MODE${NC}"
fi

# Validate prerequisites
require_commands git || exit 1
require_dir ".claude" "Claude Forge" || exit 1

# Do work
print_section "Step 1: Processing"
log_step "Creating directory..."
safe_mkdir "output"

log_step "Copying files..."
safe_cp "source.txt" "output/source.txt"

log_success "Complete!"
```

---

## See Also

- [scripts/README.md](../README.md) - Full scripts documentation
