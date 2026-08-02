"""Doctrine test: AGENTS.md is seeded only where it is wanted, and never overwritten.

AI reviewers read AGENTS.md from the repo ROOT automatically, and both the
pre-push and post-PR passes read the same file — so it is where review direction
belongs, and it is project data the framework must never clobber.

Two properties, pulling in opposite directions:

  - Seed it when a reviewer is configured but the file is gone, so a refresh
    self-heals rather than leaving the reviewer with no direction.
  - Do NOT seed it otherwise. An empty AGENTS.md in a project with no reviewer
    is a file nobody will ever fill in, and the framework has no business
    littering project roots against the chance one is added later.

These run the function EXTRACTED FROM install.sh rather than a copy of it, so a
change to the shipped code is caught here instead of passing against a stale
duplicate.
"""

from __future__ import annotations

import re
import subprocess
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
INSTALL_SH = REPO_ROOT / "scripts" / "install" / "install.sh"
FUNC = "seed_agents_md_if_missing"


def _extract_function() -> str:
    """Pull the real function body out of install.sh."""
    text = INSTALL_SH.read_text(encoding="utf-8")
    m = re.search(rf"^{FUNC}\(\) \{{.*?^\}}", text, re.S | re.M)
    assert m, f"{FUNC} not found in install.sh — did it get renamed?"
    return m.group(0)


def _run_seed(project: Path) -> subprocess.CompletedProcess:
    script = f"""
set -e
FRAMEWORK_DIR={str(REPO_ROOT)!r}
ok() {{ echo "SEEDED: $*"; }}
{_extract_function()}
{FUNC} {str(project)!r}
"""
    return subprocess.run(["bash", "-c", script], capture_output=True, text=True)


def _repo(tmp_path: Path, name: str, **config: str) -> Path:
    d = tmp_path / name
    d.mkdir()
    subprocess.run(["git", "init", "-q", str(d)], check=True, capture_output=True)
    for k, v in config.items():
        subprocess.run(["git", "-C", str(d), "config", f"forge.{k}", v],
                       check=True, capture_output=True)
    return d


def test_no_reviewer_configured_is_not_seeded(tmp_path):
    """The anti-case, and the reason the seeding is gated at all."""
    d = _repo(tmp_path, "none")
    _run_seed(d)
    assert not (d / "AGENTS.md").exists()


def test_post_pr_bot_alone_triggers_seeding(tmp_path):
    d = _repo(tmp_path, "mention", reviewBot="cc @codex — please review.")
    _run_seed(d)
    assert (d / "AGENTS.md").exists()


def test_local_reviewer_alone_triggers_seeding(tmp_path):
    """Either reviewer is reason enough — they read the same file."""
    d = _repo(tmp_path, "local", localReview="codex review --base {base}")
    _run_seed(d)
    assert (d / "AGENTS.md").exists()


def test_an_existing_file_is_never_overwritten(tmp_path):
    """It is hand-written and load-bearing for the cloud reviewer."""
    d = _repo(tmp_path, "existing", reviewBot="cc @codex")
    original = "# AGENTS.md\n\nHand-written direction that must survive.\n"
    (d / "AGENTS.md").write_text(original)
    _run_seed(d)
    assert (d / "AGENTS.md").read_text() == original


def test_seeding_is_idempotent(tmp_path):
    """A refresh runs this every time; the second run must be a no-op."""
    d = _repo(tmp_path, "twice", reviewBot="cc @codex")
    _run_seed(d)
    first = (d / "AGENTS.md").read_text()
    (d / "AGENTS.md").write_text(first + "\nedited by the project\n")
    _run_seed(d)
    assert (d / "AGENTS.md").read_text().endswith("edited by the project\n")


def test_seeded_content_comes_from_the_template(tmp_path):
    d = _repo(tmp_path, "content", reviewBot="cc @codex")
    _run_seed(d)
    template = (REPO_ROOT / "templates" / "AGENTS.template.md").read_text()
    assert (d / "AGENTS.md").read_text() == template


def test_installer_calls_the_seeder_on_every_install_path(tmp_path):
    """A seeder wired into one path only heals half the fleet."""
    text = INSTALL_SH.read_text(encoding="utf-8")
    calls = re.findall(rf'^\s*{FUNC} "\$PROJECT_DIR"', text, re.M)
    assert len(calls) >= 2, f"expected the seeder on every install path, found {len(calls)}"
