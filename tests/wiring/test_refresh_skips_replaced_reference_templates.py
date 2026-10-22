"""A refresh must not re-create reference templates a consumer has replaced.

A consumer populates `reference/NN-name.md` from `NN-name.template.md` and then
deletes the template. Before T961 every refresh copied all nine templates back
(and `verify.sh` flagged the missing ones as errors, with `--fix` re-copying
them), so a consumer had to `git rm` them after each refresh. A fresh install,
which has no populated docs, must still receive every template.

The helper is exercised for real (extracted from install.sh and run in bash
against fixture dirs); the wiring into both refresh paths, install.ps1 and
verify.sh is pinned by grep.
"""

from __future__ import annotations

import re
import subprocess
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
INSTALL_SH = REPO_ROOT / "scripts" / "install" / "install.sh"
INSTALL_PS1 = REPO_ROOT / "scripts" / "install" / "install.ps1"
VERIFY_SH = REPO_ROOT / "scripts" / "install" / "verify.sh"


def _helper_source() -> str:
    m = re.search(r"^reference_template_excludes\(\) \{\n.*?^\}\n", INSTALL_SH.read_text(), re.S | re.M)
    assert m, "reference_template_excludes() not found in install.sh"
    return m.group(0)


def _run_helper(framework: Path, target: Path) -> list[str]:
    script = _helper_source() + (
        'reference_template_excludes "$2"\n'
        'for x in ${REF_TEMPLATE_EXCLUDES[@]+"${REF_TEMPLATE_EXCLUDES[@]}"}; do echo "$x"; done\n'
    )
    out = subprocess.run(
        ["bash", "-c", script, "_", str(framework), str(target)],
        env={"FRAMEWORK_DIR": str(framework), "PATH": "/usr/bin:/bin"},
        capture_output=True, text=True, check=True,
    )
    return out.stdout.split()


def _fixture(tmp_path: Path) -> tuple[Path, Path]:
    fw = tmp_path / "fw" / "reference"
    fw.mkdir(parents=True)
    for name in ("01-system-overview", "06-architecture-decisions", "07-nfr"):
        (fw / f"{name}.template.md").write_text("template\n")
    target = tmp_path / "proj" / ".claude"
    (target / "reference").mkdir(parents=True)
    return fw.parent, target


def test_populated_doc_excludes_its_template(tmp_path):
    fw, target = _fixture(tmp_path)
    (target / "reference" / "01-system-overview.md").write_text("ours\n")
    (target / "reference" / "06-architecture-decisions.md").write_text("ours\n")
    assert sorted(_run_helper(fw, target)) == [
        "--exclude=reference/01-system-overview.template.md",
        "--exclude=reference/06-architecture-decisions.template.md",
    ]


def test_fresh_install_excludes_nothing(tmp_path):
    fw, target = _fixture(tmp_path)
    assert _run_helper(fw, target) == []


def test_both_refresh_paths_apply_the_excludes():
    text = INSTALL_SH.read_text()
    assert text.count('reference_template_excludes "$PROJECT_DIR/.claude"') == 2
    assert text.count('${REF_TEMPLATE_EXCLUDES[@]+"${REF_TEMPLATE_EXCLUDES[@]}"}') == 2


def test_windows_installer_and_verify_agree():
    assert "$skipTemplates" in INSTALL_PS1.read_text()
    assert '${fname%.template.md}.md' in VERIFY_SH.read_text()
