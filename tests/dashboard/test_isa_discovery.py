"""Tests for the dashboard /isas tab's ISA discovery.

Before the broadening fix, `list_features()` only globbed `docs/tasks/F-*/ISA.md`,
missing every `T###/ISA.md`, `T###-slug/ISA.md`, and the project-level `ISA.md`.
These tests guard the broader behavior: any direct child of `docs/tasks/`
containing an `ISA.md` is surfaced, plus the project-level `ISA.md`.
"""
from __future__ import annotations

import sys
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[2]
# Add the dashboard package to sys.path so we can import its render module
if str(REPO_ROOT / "scripts" / "forge") not in sys.path:
    sys.path.insert(0, str(REPO_ROOT / "scripts" / "forge"))

from dashboard.render import isas  # noqa: E402


_ISA_BODY = """---
id: {id}
phase: draft
---

# {id} — fixture
"""


def _make_project(tmp_path: Path) -> Path:
    project = tmp_path / "demo"
    project.mkdir()
    (project / ".git").mkdir()
    (project / "docs" / "tasks").mkdir(parents=True)
    return project


def _write_isa(project: Path, dirname: str, isa_id: str) -> None:
    d = project / "docs" / "tasks" / dirname
    d.mkdir(parents=True, exist_ok=True)
    (d / "ISA.md").write_text(_ISA_BODY.format(id=isa_id))


def test_discovers_F_prefixed_isas(tmp_path):
    project = _make_project(tmp_path)
    _write_isa(project, "F-VISUALIZE", "F-VISUALIZE")
    _write_isa(project, "F-DASHBOARD", "F-DASHBOARD")

    features = isas.list_features(project)
    ids = {f["id"] for f in features}
    assert "F-VISUALIZE" in ids
    assert "F-DASHBOARD" in ids


def test_discovers_T_numeric_isas(tmp_path):
    """The bug we're fixing — consumers using the T### shape for ISA
    directories were silently missed by the old F-* glob."""
    project = _make_project(tmp_path)
    _write_isa(project, "T287", "T287")
    _write_isa(project, "T413", "T413")
    _write_isa(project, "T287-with-slug", "T287-with-slug")

    features = isas.list_features(project)
    ids = {f["id"] for f in features}
    assert "T287" in ids
    assert "T413" in ids
    assert "T287-with-slug" in ids


def test_discovers_mixed_shapes(tmp_path):
    project = _make_project(tmp_path)
    _write_isa(project, "F-DASHBOARD", "F-DASHBOARD")
    _write_isa(project, "T287", "T287")
    _write_isa(project, "T413-extra-slug", "T413-extra-slug")

    features = isas.list_features(project)
    assert len(features) == 3


def test_surfaces_project_level_ISA_md(tmp_path):
    """The project-root ISA.md is the long-lived system of record per
    CLAUDE.md doctrine, and the dashboard should surface it."""
    project = _make_project(tmp_path)
    (project / "ISA.md").write_text(_ISA_BODY.format(id="project"))
    _write_isa(project, "T1", "T1")

    features = isas.list_features(project)
    ids = {f["id"] for f in features}
    feature_dirs = {f["feature_dir"] for f in features}
    assert "project" in ids
    assert "__project__" in feature_dirs


def test_skips_dirs_without_ISA_md(tmp_path):
    """A task dir without an ISA.md (most tasks) shouldn't surface."""
    project = _make_project(tmp_path)
    (project / "docs" / "tasks" / "T1").mkdir(parents=True)
    # No ISA.md inside T1 — only the body lives elsewhere
    _write_isa(project, "T2", "T2")

    features = isas.list_features(project)
    ids = {f["id"] for f in features}
    assert "T1" not in ids
    assert "T2" in ids


def test_render_one_handles_T_id(tmp_path):
    """The old guard rejected anything not starting with F-. Verify T###
    URLs now render."""
    project = _make_project(tmp_path)
    _write_isa(project, "T287", "T287")

    html = isas.render_one(project, "T287")
    assert "T287" in html


def test_render_one_handles_project_level(tmp_path):
    project = _make_project(tmp_path)
    (project / "ISA.md").write_text(_ISA_BODY.format(id="project"))

    html = isas.render_one(project, "__project__")
    assert "project" in html


def test_render_one_rejects_traversal(tmp_path):
    project = _make_project(tmp_path)
    with pytest.raises(FileNotFoundError):
        isas.render_one(project, "../etc/passwd")
    with pytest.raises(FileNotFoundError):
        isas.render_one(project, "")
    with pytest.raises(FileNotFoundError):
        isas.render_one(project, "T1/subdir")
