#!/bin/bash
# common.sh - Shared functions for Claude Forge scripts
#
# Source this file at the start of any script:
#   source "$(dirname "${BASH_SOURCE[0]}")/../lib/common.sh"
#
# Or with auto-detection:
#   SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
#   source "$SCRIPT_DIR/../lib/common.sh" 2>/dev/null || source "$SCRIPT_DIR/lib/common.sh"

# ============================================================================
# COLORS
# ============================================================================

export RED='\033[0;31m'
export GREEN='\033[0;32m'
export YELLOW='\033[1;33m'
export BLUE='\033[0;34m'
export MAGENTA='\033[0;35m'
export CYAN='\033[0;36m'
export WHITE='\033[1;37m'
export NC='\033[0m' # No Color
export BOLD='\033[1m'
export DIM='\033[2m'

# ============================================================================
# LOGGING
# ============================================================================

# Log levels: DEBUG=0, INFO=1, WARN=2, ERROR=3
LOG_LEVEL=${LOG_LEVEL:-1}

log_debug() {
    [[ $LOG_LEVEL -le 0 ]] && echo -e "${DIM}[DEBUG]${NC} $*" >&2
}

log_info() {
    [[ $LOG_LEVEL -le 1 ]] && echo -e "${CYAN}[INFO]${NC} $*"
}

log_warn() {
    [[ $LOG_LEVEL -le 2 ]] && echo -e "${YELLOW}[WARN]${NC} $*" >&2
}

log_error() {
    [[ $LOG_LEVEL -le 3 ]] && echo -e "${RED}[ERROR]${NC} $*" >&2
}

log_success() {
    echo -e "${GREEN}✓${NC} $*"
}

log_step() {
    echo -e "${CYAN}▸${NC} $*"
}

# ============================================================================
# DRY RUN SUPPORT
# ============================================================================

# Set DRY_RUN=1 or pass --dry-run to enable
DRY_RUN=${DRY_RUN:-0}

# Check if dry run mode is enabled
is_dry_run() {
    [[ "$DRY_RUN" == "1" || "$DRY_RUN" == "true" ]]
}

# Execute command or show what would be done in dry run mode
run_cmd() {
    if is_dry_run; then
        echo -e "${DIM}[DRY-RUN] Would execute:${NC} $*"
        return 0
    else
        "$@"
    fi
}

# Copy file with dry run support
safe_cp() {
    local src="$1"
    local dst="$2"
    if is_dry_run; then
        echo -e "${DIM}[DRY-RUN] Would copy:${NC} $src → $dst"
    else
        cp "$src" "$dst"
    fi
}

# Move file with dry run support
safe_mv() {
    local src="$1"
    local dst="$2"
    if is_dry_run; then
        echo -e "${DIM}[DRY-RUN] Would move:${NC} $src → $dst"
    else
        mv "$src" "$dst"
    fi
}

# Remove file with dry run support
safe_rm() {
    local target="$1"
    if is_dry_run; then
        echo -e "${DIM}[DRY-RUN] Would remove:${NC} $target"
    else
        rm -rf "$target"
    fi
}

# Create directory with dry run support
safe_mkdir() {
    local dir="$1"
    if is_dry_run; then
        echo -e "${DIM}[DRY-RUN] Would create directory:${NC} $dir"
    else
        mkdir -p "$dir"
    fi
}

# ============================================================================
# ARGUMENT PARSING
# ============================================================================

# Parse common arguments from $@
# Sets: DRY_RUN, VERBOSE, HELP, remaining args in ARGS array
parse_common_args() {
    ARGS=()
    while [[ $# -gt 0 ]]; do
        case "$1" in
            --dry-run|-n)
                DRY_RUN=1
                shift
                ;;
            --verbose|-v)
                LOG_LEVEL=0
                VERBOSE=1
                shift
                ;;
            --quiet|-q)
                LOG_LEVEL=3
                QUIET=1
                shift
                ;;
            --help|-h)
                HELP=1
                shift
                ;;
            --)
                shift
                ARGS+=("$@")
                break
                ;;
            *)
                ARGS+=("$1")
                shift
                ;;
        esac
    done
}

# ============================================================================
# PATH UTILITIES
# ============================================================================

# Find Claude Forge root directory (contains CLAUDE.md or .claude/CLAUDE.md)
find_forge_root() {
    local dir="${1:-$(pwd)}"
    while [[ "$dir" != "/" ]]; do
        if [[ -f "$dir/CLAUDE.md" ]] || [[ -f "$dir/.claude/CLAUDE.md" ]]; then
            echo "$dir"
            return 0
        fi
        dir="$(dirname "$dir")"
    done
    return 1
}

# Get the .claude directory path
get_claude_dir() {
    local root
    root=$(find_forge_root "$1") || return 1
    if [[ -f "$root/.claude/CLAUDE.md" ]]; then
        echo "$root/.claude"
    else
        echo "$root"
    fi
}

# Resolve path to absolute
resolve_path() {
    local path="$1"
    if [[ -d "$path" ]]; then
        (cd "$path" && pwd)
    elif [[ -f "$path" ]]; then
        echo "$(cd "$(dirname "$path")" && pwd)/$(basename "$path")"
    else
        echo "$path"
    fi
}

# ============================================================================
# JSON UTILITIES (requires jq)
# ============================================================================

# Check if jq is available
has_jq() {
    command -v jq &>/dev/null
}

# Safe JSON extraction with fallback
json_get() {
    local json="$1"
    local path="$2"
    local default="${3:-}"

    if has_jq; then
        local result
        result=$(echo "$json" | jq -r "$path" 2>/dev/null)
        if [[ "$result" == "null" || -z "$result" ]]; then
            echo "$default"
        else
            echo "$result"
        fi
    else
        echo "$default"
    fi
}

# Read JSON file and extract value
json_file_get() {
    local file="$1"
    local path="$2"
    local default="${3:-}"

    if [[ ! -f "$file" ]]; then
        echo "$default"
        return
    fi

    json_get "$(cat "$file")" "$path" "$default"
}

# ============================================================================
# GIT UTILITIES
# ============================================================================

# Check if current directory is a git repository
is_git_repo() {
    git rev-parse --git-dir &>/dev/null
}

# Get current git branch name
git_branch() {
    git branch --show-current 2>/dev/null
}

# Extract task ID from branch name (e.g., feat/T015-description → T015)
extract_task_from_branch() {
    local branch="${1:-$(git_branch)}"
    if [[ "$branch" =~ (T[0-9]+) ]]; then
        echo "${BASH_REMATCH[1]}"
    fi
}

# Extract ticket ID from branch name (e.g., feat/PROJ-123-description → PROJ-123)
extract_ticket_from_branch() {
    local branch="${1:-$(git_branch)}"
    if [[ "$branch" =~ ([A-Z]+-[0-9]+) ]]; then
        echo "${BASH_REMATCH[1]}"
    fi
}

# ============================================================================
# PLATFORM DETECTION
# ============================================================================

# Get OS type: darwin, linux, windows
get_os() {
    case "$OSTYPE" in
        darwin*) echo "darwin" ;;
        linux*) echo "linux" ;;
        msys*|cygwin*|mingw*) echo "windows" ;;
        *) echo "unknown" ;;
    esac
}

# Platform-safe sed in-place edit
sed_inplace() {
    local file="$1"
    shift
    if [[ "$(get_os)" == "darwin" ]]; then
        sed -i '' "$@" "$file"
    else
        sed -i "$@" "$file"
    fi
}

# ============================================================================
# VALIDATION
# ============================================================================

# Check required commands exist
require_commands() {
    local missing=()
    for cmd in "$@"; do
        if ! command -v "$cmd" &>/dev/null; then
            missing+=("$cmd")
        fi
    done

    if [[ ${#missing[@]} -gt 0 ]]; then
        log_error "Required commands not found: ${missing[*]}"
        return 1
    fi
}

# Validate file exists
require_file() {
    local file="$1"
    local desc="${2:-File}"
    if [[ ! -f "$file" ]]; then
        log_error "$desc not found: $file"
        return 1
    fi
}

# Validate directory exists
require_dir() {
    local dir="$1"
    local desc="${2:-Directory}"
    if [[ ! -d "$dir" ]]; then
        log_error "$desc not found: $dir"
        return 1
    fi
}

# ============================================================================
# BACKUP UTILITIES
# ============================================================================

# Create timestamped backup of file or directory
create_backup() {
    local source="$1"
    local backup_dir="${2:-./backups}"
    local timestamp
    timestamp=$(date +%Y%m%d-%H%M%S)

    local backup_path="$backup_dir/$timestamp"
    safe_mkdir "$backup_path"

    if is_dry_run; then
        echo -e "${DIM}[DRY-RUN] Would backup:${NC} $source → $backup_path"
    else
        if [[ -d "$source" ]]; then
            cp -r "$source" "$backup_path/"
        else
            cp "$source" "$backup_path/"
        fi
        log_success "Backup created: $backup_path"
    fi

    echo "$backup_path"
}

# ============================================================================
# USER INTERACTION
# ============================================================================

# Confirm action with user
confirm() {
    local prompt="${1:-Continue?}"
    local default="${2:-n}"

    if is_dry_run; then
        log_debug "Skipping confirmation in dry run mode"
        return 0
    fi

    local yn
    if [[ "$default" == "y" ]]; then
        read -p "$prompt [Y/n] " -n 1 -r yn
    else
        read -p "$prompt [y/N] " -n 1 -r yn
    fi
    echo

    if [[ "$default" == "y" ]]; then
        [[ ! $yn =~ ^[Nn]$ ]]
    else
        [[ $yn =~ ^[Yy]$ ]]
    fi
}

# ============================================================================
# BANNER/FORMATTING
# ============================================================================

# Print a styled banner
print_banner() {
    local title="$1"
    local width="${2:-65}"
    local char="${3:-═}"

    local line
    line=$(printf "%${width}s" | tr ' ' "$char")

    echo -e "${CYAN}╔${line}╗${NC}"
    printf "${CYAN}║${NC} %-$((width-2))s ${CYAN}║${NC}\n" "$title"
    echo -e "${CYAN}╚${line}╝${NC}"
}

# Print a section header
print_section() {
    local title="$1"
    echo ""
    echo -e "${CYAN}═══════════════════════════════════════════════════════════════${NC}"
    echo -e "${CYAN}$title${NC}"
    echo -e "${CYAN}═══════════════════════════════════════════════════════════════${NC}"
}
