#!/usr/bin/env python3
"""
consistency-banner.py
Hook wrapper around scripts/forge/check_consistency.py.

Behaviour by mode (selected via the flags forwarded to the checker):

  --summary  SessionStart banner. Auto-fix safe drift, then print a
             max-300-char banner if anything remains. Silent on clean.
  --json     PostToolUse silent recompute. Auto-fix; output JSON only on drift.
             Self-filters: only runs when the edited path looks like
             registry.json or docs/epics/**/T*.md.
  --strict   PreToolUse git-commit gate. Exits 2 (blocks the tool call) if
             blocking drift remains.
             Self-filters: only runs when the Bash command contains "git commit"
             so unrelated Bash calls don't pay the consistency-check tax.

Safety:
  - Token-budget: silent on success. Banner mode caps output at 300 chars.
  - Recursion guard: when --fix writes the registry, the resulting
    PostToolUse fires this script again. The FORGE_CONSISTENCY_RECURSION_GUARD
    env var short-circuits the recursive call.

Installed location:
  {project}/.claude/hooks/forge/consistency-banner.py
The checker it invokes lives at:
  {project}/.claude/scripts/forge/check_consistency.py
"""

from __future__ import annotations

import os
import re
import subprocess
import sys
from pathlib import Path

_REGISTRY_PATTERN = re.compile(r"docs/tasks/registry\.json$")
_TASK_FILE_PATTERN = re.compile(r"docs/epics/E\d+[^/]*/tasks/T\d+[^/]*\.md$")


def get_project_root() -> Path:
    env_root = os.environ.get("CLAUDE_PROJECT_DIR")
    if env_root and Path(env_root).exists():
        return Path(env_root)
    try:
        out = subprocess.run(
            ["git", "rev-parse", "--show-toplevel"],
            capture_output=True, text=True, check=True
        )
        return Path(out.stdout.strip())
    except (subprocess.CalledProcessError, FileNotFoundError):
        return Path.cwd()


# Non-blocking stdin read lives in the shared hook lib so every hook inherits
# the same guard (a plain read() hangs forever on an open, idle pipe — e.g. a
# manual `--summary` run or /reflect).
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from _hooklib import read_stdin_input  # noqa: E402


def should_run_post(input_data: dict) -> bool:
    """PostToolUse --json: run only when the touched path is registry or task file."""
    if not input_data:
        return True  # called manually / no envelope; just run
    file_path = (input_data.get("tool_input") or {}).get("file_path", "")
    if not file_path:
        return False
    return bool(
        _REGISTRY_PATTERN.search(file_path) or _TASK_FILE_PATTERN.search(file_path)
    )


def should_run_strict(input_data: dict) -> bool:
    """PreToolUse --strict: run only when Bash command contains "git commit"."""
    if not input_data:
        return True
    cmd = (input_data.get("tool_input") or {}).get("command", "")
    return "git commit" in cmd


def _resolve_checker(project_root: Path) -> Path | None:
    """Find the checker. Tries installed (.claude/scripts/forge) and
    framework-repo (scripts/forge) layouts."""
    candidates = [
        project_root / ".claude" / "scripts" / "forge" / "check_consistency.py",
        project_root / "scripts" / "forge" / "check_consistency.py",
    ]
    for c in candidates:
        if c.exists():
            return c
    return None


def _resolve_doctor(project_root: Path) -> Path | None:
    """Find doctor.py. Same candidate layouts as _resolve_checker — doctor
    is co-located with check_consistency.py in both installed and
    framework-repo trees."""
    candidates = [
        project_root / ".claude" / "scripts" / "forge" / "doctor.py",
        project_root / "scripts" / "forge" / "doctor.py",
    ]
    for c in candidates:
        if c.exists():
            return c
    return None


def _print_doctor_banner(project_root: Path) -> None:
    """Append forge doctor's one-line SessionStart banner, if unhealthy.

    Purely informational: doctor.py --banner is silent when healthy and
    always exits 0 by its own contract. This wrapper additionally never lets
    a doctor failure surface — any error here is swallowed silently, same
    doctrine as the rest of this hook.
    """
    doctor = _resolve_doctor(project_root)
    if doctor is None:
        return
    try:
        result = subprocess.run(
            ["python3", str(doctor), "--project-root", str(project_root), "--banner"],
            capture_output=True,
            text=True,
            timeout=5,
        )
    except (subprocess.TimeoutExpired, FileNotFoundError, OSError):
        return
    if result.stdout:
        sys.stdout.write(result.stdout)


def main() -> int:
    if os.environ.get("FORGE_CONSISTENCY_RECURSION_GUARD") == "1":
        return 0

    forwarded = sys.argv[1:] if len(sys.argv) > 1 else ["--fix", "--summary"]
    is_strict = "--strict" in forwarded
    is_json = "--json" in forwarded

    input_data = read_stdin_input()
    if is_strict and not should_run_strict(input_data):
        return 0
    if is_json and not should_run_post(input_data):
        return 0

    project_root = get_project_root()
    checker = _resolve_checker(project_root)
    if checker is None:
        if "--summary" in forwarded:
            _print_doctor_banner(project_root)
        return 0

    env = os.environ.copy()
    env["FORGE_CONSISTENCY_RECURSION_GUARD"] = "1"

    try:
        result = subprocess.run(
            ["python3", str(checker), *forwarded],
            env=env,
            capture_output=True,
            text=True,
            timeout=10,
        )
    except (subprocess.TimeoutExpired, FileNotFoundError, OSError) as exc:
        print(f"FORGE-CONSISTENCY: skipped ({exc})", file=sys.stderr)
        if "--summary" in forwarded:
            _print_doctor_banner(project_root)
        return 0

    if result.stdout:
        sys.stdout.write(result.stdout)
    if result.stderr:
        sys.stderr.write(result.stderr)

    # SessionStart banner mode only — doctor's check is purely informational
    # and belongs alongside the registry-consistency banner, not the
    # PostToolUse/PreToolUse paths (those are budget- and latency-sensitive).
    if "--summary" in forwarded:
        _print_doctor_banner(project_root)

    # PreToolUse contract: exit 2 blocks the tool call. The checker uses
    # exit 1 to mean "blocking drift remains" so it stays usable from CLI;
    # we translate here.
    if is_strict and result.returncode == 1:
        return 2
    return 0


if __name__ == "__main__":
    sys.exit(main())
