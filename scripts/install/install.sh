#!/bin/bash
#
# Claude Forge — Unified Installer
#
# Interactive installer that handles every install scenario from a single
# entry point:
#
#   • Fresh install      — new project, no existing .claude/
#   • Full install       — overwrite .claude/ with a backup to .claude_old/
#   • Refresh framework  — re-copy framework files, preserve user content
#   • Refresh v3         — additive Forge Flow v3 upgrade (NEW): drops in v3
#                          framework surfaces, removes legacy .claude/cross-repo/
#                          (backed up), preserves all user content, then runs
#                          verify.sh --fix to auto-fix trivial drift.
#
# Run from the forgeFlow repository root:
#
#   ./scripts/install/install.sh                 # interactive
#   ./scripts/install/install.sh /path/to/proj   # interactive, preset path
#
# Non-interactive flags (skip menu/confirm prompts):
#   --mode <full|refresh|refresh-v3>             # preset install mode
#   --yes, -y                                    # auto-confirm "Proceed?"
#   --backup                                     # force backup ON (default)
#   --no-backup                                  # skip the pre-refresh snapshot
#
# Backup behavior:
#   refresh / refresh-v3 modes back up the existing .claude/ to
#   backups/<timestamp>/ before overwriting framework files. This is the
#   default and the only way to roll back the refresh in place.
#   Pass --no-backup to skip the snapshot (faster but irreversible).
#   Interactive runs prompt for the choice when an existing .claude/ is found.
#
# Examples:
#   # Refresh framework files in a project, no prompts:
#   ./scripts/install/install.sh --mode refresh --yes /path/to/proj
#
#   # Upgrade a v2.x project to Forge Flow v3:
#   ./scripts/install/install.sh --mode refresh-v3 --yes /path/to/proj
#
#   # Refresh-v3 without backup (faster, irreversible):
#   ./scripts/install/install.sh --mode refresh-v3 --yes --no-backup /path/to/proj
#

set -e

RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
CYAN='\033[0;36m'
BOLD='\033[1m'
NC='\033[0m'

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
FRAMEWORK_DIR="$(cd "$SCRIPT_DIR/../.." && pwd)"
BACKUP_TIMESTAMP="$(date +%Y%m%d-%H%M%S)"

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

banner() {
    echo -e "${CYAN}"
    echo "╔═══════════════════════════════════════════════════════════════╗"
    echo "║              Claude Forge — Unified Installer                  ║"
    echo "╚═══════════════════════════════════════════════════════════════╝"
    echo -e "${NC}"
}

ok()    { echo -e "${GREEN}✓${NC} $1"; }
warn()  { echo -e "${YELLOW}⚠${NC} $1"; }
fail()  { echo -e "${RED}✗${NC} $1"; }
step()  { echo -e "${BLUE}▸${NC} $1"; }

# ---------------------------------------------------------------------------
# Visual progress helpers (TTY only; no-ops in CI / pipes)
# ---------------------------------------------------------------------------

PHASES_TOTAL=0
PHASES_DONE=0
INSTALL_START_TIME=$(date +%s)

set_phases() { PHASES_TOTAL="$1"; PHASES_DONE=0; }

# section() prefixed with a phase counter when set_phases has been called.
# Falls back to the unnumbered banner otherwise.
section() {
    PHASES_DONE=$((PHASES_DONE + 1))
    echo ""
    echo -e "${CYAN}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
    if [ "$PHASES_TOTAL" -gt 0 ]; then
        echo -e "${CYAN}${BOLD}[$PHASES_DONE/$PHASES_TOTAL]${NC} ${CYAN}${BOLD}$1${NC}"
    else
        echo -e "${CYAN}${BOLD}$1${NC}"
    fi
    echo -e "${CYAN}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
}

# with_spinner "label" cmd args...
# Runs cmd in background and shows a spinner with elapsed seconds. Falls back
# to plain run on non-TTY or when NO_SPINNER=1.
with_spinner() {
    local label="$1"; shift
    if [ "${NO_SPINNER:-0}" = "1" ] || [ ! -t 1 ]; then
        echo -e "  ${BLUE}▸${NC} $label"
        "$@"
        return $?
    fi

    local frames='⠋⠙⠹⠸⠼⠴⠦⠧⠇⠏'
    local idx=0 start
    start=$(date +%s)

    "$@" &
    local pid=$!

    while kill -0 "$pid" 2>/dev/null; do
        local frame="${frames:$idx:1}"
        local elapsed=$(( $(date +%s) - start ))
        printf "\r  ${CYAN}%s${NC} %s ${YELLOW}(%ds)${NC}    " "$frame" "$label" "$elapsed"
        idx=$(( (idx + 1) % ${#frames} ))
        sleep 0.1
    done

    wait "$pid"; local rc=$?
    local elapsed=$(( $(date +%s) - start ))
    printf "\r"
    if [ "$rc" -eq 0 ]; then
        printf "  ${GREEN}✓${NC} %s ${YELLOW}(%ds)${NC}\n" "$label" "$elapsed"
    else
        printf "  ${RED}✗${NC} %s ${YELLOW}(%ds, exit %d)${NC}\n" "$label" "$elapsed" "$rc"
    fi
    return "$rc"
}

# Detect rsync's progress capability once. Sets RSYNC_PROGRESS_FLAGS to:
#   "--info=progress2 --no-i-r"  for rsync 3.1.0+ (live single-line progress)
#   ""                          for rsync 2.x / openrsync (no progress flags;
#                                rsync_visual will wrap the silent call in a
#                                spinner instead).
RSYNC_PROGRESS_FLAGS=""
RSYNC_VERSION_LABEL=""

detect_rsync_progress() {
    local raw ver major minor
    raw=$(rsync --version 2>/dev/null | head -1)
    # Match standard rsync ("rsync  version 3.2.7 ...") and openrsync
    # ("openrsync: protocol version 29 ... rsync version 2.6.9 compatible").
    ver=$(echo "$raw" | grep -oE 'rsync.{0,15}version *[0-9]+\.[0-9]+\.[0-9]+' | grep -oE '[0-9]+\.[0-9]+\.[0-9]+' | head -1)
    RSYNC_VERSION_LABEL="$raw"
    if [ -z "$ver" ]; then
        return
    fi
    IFS=. read -r major minor _ <<< "$ver"
    if [ "${major:-0}" -ge 4 ] || { [ "${major:-0}" -eq 3 ] && [ "${minor:-0}" -ge 1 ]; }; then
        RSYNC_PROGRESS_FLAGS="--info=progress2 --no-i-r"
    fi
}

# rsync_visual ...args (same args as plain rsync, minus -a which we add)
# Tier 1 (rsync 3.1+): live --info=progress2 progress bar.
# Tier 2 (legacy / openrsync): silent rsync wrapped in a spinner.
# Tier 3 (NO_PROGRESS=1 or non-TTY): plain rsync -a, no decoration.
rsync_visual() {
    if [ "${NO_PROGRESS:-0}" = "1" ] || [ ! -t 1 ]; then
        rsync -a "$@"
        return $?
    fi
    if [ -n "$RSYNC_PROGRESS_FLAGS" ]; then
        rsync -a $RSYNC_PROGRESS_FLAGS "$@" | \
            awk '{ printf "\r  %s    ", $0; fflush() }
                 END { printf "\n" }'
        return "${PIPESTATUS[0]}"
    fi
    # Legacy rsync — show a spinner so user knows it's working.
    with_spinner "Copying files (rsync — legacy, no live progress)" \
        rsync -a "$@"
    return $?
}

backup_path() { echo "$PROJECT_DIR/.claude/backups/$BACKUP_TIMESTAMP"; }

# Default: backups enabled. Set BACKUP_ENABLED=0 (or pass --no-backup) to skip.
BACKUP_ENABLED=1

backup_file() {
    local src="$1"
    [ -e "$src" ] || return 0
    if [ "$BACKUP_ENABLED" = "0" ]; then
        return 0
    fi
    local dest_root
    dest_root="$(backup_path)"
    mkdir -p "$dest_root"
    local rel="${src#$PROJECT_DIR/}"
    local dest="$dest_root/$rel"
    mkdir -p "$(dirname "$dest")"
    if [ -d "$src" ]; then
        # Directory snapshot: exclude the backups/ tree itself (avoids
        # embedding every prior snapshot plus racing this in-progress copy)
        # and other heavyweight machine-local dirs that don't belong in a
        # portable snapshot.
        rsync -a \
            --exclude='backups' \
            --exclude='worktrees' \
            --exclude='.venv' \
            --exclude='__pycache__' \
            --exclude='.pytest_cache' \
            --exclude='.forge/venv' \
            --exclude='node_modules' \
            --exclude='.DS_Store' \
            "$src/" "$dest/"
    else
        cp "$src" "$dest"
    fi
    BACKUPS_CREATED=$((BACKUPS_CREATED + 1))
    prune_old_backups
}

# Keep only the 5 newest timestamped snapshot dirs directly under
# .claude/backups/ (lexicographic sort == chronological for the
# YYYYMMDD-HHMMSS pattern). 5 is a deliberate hardcode for the solo-dev
# default; make it a flag only if someone actually asks for more history.
prune_old_backups() {
    local backups_root="$PROJECT_DIR/.claude/backups"
    [ -d "$backups_root" ] || return 0
    local entries=()
    local entry base
    for entry in "$backups_root"/*; do
        [ -d "$entry" ] || continue
        base="$(basename "$entry")"
        case "$base" in
            [0-9][0-9][0-9][0-9][0-9][0-9][0-9][0-9]-[0-9][0-9][0-9][0-9][0-9][0-9])
                entries+=("$base")
                ;;
            *)
                ;;
        esac
    done
    local count="${#entries[@]}"
    [ "$count" -gt 5 ] || return 0
    local sorted
    IFS=$'\n' sorted=($(sort <<<"${entries[*]}"))
    unset IFS
    local to_remove=$((count - 5))
    local i pruned=0
    for ((i = 0; i < to_remove; i++)); do
        rm -rf -- "$backups_root/${sorted[$i]}"
        pruned=$((pruned + 1))
    done
    [ "$pruned" -gt 0 ] && ok "Pruned $pruned old backup snapshot(s) (keep-last-5)"
}

# Seed scripts/preflight/_local_shims.sh into the consumer project on first
# install only. The rsync step excludes this path so we never trample a
# project-extended copy on subsequent refreshes; this function fills the gap
# when the file is genuinely missing.
seed_preflight_shim_if_missing() {
    local claude_dir="$1"
    local target="$claude_dir/scripts/preflight/_local_shims.sh"
    local source="$FRAMEWORK_DIR/scripts/preflight/_local_shims.sh"
    [ -f "$target" ] && return 0
    [ -f "$source" ] || return 0
    mkdir -p "$(dirname "$target")"
    cp "$source" "$target"
    chmod +x "$target"
    ok "Seeded preflight portability shim (project-local, survives refresh)"
}

# ---------------------------------------------------------------------------
# Preflight
# ---------------------------------------------------------------------------

preflight() {
    section "Preflight"
    local failed=0

    if command -v python3 >/dev/null 2>&1; then
        local ver ok_py
        ver=$(python3 -c 'import sys; print(f"{sys.version_info.major}.{sys.version_info.minor}")')
        ok_py=$(python3 -c 'import sys; print(1 if sys.version_info >= (3, 10) else 0)')
        if [ "$ok_py" = "1" ]; then
            ok "python3 $ver (>=3.10 required)"
        else
            fail "python3 $ver found, but 3.10+ is required"
            failed=1
        fi
    else
        fail "python3 not found on PATH — settings.json merge and forge scripts will not run"
        failed=1
    fi

    if command -v claude >/dev/null 2>&1; then
        ok "claude CLI found ($(command -v claude))"
    else
        warn "claude CLI not found on PATH — install it before running Claude Code sessions"
        echo "   Install: https://docs.anthropic.com/en/docs/claude-code"
    fi

    if command -v rsync >/dev/null 2>&1; then
        detect_rsync_progress
        if [ -n "$RSYNC_PROGRESS_FLAGS" ]; then
            ok "rsync available (live progress supported)"
        else
            warn "rsync available — legacy/openrsync (\"$RSYNC_VERSION_LABEL\")"
            echo "   Live transfer progress requires rsync 3.1.0+. On macOS:"
            echo "       brew install rsync     # then run installer in a fresh shell"
            echo "   Falls back to a spinner — install will work, just less verbose."
        fi
    else
        fail "rsync not found — required for framework file copy"
        failed=1
    fi

    if command -v git >/dev/null 2>&1; then
        ok "git available"
    else
        warn "git not found — some features (branch detection) will be unavailable"
    fi

    if [ "$failed" = "1" ]; then
        echo ""
        warn "Preflight failed. Install missing prerequisites and re-run."
        read -r -p "Continue anyway? [y/N] " cont
        [[ "$cont" =~ ^[Yy]$ ]] || exit 1
    fi
}

# ---------------------------------------------------------------------------
# Target selection and state detection
# ---------------------------------------------------------------------------

choose_project_dir() {
    section "Target project"

    if [ -n "$1" ]; then
        PROJECT_DIR="$1"
    else
        echo "Enter the absolute path to your project directory."
        echo -e "${YELLOW}(Tilde expansion is supported; the directory must already exist.)${NC}"
        read -r -p "> " PROJECT_DIR
    fi

    PROJECT_DIR="${PROJECT_DIR/#\~/$HOME}"
    if ! PROJECT_DIR="$(cd "$PROJECT_DIR" 2>/dev/null && pwd)"; then
        fail "Directory does not exist: $PROJECT_DIR"
        exit 1
    fi

    # Refuse to install into the framework repo itself
    if [ "$PROJECT_DIR" = "$FRAMEWORK_DIR" ]; then
        fail "Refusing to install into the framework repo itself: $PROJECT_DIR"
        exit 1
    fi

    ok "Project directory: $PROJECT_DIR"
}

detect_state() {
    HAS_CLAUDE=0
    HAS_PROJECT_MEMORY=0
    HAS_SETTINGS=0
    HAS_LEGACY_SETTINGS=0

    [ -d "$PROJECT_DIR/.claude" ] && HAS_CLAUDE=1
    [ -d "$PROJECT_DIR/docs/project-memory" ] && HAS_PROJECT_MEMORY=1
    [ -f "$PROJECT_DIR/.claude/settings.json" ] && HAS_SETTINGS=1
    [ -f "$PROJECT_DIR/hooks/settings.json" ] && HAS_LEGACY_SETTINGS=1

    section "Detected state"
    if [ "$HAS_CLAUDE" = "1" ];          then ok ".claude/ present";                                    else warn ".claude/ absent"; fi
    if [ "$HAS_PROJECT_MEMORY" = "1" ];  then ok "docs/project-memory/ present";                        else warn "docs/project-memory/ absent"; fi
    if [ "$HAS_SETTINGS" = "1" ];        then ok ".claude/settings.json present";                       else warn ".claude/settings.json absent (hooks won't fire)"; fi
    if [ "$HAS_LEGACY_SETTINGS" = "1" ]; then warn "Legacy hooks/settings.json at project root (Claude Code does NOT read this)"; fi
}

# ---------------------------------------------------------------------------
# Mode selection
# ---------------------------------------------------------------------------

choose_mode() {
    # If mode was supplied on the CLI, skip the menu.
    if [ -n "$INSTALL_MODE" ]; then
        section "Installation mode"
        ok "Selected mode: $INSTALL_MODE (from --mode)"
        return
    fi

    section "Installation mode"

    echo "Based on the detected state, choose an action:"
    echo ""
    if [ "$HAS_CLAUDE" = "0" ]; then
        echo -e "  ${GREEN}1${NC}) Fresh install                — new project, no existing .claude/"
        echo -e "     (Installs framework + hooks from scratch.)"
    else
        echo -e "  ${YELLOW}1${NC}) Full reinstall               — back up .claude/ to .claude_old/ and overwrite"
        echo -e "     (Creates a restoration script so you can roll back.)"
    fi
    echo ""
    echo -e "  ${GREEN}2${NC}) Refresh framework files      — update .claude/ in-place (also removes framework-retired files; backed up first)"
    echo -e "     (Backs up any overwritten files to .claude/backups/; preserves your content.)"
    echo ""
    echo -e "  ${GREEN}3${NC}) Quit"
    echo ""

    local default="2"
    [ "$HAS_CLAUDE" = "0" ] && default="1"

    read -r -p "Select [1-3] (default: $default): " choice
    choice="${choice:-$default}"

    case "$choice" in
        1) INSTALL_MODE="full" ;;
        2) INSTALL_MODE="refresh-framework" ;;
        3) echo "Cancelled."; exit 0 ;;
        *) fail "Invalid choice"; exit 1 ;;
    esac

    ok "Selected mode: $INSTALL_MODE"
}

# ---------------------------------------------------------------------------
# Install step functions
# ---------------------------------------------------------------------------

install_framework_fresh() {
    step "Installing framework into .claude/ (fresh)"
    mkdir -p "$PROJECT_DIR/.claude"
    rsync_visual \
        --exclude='.git' \
        --exclude='.claude' \
        --exclude='.github' \
        --exclude='scripts/install' \
        --exclude='daily' \
        --exclude='docs' \
        --exclude='docs/**' \
        --exclude='.venv' \
        --exclude='.pytest_cache' \
        --exclude='__pycache__' \
        --exclude='_archive' \
        --exclude='.DS_Store' \
        --exclude='.remember' \
        --exclude='.forge' \
        --exclude='.superpowers' \
        --exclude='.vscode' \
        "$FRAMEWORK_DIR/" "$PROJECT_DIR/.claude/"
    # Doctrine: the framework's own docs/ tree is dev-repo state (framework
    # self-documentation, code-map of the framework, planning notes, debug
    # audits). None of it is referenced by framework runtime code, settings,
    # or templates. Consumer projects own a SEPARATE docs/ tree at PROJECT
    # root for their own data (tasks, project-memory, generated artifacts,
    # epic ISAs). See rules/framework-vs-project-root.md.
    #
    # Heal past leaks: older installs rsynced the framework dev repo's docs/
    # into .claude/docs/ — wipe any of those that may still be present.
    rm -rf \
        "$PROJECT_DIR/.claude/daily" \
        "$PROJECT_DIR/.claude/docs" \
        2>/dev/null || true
    install_cut_paths_manifest
    ok "Framework copied to .claude/"
}

install_cut_paths_manifest() {
    # scripts/install/ is excluded from the rsync above (the installer never
    # ships itself), but forge doctor's orphans check needs the retired-paths
    # ledger to do its job on consumer installs. Ship just this one file.
    local src="$FRAMEWORK_DIR/scripts/install/cut-paths.txt"
    local dst="$PROJECT_DIR/.claude/scripts/install/cut-paths.txt"
    if [ ! -f "$src" ]; then return 0; fi
    mkdir -p "$(dirname "$dst")"
    cp "$src" "$dst"
    ok "Installed cut-paths.txt manifest (enables doctor's orphans check)"
}

install_framework_overwrite() {
    # Back up existing .claude/ to .claude_old/, then fresh install
    step "Backing up existing .claude/ → .claude_old/"
    if [ -d "$PROJECT_DIR/.claude_old" ]; then
        warn ".claude_old/ already exists."
        # Never silently destroy an existing backup. Non-interactive runs
        # rotate it aside instead of prompting (EOF on read would kill the
        # whole install under set -e).
        if [ "${AUTO_YES:-0}" = "1" ] || [ ! -t 0 ]; then
            local rotated=".claude_old.$(date +%Y%m%d-%H%M%S)"
            mv "$PROJECT_DIR/.claude_old" "$PROJECT_DIR/$rotated"
            ok "Existing backup rotated to $rotated (non-interactive)"
        else
            read -r -p "Overwrite existing backup? [y/N] " overwrite
            if [[ "$overwrite" =~ ^[Yy]$ ]]; then
                rm -rf "$PROJECT_DIR/.claude_old"
            else
                fail "Cannot proceed — backup directory in the way."
                exit 1
            fi
        fi
    fi
    with_spinner "Moving .claude/ → .claude_old/" \
        mv "$PROJECT_DIR/.claude" "$PROJECT_DIR/.claude_old"
    ok "Backed up to $PROJECT_DIR/.claude_old"

    create_restoration_script

    install_framework_fresh
}

install_framework_refresh() {
    step "Refreshing framework files in .claude/ (preserving user content)"
    mkdir -p "$PROJECT_DIR/.claude"
    # Backup anything that will be overwritten so users can diff later
    if [ "$BACKUP_ENABLED" = "1" ]; then
        with_spinner "Snapshotting current .claude/ to backups/" \
            backup_file "$PROJECT_DIR/.claude"
    else
        warn "Skipping snapshot (--no-backup) — refresh is not reversible in place"
    fi
    rsync_visual \
        --exclude='.git' \
        --exclude='.claude' \
        --exclude='.github' \
        --exclude='scripts/install' \
        --exclude='scripts/preflight/_local_shims.sh' \
        --exclude='daily' \
        --exclude='docs' \
        --exclude='docs/**' \
        --exclude='memories/sessions/active/*' \
        --exclude='memories/sessions/completed/*' \
        --exclude='memories/progress-notes.md' \
        --exclude='backups' \
        --exclude='settings.json' \
        --exclude='settings.local.json' \
        --exclude='rules/*.local.md' \
        --exclude='.venv' \
        --exclude='.pytest_cache' \
        --exclude='__pycache__' \
        --exclude='_archive' \
        --exclude='.DS_Store' \
        --exclude='.remember' \
        --exclude='.forge' \
        --exclude='.superpowers' \
        --exclude='.vscode' \
        "$FRAMEWORK_DIR/" "$PROJECT_DIR/.claude/"
    seed_preflight_shim_if_missing "$PROJECT_DIR/.claude"
    # Doctrine: framework code lives under .claude/; project data lives at
    # PROJECT root (one level up). The framework's own docs/ tree is dev-repo
    # state (self-documentation + planning) and never belongs in consumer
    # .claude/. Heal past leaks here. See rules/framework-vs-project-root.md.
    rm -rf \
        "$PROJECT_DIR/.claude/daily" \
        "$PROJECT_DIR/.claude/docs" \
        2>/dev/null || true
    install_cut_paths_manifest
    ok "Framework files refreshed (settings.json preserved — merge step runs next)"
}

create_restoration_script() {
    cat > "$PROJECT_DIR/.claude_restore.sh" <<'RESTORE_EOF'
#!/bin/bash
#
# Claude Forge Restoration Script — restores the backup taken at install time.
#
set -e
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

if [ ! -d "$SCRIPT_DIR/.claude_old" ]; then
    echo "No .claude_old/ backup found. Nothing to restore."
    exit 1
fi

echo "This will delete $SCRIPT_DIR/.claude and restore $SCRIPT_DIR/.claude_old."
read -r -p "Proceed? [y/N] " response
[[ "$response" =~ ^[Yy]$ ]] || { echo "Cancelled."; exit 0; }

[ -d "$SCRIPT_DIR/.claude" ] && rm -rf "$SCRIPT_DIR/.claude"
mv "$SCRIPT_DIR/.claude_old" "$SCRIPT_DIR/.claude"
rm -f "$SCRIPT_DIR/.claude_restore.sh"
echo "✓ Restoration complete."
RESTORE_EOF
    chmod +x "$PROJECT_DIR/.claude_restore.sh"
    ok "Created restoration script: .claude_restore.sh"
}

install_session_dirs() {
    step "Initializing session directories"
    mkdir -p "$PROJECT_DIR/.claude/memories/sessions/active"
    mkdir -p "$PROJECT_DIR/.claude/memories/sessions/completed"
    touch "$PROJECT_DIR/.claude/memories/sessions/active/.gitkeep"
    touch "$PROJECT_DIR/.claude/memories/sessions/completed/.gitkeep"
    ok "Session directories ready"
}

install_project_memory() {
    step "Installing docs/project-memory/"
    local target="$PROJECT_DIR/docs/project-memory"
    local src="$FRAMEWORK_DIR/templates/project-memory"

    if [ -d "$target" ]; then
        warn "docs/project-memory/ already exists"
        # Non-interactive runs (--yes, or no tty) keep existing memory — the
        # safe default; an EOF from `read` under `set -e` used to kill the
        # whole install here, silently skipping every later step.
        if [ "${AUTO_YES:-0}" = "1" ] || [ ! -t 0 ]; then
            ok "Keeping existing project memory files (non-interactive)"
            return
        fi
        read -r -p "Overwrite template files? [y/N] " overwrite
        if [[ ! "$overwrite" =~ ^[Yy]$ ]]; then
            ok "Keeping existing project memory files"
            return
        fi
        backup_file "$target"
    fi

    mkdir -p "$target"
    if [ -d "$src" ]; then
        for f in index.md bugs.md decisions.md key-facts.md patterns.md; do
            [ -f "$src/$f" ] && cp "$src/$f" "$target/"
        done
        ok "Installed template files to docs/project-memory/"
    else
        warn "Template dir missing — created empty docs/project-memory/"
    fi

    # Also copy to .claude/templates/project-memory for in-project resets
    local reset_dir="$PROJECT_DIR/.claude/templates/project-memory"
    if [ -d "$src" ]; then
        mkdir -p "$reset_dir"
        cp -r "$src/." "$reset_dir/"
    fi

    # Index file (skeleton)
    if [ ! -f "$target/index.md" ]; then
        cat > "$target/index.md" <<'INDEX_EOF'
# Project Memory Index

> Auto-generated catalog of all project knowledge.
> This file is injected at session start for instant context.

## Summary

| Category | Count | Last Updated |
|----------|-------|--------------|
| Bugs | 0 | — |
| Decisions | 0 | — |
| Patterns | 0 | — |
| Key Facts | 0 | — |

## Recent Entries

_No entries yet._
INDEX_EOF
        ok "Created docs/project-memory/index.md"
    fi
}

install_settings() {
    step "Wiring .claude/settings.json (the only location Claude Code reads)"
    local fw="$FRAMEWORK_DIR/hooks/settings.json"
    local pr="$PROJECT_DIR/.claude/settings.json"

    if [ ! -f "$fw" ]; then
        warn "Framework hook template missing at $fw"
        return
    fi

    mkdir -p "$PROJECT_DIR/.claude"

    if [ -f "$pr" ]; then
        if ! command -v python3 >/dev/null 2>&1; then
            warn "python3 unavailable — skipping settings.json merge (manual review required)"
            return
        fi
        backup_file "$pr"
        python3 - "$fw" "$pr" <<'MERGE_EOF'
import json, sys
from pathlib import Path
framework = json.loads(Path(sys.argv[1]).read_text())
project = json.loads(Path(sys.argv[2]).read_text())
fw_hooks = framework.get("hooks", {})
pr_hooks = project.setdefault("hooks", {})
for event, entries in fw_hooks.items():
    pr_hooks[event] = entries   # framework's wiring wins per-event
fw_allow = framework.get("permissions", {}).get("allow", [])
pr_allow = project.setdefault("permissions", {}).setdefault("allow", [])
for p in fw_allow:
    if p not in pr_allow:
        pr_allow.append(p)
# Same union for deny — without this, deny rules added to the framework
# template never reach existing consumers via refresh (only fresh installs).
fw_deny = framework.get("permissions", {}).get("deny", [])
pr_deny = project["permissions"].setdefault("deny", [])
for p in fw_deny:
    if p not in pr_deny:
        pr_deny.append(p)
Path(sys.argv[2]).write_text(json.dumps(project, indent=2) + "\n")
MERGE_EOF
        ok "Merged hooks & permissions into .claude/settings.json"
    else
        cp "$fw" "$pr"
        ok "Installed .claude/settings.json"
    fi

    # Warn if a project-level hooks/settings.json is sitting unused
    if [ "$HAS_LEGACY_SETTINGS" = "1" ]; then
        warn "Found $PROJECT_DIR/hooks/settings.json — Claude Code does NOT read this location."
        echo "   Its hooks are merged into .claude/settings.json above."
        echo "   You may delete the legacy file once verified."
    fi
}

install_schema() {
    local src="$FRAMEWORK_DIR/MEMORY-SCHEMA.md"
    local dst="$PROJECT_DIR/MEMORY-SCHEMA.md"
    if [ ! -f "$src" ]; then return 0; fi
    if [ -f "$dst" ]; then
        ok "MEMORY-SCHEMA.md already present (kept)"
        return 0
    fi
    cp "$src" "$dst"
    ok "Installed MEMORY-SCHEMA.md"
}

install_mcp_servers() {
    # Register Forge Flow's MCP servers in <project>/.mcp.json. Idempotent:
    # creates the file if missing, adds servers Claude Code should know about
    # without touching any other server the user already registered.
    #
    # Currently registers:
    #   - forge-code-map  → mcp-servers/code-map/server.py
    #     (symbol-level navigation backed by docs/code-map.json)
    #
    # The .mcp.json file lives at project root (committed, team-shared) per
    # Claude Code convention. Users who prefer settings.json mcpServers can
    # remove the entry here and add it there manually.
    step "Wiring MCP servers in .mcp.json"

    if ! command -v python3 >/dev/null 2>&1; then
        warn "python3 unavailable — skipping .mcp.json wiring (manual setup required)"
        return 0
    fi

    if ! command -v uv >/dev/null 2>&1; then
        warn "uv unavailable — forge-code-map MCP server requires uv to fetch the mcp SDK ephemerally (install via 'brew install uv'); .mcp.json will still be written"
    fi

    local mcp_file="$PROJECT_DIR/.mcp.json"
    [ -f "$mcp_file" ] && backup_file "$mcp_file"

    python3 - "$mcp_file" <<'MCP_EOF'
import json
import sys
from pathlib import Path

mcp_path = Path(sys.argv[1])

# Forge-managed MCP servers. Add entries here when a new Forge MCP server ships.
# Each entry: server name -> config block.
#
# PATH MUST BE PROJECT-ROOT-RELATIVE — do NOT use ${CLAUDE_PROJECT_DIR} here.
# Claude Code does NOT expand ${CLAUDE_PROJECT_DIR} inside MCP `args` (it DOES
# expand it in `hooks` command strings — that asymmetry is the trap). A literal
# `${CLAUDE_PROJECT_DIR}/…` would be passed verbatim to python and fail with
# `No such file or directory` → JSON-RPC error -32000 on every consumer.
# Claude Code launches MCP servers with the project root as cwd, and
# server.py::_project_root() already falls back to cwd, so a relative path is
# both correct and portable. (Fixed per consumer-project handoff 2026-06-01.)
#
# Note: no `env:` block is emitted. Claude Code injects CLAUDE_PROJECT_DIR
# into the spawned MCP server process automatically — declaring it again in
# `env: {CLAUDE_PROJECT_DIR: "${CLAUDE_PROJECT_DIR}"}` makes `claude doctor`
# flag it as a missing OS env var (because the variable doesn't exist at
# diagnostic time, only at spawn time). The server itself derives its own
# location via os.path.dirname(__file__), so no env var is needed.
#
# Launch via `uv run --with mcp python <server.py>` so the `mcp` Python SDK is
# pulled into an ephemeral env per run — no global `pip install mcp` needed.
# Bare `python3` fails on systems whose system interpreter (e.g. Homebrew
# Python 3.14) has no `mcp` installed; the server then prints the install hint
# to stderr and exits, and Claude Code reports JSON-RPC error -32000.
FORGE_SERVERS = {
    "forge-code-map": {
        "command": "uv",
        "args": [
            "run",
            "--with",
            "mcp",
            "python",
            ".claude/mcp-servers/code-map/server.py"
        ]
    }
}

if mcp_path.exists():
    try:
        config = json.loads(mcp_path.read_text())
    except json.JSONDecodeError as exc:
        print(f"warn: existing .mcp.json is not valid JSON ({exc}) — leaving it untouched", file=sys.stderr)
        sys.exit(0)
else:
    config = {}

servers = config.setdefault("mcpServers", {})
added, updated, kept = [], [], []
for name, block in FORGE_SERVERS.items():
    if name not in servers:
        servers[name] = block
        added.append(name)
    elif servers[name] != block:
        # Update Forge-managed server config if it has drifted from the
        # framework's current shape. Users who customized the entry get a
        # backup via the install script's backup_file step above.
        servers[name] = block
        updated.append(name)
    else:
        kept.append(name)

mcp_path.write_text(json.dumps(config, indent=2) + "\n")

if added:
    print(f"added: {', '.join(added)}")
if updated:
    print(f"updated: {', '.join(updated)}")
if kept:
    print(f"already current: {', '.join(kept)}")
MCP_EOF

    ok "MCP servers registered in .mcp.json (forge-code-map)"

    # Bonus: ensure docs/code-map.json is gitignored. Generated artifact, like
    # node_modules — committing it creates churn.
    local gi="$PROJECT_DIR/.gitignore"
    if [ -f "$gi" ] && ! grep -qE "^docs/code-map\.json$" "$gi"; then
        printf '\n# Generated code-map JSON (regenerated on SessionStart, consumed by forge-code-map MCP server)\ndocs/code-map.json\n' >> "$gi"
        ok "Added docs/code-map.json to .gitignore"
    fi
}

# The project-context skeleton written below the framework import when the
# project slot is empty. Carries only what the model cannot infer from code
# (identity, intent, deviating-from-convention architecture, version quirks,
# global invariants) and points to reference/01-system-overview.md as the
# authoritative source — no duplication, per the 4-tier governance model.
print_project_skeleton() {
    cat <<'EOF'
<!-- forge-flow:project-context -->
## Project context

> Fill in the sections below. Document only what Claude **cannot infer from the
> code** — intent, gotchas, version quirks, hard rules. Everything obvious from
> reading the source is wasted tokens. The full intent & architecture live in
> `.claude/reference/01-system-overview.md` (Tier-2 source-of-truth) — keep this
> a ≤3-line pitch plus pointers, not a duplicate.

### Identity
<!-- One line: what is this project, in plain terms. -->

### Why it exists
<!-- 2-3 lines: the problem it solves / the value it delivers. Not visible in code. -->

### Architecture (deviations only)
<!-- Only the parts that DEPART from convention. Skip anything a reader infers from structure. -->

### Version quirks & pins
<!-- "This library version behaves this way / is real, don't reinvent it." Tribal knowledge. -->

### Global invariants & anti-patterns
<!-- Verifiable hard rules: "never bypass X", "all auth errors route through Y", "parameterize all SQL". -->

### See also
<!-- - Full intent & architecture: .claude/reference/01-system-overview.md -->
EOF
}

# Should we inject the project-context skeleton? Two ways the slot counts as
# already handled (return 1 = do NOT inject):
#   (a) the project-context sentinel is present  -> we already scaffolded it once;
#       never touch again, whether or not the user has since edited the body.
#       This is the idempotency + clobber guard.
#   (b) no sentinel, but the user wrote real project content by hand -> respect it.
# Only a slot that is BOTH sentinel-free AND substantively empty gets the skeleton.
root_claude_md_slot_is_empty() {
    local root_md="$1"
    local import_line='@.claude/CLAUDE.md'
    # (a) sentinel present -> already scaffolded
    if grep -qF '<!-- forge-flow:project-context -->' "$root_md"; then
        return 1
    fi
    # (b) inspect everything after the import for hand-written content.
    local body
    body=$(awk -v imp="$import_line" '
        seen { print }
        index($0, imp) { seen=1 }
    ' "$root_md")
    # Drop framework-import markers, the boilerplate blockquote, html comments,
    # headers, and pure-whitespace. Anything left = the user filled it in.
    local remainder
    remainder=$(printf '%s\n' "$body" \
        | grep -v -- '<!-- forge-flow:framework-import -->' \
        | grep -v '^> ' \
        | grep -v '<!--' \
        | grep -v '^[[:space:]]*$' \
        | grep -v '^#')
    [ -z "$remainder" ]
}

install_root_claude_md_import() {
    # Ensure the project root has a CLAUDE.md that imports the framework's
    # rules via @.claude/CLAUDE.md. Claude Code reliably auto-loads root
    # CLAUDE.md; auto-discovery of .claude/CLAUDE.md is version-dependent and
    # has been observed to skip silently in consumer projects. The @-import
    # makes the framework wiring explicit and version-independent.
    #
    # Three cases for the IMPORT:
    #   1. No root CLAUDE.md            -> create one with the import + header
    #   2. Root CLAUDE.md has import    -> idempotent no-op (import side)
    #   3. Root CLAUDE.md without import-> prepend the import (prompt unless --yes)
    #
    # Independently of which case wired the import, we then ensure the PROJECT
    # SLOT is populated: if it's empty (fresh install, or an existing project
    # that only ever got the import), inject the project-context
    # skeleton so the root file actually says what the project IS — never blank.
    step "Wiring root CLAUDE.md -> @.claude/CLAUDE.md"
    local root_md="$PROJECT_DIR/CLAUDE.md"
    local import_line='@.claude/CLAUDE.md'
    local managed_marker='<!-- forge-flow:framework-import -->'

    if [ ! -f "$root_md" ]; then
        cat > "$root_md" <<EOF
# $(basename "$PROJECT_DIR")

$managed_marker
$import_line
$managed_marker

EOF
        ok "Created $root_md with framework import"
        ensure_root_claude_md_project_slot "$root_md"
        return 0
    fi

    if grep -qF "$import_line" "$root_md"; then
        ok "Root CLAUDE.md already imports framework (idempotent no-op)"
        ensure_root_claude_md_project_slot "$root_md"
        return 0
    fi

    # Root CLAUDE.md exists but lacks the import — prepend it
    if [ "$AUTO_YES" = "1" ]; then
        add_import=1
    else
        warn "Existing $root_md does not import .claude/CLAUDE.md"
        echo "   Framework rules will not load reliably without this import."
        read -r -p "Prepend '$import_line' to existing root CLAUDE.md? [Y/n] " add_choice
        if [[ "$add_choice" =~ ^[Nn]$ ]]; then
            add_import=0
        else
            add_import=1
        fi
    fi

    if [ "$add_import" = "1" ]; then
        local tmpf
        tmpf=$(mktemp)
        {
            echo "$managed_marker"
            echo "$import_line"
            echo "$managed_marker"
            echo ""
            cat "$root_md"
        } > "$tmpf"
        mv "$tmpf" "$root_md"
        ok "Prepended framework import to existing $root_md"
        ensure_root_claude_md_project_slot "$root_md"
    else
        warn "Skipped — framework rules may not auto-load. Add manually:"
        echo "   $import_line"
    fi
}

# Inject the project-context skeleton iff the project slot is empty. Idempotent:
# once the user fills any section, this becomes a no-op on every future refresh.
ensure_root_claude_md_project_slot() {
    local root_md="$1"
    if root_claude_md_slot_is_empty "$root_md"; then
        {
            print_project_skeleton
            echo ""
        } >> "$root_md"
        ok "Scaffolded project-context skeleton in $root_md"
        warn "ACTION NEEDED: $root_md has an empty project section."
        echo "   Fill the 'Project context' headers (or run /refresh-project-context to draft them)."
        echo "   Claude starts every session here — without it, the project is invisible to the model."
    else
        ok "Root CLAUDE.md project section already populated (left untouched)"
    fi
}

install_layered_claude_md() {
    # Detect monorepo workspaces and create subdirectory CLAUDE.md stubs.
    # Anthropic's large-codebase guidance is to layer CLAUDE.md by working
    # directory — root file holds project-wide rules, each workspace/service
    # holds its own conventions. Claude Code walks up the tree at runtime,
    # composing the layered context as the session moves between directories.
    #
    # We only scaffold STUBS — empty templates with a comment explaining
    # what to put there. We never overwrite an existing CLAUDE.md. The user
    # fills them in with real conventions on their own schedule.
    step "Scaffolding layered CLAUDE.md stubs (monorepo workspace detection)"

    if ! command -v python3 >/dev/null 2>&1; then
        warn "python3 unavailable — skipping layered CLAUDE.md scaffold"
        return 0
    fi

    python3 - "$PROJECT_DIR" <<'LAYERED_EOF'
import json
import sys
from pathlib import Path

root = Path(sys.argv[1])
created = []

def has_claude_md(d: Path) -> bool:
    return (d / "CLAUDE.md").exists()

def stub_for(d: Path) -> str:
    name = d.name
    return f"""# {name} — CLAUDE.md

> Subdirectory CLAUDE.md. Claude Code auto-loads this when the session works
> inside `{d.relative_to(root).as_posix()}/`, layered on top of the root
> CLAUDE.md. Keep it focused on conventions specific to this workspace —
> tech stack quirks, internal vocabulary, test commands, gotchas. Skip
> anything already covered by the root CLAUDE.md.

## What this workspace does

_(One sentence on the responsibility of `{name}`. Replace this stub.)_

## Conventions specific to this workspace

- _(Add the rules that bite here but don't apply elsewhere.)_

## Commands

```bash
# Dev:
# Test:
# Build:
```
"""

def write_stub(d: Path) -> None:
    if has_claude_md(d):
        return
    (d / "CLAUDE.md").write_text(stub_for(d))
    created.append(str(d.relative_to(root).as_posix()))

# Detection 1: npm/pnpm workspaces — read root package.json
pkg_root = root / "package.json"
if pkg_root.exists():
    try:
        pkg = json.loads(pkg_root.read_text())
    except (json.JSONDecodeError, OSError):
        pkg = {}
    workspaces = pkg.get("workspaces", [])
    if isinstance(workspaces, dict):
        workspaces = workspaces.get("packages", [])
    for pattern in workspaces:
        if "*" in pattern:
            # Expand the glob
            for match in root.glob(pattern):
                if match.is_dir():
                    write_stub(match)
        else:
            d = root / pattern
            if d.is_dir():
                write_stub(d)

# Detection 2: pnpm-workspace.yaml
pnpm_ws = root / "pnpm-workspace.yaml"
if pnpm_ws.exists():
    try:
        text = pnpm_ws.read_text()
    except OSError:
        text = ""
    import re
    # Naive parse — list of glob strings under 'packages:'
    in_packages = False
    for line in text.splitlines():
        s = line.strip()
        if s.startswith("packages:"):
            in_packages = True
            continue
        if in_packages and s.startswith("-"):
            pattern = s.lstrip("- ").strip("'\"")
            for match in root.glob(pattern):
                if match.is_dir():
                    write_stub(match)
        elif in_packages and s and not s.startswith("#"):
            in_packages = False

# Detection 3: cargo workspace — Cargo.toml at root with [workspace] members
cargo = root / "Cargo.toml"
if cargo.exists():
    try:
        text = cargo.read_text()
    except OSError:
        text = ""
    import re
    m = re.search(r'\[workspace\][^\[]*?members\s*=\s*\[(.*?)\]', text, re.DOTALL)
    if m:
        members = re.findall(r'"([^"]+)"', m.group(1))
        for member in members:
            for match in root.glob(member):
                if match.is_dir():
                    write_stub(match)

# Detection 4: top-level service/app/package directories
for layout in ("services", "apps", "packages", "libs", "crates"):
    base = root / layout
    if not base.is_dir():
        continue
    for child in base.iterdir():
        if not child.is_dir():
            continue
        if child.name.startswith(".") or child.name == "node_modules":
            continue
        # Heuristic: stub only if the child has its own manifest
        if any((child / m).exists() for m in (
            "package.json", "pyproject.toml", "Cargo.toml",
            "go.mod", "tsconfig.json", "requirements.txt"
        )):
            write_stub(child)

if created:
    print(f"created: {', '.join(sorted(set(created)))}")
else:
    print("no workspaces detected (or all already have a CLAUDE.md)")
LAYERED_EOF

    ok "Layered CLAUDE.md scaffold complete"
}

install_claudeignore() {
    # Drop a default .claudeignore at project root so Claude Code never reads
    # build artifacts, dependency caches, or generated bundles. Pure token-cost
    # win — every session benefits. Idempotent: refuses to overwrite an
    # existing file (user customization wins).
    step "Installing .claudeignore (Claude Code read-exclusion list)"
    local dst="$PROJECT_DIR/.claudeignore"
    if [ -f "$dst" ]; then
        ok ".claudeignore already present (kept)"
        return 0
    fi
    cat > "$dst" <<'CLAUDEIGNORE_EOF'
# .claudeignore — paths Claude Code should never read.
#
# Generated by Forge Flow installer. Edit freely — refresh re-runs respect
# any existing file. Idiom matches .gitignore (one path/pattern per line).
#
# Goal: keep agent context windows lean. Reading these paths burns tokens
# without informing decisions.

# --- Dependency caches ---
node_modules/
.pnpm-store/
.yarn/cache/
.venv/
venv/
__pycache__/
vendor/
target/

# --- Build outputs ---
dist/
build/
out/
.next/
.nuxt/
.turbo/
.cache/
.parcel-cache/
*.tsbuildinfo

# --- Coverage and test artifacts ---
coverage/
.nyc_output/
.pytest_cache/
.mypy_cache/
.ruff_cache/

# --- IaC / cloud caches ---
.terraform/
.serverless/

# --- Lockfiles (large, low signal per token) ---
package-lock.json
pnpm-lock.yaml
yarn.lock
Cargo.lock
poetry.lock
uv.lock
Gemfile.lock
composer.lock

# --- Generated Forge Flow artifacts ---
# docs/code-map.md stays readable — it's the structural summary.
# docs/code-map.json is consumed by the forge-code-map MCP server, not read directly.
docs/code-map.json

# --- OS / editor noise ---
.DS_Store
Thumbs.db
.idea/
.vscode/settings.json
CLAUDEIGNORE_EOF
    ok "Installed .claudeignore"
}

install_daily() {
    local dir="$PROJECT_DIR/daily"
    mkdir -p "$dir"
    if [ ! -f "$dir/.gitignore" ]; then
        cat > "$dir/.gitignore" <<'EOF'
# Daily conversation logs — per-user, not committed
*
!.gitignore
EOF
    fi
    ok "daily/ directory ready (gitignored)"
}

cleanup_stray_dirs() {
    # Older installs (and the rsync step in current full/refresh modes) used
    # to copy the framework's daily/ into .claude/. That is never read at
    # runtime — project-root-relative paths are used instead. Delete it so
    # users don't have two copies that look like they should be kept in sync.
    local claude_daily="$PROJECT_DIR/.claude/daily"
    local claude_pm="$PROJECT_DIR/.claude/docs/project-memory"
    local found=0
    for d in "$claude_daily" "$claude_pm"; do
        if [ -d "$d" ]; then
            backup_file "$d"
            rm -rf "$d"
            found=1
        fi
    done
    if [ "$found" = "1" ]; then
        ok "Removed legacy copies under .claude/ (runtime uses project root)"
    fi
}

update_gitignore() {
    local gi="$PROJECT_DIR/.gitignore"
    [ -f "$gi" ] || return 0
    if ! grep -q "^daily/" "$gi"; then
        cat >> "$gi" <<'EOF'

# Per-user generated data
daily/
.claude/tmp/
EOF
        ok "Updated project .gitignore with daily/ entries"
    fi
    # Framework-owned Python venv — created by `forge preflight enable-git-hook`.
    # Per-machine, never committed. See scripts/preflight/venv_manager.py.
    if ! grep -q "^\.forge/venv/" "$gi"; then
        cat >> "$gi" <<'EOF'

# Forge Flow preflight venv — framework-owned, per-machine
.forge/venv/
EOF
        ok "Updated project .gitignore with .forge/venv/ entry"
    fi
    # Registry mutation lock sidecar — machine-local, never committed.
    # See registry_ops.registry_write_lock docstring: intentionally never deleted.
    if ! grep -q "^docs/tasks/\.registry\.lock" "$gi"; then
        cat >> "$gi" <<'EOF'

# Forge Flow registry lock sidecar — machine-local, never committed
docs/tasks/.registry.lock
EOF
        ok "Updated project .gitignore with docs/tasks/.registry.lock entry"
    fi
}

# ---------------------------------------------------------------------------
# v3-specific install steps (Forge Flow refresh-v3 upgrade)
# ---------------------------------------------------------------------------

install_v3_cross_repo_cleanup() {
    local cross_repo_dir="$PROJECT_DIR/.claude/cross-repo"
    local legacy_script="$PROJECT_DIR/.claude/scripts/install/add-cross-repo.sh"

    if [ ! -d "$cross_repo_dir" ] && [ ! -f "$legacy_script" ]; then
        ok "No legacy .claude/cross-repo/ — skipping cleanup"
        return 0
    fi

    step "Removing legacy .claude/cross-repo/ (replaced by Specialist Export Artifact pattern)"

    local backup_root="$(backup_path)/cross-repo"
    local notes_file="$PROJECT_DIR/.claude/v3-migration-notes.md"

    if [ -d "$cross_repo_dir" ]; then
        mkdir -p "$(dirname "$backup_root")"
        cp -r "$cross_repo_dir" "$backup_root"
        BACKUPS_CREATED=$((BACKUPS_CREATED + 1))
        ok "Backed up $cross_repo_dir → $backup_root"
    fi

    {
        echo "# v3 Migration Notes — Cross-repo Cleanup"
        echo
        echo "> Auto-generated by install.sh --mode refresh-v3 on $(date -u +%Y-%m-%dT%H:%M:%SZ)."
        echo
        echo "The legacy \`.claude/cross-repo/\` configuration was removed during the v3"
        echo "upgrade and replaced by the **Specialist Export Artifact** pattern."
        echo
        echo "## What was removed"
        echo
        if [ -d "$backup_root" ]; then
            echo "- \`.claude/cross-repo/\` (backed up to \`${backup_root#$PROJECT_DIR/}\`)"
        fi
        if [ -f "$legacy_script" ]; then
            echo "- \`.claude/scripts/install/add-cross-repo.sh\` (no longer ships in v3)"
        fi
        echo
        echo "## What to do next"
        echo
        echo "If sibling projects depended on cross-repo, vendor each project's \`EXPERT.md\`"
        echo "instead. From the home project:"
        echo
        echo "    python3 .claude/scripts/forge/forge.py specialist add <name> --domain \"...\""
        echo
        echo "Then vendor the generated \`EXPERT.md\` into consumer projects via git submodule,"
        echo "copy-with-sync, or symlink (see Forge Flow specialist pattern docs)."
        echo
        if [ -d "$backup_root" ]; then
            echo "## Original cross-repo entries (for reference)"
            echo
            echo '```'
            (cd "$backup_root" && find . -maxdepth 2 -mindepth 1 | sort) || true
            echo '```'
        fi
    } > "$notes_file"

    [ -d "$cross_repo_dir" ] && rm -rf "$cross_repo_dir"
    [ -f "$legacy_script" ] && rm -f "$legacy_script"

    ok "Cleanup complete; notes at .claude/v3-migration-notes.md"
}

install_v3_framework_files() {
    step "Copying v3 framework surfaces into .claude/ (preserving user content)"
    mkdir -p "$PROJECT_DIR/.claude"
    if [ "$BACKUP_ENABLED" = "1" ]; then
        with_spinner "Snapshotting current .claude/ to backups/" \
            backup_file "$PROJECT_DIR/.claude"
    else
        warn "Skipping snapshot (--no-backup) — refresh-v3 is not reversible in place"
    fi

    # rsync framework root → .claude/ with v3 excludes:
    #   - VCS / archives / planning artifacts (framework-only)
    #   - the installer itself (avoids overwriting in-flight)
    #   - user content under .claude/ that the framework MUST NOT clobber
    #     (specialists/, knowledge/, worktrees/, backups/)
    #   - settings.json (handled by the merge step in install_settings)
    #   - per-user state files
    #
    # NOTE on mcp-servers/: rsync rules are first-match-wins. We INCLUDE
    # framework-shipped servers explicitly (code-map, …) BEFORE excluding the
    # rest of mcp-servers/. That way:
    #   - mcp-servers/code-map/** ships (framework-owned, updates with refresh)
    #   - mcp-servers/<anything-else>/** is left alone (user-owned)
    # Add new framework-shipped servers as additional --include lines, NOT by
    # widening the exclude.
    rsync_visual \
        --exclude='.git' \
        --exclude='.claude' \
        --exclude='.github' \
        --exclude='.gitignore' \
        --exclude='_archive' \
        --exclude='scripts/install' \
        --exclude='scripts/preflight/_local_shims.sh' \
        --exclude='daily' \
        --exclude='docs' \
        --exclude='docs/**' \
        --exclude='ISA.md' \
        --exclude='memories/sessions/active/*' \
        --exclude='memories/sessions/completed/*' \
        --exclude='memories/progress-notes.md' \
        --exclude='backups' \
        --exclude='settings.json' \
        --exclude='settings.local.json' \
        --exclude='agents/specialists/**' \
        --exclude='knowledge/**' \
        --exclude='worktrees/**' \
        --exclude='rules/*.local.md' \
        --exclude='skills/*.local/' \
        --exclude='skills/*.local/***' \
        --exclude='**/__pycache__' \
        --exclude='**/*.pyc' \
        --exclude='.venv' \
        --exclude='.pytest_cache' \
        --exclude='__pycache__' \
        --exclude='.DS_Store' \
        --exclude='.remember' \
        --exclude='.forge' \
        --exclude='.superpowers' \
        --exclude='.vscode' \
        --include='mcp-servers/' \
        --include='mcp-servers/code-map/***' \
        --exclude='mcp-servers/*' \
        "$FRAMEWORK_DIR/" "$PROJECT_DIR/.claude/"

    # Doctrine: .claude/ is framework_root (CODE only — skills, agents, hooks,
    # scripts, reference, rules, templates). All project data — docs/tasks/,
    # docs/project-memory/, docs/code-map.json/.md, docs/visualizations/, daily/,
    # ISA.md — lives at PROJECT root, one level UP from .claude/. The
    # framework's own docs/ tree is dev-repo state (self-documentation,
    # planning notes, debug audits, framework code-map). None of it belongs
    # in consumer .claude/. See rules/framework-vs-project-root.md.
    #
    # Heal past leaks here in case older installs rsynced framework docs/ or
    # daily/ into .claude/ under prior exclude policies.
    rm -rf \
        "$PROJECT_DIR/.claude/daily" \
        "$PROJECT_DIR/.claude/docs" \
        2>/dev/null || true

    seed_preflight_shim_if_missing "$PROJECT_DIR/.claude"

    ok "v3 framework files in place"
}

guard_skill_collisions() {
    # Safety net for consumers who did NOT adopt the `.local` convention.
    # A consumer skill at skills/<name>/ whose dir name collides with an
    # incoming framework skill will be OVERWRITTEN by the rsync (no --delete,
    # but same-name files are replaced). Before that happens, back up any
    # colliding consumer copy that DIFFERS from the framework copy, and warn.
    #
    # `.local`-suffixed skills are never at risk (excluded from the rsync +
    # the framework never ships a `.local` skill), so they are skipped here.
    # Run this BEFORE install_v3_framework_files' rsync.
    local consumer_skills="$PROJECT_DIR/.claude/skills"
    local framework_skills="$FRAMEWORK_DIR/skills"
    [ -d "$consumer_skills" ] || return 0
    [ -d "$framework_skills" ] || return 0

    local backup_root
    backup_root="$(backup_path)/skill-collisions"
    local collisions=0

    local cdir name
    for cdir in "$consumer_skills"/*/; do
        [ -d "$cdir" ] || continue
        name=$(basename "$cdir")
        case "$name" in
            *.local) continue ;;   # protected convention — never at risk
        esac
        local fdir="$framework_skills/$name"
        [ -d "$fdir" ] || continue          # no framework skill of this name → no collision
        # Same name on both sides. Only act if the consumer copy DIFFERS from
        # the framework copy (an identical copy is just a prior refresh — no data loss).
        if ! diff -rq "$cdir" "$fdir" >/dev/null 2>&1; then
            mkdir -p "$backup_root"
            cp -R "$cdir" "$backup_root/$name"
            warn "Skill name collision: consumer skills/$name/ differs from the framework's — refresh will overwrite it."
            echo "   Backed up your copy to: $backup_root/$name"
            echo "   To keep it across future refreshes, rename it to skills/$name.local/ (invoked as /$name.local)."
            collisions=$((collisions + 1))
        fi
    done

    [ "$collisions" -gt 0 ] \
        && warn "$collisions skill collision(s) backed up before refresh — see messages above." \
        || ok "No skill name collisions (consumer skills safe)"
}

install_v3_seed_specialists() {
    # The v3 framework ships a README.md + .gitkeep at agents/specialists/ to
    # document the user-owned-never-replaced guarantee. install_v3_framework_files
    # excludes 'agents/specialists/**' from the rsync to preserve any user
    # specialists already on disk — but that exclusion ALSO blocks seeding the
    # README + .gitkeep into a fresh or empty target. Seed them explicitly
    # here, only when missing.
    local dst="$PROJECT_DIR/.claude/agents/specialists"
    mkdir -p "$dst"
    local seeded=0
    if [ ! -f "$dst/README.md" ] && [ -f "$FRAMEWORK_DIR/agents/specialists/README.md" ]; then
        cp "$FRAMEWORK_DIR/agents/specialists/README.md" "$dst/README.md"
        seeded=1
    fi
    if [ ! -f "$dst/.gitkeep" ]; then
        touch "$dst/.gitkeep"
        seeded=1
    fi
    [ "$seeded" = "1" ] && ok "Seeded agents/specialists/ scaffold (README + .gitkeep)" \
                       || ok "agents/specialists/ scaffold already present"
}

install_v3_cut_v2_cleanup() {
    step "Removing v2 framework files cut in v3 (cleanup)"

    local cleanup_root="$PROJECT_DIR/.claude"
    local backup_root
    backup_root="$(backup_path)/cut-v2"
    local removed=0
    local backed_up=0

    backup_then_remove() {
        local src="$1"
        local rel="${src#$cleanup_root/}"
        local dest="$backup_root/$rel"
        if [ -e "$src" ]; then
            mkdir -p "$(dirname "$dest")"
            cp -r "$src" "$dest"
            rm -rf "$src"
            removed=$((removed + 1))
            backed_up=1
        fi
    }

    # 13 cut framework agents (v3 keeps: architect, project-manager,
    # quality-engineer, security-boss, devops). Their summaries also go.
    local cut_agents=(
        analyst api-tester build-resolver doc-updater e2e-runner
        orchestrator performance-enhancer refactor-cleaner scrum-master
        tdd-guide ux-designer visual-mistro whimsy
    )
    for a in "${cut_agents[@]}"; do
        backup_then_remove "$cleanup_root/agents/$a.md"
        backup_then_remove "$cleanup_root/agents/summaries/$a.md"
    done

    # commands/ — entire directory cut in v3 (ISC-12 + ISC-13: 4 v2 ops
    # commands all duplicated by skills; 17 nested design commands moved
    # to skills/design/<name>.md).
    backup_then_remove "$cleanup_root/commands"

    # features/ — empty placeholder dir in v2; cut in v3.
    backup_then_remove "$cleanup_root/features"

    # skills/cross-repo/ — replaced by Specialist Export Artifact pattern.
    # (.claude/cross-repo/ config dir is handled separately by
    # install_v3_cross_repo_cleanup at the start of run_refresh_v3.)
    backup_then_remove "$cleanup_root/skills/cross-repo"

    if [ "$removed" -gt 0 ]; then
        ok "Removed $removed v2 cut framework path(s); backups at ${backup_root#$PROJECT_DIR/}"
        [ "$backed_up" = "1" ] && BACKUPS_CREATED=$((BACKUPS_CREATED + 1))
    else
        ok "No v2 cut framework files present (clean)"
    fi
}

# Read the cut-paths manifest (one relative path per line, # comments allowed)
# and remove each listed path from the consumer's .claude/ tree. Honors
# --no-backup; refuses to touch user-owned roots; rejects absolute paths and
# `..` traversals. See scripts/install/README.md for the maintainer workflow.
install_v3_cleanup_cut_paths() {
    step "Removing framework-cut paths (cut-paths.txt)"

    local manifest="$SCRIPT_DIR/cut-paths.txt"
    if [ ! -f "$manifest" ]; then
        warn "cut-paths manifest not found at $manifest — skipping"
        return 0
    fi

    local cleanup_root="$PROJECT_DIR/.claude"
    local backup_root
    backup_root="$(backup_path)/cut-paths"
    local removed=0
    local backed_up=0

    # Anti-clobber denylist (ISC-10): any manifest entry whose normalized path
    # starts with one of these is refused. These are user-owned roots.
    local protected_roots=(
        "agents/specialists"
        "docs/tasks"
        "docs/project-memory"
        "daily"
    )

    local raw rel
    while IFS= read -r raw || [ -n "$raw" ]; do
        # Strip leading/trailing whitespace.
        rel="${raw#"${raw%%[![:space:]]*}"}"
        rel="${rel%"${rel##*[![:space:]]}"}"
        # Skip blanks and comments.
        [ -z "$rel" ] && continue
        case "$rel" in \#*) continue ;; esac

        # Reject absolute paths (ISC-11).
        case "$rel" in
            /*)
                fail "cut-paths manifest rejected: absolute path not allowed: '$rel'"
                return 1
                ;;
        esac
        # Reject `..` traversal anywhere in the path (ISC-11).
        case "$rel" in
            *..*)
                fail "cut-paths manifest rejected: '..' traversal not allowed: '$rel'"
                return 1
                ;;
        esac
        # Strip trailing slash for uniform comparison.
        rel="${rel%/}"

        # Enforce denylist (ISC-10).
        local protected="" guard
        for guard in "${protected_roots[@]}"; do
            case "$rel" in
                "$guard"|"$guard"/*)
                    protected="$guard"
                    break
                    ;;
            esac
        done
        if [ -n "$protected" ]; then
            fail "cut-paths manifest rejected: '$rel' is under protected user-owned root '$protected/' (denylist)"
            return 1
        fi

        local src="$cleanup_root/$rel"
        if [ ! -e "$src" ]; then
            continue
        fi

        if [ "$BACKUP_ENABLED" = "1" ]; then
            local dest="$backup_root/$rel"
            mkdir -p "$(dirname "$dest")"
            cp -r "$src" "$dest"
            rm -rf "$src"
            echo "  cut: $rel (backed up to ${backup_root#$PROJECT_DIR/}/$rel)"
            backed_up=1
        else
            rm -rf "$src"
            echo "  cut: $rel (removed)"
        fi
        removed=$((removed + 1))
    done < "$manifest"

    if [ "$removed" -gt 0 ]; then
        if [ "$backed_up" = "1" ]; then
            ok "Removed $removed cut path(s); backups at ${backup_root#$PROJECT_DIR/}"
            BACKUPS_CREATED=$((BACKUPS_CREATED + 1))
        else
            ok "Removed $removed cut path(s)"
        fi
    else
        ok "No framework-cut paths present (clean)"
    fi
}

install_v3_verify_fix() {
    local verify="$SCRIPT_DIR/verify.sh"
    if [ ! -x "$verify" ]; then
        warn "verify.sh not executable — skipping --fix step"
        return 0
    fi
    step "Running verify.sh --fix to auto-fix trivial drift"
    if "$verify" "$PROJECT_DIR" --fix; then
        ok "verify.sh --fix completed"
    else
        warn "verify.sh reported issues — review the output above"
    fi
}

# ---------------------------------------------------------------------------
# Orchestration per mode
# ---------------------------------------------------------------------------

run_full_install() {
    set_phases 12
    section "Running: Full install"
    if [ "$HAS_CLAUDE" = "1" ]; then
        section "Backing up existing .claude/"
        install_framework_overwrite
    else
        section "Installing framework files"
        install_framework_fresh
    fi
    section "Session directories"
    install_session_dirs
    section "Project memory"
    install_project_memory
    section "Wiring settings.json"
    install_settings
    section "MCP servers"
    install_mcp_servers
    section ".claudeignore"
    install_claudeignore
    section "Root CLAUDE.md framework import"
    install_root_claude_md_import
    section "Layered CLAUDE.md stubs"
    install_layered_claude_md
    section "Memory schema doc"
    install_schema
    section "Daily logs directory"
    install_daily
    section ".gitignore"
    update_gitignore
    section "Cleanup stray dirs"
    cleanup_stray_dirs
}

run_refresh_framework() {
    set_phases 12
    section "Running: Refresh framework files"
    install_framework_refresh
    section "Removing framework-retired paths"
    install_v3_cleanup_cut_paths
    section "Session directories"
    install_session_dirs
    section "Wiring settings.json"
    install_settings
    section "MCP servers"
    install_mcp_servers
    section ".claudeignore"
    install_claudeignore
    section "Root CLAUDE.md framework import"
    install_root_claude_md_import
    section "Layered CLAUDE.md stubs"
    install_layered_claude_md
    section "Memory schema doc"
    install_schema
    section "Daily logs directory"
    install_daily
    section ".gitignore"
    update_gitignore
    section "Cleanup stray dirs"
    cleanup_stray_dirs
}

install_v3_preflight_hook() {
    step "Installing pre-push hook for /preflight-ci"
    local forge_py="$PROJECT_DIR/.claude/scripts/forge/forge.py"
    if [ ! -f "$forge_py" ]; then
        warn "forge CLI not found at $forge_py — skipping hook install"
        return 0
    fi
    if [ ! -d "$PROJECT_DIR/.git" ]; then
        warn "$PROJECT_DIR is not a git repo — skipping hook install"
        return 0
    fi
    # Idempotent: re-installs over a Forge-owned hook, refuses to clobber a
    # user-written hook (exit 2). Either outcome is non-fatal.
    python3 "$forge_py" --project-root "$PROJECT_DIR" preflight enable-git-hook || true
}

run_refresh_v3() {
    set_phases 17
    section "Running: Forge Flow v3 upgrade (refresh-v3)"
    if [ "$HAS_CLAUDE" = "0" ]; then
        warn ".claude/ not present — refresh-v3 expects an existing install."
        warn "For a fresh install, use --mode full instead."
    fi
    section "Cross-repo cleanup"
    install_v3_cross_repo_cleanup
    section "Skill collision guard"
    guard_skill_collisions
    section "Framework files (rsync)"
    install_v3_framework_files
    section "Cutting v2 leftovers"
    install_v3_cut_v2_cleanup
    section "Cutting framework-removed paths"
    install_v3_cleanup_cut_paths
    section "Seeding specialists/ scaffold"
    install_v3_seed_specialists
    section "Session directories"
    install_session_dirs
    section "Wiring settings.json"
    install_settings
    section "MCP servers"
    install_mcp_servers
    section ".claudeignore"
    install_claudeignore
    section "Root CLAUDE.md framework import"
    install_root_claude_md_import
    section "Layered CLAUDE.md stubs"
    install_layered_claude_md
    section "Memory schema doc"
    install_schema
    section "Daily logs directory"
    install_daily
    section ".gitignore"
    update_gitignore
    section "Cleanup stray dirs"
    cleanup_stray_dirs
    section "Pre-push hook (/preflight-ci)"
    install_v3_preflight_hook
    section "Verify and fix"
    install_v3_verify_fix
}

# ---------------------------------------------------------------------------
# Summary
# ---------------------------------------------------------------------------

print_summary() {
    PHASES_TOTAL=0  # final summary banner — no counter
    section "Done"
    local total_elapsed=$(( $(date +%s) - INSTALL_START_TIME ))
    ok "Installation mode: $INSTALL_MODE"
    ok "Project: $PROJECT_DIR"
    ok "Total time: ${total_elapsed}s"
    [ "$BACKUPS_CREATED" -gt 0 ] && ok "Backups: $BACKUPS_CREATED file(s) saved to $(backup_path)"

    echo ""
    echo -e "${CYAN}Next steps:${NC}"
    echo ""
    case "$INSTALL_MODE" in
        full)
            if [ "$HAS_CLAUDE" = "1" ]; then
                echo "  1. cd \"$PROJECT_DIR\""
                echo "  2. claude"
                echo "  3. Run /migrate inside Claude Code to merge your old .claude/ config"
                echo "  4. If something goes wrong: ./.claude_restore.sh"
            else
                echo "  1. cd \"$PROJECT_DIR\""
                echo "  2. claude"
                echo "  3. Run /new-project or /new-project --current"
            fi
            ;;
        refresh-framework)
            if [ "$BACKUPS_CREATED" -gt 0 ]; then
                echo "  1. Review diffs of any files in $(backup_path)"
                echo "  2. cd \"$PROJECT_DIR\" && claude"
            else
                echo "  1. cd \"$PROJECT_DIR\" && claude"
                echo "  (No backup taken — refresh is not reversible in place.)"
            fi
            ;;
        refresh-v3)
            echo "  1. Review .claude/v3-migration-notes.md (if present — cross-repo cleanup notes)"
            if [ "$BACKUPS_CREATED" -gt 0 ]; then
                echo "  2. Review backups at $(backup_path)"
                echo "  3. cd \"$PROJECT_DIR\" && claude"
                echo "  4. Verify .claude/ALGORITHM/LATEST and .claude/CLAUDE.md reflect the current framework version"
                echo "  5. Run python3 .claude/scripts/forge/forge.py specialist list"
            else
                echo "  2. cd \"$PROJECT_DIR\" && claude"
                echo "  3. Verify .claude/ALGORITHM/LATEST and .claude/CLAUDE.md reflect the current framework version"
                echo "  4. Run python3 .claude/scripts/forge/forge.py specialist list"
                echo "  (No backup taken — refresh is not reversible in place.)"
            fi
            ;;
    esac

    echo ""
    echo -e "${CYAN}Verify:${NC}"
    echo "  $SCRIPT_DIR/verify.sh \"$PROJECT_DIR\""
    echo ""
}

run_verify() {
    local verify="$SCRIPT_DIR/verify.sh"
    if [ -x "$verify" ]; then
        echo ""
        # Default is yes; non-interactive runs verify without prompting
        # (EOF on read would kill the install under set -e).
        if [ "${AUTO_YES:-0}" = "1" ] || [ ! -t 0 ]; then
            "$verify" "$PROJECT_DIR"
            return
        fi
        read -r -p "Run post-install verification? [Y/n] " verify_choice
        if [[ ! "$verify_choice" =~ ^[Nn]$ ]]; then
            "$verify" "$PROJECT_DIR"
        fi
    fi
}

# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

parse_args() {
    INSTALL_MODE=""
    AUTO_YES=0
    PROJECT_DIR_ARG=""
    BACKUP_OVERRIDE=""   # "" | "on" | "off" — set by --backup / --no-backup

    while [ $# -gt 0 ]; do
        case "$1" in
            --mode)
                shift
                [ $# -gt 0 ] || { fail "--mode requires a value (full|refresh|refresh-v3)"; exit 1; }
                case "$1" in
                    full)                  INSTALL_MODE="full" ;;
                    refresh|refresh-framework) INSTALL_MODE="refresh-framework" ;;
                    refresh-v3|v3-upgrade) INSTALL_MODE="refresh-v3" ;;
                    *)
                        fail "Unknown --mode value: $1 (expected: full, refresh, refresh-v3)"
                        exit 1
                        ;;
                esac
                ;;
            --mode=*)
                local val="${1#--mode=}"
                case "$val" in
                    full)                  INSTALL_MODE="full" ;;
                    refresh|refresh-framework) INSTALL_MODE="refresh-framework" ;;
                    refresh-v3|v3-upgrade) INSTALL_MODE="refresh-v3" ;;
                    *)
                        fail "Unknown --mode value: $val (expected: full, refresh, refresh-v3)"
                        exit 1
                        ;;
                esac
                ;;
            --yes|-y)
                AUTO_YES=1
                ;;
            --backup)
                BACKUP_OVERRIDE="on"
                ;;
            --no-backup)
                BACKUP_OVERRIDE="off"
                ;;
            -h|--help)
                sed -n '2,20p' "$0" | sed 's/^# \{0,1\}//'
                exit 0
                ;;
            --*)
                fail "Unknown flag: $1"
                exit 1
                ;;
            *)
                if [ -z "$PROJECT_DIR_ARG" ]; then
                    PROJECT_DIR_ARG="$1"
                else
                    fail "Unexpected positional argument: $1"
                    exit 1
                fi
                ;;
        esac
        shift
    done
}

main() {
    BACKUPS_CREATED=0

    parse_args "$@"

    banner

    # Verify we're inside the framework repo. v2 required skills/; v3 builds
    # incrementally so the spine (scripts/forge/) is the stable signature.
    if [ ! -f "$FRAMEWORK_DIR/CLAUDE.md" ] || [ ! -d "$FRAMEWORK_DIR/scripts/forge" ]; then
        fail "Must be run from inside the forgeFlow repository. Expected framework at: $FRAMEWORK_DIR"
        exit 1
    fi
    ok "Framework at: $FRAMEWORK_DIR"

    preflight
    choose_project_dir "$PROJECT_DIR_ARG"
    detect_state
    choose_mode

    # --- Backup decision (refresh modes back up existing .claude/) ---
    # Resolution order:
    #   1. Explicit CLI flag (--backup / --no-backup) — wins
    #   2. BACKUP_ENABLED env var if pre-set by caller
    #   3. Interactive prompt (default Yes) on refresh / refresh-v3
    #   4. Default ON for full (cheap; user safety > friction)
    case "$BACKUP_OVERRIDE" in
        on)  BACKUP_ENABLED=1; ok "Backup: ON (--backup)" ;;
        off) BACKUP_ENABLED=0; warn "Backup: OFF (--no-backup) — you cannot revert this refresh in place" ;;
        "")
            case "$INSTALL_MODE" in
                refresh-framework|refresh-v3)
                    if [ "$AUTO_YES" = "1" ]; then
                        BACKUP_ENABLED=1
                        ok "Backup: ON (--yes default — pass --no-backup to skip)"
                    elif [ "$HAS_CLAUDE" = "1" ]; then
                        echo ""
                        echo "Refresh will overwrite framework files in $PROJECT_DIR/.claude/"
                        echo "A backup snapshots the current .claude/ to backups/$BACKUP_TIMESTAMP/"
                        echo "before the refresh — lets you diff or roll back per file."
                        read -r -p "Back up existing .claude/ before refresh? [Y/n] " backup_choice
                        if [[ "$backup_choice" =~ ^[Nn]$ ]]; then
                            BACKUP_ENABLED=0
                            warn "Backup: OFF — refresh will not be reversible in place"
                        else
                            BACKUP_ENABLED=1
                            ok "Backup: ON — snapshot will land at backups/$BACKUP_TIMESTAMP/"
                        fi
                    fi
                    ;;
                # full: backup defaults stay ON; full mode also does the
                # additional .claude_old/ sibling rename, which is its primary
                # rollback path.
            esac
            ;;
    esac

    echo ""
    if [ "$AUTO_YES" = "1" ]; then
        ok "Proceeding with $INSTALL_MODE (--yes)"
    else
        read -r -p "Proceed with $INSTALL_MODE? [Y/n] " go
        if [[ "$go" =~ ^[Nn]$ ]]; then
            echo "Cancelled."
            exit 0
        fi
    fi

    case "$INSTALL_MODE" in
        full)              run_full_install ;;
        refresh-framework) run_refresh_framework ;;
        refresh-v3)        run_refresh_v3 ;;
    esac

    print_summary
    run_verify
}

main "$@"
