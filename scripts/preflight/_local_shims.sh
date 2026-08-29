#!/usr/bin/env bash
# Project-local portability shims for /preflight-ci generated scripts.
#
# This file is sourced by every `.forge/preflight/<job>.sh` before its
# CI-transcribed steps run. It ships empty — extend it when your local
# toolchain differs from the CI runner's.
#
# Common shims:
#
#   # `pip` -> `python3 -m pip` when only pip3 / framework Python is present:
#   command -v pip >/dev/null 2>&1 || pip() { python3 -m pip "$@"; }
#
#   # `python` -> `python3` on systems without the unversioned symlink:
#   command -v python >/dev/null 2>&1 || python() { python3 "$@"; }
#
# Guidelines:
#   1. Idempotent — guard each shim with `command -v <bin> >/dev/null` so
#      it's a no-op when the real binary is on PATH.
#   2. Define functions, not aliases (aliases don't expand in non-interactive
#      shells, which is what preflight scripts run under).
#   3. This file is yours. It survives `install.sh --mode refresh` (the rsync
#      excludes it) AND `/preflight-ci --regenerate` (the generator seeds it
#      only when absent, and never overwrites a copy that differs). Edit the
#      copy in `.forge/preflight/` — that is the one the generated scripts
#      source, and it belongs in version control.

# --- pg reachability -------------------------------------------------------
# Used by the generated preflight guard for DB-dependent jobs: when the compose
# postgres is down, the job skips cleanly (exit 0) instead of ERRORing every DB
# test on a bad connection. The generator emits FORGE_PG_HOST/FORGE_PG_PORT
# (extracted from the Compose-rewritten DATABASE_URL) because DATABASE_URL is
# exported per-step inside subshells, after the guard runs.
#
# NOTE: this file is seeded only-if-missing, so installs predating this helper
# will not have it. The generated guard checks `declare -F` first and treats an
# absent helper as "run the job" — never as a silent skip.
_forge_pg_reachable() {
  local _host _port
  if [ -n "${FORGE_PG_HOST:-}" ] || [ -n "${FORGE_PG_PORT:-}" ]; then
    _host="${FORGE_PG_HOST:-localhost}"
    _port="${FORGE_PG_PORT:-5432}"
  elif [ -n "${DATABASE_URL:-}" ]; then
    local _hp="${DATABASE_URL#*@}"       # strip through the '@'
    _hp="${_hp%%/*}"                     # drop path
    if [ -n "$_hp" ] && [ "$_hp" != "$DATABASE_URL" ]; then
      _host="${_hp%%:*}"
      case "$_hp" in *:*) _port="${_hp##*:}";; esac
    fi
    _host="${_host:-localhost}"
    _port="${_port:-5432}"
  else
    _host="localhost"
    _port="5432"
  fi
  # No pg_isready on this machine -> cannot prove it's down; assume reachable
  # so the job RUNS. Skipping on missing tooling would hide real failures.
  if ! command -v pg_isready >/dev/null 2>&1; then
    return 0
  fi
  pg_isready -h "$_host" -p "$_port" >/dev/null 2>&1
}
export -f _forge_pg_reachable 2>/dev/null || true
:
