#!/usr/bin/env python3
"""
worktree_safe_cleanup.py
Safe deletion of git worktrees spawned by background agents.

Contract (per ALGORITHM/v1.2.0.md "Background Agent Checkpoint Discipline"):
  - Refuses to delete a worktree whose `git status --porcelain` is non-empty.
  - With --force-promote, commits the dirty state under a `wip(reaped):` prefix
    on the worktree's branch, then deletes the worktree. The promoted commit
    SHA is printed to stdout so the parent can recover the state.
  - Never operates on the main worktree (refuses with non-zero exit).

This helper is for any Forge-owned code path that manages worktree lifecycle.
The Claude Code Agent-tool harness manages its own worktrees independently;
this script does NOT hook into that — it's available for skills/scripts that
spawn worktrees directly.

Usage:
  python3 .claude/scripts/forge/worktree_safe_cleanup.py <worktree-path>
  python3 .claude/scripts/forge/worktree_safe_cleanup.py <worktree-path> \
      --force-promote
  python3 .claude/scripts/forge/worktree_safe_cleanup.py <worktree-path> \
      --force-promote --json

Exit codes:
  0  - Worktree was clean (or successfully force-promoted) and deleted.
  1  - Worktree is dirty and --force-promote was not passed (refused).
  2  - Worktree path does not exist or is not a worktree.
  3  - Refused: target is the main worktree, not a linked worktree.
  4  - Git error (failed to commit or remove).
"""

from __future__ import annotations

import argparse
import json
import subprocess
import sys
from pathlib import Path


def _run(args: list[str], cwd: Path | None = None) -> subprocess.CompletedProcess:
    return subprocess.run(args, cwd=cwd, capture_output=True, text=True, check=False)


def _is_worktree(path: Path) -> tuple[bool, str]:
    """Return (is_linked_worktree, reason). Refuses main worktree."""
    if not path.exists():
        return False, f"path does not exist: {path}"
    if not (path / ".git").exists():
        return False, f"not a git worktree (no .git entry): {path}"
    # In a linked worktree, .git is a FILE containing 'gitdir: ...'.
    # In the main worktree, .git is a directory.
    git_entry = path / ".git"
    if git_entry.is_dir():
        return False, f"main worktree (refuses to operate): {path}"
    return True, ""


def _porcelain_status(worktree: Path) -> str:
    result = _run(["git", "status", "--porcelain"], cwd=worktree)
    if result.returncode != 0:
        raise RuntimeError(f"git status failed: {result.stderr.strip()}")
    return result.stdout


def _current_branch(worktree: Path) -> str:
    result = _run(["git", "rev-parse", "--abbrev-ref", "HEAD"], cwd=worktree)
    if result.returncode != 0:
        raise RuntimeError(f"git rev-parse failed: {result.stderr.strip()}")
    return result.stdout.strip()


def _force_promote(worktree: Path) -> str:
    """Commit current dirty state as wip(reaped) and return SHA."""
    add = _run(["git", "add", "-A"], cwd=worktree)
    if add.returncode != 0:
        raise RuntimeError(f"git add failed: {add.stderr.strip()}")
    commit = _run(
        [
            "git",
            "-c", "user.name=forge-worktree-safe-cleanup",
            "-c", "user.email=forge@local",
            "commit",
            "--no-verify",
            "--allow-empty",
            "-m", "wip(reaped): final state at cleanup",
        ],
        cwd=worktree,
    )
    if commit.returncode != 0:
        raise RuntimeError(f"git commit failed: {commit.stderr.strip()}")
    sha = _run(["git", "rev-parse", "HEAD"], cwd=worktree)
    if sha.returncode != 0:
        raise RuntimeError(f"git rev-parse HEAD failed: {sha.stderr.strip()}")
    return sha.stdout.strip()


def _remove_worktree(worktree: Path) -> None:
    """Remove the worktree via `git worktree remove`."""
    # Use the worktree path as a relative argument from the main repo root.
    main_root = _run(["git", "rev-parse", "--git-common-dir"], cwd=worktree)
    if main_root.returncode != 0:
        raise RuntimeError(
            f"failed to resolve main repo: {main_root.stderr.strip()}"
        )
    common_dir = Path(main_root.stdout.strip())
    main_repo = common_dir.parent if common_dir.name == ".git" else common_dir
    result = _run(
        ["git", "worktree", "remove", str(worktree), "--force"],
        cwd=main_repo,
    )
    if result.returncode != 0:
        raise RuntimeError(f"git worktree remove failed: {result.stderr.strip()}")


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Safe deletion of git worktrees spawned by background agents."
    )
    parser.add_argument("worktree", type=Path, help="path to the worktree to delete")
    parser.add_argument(
        "--force-promote",
        action="store_true",
        help="if worktree is dirty, commit state as wip(reaped) then delete",
    )
    parser.add_argument(
        "--json", action="store_true", help="emit JSON result to stdout"
    )
    args = parser.parse_args()

    worktree = args.worktree.resolve()
    result: dict[str, object] = {
        "worktree": str(worktree),
        "action": None,
        "promoted_sha": None,
        "branch": None,
        "dirty": None,
    }

    is_wt, reason = _is_worktree(worktree)
    if not is_wt:
        if "main worktree" in reason:
            print(reason, file=sys.stderr)
            if args.json:
                result["action"] = "refused-main-worktree"
                print(json.dumps(result))
            return 3
        print(reason, file=sys.stderr)
        if args.json:
            result["action"] = "not-a-worktree"
            print(json.dumps(result))
        return 2

    try:
        status = _porcelain_status(worktree)
        result["branch"] = _current_branch(worktree)
    except RuntimeError as e:
        print(f"error: {e}", file=sys.stderr)
        if args.json:
            result["action"] = "git-error"
            print(json.dumps(result))
        return 4

    dirty = bool(status.strip())
    result["dirty"] = dirty

    if dirty and not args.force_promote:
        print(
            f"refusing to delete dirty worktree (uncommitted changes detected):\n"
            f"{status}\n"
            f"re-run with --force-promote to auto-commit as wip(reaped) then delete",
            file=sys.stderr,
        )
        if args.json:
            result["action"] = "refused-dirty"
            print(json.dumps(result))
        return 1

    if dirty and args.force_promote:
        try:
            sha = _force_promote(worktree)
        except RuntimeError as e:
            print(f"error: {e}", file=sys.stderr)
            if args.json:
                result["action"] = "promote-failed"
                print(json.dumps(result))
            return 4
        result["promoted_sha"] = sha
        result["action"] = "promoted-and-deleted"
        if not args.json:
            print(f"promoted dirty state as wip(reaped) commit: {sha}")
    else:
        result["action"] = "deleted-clean"

    try:
        _remove_worktree(worktree)
    except RuntimeError as e:
        print(f"error: {e}", file=sys.stderr)
        if args.json:
            result["action"] = "remove-failed"
            print(json.dumps(result))
        return 4

    if args.json:
        print(json.dumps(result))
    else:
        print(f"worktree removed: {worktree}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
