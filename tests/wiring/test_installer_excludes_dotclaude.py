"""Doctrine test: the installer must never copy the framework's own `.claude/`
into a target project.

The install/refresh rsync copies `$FRAMEWORK_DIR/ -> $PROJECT_DIR/.claude/`.
The framework repo's *own* working tree contains a `.claude/` (local dev state:
agents, memories, worktrees, settings.local.json — gitignored, so it's invisible
in the public repo but present on disk). Without an explicit exclude, rsync
copies it and the target ends up with `$PROJECT_DIR/.claude/.claude/` — the
framework's private dev cruft (incl. unrelated agent files) nested inside every
consumer. Observed 2026-07-12: a consumer project got a `.claude/.claude/` full
of unrelated agent files that have nothing to do with Forge Flow.

`.git` is already excluded for the same reason; `.claude` belongs right beside
it. This is a grep-based assertion over both installers — every framework->`
.claude/` copy site must exclude `.claude`.
"""

from __future__ import annotations

import re
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
INSTALL_SH = REPO_ROOT / "scripts" / "install" / "install.sh"
INSTALL_PS1 = REPO_ROOT / "scripts" / "install" / "install.ps1"


def test_install_sh_every_framework_copy_excludes_dotclaude():
    text = INSTALL_SH.read_text()

    # Each framework-root copy targets "$PROJECT_DIR/.claude/". Count them so a
    # newly-added copy site without the exclude can't slip by unnoticed.
    copy_sites = text.count('"$FRAMEWORK_DIR/" "$PROJECT_DIR/.claude/"')
    assert copy_sites >= 3, (
        f"expected >=3 framework->.claude rsync sites, found {copy_sites} — "
        "did the copy invocation change shape?"
    )

    dotclaude_excludes = len(re.findall(r"--exclude='\.claude'", text))
    assert dotclaude_excludes >= copy_sites, (
        f"install.sh has {copy_sites} framework->.claude copy sites but only "
        f"{dotclaude_excludes} `--exclude='.claude'` — every copy site must "
        "exclude the framework's own .claude/ (else it nests in the target)"
    )


def test_install_ps1_every_framework_copy_excludes_dotclaude():
    text = INSTALL_PS1.read_text()
    # The Windows installer lists excludes in @(...) arrays. Every array that
    # excludes '.git' is a framework-copy exclude list and must also list
    # '.claude' (single- or double-quoted).
    git_excludes = len(re.findall(r"""['"]\.git['"]""", text))
    claude_excludes = len(re.findall(r"""['"]\.claude['"]""", text))
    assert git_excludes >= 3, (
        f"expected >=3 .git exclude sites in install.ps1, found {git_excludes}"
    )
    assert claude_excludes >= git_excludes, (
        f"install.ps1 excludes '.git' in {git_excludes} places but '.claude' in "
        f"only {claude_excludes} — each framework-copy exclude list must also "
        "exclude .claude"
    )
