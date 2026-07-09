#!/usr/bin/env python3
"""
check_undefined_names.py — slicing-pattern bug catcher for the /refactor skill.

Catches the class of bug produced when a Structural refactor splits a Python
file along section boundaries but forgets to import a module-local helper
into each new file that calls it. The call is a NameError at runtime — and
if the calling code sits inside a broad `try/except Exception`, it gets
swallowed and silently corrupts behaviour.

Strategy: delegate to pyflakes. Pyflakes' built-in undefined-name check is
exactly what we need — it walks the AST, builds defined+imported sets per
scope, and flags any reference that doesn't resolve. We filter pyflakes
output to only `undefined name` (F821-class) findings — that's the slicing
bug class. Other pyflakes findings (unused imports, etc.) are surfaced as
non-blocking context.

Usage (called from /refactor skill Step 3 or Step 5):

    python3 .claude/skills/refactor/Tools/check_undefined_names.py \\
        path/to/new/module_a.py path/to/new/module_b.py

Or by glob:

    python3 .claude/skills/refactor/Tools/check_undefined_names.py \\
        path/to/new/module_*.py

Exit codes:
    0  — no undefined-name errors found in any input file
    1  — one or more undefined-name errors (slicing bug — fix before merge)
    2  — pyflakes not available; check skipped (warn but don't block)

Pyflakes lookup order:
    1. `pyflakes` on PATH
    2. `python3 -m pyflakes`
    3. `docker exec $REFACTOR_CHECK_CONTAINER python -m pyflakes` — opt-in.
       Only attempted when REFACTOR_CHECK_CONTAINER is set to the name of a
       running container that has pyflakes inside it. Useful when the
       project's deps live in a dev container, not the host.

The skill does not block the refactor when pyflakes is unavailable; the
finding surfaces in the PR description so reviewers know the gate didn't run.
"""

from __future__ import annotations

import os
import shutil
import subprocess
import sys
from pathlib import Path


CONTAINER_NAME = os.environ.get("REFACTOR_CHECK_CONTAINER", "")


def find_pyflakes_invocation(files: list[str]) -> tuple[list[str], str] | None:
    """Return (argv, label) for the best pyflakes invocation, or None.

    Tries in order:
      1. `pyflakes` on PATH
      2. `python3 -m pyflakes` on PATH
      3. `docker exec <container> python -m pyflakes` — only if
         REFACTOR_CHECK_CONTAINER env var is set to a running container.
    """
    if shutil.which("pyflakes"):
        return (["pyflakes", *files], "host pyflakes")

    # Try host python -m pyflakes
    try:
        subprocess.run(
            [sys.executable, "-c", "import pyflakes"],
            check=True,
            capture_output=True,
            timeout=5,
        )
        return ([sys.executable, "-m", "pyflakes", *files], "host python -m pyflakes")
    except (subprocess.CalledProcessError, subprocess.TimeoutExpired, FileNotFoundError):
        pass

    # Opt-in docker exec fallback. Only attempted when REFACTOR_CHECK_CONTAINER
    # is set; framework default is empty, so projects that don't use this
    # pattern are unaffected.
    if CONTAINER_NAME and shutil.which("docker"):
        try:
            ps = subprocess.run(
                ["docker", "ps", "--filter", f"name={CONTAINER_NAME}", "--format", "{{.Names}}"],
                check=True,
                capture_output=True,
                text=True,
                timeout=5,
            )
            if CONTAINER_NAME in ps.stdout:
                return (
                    [
                        "docker",
                        "exec",
                        CONTAINER_NAME,
                        "python",
                        "-m",
                        "pyflakes",
                        *files,
                    ],
                    f"docker exec {CONTAINER_NAME} python -m pyflakes",
                )
        except (subprocess.CalledProcessError, subprocess.TimeoutExpired, FileNotFoundError):
            pass

    return None


def main(argv: list[str]) -> int:
    if not argv:
        print(
            "usage: check_undefined_names.py FILE [FILE ...]\n"
            "  Runs pyflakes against each FILE and surfaces only F821-class "
            "(undefined name) findings.",
            file=sys.stderr,
        )
        return 2

    # Filter out non-existent paths early so pyflakes doesn't error on its own.
    files: list[str] = []
    for path in argv:
        p = Path(path)
        if not p.exists():
            print(f"warning: file not found, skipping: {path}", file=sys.stderr)
            continue
        files.append(path)

    if not files:
        print("error: no valid files to check", file=sys.stderr)
        return 2

    invocation = find_pyflakes_invocation(files)
    if invocation is None:
        container_hint = (
            f" or in the {CONTAINER_NAME!r} container" if CONTAINER_NAME else ""
        )
        print(
            f"warning: pyflakes is not available on the host{container_hint} — "
            "skipping undefined-name check.\n"
            "         Install pyflakes (`pip install pyflakes`) or set "
            "REFACTOR_CHECK_CONTAINER to a running dev container that has it.",
            file=sys.stderr,
        )
        return 2

    cmd, label = invocation
    print(f"check_undefined_names: invoking {label}", file=sys.stderr)

    try:
        result = subprocess.run(cmd, capture_output=True, text=True, timeout=30)
    except subprocess.TimeoutExpired:
        print("error: pyflakes timed out (30s)", file=sys.stderr)
        return 2

    # Pyflakes prints findings to stdout, errors to stderr.
    # We care about lines containing "undefined name" — the F821 class.
    undefined_lines = [
        line
        for line in result.stdout.splitlines()
        if "undefined name" in line
    ]

    # Surface other pyflakes output (unused imports, etc.) for context but
    # don't fail the check on them — only undefined-name is a slicing bug.
    other_lines = [
        line
        for line in result.stdout.splitlines()
        if line and "undefined name" not in line
    ]

    if undefined_lines:
        print(
            f"\n[FAIL] check_undefined_names: {len(undefined_lines)} undefined-name "
            f"reference(s) found — likely slicing bug:\n",
            file=sys.stderr,
        )
        for line in undefined_lines:
            print(f"  {line}", file=sys.stderr)
        if other_lines:
            print(
                f"\n  ({len(other_lines)} other pyflakes finding(s) suppressed; "
                "run pyflakes directly to see them.)",
                file=sys.stderr,
            )
        return 1

    if other_lines:
        print(
            f"check_undefined_names: PASS (0 undefined-name issues; "
            f"{len(other_lines)} other pyflakes findings — non-blocking).",
            file=sys.stderr,
        )
    else:
        print(
            "check_undefined_names: PASS (0 undefined-name issues, "
            "0 other pyflakes findings).",
            file=sys.stderr,
        )
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
