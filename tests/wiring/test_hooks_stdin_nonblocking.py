"""Regression: hooks must not hang on an open, idle stdin pipe.

The class bug (surfaced when a manual `consistency-banner.py --summary` hung
/reflect for 10 minutes): every hook that read its JSON envelope with a plain
`sys.stdin.read()` / `json.load(sys.stdin)` blocked forever when stdin was a
non-tty pipe that stayed open. `isatty()` can't distinguish a closed pipe
(EOF, safe) from an open idle one (EOF never arrives) — both are non-ttys.

Fix: every hook reads stdin via `_hooklib.read_stdin_input()`, which sets the
fd non-blocking. This test spawns each hook with an OS-level open-but-idle pipe
as stdin and asserts it returns quickly. Timing the child directly with
`os.pipe()` is deliberate — `sleep 30 | hook` would make the shell wait on
`sleep` and give a false "still hangs" reading.

New stdin-reading hooks are discovered automatically: if you add one, this test
covers it (and fails until it routes through the shared non-blocking helper).

Run from project root:
    python3 -m pytest tests/wiring/test_hooks_stdin_nonblocking.py -v
"""
from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[2]
HOOKS_DIR = REPO_ROOT / "hooks"

RETURN_BUDGET_S = 5.0  # generous; a fixed hook returns in <0.3s, a hung one never

# Hooks that read stdin but need a flag/env to reach their read without erroring
# earlier. path -> (extra argv, extra env). Everything else runs with no args.
HOOK_INVOCATION = {
    "hooks/forge/consistency-banner.py": (["--summary"], {}),
    "hooks/forge/checkpoint-nudge.py": ([], {"CHECKPOINT_NUDGE_DISABLED": "1"}),
    # base.py is an abstract class, not a runnable hook — exercise the shared
    # read path through a concrete subclass instead (see the explicit entry).
}

# base.py can't be run directly; a concrete validator stands in for it.
EXTRA_TARGETS = ["hooks/validators/agents/tdd_aaa.py"]


def _reads_stdin(path: Path) -> bool:
    """True if the file consumes stdin (so it's at risk of the hang)."""
    text = path.read_text(encoding="utf-8", errors="ignore")
    return (
        "sys.stdin.read" in text
        or "json.load(sys.stdin" in text
        or "read_stdin_input" in text
    )


def _discover_hooks() -> list[str]:
    found = []
    for p in sorted(HOOKS_DIR.rglob("*.py")):
        if "__pycache__" in p.parts:
            continue
        if p.name in ("_hooklib.py", "base.py") or p.name.startswith("__"):
            continue  # helper / abstract base — covered via EXTRA_TARGETS
        if _reads_stdin(p):
            found.append(str(p.relative_to(REPO_ROOT)))
    for extra in EXTRA_TARGETS:
        if extra not in found:
            found.append(extra)
    return found


HOOK_PATHS = _discover_hooks()


def _run_with_idle_pipe(rel_path: str) -> float | None:
    """Spawn the hook with an open, idle pipe on stdin. Return elapsed seconds,
    or None if it exceeded the budget (i.e. hung)."""
    import time

    argv, extra_env = HOOK_INVOCATION.get(rel_path, ([], {}))
    env = {**os.environ, **extra_env}
    r, w = os.pipe()  # read end -> child stdin; write end kept open, never written
    try:
        start = time.time()
        try:
            subprocess.run(
                [sys.executable, str(REPO_ROOT / rel_path), *argv],
                stdin=r, capture_output=True, timeout=RETURN_BUDGET_S,
                env=env, cwd=str(REPO_ROOT),
            )
        except subprocess.TimeoutExpired:
            return None
        return time.time() - start
    finally:
        os.close(r)
        os.close(w)


def test_discovery_found_the_known_hooks():
    """Guard the guard: the discovery must actually find the stdin hooks, so a
    broken _reads_stdin can't silently reduce this suite to zero cases."""
    assert len(HOOK_PATHS) >= 6, HOOK_PATHS
    assert "hooks/forge/consistency-banner.py" in HOOK_PATHS


@pytest.mark.parametrize("rel_path", HOOK_PATHS)
def test_hook_does_not_hang_on_idle_pipe(rel_path):
    elapsed = _run_with_idle_pipe(rel_path)
    assert elapsed is not None, (
        f"{rel_path} HANGS on an open idle stdin pipe (exceeded "
        f"{RETURN_BUDGET_S}s) — route its stdin read through "
        f"_hooklib.read_stdin_input()"
    )
    assert elapsed < RETURN_BUDGET_S


@pytest.mark.parametrize("rel_path", HOOK_PATHS)
def test_hook_handles_closed_stdin(rel_path):
    """Closed stdin (immediate EOF) is the automatic-event path — must still
    return promptly and must not be broken by the non-blocking change."""
    import time

    argv, extra_env = HOOK_INVOCATION.get(rel_path, ([], {}))
    env = {**os.environ, **extra_env}
    start = time.time()
    subprocess.run(
        [sys.executable, str(REPO_ROOT / rel_path), *argv],
        stdin=subprocess.DEVNULL, capture_output=True,
        timeout=RETURN_BUDGET_S, env=env, cwd=str(REPO_ROOT),
    )
    assert time.time() - start < RETURN_BUDGET_S
