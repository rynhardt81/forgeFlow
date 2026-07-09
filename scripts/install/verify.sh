#!/bin/bash
#
# Claude Forge — Post-install verification
#
# Compares an installed project against the framework source and reports
# what's missing, outdated, misplaced, or broken. Run after install.sh
# or any time you suspect drift.
#
# Usage:
#   ./scripts/install/verify.sh /path/to/project        # verify a specific project
#   ./scripts/install/verify.sh /path/to/project --fix   # report + auto-fix trivial issues
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

ERRORS=0
WARNINGS=0
FIXES=0
FIX_MODE=0

ok()   { echo -e "  ${GREEN}✓${NC} $1"; }
fail() { echo -e "  ${RED}✗${NC} $1"; ERRORS=$((ERRORS + 1)); }
warn() { echo -e "  ${YELLOW}⚠${NC} $1"; WARNINGS=$((WARNINGS + 1)); }
info() { echo -e "  ${BLUE}·${NC} $1"; }

section() {
    echo ""
    echo -e "${CYAN}${BOLD}$1${NC}"
    echo -e "${CYAN}$(printf '%.0s─' {1..60})${NC}"
}

auto_fix() {
    # $1 = description, $2+ = command
    if [ "$FIX_MODE" = "1" ]; then
        local desc="$1"; shift
        "$@"
        echo -e "  ${GREEN}⚡${NC} Fixed: $desc"
        FIXES=$((FIXES + 1))
    fi
}

# ---------------------------------------------------------------------------
# Args
# ---------------------------------------------------------------------------

if [ -z "$1" ] || [ "$1" = "--help" ] || [ "$1" = "-h" ]; then
    echo "Usage: $0 /path/to/project [--fix]"
    echo ""
    echo "Checks a Claude Forge installation against the framework source and"
    echo "reports missing, outdated, or misplaced files."
    echo ""
    echo "  --fix    Auto-fix trivial issues (create missing dirs, copy missing"
    echo "           files, remove stray copies). Non-destructive fixes only."
    exit 0
fi

PROJECT_DIR="$1"
[ "$2" = "--fix" ] && FIX_MODE=1

if [ ! -d "$PROJECT_DIR" ]; then
    echo -e "${RED}Error: directory does not exist: $PROJECT_DIR${NC}"
    exit 1
fi
PROJECT_DIR="$(cd "$PROJECT_DIR" && pwd)"

if [ ! -f "$FRAMEWORK_DIR/CLAUDE.md" ]; then
    echo -e "${RED}Error: framework not found at $FRAMEWORK_DIR${NC}"
    exit 1
fi

echo ""
echo -e "${CYAN}${BOLD}Claude Forge — Installation Verification${NC}"
echo -e "${CYAN}$(printf '%.0s═' {1..60})${NC}"
echo -e "  Project:   $PROJECT_DIR"
echo -e "  Framework: $FRAMEWORK_DIR"
[ "$FIX_MODE" = "1" ] && echo -e "  Mode:      ${GREEN}auto-fix enabled${NC}"

# ---------------------------------------------------------------------------
# 1. Core framework structure under .claude/
# ---------------------------------------------------------------------------

section "1. Framework structure (.claude/)"

CLAUDE_DIR="$PROJECT_DIR/.claude"

if [ ! -d "$CLAUDE_DIR" ]; then
    fail ".claude/ directory missing — run install.sh first"
    echo ""
    echo -e "${RED}Cannot continue without .claude/. Aborting.${NC}"
    exit 1
fi
ok ".claude/ exists"

# Required subdirectories (v3 roster — commands/ and features/ deliberately cut)
for dir in agents hooks memories reference rules skills standards templates; do
    if [ -d "$CLAUDE_DIR/$dir" ]; then
        ok "$dir/"
    else
        fail "$dir/ missing"
        auto_fix "create $dir/" mkdir -p "$CLAUDE_DIR/$dir"
    fi
done

# Session dirs
for dir in memories/sessions/active memories/sessions/completed; do
    if [ -d "$CLAUDE_DIR/$dir" ]; then
        ok "$dir/"
    else
        fail "$dir/ missing"
        auto_fix "create $dir/" mkdir -p "$CLAUDE_DIR/$dir"
    fi
done

# ---------------------------------------------------------------------------
# 2. Reference documentation
# ---------------------------------------------------------------------------

section "2. Reference documentation (.claude/reference/)"

ref_missing=0
for f in "$FRAMEWORK_DIR"/reference/*.md; do
    fname="$(basename "$f")"
    target="$CLAUDE_DIR/reference/$fname"
    if [ -f "$target" ]; then
        # Check if outdated (different from framework source)
        if ! diff -q "$f" "$target" >/dev/null 2>&1; then
            warn "$fname exists but differs from framework source"
        fi
    else
        fail "$fname missing"
        ref_missing=$((ref_missing + 1))
        auto_fix "copy $fname" cp "$f" "$CLAUDE_DIR/reference/"
    fi
done
[ "$ref_missing" = "0" ] && ok "All reference files present"

# ---------------------------------------------------------------------------
# 3. Agent definitions
# ---------------------------------------------------------------------------

section "3. Agents (.claude/agents/)"

agent_missing=0
for f in "$FRAMEWORK_DIR"/agents/*.md; do
    fname="$(basename "$f")"
    target="$CLAUDE_DIR/agents/$fname"
    if [ ! -f "$target" ]; then
        fail "agent $fname missing"
        agent_missing=$((agent_missing + 1))
        auto_fix "copy agent $fname" cp "$f" "$CLAUDE_DIR/agents/"
    fi
done

[ "$agent_missing" = "0" ] && ok "All agent definitions present"

# ---------------------------------------------------------------------------
# 4. Rules
# ---------------------------------------------------------------------------

section "4. Rules (.claude/rules/)"

rules_missing=0
for f in "$FRAMEWORK_DIR"/rules/*.md; do
    fname="$(basename "$f")"
    if [ ! -f "$CLAUDE_DIR/rules/$fname" ]; then
        fail "rule $fname missing"
        rules_missing=$((rules_missing + 1))
        auto_fix "copy rule $fname" cp "$f" "$CLAUDE_DIR/rules/"
    fi
done
[ "$rules_missing" = "0" ] && ok "All rules present"

# ---------------------------------------------------------------------------
# 5. Skills
# ---------------------------------------------------------------------------

section "5. Skills (.claude/skills/)"

skills_missing=0
for d in "$FRAMEWORK_DIR"/skills/*/; do
    sname="$(basename "$d")"
    # Skip non-skill directories (eval workspaces, etc.)
    [ -f "$d/SKILL.md" ] || continue
    target="$CLAUDE_DIR/skills/$sname"
    if [ ! -d "$target" ]; then
        fail "skill $sname/ missing"
        skills_missing=$((skills_missing + 1))
        auto_fix "copy skill $sname/" cp -r "$d" "$CLAUDE_DIR/skills/"
    elif [ ! -f "$target/SKILL.md" ]; then
        fail "skill $sname/SKILL.md missing"
        skills_missing=$((skills_missing + 1))
    fi
done
[ "$skills_missing" = "0" ] && ok "All skills present"

# ---------------------------------------------------------------------------
# 6. Settings and hooks wiring
# ---------------------------------------------------------------------------

section "6. Settings & hooks"

settings="$CLAUDE_DIR/settings.json"
if [ -f "$settings" ]; then
    ok "settings.json exists"
    if command -v python3 >/dev/null 2>&1; then
        # Check hook events are wired
        wired=$(python3 -c "
import json, sys
try:
    d = json.load(open(sys.argv[1]))
    hooks = d.get('hooks', {})
    expected = {'SessionStart', 'PreCompact', 'SessionEnd'}
    missing = expected - set(hooks.keys())
    if missing:
        print('MISSING:' + ','.join(sorted(missing)))
    else:
        print('OK')
except Exception as e:
    print('ERROR:' + str(e))
" "$settings")
        if [ "$wired" = "OK" ]; then
            ok "SessionStart, PreCompact, SessionEnd hooks wired"
        elif [[ "$wired" == MISSING:* ]]; then
            fail "Hook events not wired: ${wired#MISSING:}"
            warn "Run install.sh (refresh mode) to re-merge settings.json"
        else
            fail "Cannot parse settings.json: ${wired#ERROR:}"
        fi
    else
        warn "python3 not available — cannot verify hook wiring"
    fi
else
    fail "settings.json missing — hooks will NOT fire"
    auto_fix "copy settings.json" cp "$FRAMEWORK_DIR/hooks/settings.json" "$settings"
fi

# Legacy settings warning
if [ -f "$PROJECT_DIR/hooks/settings.json" ]; then
    warn "Legacy hooks/settings.json at project root — Claude Code ignores this location"
fi

# ---------------------------------------------------------------------------
# 7. Project data (project root)
# ---------------------------------------------------------------------------

section "7. Project data (project root)"

# docs/project-memory/
if [ -d "$PROJECT_DIR/docs/project-memory" ]; then
    ok "docs/project-memory/ at project root"
    for f in bugs.md decisions.md key-facts.md patterns.md; do
        [ -f "$PROJECT_DIR/docs/project-memory/$f" ] || warn "docs/project-memory/$f missing (template)"
    done
else
    fail "docs/project-memory/ missing"
fi

# daily/
if [ -d "$PROJECT_DIR/daily" ]; then
    ok "daily/ at project root"
    [ -f "$PROJECT_DIR/daily/.gitignore" ] || warn "daily/.gitignore missing"
else
    fail "daily/ missing"
    auto_fix "create daily/" bash -c "mkdir -p '$PROJECT_DIR/daily' && printf '# Daily logs\\n*\\n!.gitignore\\n' > '$PROJECT_DIR/daily/.gitignore'"
fi

# MEMORY-SCHEMA.md
if [ -f "$PROJECT_DIR/MEMORY-SCHEMA.md" ]; then
    ok "MEMORY-SCHEMA.md present"
else
    warn "MEMORY-SCHEMA.md missing"
    [ -f "$FRAMEWORK_DIR/MEMORY-SCHEMA.md" ] && auto_fix "copy MEMORY-SCHEMA.md" cp "$FRAMEWORK_DIR/MEMORY-SCHEMA.md" "$PROJECT_DIR/"
fi

# ---------------------------------------------------------------------------
# 8. Stray copies (should NOT exist under .claude/)
# ---------------------------------------------------------------------------

section "8. Stray copies check"

stray_found=0
for stray in "$CLAUDE_DIR/daily" "$CLAUDE_DIR/docs/project-memory"; do
    if [ -d "$stray" ]; then
        fail "Stray directory: ${stray#$PROJECT_DIR/} (runtime uses project root, not .claude/)"
        stray_found=1
        auto_fix "remove stray ${stray#$PROJECT_DIR/}" rm -rf "$stray"
    fi
done
[ "$stray_found" = "0" ] && ok "No stray copies under .claude/"

# ---------------------------------------------------------------------------
# 9. Runtime prerequisites
# ---------------------------------------------------------------------------

section "9. Runtime prerequisites"

if command -v python3 >/dev/null 2>&1; then
    ver=$(python3 -c 'import sys; print(f"{sys.version_info.major}.{sys.version_info.minor}")')
    pyok=$(python3 -c 'import sys; print(1 if sys.version_info >= (3, 10) else 0)')
    if [ "$pyok" = "1" ]; then ok "python3 $ver (>=3.10)"; else fail "python3 $ver (need 3.10+)"; fi
else
    fail "python3 not found"
fi

if command -v claude >/dev/null 2>&1; then
    ok "claude CLI: $(command -v claude)"
else
    warn "claude CLI not found (memory flush/compile will fail)"
fi

if command -v git >/dev/null 2>&1; then ok "git available"; else warn "git not found"; fi

# ---------------------------------------------------------------------------
# 10. CLAUDE.md presence
# ---------------------------------------------------------------------------

section "10. Project documentation"

if [ -f "$PROJECT_DIR/CLAUDE.md" ] || [ -f "$CLAUDE_DIR/CLAUDE.md" ] || [ -f "$PROJECT_DIR/.claude/CLAUDE.md" ]; then
    ok "CLAUDE.md found"
else
    warn "No CLAUDE.md — run /new-project or /refresh-project-context after first session"
fi

if [ -f "$PROJECT_DIR/CHEATSHEET.md" ] || [ -f "$CLAUDE_DIR/CHEATSHEET.md" ]; then
    ok "CHEATSHEET.md found"
else
    info "No CHEATSHEET.md yet (created by /new-project or /refresh-project-context)"
fi

# .gitignore entries
if [ -f "$PROJECT_DIR/.gitignore" ]; then
    if grep -q "daily/" "$PROJECT_DIR/.gitignore"; then
        ok ".gitignore includes daily/"
    else
        warn ".gitignore missing daily/ entry"
    fi
else
    info "No .gitignore (daily/ logs may get committed)"
fi

# ---------------------------------------------------------------------------
# Summary
# ---------------------------------------------------------------------------

echo ""
echo -e "${CYAN}${BOLD}$(printf '%.0s═' {1..60})${NC}"
if [ "$ERRORS" = "0" ] && [ "$WARNINGS" = "0" ]; then
    echo -e "${GREEN}${BOLD}All checks passed.${NC} Installation is healthy."
elif [ "$ERRORS" = "0" ]; then
    echo -e "${YELLOW}${BOLD}$WARNINGS warning(s), 0 errors.${NC} Install is functional but has minor gaps."
else
    echo -e "${RED}${BOLD}$ERRORS error(s), $WARNINGS warning(s).${NC} Install needs attention."
fi

if [ "$FIXES" -gt 0 ]; then
    echo -e "${GREEN}Auto-fixed $FIXES issue(s).${NC}"
fi

if [ "$ERRORS" -gt 0 ] && [ "$FIX_MODE" = "0" ]; then
    echo ""
    echo -e "Run with ${BOLD}--fix${NC} to auto-repair trivial issues:"
    echo -e "  $0 \"$PROJECT_DIR\" --fix"
fi

echo ""
exit "$( [ "$ERRORS" = "0" ] && echo 0 || echo 1 )"
