#!/usr/bin/env python3
"""Shared helpers for Forge Flow hooks.

Hooks are standalone scripts (`python3 .claude/hooks/<area>/<name>.py`), not a
package, so each imports this via a two-line sys.path insert:

    import sys
    from pathlib import Path
    sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
    from _hooklib import read_stdin_input   # noqa: E402

The one thing every hook needs and kept re-implementing (badly) is reading the
JSON envelope off stdin WITHOUT hanging.
"""

from __future__ import annotations

import json
import os
import sys


def read_stdin_raw() -> str:
    """Read the hook's stdin envelope without blocking on an open, idle pipe.

    Automatic hook events (SessionStart/PostToolUse/...) send the envelope and
    close stdin -> immediate EOF, so a plain read() returns at once. But manual
    or wrapped runs -- `consistency-banner.py --summary`, /reflect calling a
    banner, an agent's Bash tool that leaves stdin open -- hand the hook a pipe
    that never sees EOF. A plain read() then blocks until the caller times out
    (observed: a full 10-minute timeout).

    isatty() can't tell the two apart: a pipe is not a tty in EITHER case. So we
    set the fd non-blocking and treat "no data available" the same as "no
    envelope". Cross-platform: os.set_blocking works on Windows pipes;
    select.select on a non-socket fd does not, which is why we don't use it.
    """
    if sys.stdin.isatty():
        return ""
    try:
        fd = sys.stdin.fileno()
    except (OSError, ValueError):
        return ""
    try:
        os.set_blocking(fd, False)
    except (OSError, ValueError):
        # Can't switch to non-blocking (rare). Fall back to a plain read; on an
        # automatic event this still returns immediately at EOF.
        try:
            return sys.stdin.read()
        except (OSError, ValueError):
            return ""
    chunks = []
    try:
        while True:
            try:
                chunk = os.read(fd, 65536)
            except BlockingIOError:
                break  # open pipe, no data right now -> treat as no envelope
            if not chunk:
                break  # EOF -> done
            chunks.append(chunk)
    except (OSError, ValueError):
        return ""
    finally:
        try:
            os.set_blocking(fd, True)
        except (OSError, ValueError):
            pass
    return b"".join(chunks).decode("utf-8", "replace")


def read_stdin_input() -> dict:
    """Non-blocking stdin read parsed as JSON. Returns {} on empty/invalid."""
    raw = read_stdin_raw()
    if not raw.strip():
        return {}
    try:
        return json.loads(raw)
    except (json.JSONDecodeError, ValueError):
        return {}


if __name__ == "__main__":
    # Self-check: the class bug is "open idle pipe hangs forever". Prove the
    # helper returns fast on an idle pipe, on EOF, and on a real envelope.
    import subprocess
    import time

    probe = (
        "import sys; from pathlib import Path;"
        "sys.path.insert(0, str(Path(%r)));"
        "from _hooklib import read_stdin_input;"
        "import json; print(json.dumps(read_stdin_input()))"
    ) % os.path.dirname(os.path.abspath(__file__))

    def _run(stdin, label, feed=None):
        start = time.time()
        try:
            p = subprocess.run(
                [sys.executable, "-c", probe],
                stdin=stdin, input=feed, capture_output=True, text=True, timeout=10,
            )
            elapsed = time.time() - start
            assert elapsed < 2, f"{label}: took {elapsed:.1f}s (should be <2s)"
            return p.stdout.strip()
        except subprocess.TimeoutExpired:
            raise AssertionError(f"{label}: STILL HANGS")

    # 1. open idle pipe -> must return fast with {}
    r, w = os.pipe()
    try:
        out = _run(r, "idle-pipe")
        assert out == "{}", f"idle-pipe returned {out!r}"
    finally:
        os.close(r); os.close(w)

    # 2. closed stdin (EOF) -> {}
    assert _run(subprocess.DEVNULL, "eof") == "{}"

    # 3. real JSON envelope -> parsed
    out = _run(None, "json", feed='{"tool_input": {"file_path": "x"}}')
    assert json.loads(out) == {"tool_input": {"file_path": "x"}}, out

    # 4. data written then pipe left open -> parsed, no hang
    r, w = os.pipe()
    os.write(w, b'{"a": 1}')
    try:
        out = _run(r, "data+open")
        assert json.loads(out) == {"a": 1}, out
    finally:
        os.close(r); os.close(w)

    print("_hooklib self-check OK")
