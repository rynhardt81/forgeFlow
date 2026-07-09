"""Tests for the framework_root() / project_root() distinction in the dashboard.

The trap these tests guard against: when the framework is vendored into a
project at <project>/.claude/, the dashboard's server.py and the visualize
generator's _shared.py both have to know that

  - framework_root  = <project>/.claude/        (where CODE lives)
  - project_root    = <project>/                 (where DATA lives)

Earlier versions used `CLAUDE.md` as a project-root marker, which produced a
false-positive at `.claude/CLAUDE.md`. Earlier `_shared.py` used
`docs/code-map.json` as a marker, which produced a false-positive when the
framework dev repo's code-map.json leaked into `.claude/docs/` via rsync.
Both bugs caused the dashboard to serve `.claude/docs/...` (framework dev
state, or empty) instead of the project's real `docs/...`.

These tests synthesize a vendored install on disk, monkeypatch the
modules' `__file__` to point inside it, and assert the resolution.
"""
from __future__ import annotations

import sys
from pathlib import Path


def _make_vendored_install(tmp_path: Path, *, with_fake_code_map: bool = False,
                          with_fake_claude_md: bool = True) -> Path:
    """Build a synthetic <project>/.claude/ layout mirroring a vendored install.

    Returns the project root.
    """
    project = tmp_path / "myproject"
    claude = project / ".claude"

    # Project root markers
    (project / ".git").mkdir(parents=True)
    (project / "docs" / "tasks").mkdir(parents=True)
    (project / "docs" / "tasks" / "registry.json").write_text("{}")

    # Framework code locations the resolvers depend on
    (claude / "scripts" / "forge" / "dashboard").mkdir(parents=True)
    (claude / "skills" / "visualize" / "Tools").mkdir(parents=True)

    # The two historical false-positive marker files
    if with_fake_claude_md:
        (claude / "CLAUDE.md").write_text("# framework copy\n")
    if with_fake_code_map:
        (claude / "docs").mkdir(parents=True, exist_ok=True)
        (claude / "docs" / "code-map.json").write_text("{}")

    return project


def _load_server_with_file(file_path: Path):
    """Import server.py with __file__ pretending to be `file_path`."""
    # Drop any previously imported copy
    for mod in list(sys.modules):
        if mod.startswith("dashboard"):
            del sys.modules[mod]

    real = (Path(__file__).resolve().parents[2]
            / "scripts" / "forge" / "dashboard" / "server.py")
    src = real.read_text()
    file_path.parent.mkdir(parents=True, exist_ok=True)
    file_path.write_text(src)

    # The module's relative imports (`from . import DEFAULT_HOST`, etc.)
    # only work when loaded as a package — we can't exec it here. Instead
    # just exec enough to get the resolver functions, by stubbing the
    # package-level deps.
    # Simpler path: copy the resolver block as a string and exec it in a
    # fresh module-like namespace with __file__ set.
    src_code = compile(
        "from pathlib import Path\n"
        "__file__ = " + repr(str(file_path)) + "\n"
        + _extract_resolvers(src),
        str(file_path),
        "exec",
    )
    ns: dict = {}
    exec(src_code, ns)
    return ns


def _extract_resolvers(src: str) -> str:
    """Extract just the framework_root() and project_root() defs from server.py."""
    lines = src.splitlines()
    out: list[str] = []
    capture = False
    for i, line in enumerate(lines):
        if line.startswith("def framework_root") or line.startswith("def project_root"):
            capture = True
        elif capture and line.startswith("def ") and not line.startswith("def framework_root") and not line.startswith("def project_root"):
            capture = False
        if capture:
            out.append(line)
    return "\n".join(out)


def _load_shared_with_file(file_path: Path):
    """Same trick for _shared.py — exec the resolver block with patched __file__."""
    real = (Path(__file__).resolve().parents[2]
            / "skills" / "visualize" / "Tools" / "_shared.py")
    src = real.read_text()
    file_path.parent.mkdir(parents=True, exist_ok=True)
    file_path.write_text(src)

    src_code = compile(
        "from pathlib import Path\n"
        "__file__ = " + repr(str(file_path)) + "\n"
        + _extract_resolvers(src),
        str(file_path),
        "exec",
    )
    ns: dict = {}
    exec(src_code, ns)
    return ns


# ---------------------------------------------------------------------------
# server.py resolvers
# ---------------------------------------------------------------------------

def test_server_framework_root_returns_dot_claude_in_vendored_install(tmp_path):
    project = _make_vendored_install(tmp_path)
    server_file = project / ".claude" / "scripts" / "forge" / "dashboard" / "server.py"
    ns = _load_server_with_file(server_file)
    assert ns["framework_root"]() == project / ".claude"


def test_server_project_root_returns_project_in_vendored_install(tmp_path):
    project = _make_vendored_install(tmp_path)
    server_file = project / ".claude" / "scripts" / "forge" / "dashboard" / "server.py"
    ns = _load_server_with_file(server_file)
    assert ns["project_root"]() == project


def test_server_project_root_ignores_dot_claude_claude_md(tmp_path):
    """The CLAUDE.md false-positive trap: .claude/ has its own CLAUDE.md but
    project_root() must NOT stop there."""
    project = _make_vendored_install(tmp_path, with_fake_claude_md=True)
    server_file = project / ".claude" / "scripts" / "forge" / "dashboard" / "server.py"
    ns = _load_server_with_file(server_file)
    resolved = ns["project_root"]()
    assert resolved == project, (
        f"project_root() resolved to {resolved} — should be {project}, "
        f"never the .claude/ directory."
    )


def test_server_root_in_self_hosting_dev_repo(tmp_path):
    """When the framework is its own project (dev repo, not vendored),
    framework_root and project_root coincide."""
    dev = tmp_path / "claude-forge"
    (dev / ".git").mkdir(parents=True)
    server_file = dev / "scripts" / "forge" / "dashboard" / "server.py"
    ns = _load_server_with_file(server_file)
    assert ns["framework_root"]() == dev
    assert ns["project_root"]() == dev


# ---------------------------------------------------------------------------
# _shared.py resolvers
# ---------------------------------------------------------------------------

def test_shared_framework_root_returns_dot_claude_in_vendored_install(tmp_path):
    project = _make_vendored_install(tmp_path)
    shared_file = project / ".claude" / "skills" / "visualize" / "Tools" / "_shared.py"
    ns = _load_shared_with_file(shared_file)
    assert ns["framework_root"]() == project / ".claude"


def test_shared_project_root_ignores_leaked_code_map_json(tmp_path):
    """The code-map.json false-positive trap: rsync leaked the framework dev
    repo's docs/code-map.json into .claude/docs/, but project_root() must
    NOT stop there."""
    project = _make_vendored_install(tmp_path, with_fake_code_map=True)
    shared_file = project / ".claude" / "skills" / "visualize" / "Tools" / "_shared.py"
    ns = _load_shared_with_file(shared_file)
    resolved = ns["project_root"]()
    assert resolved == project, (
        f"project_root() resolved to {resolved} — should be {project}, "
        f"never the .claude/ directory (leaked code-map.json must not "
        f"count as a marker)."
    )
