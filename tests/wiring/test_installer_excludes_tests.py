"""Doctrine test: the installer must never copy the framework's own `tests/`
into a target project.

Framework self-tests are not runtime functionality, so by the inclusion rule in
`rules/framework-vs-project-root.md` ("if the answer isn't a clear yes, exclude
it") they must not ship. When they did ship, seven of them asserted the
framework-DEV-repo layout — installer source at `<root>/scripts/install/`,
`hooks/settings.json` on disk, `doctor` reporting `layout: framework-repo` —
none of which can hold once `framework_root` is `<project>/.claude/`. Every
consumer install carried a permanently-red suite it could not fix locally.

The sharper cost is silent: a shipped test can be removed by a later refresh
together with the code it guarded, so the consumer's suite stays green while
coverage and implementation vanish in the same commit. Not shipping `tests/`
removes that failure mode entirely.

Grep-based assertion over both installers, mirroring the `.claude` exclusion
doctrine test next door.
"""

from __future__ import annotations

import re
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
INSTALL_SH = REPO_ROOT / "scripts" / "install" / "install.sh"
INSTALL_PS1 = REPO_ROOT / "scripts" / "install" / "install.ps1"


def test_install_sh_every_framework_copy_excludes_tests():
    text = INSTALL_SH.read_text()

    copy_sites = text.count('"$FRAMEWORK_DIR/" "$PROJECT_DIR/.claude/"')
    assert copy_sites >= 3, (
        f"expected >=3 framework->.claude rsync sites, found {copy_sites} — "
        "did the copy invocation change shape?"
    )

    tests_excludes = len(re.findall(r"--exclude='tests'", text))
    assert tests_excludes >= copy_sites, (
        f"install.sh has {copy_sites} framework->.claude copy sites but only "
        f"{tests_excludes} `--exclude='tests'` — every copy site must exclude "
        "the framework's own tests/ (7 of them cannot pass when vendored)"
    )


def test_install_ps1_every_framework_copy_excludes_tests():
    text = INSTALL_PS1.read_text()
    git_excludes = len(re.findall(r"""['"]\.git['"]""", text))
    tests_excludes = len(re.findall(r"""['"]tests['"]""", text))
    assert git_excludes >= 3, (
        f"expected >=3 .git exclude sites in install.ps1, found {git_excludes}"
    )
    assert tests_excludes >= git_excludes, (
        f"install.ps1 excludes '.git' in {git_excludes} places but 'tests' in "
        f"only {tests_excludes} — each framework-copy exclude list must also "
        "exclude tests"
    )


def test_both_installers_heal_previously_vendored_tests():
    """Excluding stops the bleeding; existing installs still carry tests/.

    The heal must MOVE rather than delete — `.claude/` is framework code by
    doctrine, but a consumer may have written its own tests there and a refresh
    must not destroy them without a copy.
    """
    sh = INSTALL_SH.read_text()
    assert "heal_vendored_tests" in sh, "install.sh must define the heal step"
    assert sh.count("    heal_vendored_tests\n") >= 3, (
        "heal_vendored_tests must run on every install path (fresh/refresh/v3)"
    )
    assert "rm -rf \"$PROJECT_DIR/.claude/tests\"" not in sh, (
        "heal must move vendored tests to backups/, never rm -rf them"
    )

    ps1 = INSTALL_PS1.read_text()
    assert "Repair-VendoredTests" in ps1, "install.ps1 must define the heal step"
    assert ps1.count("    Repair-VendoredTests\n") >= 3, (
        "Repair-VendoredTests must run on every install path"
    )
