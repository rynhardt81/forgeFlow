# /// script
# requires-python = ">=3.8"
# dependencies = []
# ///
"""
Claude Forge Damage Control - Test Lock Hook
============================================

Closes the "make the test green by editing the test" escape.

The /fix-bug discipline is: reproduce, write a regression test that fails,
commit it, then fix the source until it passes. The failure mode is editing
the test instead of the source — the suite goes green, the bug ships, and the
Stop-hook validator only notices afterwards, once the work is already done.

This hook denies writes to paths listed in a lock file while the fix is in
progress. It is opt-in: framework hooks are advisory and never block, so this
ships as a damage-control cookbook entry that a project installs deliberately.

Lock file: .claude/.test-lock — one path per line, relative to the project
root. Blank lines and # comments ignored. No lock file, or an empty one, means
nothing is blocked; that is the common case and must stay free.

Exit codes:
  0 = allow
  2 = deny (stderr is fed back to Claude)
"""

import json
import os
import sys
from pathlib import Path

LOCK_REL = Path(".claude") / ".test-lock"
WRITE_TOOLS = {"Edit", "Write", "MultiEdit", "NotebookEdit"}


def project_root() -> Path:
    return Path(os.environ.get("CLAUDE_PROJECT_DIR", os.getcwd()))


def locked_paths(root: Path) -> list[str]:
    """Paths currently protected. Absent or empty lock file -> nothing."""
    lock = root / LOCK_REL
    if not lock.is_file():
        return []
    try:
        raw = lock.read_text(encoding="utf-8")
    except OSError:
        # A lock we cannot read must not silently stop protecting; but it also
        # must not block every edit in the project. Fail open and say so.
        print(
            f"test-lock: {lock} exists but could not be read — not enforcing",
            file=sys.stderr,
        )
        return []
    return [
        line.strip()
        for line in raw.splitlines()
        if line.strip() and not line.strip().startswith("#")
    ]


def targets(payload: dict) -> list[str]:
    inp = payload.get("tool_input") or {}
    found = [inp.get("file_path"), inp.get("notebook_path")]
    for edit in inp.get("edits") or []:
        if isinstance(edit, dict):
            found.append(edit.get("file_path"))
    return [f for f in found if f]


def main() -> int:
    try:
        payload = json.load(sys.stdin)
    except (json.JSONDecodeError, ValueError):
        return 0  # malformed payload is the harness's problem, not ours

    if payload.get("tool_name") not in WRITE_TOOLS:
        return 0

    root = project_root()
    locks = locked_paths(root)
    if not locks:
        return 0

    for target in targets(payload):
        try:
            rel = Path(target).resolve().relative_to(root.resolve()).as_posix()
        except (ValueError, OSError):
            rel = target
        for locked in locks:
            if rel == locked or rel.endswith("/" + locked.lstrip("./")):
                print(
                    f"BLOCKED: {rel} is a committed regression test, locked while "
                    f"the fix is in progress.\n\n"
                    f"A failing test is the specification for this fix. Editing it "
                    f"to pass is how a bug ships green. Change the source under "
                    f"test instead.\n\n"
                    f"If the test itself is genuinely wrong, say so and clear the "
                    f"lock deliberately:\n"
                    f"    rm {LOCK_REL}\n",
                    file=sys.stderr,
                )
                return 2
    return 0


if __name__ == "__main__":
    sys.exit(main())
