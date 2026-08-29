"""`/preflight-ci --regenerate` must never destroy a project's own shim file.

Regression gate for a data-loss bug observed in two projects. The generator
copied its own `_local_shims.sh` over `<out_dir>/_local_shims.sh` on every run,
justified by a code comment asserting that out_dir "is generated and
gitignored". It is neither: the file is tracked, and it is the path both the
skill docs and the file's own header tell people to edit. Regenerating replaced
a working pip shim with the empty default, and the next preflight run died in
0.01s on `pip: command not found` instead of reaching the linter.

Absent -> seed. Present and identical -> no-op. Present and different -> keep
the project's copy, byte for byte.

These call the generator's real `sync_local_shims`, not a restatement of it.
"""
from __future__ import annotations

import sys
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO_ROOT / "scripts" / "preflight"))

import script_generator  # noqa: E402

FRAMEWORK_SHIM = Path(script_generator.__file__).parent / "_local_shims.sh"
CUSTOM = '#!/usr/bin/env bash\n# project shim\npip() { python3 -m pip "$@"; }\n'


def test_customized_shim_is_preserved_byte_for_byte(tmp_path):
    dst = tmp_path / "_local_shims.sh"
    dst.write_text(CUSTOM, encoding="utf-8")
    result = script_generator.sync_local_shims(FRAMEWORK_SHIM, dst)
    assert result == "preserved"
    assert dst.read_text(encoding="utf-8") == CUSTOM, "regenerate clobbered the project's shim"


def test_missing_shim_is_seeded(tmp_path):
    dst = tmp_path / "_local_shims.sh"
    assert script_generator.sync_local_shims(FRAMEWORK_SHIM, dst) == "seeded"
    assert dst.exists(), "a fresh out_dir must get a shim — scripts hard-exit without one"


def test_identical_shim_is_a_noop(tmp_path):
    dst = tmp_path / "_local_shims.sh"
    dst.write_bytes(FRAMEWORK_SHIM.read_bytes())
    assert script_generator.sync_local_shims(FRAMEWORK_SHIM, dst) == "unchanged"


def test_preserved_copy_warns_on_stderr(tmp_path, capsys):
    """Silence is how the original bug hid. Divergence must be announced."""
    dst = tmp_path / "_local_shims.sh"
    dst.write_text(CUSTOM, encoding="utf-8")
    script_generator.sync_local_shims(FRAMEWORK_SHIM, dst)
    assert "kept your existing" in capsys.readouterr().err


def test_missing_source_is_not_an_error(tmp_path):
    dst = tmp_path / "_local_shims.sh"
    assert script_generator.sync_local_shims(tmp_path / "absent.sh", dst) == "no-source"
    assert not dst.exists()


@pytest.mark.parametrize("path", [
    "skills/preflight-ci/SKILL.md",
    "scripts/preflight/_local_shims.sh",
])
def test_docs_state_the_preservation_contract(path):
    """Both documents promised preservation while the code did the opposite.

    A promise nobody checks is how the two drifted apart in the first place.
    """
    text = (REPO_ROOT / path).read_text(encoding="utf-8")
    assert "never overwrites a copy that differs" in text, f"{path} lost the contract"
