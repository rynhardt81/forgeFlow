"""task_file.py is the one owner of the task body-file format (T962).

The frontmatter and quoting cases moved here from test_registry_helpers_parity.py,
which existed to police copies of these helpers in two modules.
"""

from __future__ import annotations

import re
from pathlib import Path

import pytest

import task_file

FORGE = Path(__file__).resolve().parents[2] / "scripts" / "forge"

QUOTED = '---\nid: T1\nname: "hello: world"\nstatus: "ready"\n---\n\n# T1\n'
NO_FRONTMATTER = "# T1\n\nNo frontmatter here.\nstatus: pending\n"
STRAY_STATUS_IN_BODY = (
    "---\nid: T1\nstatus: ready\n---\n\n# T1\n\n"
    "Body text that happens to say status: completed but must NOT be rewritten.\n"
)


def test_only_task_file_defines_the_frontmatter_format():
    """No other forge module re-declares the frontmatter regexes or quoting."""
    for name in ("registry_ops.py", "check_consistency.py"):
        src = (FORGE / name).read_text(encoding="utf-8")
        assert "_FRONTMATTER" not in src, name
        assert not re.search(r"def _(yaml_|rewrite_frontmatter|parse_frontmatter|discover_task_file)", src), name


# --- parse / rewrite --------------------------------------------------------


def test_parse_unquotes_every_field():
    assert task_file.parse(QUOTED) == {"status": "ready", "name": "hello: world", "epic": ""}


def test_parse_without_frontmatter_is_empty():
    assert task_file.parse(NO_FRONTMATTER) == {"status": "", "name": "", "epic": ""}


def test_rewrite_status_replaces_quoted_value():
    new, changed = task_file.rewrite(QUOTED, "status", "in_progress")
    assert changed and "status: in_progress\n" in new


@pytest.mark.parametrize("field", ["status", "name", "epic"])
def test_rewrite_without_frontmatter_is_noop(field):
    assert task_file.rewrite(NO_FRONTMATTER, field, "x") == (NO_FRONTMATTER, False)


@pytest.mark.parametrize("field", ["status", "name", "epic"])
def test_rewrite_missing_field_is_noop(field):
    content = "---\nid: T1\n---\n\n# T1\n"
    assert task_file.rewrite(content, field, "x") == (content, False)


def test_rewrite_leaves_body_alone():
    new, changed = task_file.rewrite(STRAY_STATUS_IN_BODY, "status", "pr_pending")
    assert changed
    assert "status: completed but must NOT be rewritten" in new


def test_rewrite_quotes_names_only():
    name = 'name with "quotes" and: a colon # and hash'
    new, _ = task_file.rewrite(QUOTED, "name", name)
    assert task_file.parse(new)["name"] == name
    new, _ = task_file.rewrite("---\nepic: E1\n---\n", "epic", "E2")
    assert new == "---\nepic: E2\n---\n"


def test_rewrite_value_with_backslash_is_literal():
    # The old status rewriter used a template string; `\1` must not be a group ref.
    new, _ = task_file.rewrite("---\nepic: E1\n---\n", "epic", r"E\1")
    assert new == "---\nepic: E\\1\n---\n"


@pytest.mark.parametrize("value", [
    "", "plain", "with space", "colon: inside", "hash # inside", "-leading-dash",
    '"already quoted"', "trailing space ", " leading space", 'has "double" quotes',
    "has\\backslash", 'has\\backslash and "quote"',
])
def test_quote_unquote_roundtrip(value):
    assert task_file.unquote(task_file.quote(value)) == value


# --- files ------------------------------------------------------------------


def _task(root: Path, epic_dir: str, name: str, text: str = "---\nstatus: ready\n---\n") -> Path:
    d = root / "docs" / "epics" / epic_dir / "tasks"
    d.mkdir(parents=True, exist_ok=True)
    (d / name).write_text(text, encoding="utf-8")
    return d / name


def test_find_prefers_recorded_file_then_discovers(tmp_path):
    discovered = _task(tmp_path, "E1-alpha", "T1-one.md")
    recorded = tmp_path / "elsewhere.md"
    recorded.write_text("x")
    assert task_file.find(tmp_path, {"id": "T1", "epic": "E1", "file": "elsewhere.md"}) == recorded
    assert task_file.find(tmp_path, {"id": "T1", "epic": "E1", "path": "elsewhere.md"}) == recorded
    assert task_file.find(tmp_path, {"id": "T1", "epic": "E1", "file": "gone.md"}) == discovered
    assert task_file.find(tmp_path, {"id": "T2", "epic": "E1"}) is None


def test_iter_all_yields_ids_and_epics_and_skips_split_suffixes(tmp_path):
    _task(tmp_path, "E2-beta", "T5-five.md")
    _task(tmp_path, "E1-alpha", "T1.md")
    _task(tmp_path, "E1-alpha", "T149a-split.md")
    _task(tmp_path, "notes", "T9-nine.md")
    got = [(p.name, tid, eid) for p, tid, eid in task_file.iter_all(tmp_path)]
    assert got == [("T1.md", "T1", "E1"), ("T5-five.md", "T5", "E2")]


def test_read_is_none_when_unreadable(tmp_path):
    bad = _task(tmp_path, "E1-a", "T1-x.md")
    bad.write_bytes(b"\xff\xfe")
    assert task_file.read(bad) is None
    assert task_file.read(tmp_path / "missing.md") is None


def test_set_field_reports_writes(tmp_path):
    f = _task(tmp_path, "E1-a", "T1-x.md")
    assert task_file.set_field(f, "status", "completed") is True
    assert task_file.set_field(f, "status", "completed") is False
    assert task_file.set_field(None, "status", "x") is False
    assert task_file.read(f)["status"] == "completed"


def test_set_scope_replaces_or_appends_block(tmp_path):
    f = _task(tmp_path, "E1-a", "T1-x.md", "---\nid: T1\nscope:\n  directories: []\n  files: []\nstatus: ready\n---\nbody\n")
    task_file.set_scope(f, {"directories": ["src"], "files": ["a.py"]})
    assert f.read_text() == "---\nid: T1\nscope:\n  directories: [src]\n  files: [a.py]\nstatus: ready\n---\nbody\n"
    g = _task(tmp_path, "E1-a", "T2-y.md", "---\nid: T2\n---\nbody\n")
    task_file.set_scope(g, {"directories": [], "files": ["b.py"]})
    assert "scope:\n  directories: []\n  files: [b.py]\n---\nbody" in g.read_text()
