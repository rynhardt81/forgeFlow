"""Tests for the security_secrets validator's yaml-pattern loading (T305).

Verifies the dead-config defect is fixed: secret-patterns.yaml is now loaded
and UNIONed with the hardcoded defaults, bare-install safe (falls back to the
hardcoded list when PyYAML or the file is absent), and the validator stays
advisory (warn, never block).
"""

from __future__ import annotations

import importlib.util
from pathlib import Path

import pytest

_REPO_ROOT = Path(__file__).resolve().parents[2]
_VALIDATOR = (
    _REPO_ROOT / "hooks" / "validators" / "agents" / "security_secrets.py"
)


def _load_module():
    """Import security_secrets.py directly (it's not on a package path)."""
    # Its own sys.path.insert handles `from base import ...`.
    spec = importlib.util.spec_from_file_location(
        "security_secrets", _VALIDATOR
    )
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


@pytest.fixture
def mod():
    return _load_module()


def _validator(mod, file_path, content):
    v = mod.SecuritySecretsValidator()
    v.input_data = {
        "tool_name": "Write",
        "tool_input": {"file_path": file_path, "content": content},
    }
    return v


# --- union semantics (ISC-9) ---------------------------------------------


def test_resolved_patterns_includes_all_hardcoded(mod):
    resolved = {p for p, _ in mod._resolved_patterns()}
    hardcoded = {p for p, _ in mod.SECRET_PATTERNS}
    # No hardcoded pattern is dropped by the union.
    assert hardcoded <= resolved


def test_resolved_patterns_dedupes_on_regex(mod):
    pats = [p for p, _ in mod._resolved_patterns()]
    assert len(pats) == len(set(pats))  # no duplicate regexes


# --- yaml adds patterns not in the hardcoded list (ISC-12) ---------------


def test_yaml_only_pattern_is_detected(mod):
    # "Anthropic API key" (sk-ant-...) is in secret-patterns.yaml but NOT in
    # the hardcoded SECRET_PATTERNS. After the fix it must be detected.
    yaml_pats = dict((d, p) for p, d in mod._load_yaml_patterns())
    if "Anthropic API key" not in yaml_pats:
        pytest.skip("yaml/PyYAML unavailable in this env; covered by fallback test")
    content = 'KEY = "sk-ant-' + "a" * 40 + '"'
    res = _validator(mod, "config.py", content).validate()
    assert res.warning is True


# --- bare-install fallback (Anti: ISC-10) --------------------------------


def test_falls_back_when_yaml_load_fails(mod, monkeypatch):
    # Simulate PyYAML/file absent: _load_yaml_patterns returns [].
    monkeypatch.setattr(mod, "_load_yaml_patterns", lambda: [])
    resolved = mod._resolved_patterns()
    hardcoded = mod.SECRET_PATTERNS
    # Validator still works on the hardcoded floor alone.
    assert len(resolved) == len(hardcoded)
    # And a hardcoded pattern still fires.
    content = "AKIA" + "1234567890ABCDEF"  # AWS Access Key ID shape
    res = _validator(mod, "config.py", content).validate()
    assert res.warning is True


# --- advisory, never block (Anti: ISC-11) --------------------------------


def test_validator_is_advisory_only(mod):
    # A detected secret yields a WARNING ValidationResult, not a block.
    content = 'api_key = "' + "a" * 30 + '"'
    res = _validator(mod, "config.py", content).validate()
    assert res.warning is True
    # ValidationResult carries no "block" semantics — warn is the strongest.
    assert getattr(res, "blocking", False) in (False, None)


def test_clean_content_passes(mod):
    res = _validator(mod, "config.py", "x = 1\n").validate()
    assert res.warning is False
