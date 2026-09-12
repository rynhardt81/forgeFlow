"""Doctrine test: the SessionStart injection cap has two owners, keep them equal.

`hooks/session/session-context.py` truncates index.md and key-facts.md at a
hardcoded character count. `scripts/forge/doctor.py` warns when those files
cross the same line. The hook is a standalone script — it runs with no package
context and cannot import from `scripts/forge/` — so the number is duplicated
rather than shared.

Duplicated constants drift, and this pair drifts silently in the worst
direction: doctor would report a file healthy while the hook was already
dropping its tail from every session, which is precisely the failure the check
exists to surface. This test is what makes the duplication safe.
"""

from __future__ import annotations

import re
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
HOOK = REPO_ROOT / "hooks" / "session" / "session-context.py"
DOCTOR = REPO_ROOT / "scripts" / "forge" / "doctor.py"


def test_hook_and_doctor_agree_on_the_injection_cap():
    hook_caps = {int(m) for m in re.findall(r"max_chars = (\d+)", HOOK.read_text())}
    assert hook_caps, f"no `max_chars = N` found in {HOOK} — did the hook change shape?"
    assert len(hook_caps) == 1, (
        "the hook caps its injected files at different sizes, so doctor cannot "
        f"track a single number: {sorted(hook_caps)}"
    )

    m = re.search(r"INJECTED_CAP_CHARS = (\d+)", DOCTOR.read_text())
    assert m, f"INJECTED_CAP_CHARS not found in {DOCTOR}"

    assert int(m.group(1)) == hook_caps.pop(), (
        "forge doctor's INJECTED_CAP_CHARS no longer matches the hook's cap — "
        "doctor would call a file healthy while the hook silently truncates it"
    )


def test_both_injected_files_are_capped():
    """key-facts.md was once read whole on the strength of a comment calling it
    small; one consumer's reached 63 KB. Both injected files carry a cap now."""
    text = HOOK.read_text()
    assert text.count("max_chars = ") == 2, (
        "expected a cap on both index.md and key-facts.md — one of them is "
        "being injected unbounded again"
    )
