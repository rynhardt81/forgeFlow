#!/usr/bin/env python3
"""
checkpoint-nudge.py
PostToolUse advisory: nudge background agents to commit checkpoints.

Contract (per ALGORITHM/v1.2.0.md "Background Agent Checkpoint Discipline"):

When the current process is running inside a background-agent worktree
(detected via WORKTREE_AGENT_ID env OR a branch name starting with `wip-`),
this hook counts tool actions since the last commit on the branch. After
N actions (default 10) without a new commit, it emits a non-blocking
advisory to stderr suggesting a `wip(checkpoint)` commit.

NEVER blocks — always exits 0. The advisory is informational only.

Reads PostToolUse JSON from stdin (Claude Code contract); does not require
any specific fields. State is persisted to a per-branch counter file under
`.claude/.checkpoint-state/`.

Tuning:
  CHECKPOINT_NUDGE_THRESHOLD   actions-without-commit before advising (default 10)
  CHECKPOINT_NUDGE_DISABLED    if set to a truthy value, the hook is a no-op
"""

from __future__ import annotations

import json
import os
import subprocess
import sys
from pathlib import Path


def _truthy(val: str | None) -> bool:
    return val is not None and val.strip().lower() in {"1", "true", "yes", "on"}


def _project_root() -> Path:
    env = os.environ.get("CLAUDE_PROJECT_DIR")
    if env and Path(env).exists():
        return Path(env)
    try:
        out = subprocess.run(
            ["git", "rev-parse", "--show-toplevel"],
            capture_output=True, text=True, check=True
        )
        return Path(out.stdout.strip())
    except (subprocess.CalledProcessError, FileNotFoundError):
        return Path.cwd()


def _current_branch(root: Path) -> str | None:
    try:
        out = subprocess.run(
            ["git", "rev-parse", "--abbrev-ref", "HEAD"],
            cwd=root, capture_output=True, text=True, check=False,
        )
        if out.returncode != 0:
            return None
        return out.stdout.strip() or None
    except FileNotFoundError:
        return None


def _head_sha(root: Path) -> str | None:
    out = subprocess.run(
        ["git", "rev-parse", "HEAD"],
        cwd=root, capture_output=True, text=True, check=False,
    )
    if out.returncode != 0:
        return None
    return out.stdout.strip() or None


def _in_background_context(branch: str | None) -> bool:
    if os.environ.get("WORKTREE_AGENT_ID"):
        return True
    if branch and branch.startswith("wip-"):
        return True
    return False


def _read_state(state_file: Path) -> dict:
    if not state_file.exists():
        return {}
    try:
        return json.loads(state_file.read_text())
    except (json.JSONDecodeError, OSError):
        return {}


def _write_state(state_file: Path, state: dict) -> None:
    state_file.parent.mkdir(parents=True, exist_ok=True)
    state_file.write_text(json.dumps(state))


def main() -> int:
    # Always swallow stdin per Claude Code hook contract
    try:
        sys.stdin.read()
    except Exception:
        pass

    if _truthy(os.environ.get("CHECKPOINT_NUDGE_DISABLED")):
        return 0

    root = _project_root()
    branch = _current_branch(root)
    if not _in_background_context(branch):
        return 0

    head = _head_sha(root)
    if head is None:
        return 0

    threshold_raw = os.environ.get("CHECKPOINT_NUDGE_THRESHOLD", "10")
    try:
        threshold = max(1, int(threshold_raw))
    except ValueError:
        threshold = 10

    state_file = root / ".claude" / ".checkpoint-state" / f"{branch or 'detached'}.json"
    state = _read_state(state_file)

    last_head = state.get("head")
    actions = int(state.get("actions", 0))

    if last_head != head:
        # New commit landed — reset counter
        state = {"head": head, "actions": 0}
        _write_state(state_file, state)
        return 0

    actions += 1
    state["actions"] = actions
    _write_state(state_file, state)

    if actions >= threshold:
        print(
            f"⚠️  checkpoint-nudge: {actions} tool actions since last commit on "
            f"`{branch}` — consider `git commit -m \"wip(checkpoint): <stage>\"` "
            f"before the next slow operation. (Hook is advisory; never blocks. "
            f"Set CHECKPOINT_NUDGE_DISABLED=1 to silence.)",
            file=sys.stderr,
        )
        # Don't reset — let the user see the nudge until they commit. Cap
        # repeat-spam at a multiplier of threshold to avoid every-action noise.
        if actions >= threshold * 3:
            state["actions"] = threshold  # ratchet back to threshold so we keep nudging at lower volume
            _write_state(state_file, state)

    return 0


if __name__ == "__main__":
    sys.exit(main())
