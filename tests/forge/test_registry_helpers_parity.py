"""Post-consolidation contract tests for plan 007 (registry helper dedup).

Before consolidation, this file compared check_consistency's duplicated
helpers against their registry_ops counterparts to prove no drift bug
existed. That comparison passed (see git history — commit
"test(forge): characterization tests for duplicated registry helpers"),
so consolidation proceeded: check_consistency.py deleted its local copies
of _expected_stats, _rewrite_frontmatter_status, _rewrite_frontmatter_name,
_yaml_quote_if_needed, _yaml_unquote_scalar, save_registry, and
registry_write_lock, replacing every call site with `registry_ops.*`.

This file now asserts the POST-consolidation contract instead:
  - check_consistency.py has no local definition of any formerly-duplicated
    name (Step 3 of plan 007 — `rg` proves this at the text level; these
    tests prove it at the behavioral level via `cc.registry_ops.<name>`).
  - The checker's own frontmatter/YAML helpers, reached via
    `cc.registry_ops.*`, still round-trip correctly.
  - `load_registry`'s None-on-error contract (the one deliberately
    preserved difference) still holds.
"""

from __future__ import annotations

import pytest

import check_consistency as cc
import registry_ops as ops


def test_check_consistency_has_no_local_duplicate_defs():
    """The formerly-duplicated names must not be defined IN check_consistency
    (only the thin load_registry wrapper is a permitted local def)."""
    import inspect

    duplicated_names = [
        "_expected_stats",
        "_yaml_quote_if_needed",
        "_yaml_unquote_scalar",
        "_rewrite_frontmatter_status",
        "_rewrite_frontmatter_name",
        "save_registry",
        "registry_write_lock",
    ]
    for name in duplicated_names:
        assert not hasattr(cc, name) or inspect.getmodule(getattr(cc, name)) is not cc, (
            f"{name} must not be locally defined in check_consistency.py "
            f"anymore — it should be reached via registry_ops.{name}"
        )
    # registry_ops itself must still define everything.
    for name in duplicated_names:
        assert hasattr(ops, name), f"registry_ops must still define {name}"

    # And check_consistency must import registry_ops to reach them.
    assert cc.registry_ops is ops


def test_load_registry_none_on_missing_file_contract_preserved(tmp_path):
    """cc.load_registry must return None (not raise) for a missing registry —
    the checker no-ops gracefully; registry_ops.load_registry raises."""
    missing = tmp_path / "does-not-exist.json"
    assert cc.load_registry(missing) is None
    with pytest.raises(FileNotFoundError):
        ops.load_registry(missing)


def test_load_registry_none_on_corrupt_json_contract_preserved(tmp_path):
    corrupt = tmp_path / "registry.json"
    corrupt.write_text("{not valid json", encoding="utf-8")
    assert cc.load_registry(corrupt) is None
    import json as _json
    with pytest.raises(_json.JSONDecodeError):
        ops.load_registry(corrupt)


def test_load_registry_delegates_to_registry_ops_on_success(tmp_path):
    """A valid registry loads identically through both entry points."""
    good = tmp_path / "registry.json"
    good.write_text('{"tasks": [], "epics": []}', encoding="utf-8")
    assert cc.load_registry(good) == ops.load_registry(good)


# --- _expected_stats (reached via cc.registry_ops) -------------------------


def _registry_with_every_status():
    tasks = [
        {"id": "T1", "status": "pending"},
        {"id": "T2", "status": "ready"},
        {"id": "T3", "status": "in_progress"},
        {"id": "T4", "status": "pr_pending"},
        {"id": "T5", "status": "continuation"},
        {"id": "T6", "status": "completed"},
        {"id": "T7", "status": "completed"},
    ]
    epics = [
        {"id": "E1", "status": "pending"},
        {"id": "E2", "status": "ready"},
        {"id": "E3", "status": "in_progress"},
        {"id": "E4", "status": "blocked"},
        {"id": "E5", "status": "completed"},
    ]
    return {"tasks": tasks, "epics": epics, "stats": {}}


def test_expected_stats_full_status_spread_via_shared_impl():
    registry = _registry_with_every_status()
    expected = {
        "epics": {
            "total": 5, "completed": 1, "in_progress": 1,
            "blocked": 1, "ready": 1, "pending": 1,
        },
        "tasks": {
            "total": 7, "completed": 2, "in_progress": 1, "pr_pending": 1,
            "continuation": 1, "ready": 1, "pending": 1,
        },
    }
    assert cc.registry_ops._expected_stats(registry) == expected
    # And check_stats_drift (the checker's own caller) uses the same impl.
    findings = cc.check_stats_drift(registry)
    assert [f.target for f in findings] == ["stats.epics", "stats.tasks"]


def test_expected_stats_empty_registry_via_shared_impl():
    registry = {"tasks": [], "epics": [], "stats": {}}
    assert cc.registry_ops._expected_stats(registry) == {
        "epics": {"total": 0, "completed": 0, "in_progress": 0,
                   "blocked": 0, "ready": 0, "pending": 0},
        "tasks": {"total": 0, "completed": 0, "in_progress": 0,
                  "pr_pending": 0, "continuation": 0, "ready": 0, "pending": 0},
    }


# --- Frontmatter status rewriter (reached via cc.registry_ops) ------------


FRONTMATTER_QUOTED = (
    '---\n'
    'id: T1\n'
    'name: "hello: world"\n'
    'status: "ready"\n'
    '---\n\n'
    '# T1\n'
)

FRONTMATTER_UNQUOTED = (
    '---\n'
    'id: T1\n'
    'name: hello\n'
    'status: pending\n'
    '---\n\n'
    '# T1\n'
)

FRONTMATTER_NAME_NEEDS_QUOTING = (
    '---\n'
    'id: T1\n'
    'name: plain-name\n'
    'status: ready\n'
    '---\n\n'
    '# T1\n'
)

FRONTMATTER_MISSING = (
    '# T1\n\nNo frontmatter here.\nstatus: pending\n'
)

FRONTMATTER_STRAY_STATUS_IN_BODY = (
    '---\n'
    'id: T1\n'
    'status: ready\n'
    '---\n\n'
    '# T1\n\n'
    'Body text that happens to say status: completed but must NOT be rewritten.\n'
)


def test_rewrite_frontmatter_status_quoted_value():
    new_content, changed = cc.registry_ops._rewrite_frontmatter_status(
        FRONTMATTER_QUOTED, "in_progress"
    )
    assert changed is True
    assert "status: in_progress" in new_content


def test_rewrite_frontmatter_status_missing_frontmatter_is_noop():
    result = cc.registry_ops._rewrite_frontmatter_status(FRONTMATTER_MISSING, "ready")
    assert result == (FRONTMATTER_MISSING, False)


def test_rewrite_frontmatter_status_stray_status_in_body_not_rewritten():
    new_content, changed = cc.registry_ops._rewrite_frontmatter_status(
        FRONTMATTER_STRAY_STATUS_IN_BODY, "pr_pending"
    )
    assert changed is True
    assert "status: completed but must NOT be rewritten" in new_content


def test_rewrite_frontmatter_status_noop_when_no_status_field():
    content = '---\nid: T1\nname: hello\n---\n\n# T1\n'
    result = cc.registry_ops._rewrite_frontmatter_status(content, "ready")
    assert result == (content, False)


# --- Frontmatter name rewriter (reached via cc.registry_ops) --------------


def test_rewrite_frontmatter_name_value_needing_yaml_quoting():
    new_name = 'name with "quotes" and: a colon # and hash'
    new_content, changed = cc.registry_ops._rewrite_frontmatter_name(
        FRONTMATTER_NAME_NEEDS_QUOTING, new_name
    )
    assert changed is True
    assert '\\"quotes\\"' in new_content


def test_rewrite_frontmatter_name_missing_frontmatter_is_noop():
    result = cc.registry_ops._rewrite_frontmatter_name(FRONTMATTER_MISSING, "whatever")
    assert result == (FRONTMATTER_MISSING, False)


def test_rewrite_frontmatter_name_noop_when_no_name_field():
    content = '---\nid: T1\nstatus: ready\n---\n\n# T1\n'
    result = cc.registry_ops._rewrite_frontmatter_name(content, "new name")
    assert result == (content, False)


def test_parse_frontmatter_name_uses_shared_unquote(monkeypatch):
    """cc._parse_frontmatter_name must call through to
    registry_ops._yaml_unquote_scalar rather than a local copy."""
    calls = []
    original = ops._yaml_unquote_scalar

    def spy(raw):
        calls.append(raw)
        return original(raw)

    monkeypatch.setattr(ops, "_yaml_unquote_scalar", spy)
    name = cc._parse_frontmatter_name(FRONTMATTER_QUOTED)
    assert name == "hello: world"
    assert calls, "expected _parse_frontmatter_name to call registry_ops._yaml_unquote_scalar"


# --- YAML quote / unquote round-trips (reached via cc.registry_ops) -------


@pytest.mark.parametrize("value", [
    "",
    "plain",
    "with space",
    "colon: inside",
    "hash # inside",
    "-leading-dash",
    '"already quoted"',
    "trailing space ",
    " leading space",
    'has "double" quotes',
    "has\\backslash",
    "has\\backslash and \"quote\"",
])
def test_yaml_quote_unquote_roundtrip(value):
    quoted = cc.registry_ops._yaml_quote_if_needed(value)
    assert cc.registry_ops._yaml_unquote_scalar(quoted) == value


# --- Lock timeout exception ------------------------------------------------


def test_checker_fix_path_raises_registry_ops_lock_timeout_type():
    """check_consistency.py's --fix path must reference registry_ops's
    RegistryLockTimeout, not a local ConsistencyLockTimeout (deleted by
    plan 007's consolidation)."""
    assert not hasattr(cc, "ConsistencyLockTimeout")
    assert issubclass(cc.registry_ops.RegistryLockTimeout, RuntimeError)
