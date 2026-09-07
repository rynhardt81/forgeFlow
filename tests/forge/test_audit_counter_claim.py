"""The epic progress-counter audit must read the counter, or say it did not.

Ported upstream 2026-09-07 from a consumer carrying it as a project-local
patch and re-applying it after every refresh (documented as overwritten again
on 2026-08-31 by v4.4.1).

Two defects, and the second is what made the first invisible:

  1. One regex. Epic files are human-authored prose and each project settles
     on its own phrasing. The shipped pattern (`N total ... M completed`)
     matched none of the consumer's epics, every one of which wrote
     `**Status:** in_progress -- 23/50 tasks completed`.
  2. A parse failure rendered as a green tick. `flag = "STALE" if stale else
     "OK"` -- with `claimed=None`, `stale` is False, so an epic nothing had
     checked was reported identically to a verified one. Section [3] passed
     vacuously for a whole repo while E01's counter had drifted to 23/50
     against a registry saying 32/56.

A parser that matches nothing must not be indistinguishable from a clean
audit, which is why the "not checked" state is asserted here separately from
the parsing.
"""
from __future__ import annotations

import sys
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO_ROOT / "skills" / "audit-task-status" / "scripts"))

from audit_status import parse_counter_claim  # noqa: E402


@pytest.mark.parametrize(
    "line,expected",
    [
        ("**Tasks:** 19 total — 14 completed", {"completed": 14, "total": 19}),
        ("**Status:** in_progress — 12/26 tasks completed", {"completed": 12, "total": 26}),
        ("**Progress:** 14 of 19 tasks completed", {"completed": 14, "total": 19}),
        ("**Status:** completed: 14 / 19", {"completed": 14, "total": 19}),
    ],
)
def test_reads_every_counter_idiom(line, expected):
    """Four idioms, not one. Each is a real shape seen in an epic file."""
    assert parse_counter_claim(f"# Epic\n\n{line}\n\nBody text.\n") == expected


def test_returns_none_when_there_is_no_counter():
    """The state the caller must render as NOT CHECKED rather than a tick."""
    assert parse_counter_claim("# Epic\n\nNo counter anywhere in this file.\n") is None


def test_counter_line_wins_over_prose_containing_numbers():
    """A progress-log sentence must not be mistaken for the epic's claim.

    The header line is tried first; without that restriction the prose below
    would answer, and the audit would compare the registry against a number
    from a narrative."""
    text = (
        "# Epic\n\n"
        "**Status:** in_progress — 3/10 tasks completed\n\n"
        "## Log\n- 2026-01-01: 9 of 10 tasks completed in the first pass\n"
    )
    assert parse_counter_claim(text) == {"completed": 3, "total": 10}


def test_falls_back_to_whole_text_when_counter_is_not_on_a_header_line():
    """Preserves the pre-patch behaviour for epics whose counter sits in prose
    rather than on a **Status:**/**Tasks:**/**Progress:** line."""
    assert parse_counter_claim(
        "# Epic\n\nThis epic has 19 total tasks, 14 completed so far.\n"
    ) == {"completed": 14, "total": 19}


# --- The rendering half ----------------------------------------------------
# The parser above is only half the fix. With `claimed=None`, `stale` is False,
# so the pre-patch `flag = STALE if stale else OK` printed a tick beside an
# epic nothing had checked -- which is precisely why one regex matching nothing
# went unnoticed for months. Driven through the real CLI, not a copy of the
# format string.

import json  # noqa: E402
import subprocess  # noqa: E402

AUDIT = REPO_ROOT / "skills" / "audit-task-status" / "scripts" / "audit_status.py"


def _fixture_project(tmp_path: Path, epic_body: str) -> Path:
    (tmp_path / "docs" / "tasks").mkdir(parents=True)
    (tmp_path / "docs" / "epics" / "E01").mkdir(parents=True)
    (tmp_path / "docs" / "epics" / "E01" / "E01.md").write_text(epic_body)
    registry = {
        "tasks": [
            {"id": "T001", "epic": "E01", "status": "completed", "file": None},
            {"id": "T002", "epic": "E01", "status": "ready", "file": None},
        ]
    }
    (tmp_path / "docs" / "tasks" / "registry.json").write_text(json.dumps(registry))
    return tmp_path


def _run_audit(project: Path) -> str:
    proc = subprocess.run(
        [sys.executable, str(AUDIT), "--project-root", str(project)],
        capture_output=True, text=True,
    )
    return proc.stdout


def test_unparsed_counter_is_reported_as_not_checked_not_as_a_tick(tmp_path):
    """The defect that hid the other one: no counter must never render green."""
    out = _run_audit(_fixture_project(tmp_path, "# E01\n\nNo counter here at all.\n"))
    section = out.split("[3]")[1].split("[4]")[0]
    assert "NOT CHECKED" in section
    assert "✅ E01" not in section, "an unchecked epic must not render as verified"


def test_a_counter_it_actually_read_still_renders_a_verdict(tmp_path):
    """Guards against over-correcting into never reporting a verdict at all."""
    body = "# E01\n\n**Status:** in_progress — 1/2 tasks completed\n"
    section = _run_audit(_fixture_project(tmp_path, body)).split("[3]")[1].split("[4]")[0]
    assert "file claims 1/2" in section
    assert "NOT CHECKED" not in section
