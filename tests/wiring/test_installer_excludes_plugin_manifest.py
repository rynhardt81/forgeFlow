"""`.claude-plugin/plugin.json` exists only so `claude plugin eval` can load the
framework's skills and agents as a plugin (suite: tests/plugin-evals/). It is
not a consumer feature, so no framework copy may ship it into `.claude/`."""

from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]


def test_every_install_sh_copy_excludes_the_plugin_manifest():
    text = (ROOT / "scripts" / "install" / "install.sh").read_text()
    assert text.count("--exclude='.claude-plugin'") == text.count("--exclude='tests'") >= 3


def test_install_ps1_excludes_the_plugin_manifest():
    assert "'.claude-plugin'," in (ROOT / "scripts" / "install" / "install.ps1").read_text()
