"""Tests for `forge version` — reads the repo-root VERSION file."""

from __future__ import annotations

import re
import subprocess
import sys
from pathlib import Path

_REPO_ROOT = Path(__file__).resolve().parents[2]
_FORGE_PY = _REPO_ROOT / "scripts" / "forge" / "forge.py"
_VERSION_FILE = _REPO_ROOT / "VERSION"


def test_version_subcommand_prints_version_file_contents():
    expected = _VERSION_FILE.read_text().strip()

    result = subprocess.run(
        [sys.executable, str(_FORGE_PY), "version"],
        capture_output=True,
        text=True,
    )

    assert result.returncode == 0
    assert result.stdout.strip() == expected


def test_version_file_is_semver():
    content = _VERSION_FILE.read_text().strip()
    assert re.match(r"^\d+\.\d+\.\d+$", content), f"VERSION file is not semver: {content!r}"
