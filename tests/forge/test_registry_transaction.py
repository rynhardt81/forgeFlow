"""registry_transaction owns lock -> load -> mutate -> stats -> save (T964)."""

from __future__ import annotations

import json
import re
from pathlib import Path

import pytest

import registry_ops as ops
from conftest import base_registry, make_repo

OPS = Path(__file__).resolve().parents[2] / "scripts" / "forge" / "registry_ops.py"


@pytest.fixture
def reg_path(tmp_path):
    root = make_repo(tmp_path, base_registry(tasks=[{"id": "T1", "status": "ready", "dependencies": []}]))
    return root / "docs" / "tasks" / "registry.json"


def test_clean_exit_recomputes_and_saves(reg_path):
    with ops.registry_transaction(reg_path) as reg:
        ops.find_task(reg, "T1")["status"] = "pending"
    saved = json.loads(reg_path.read_text())
    assert ops.find_task(saved, "T1")["status"] == "pending"
    assert saved["stats"]["tasks"]["pending"] == 1


def test_exception_skips_the_save(reg_path):
    before = reg_path.read_text()
    with pytest.raises(ops.IllegalTransition):
        with ops.registry_transaction(reg_path) as reg:
            ops.find_task(reg, "T1")["status"] = "completed"
            raise ops.IllegalTransition("refused")
    assert reg_path.read_text() == before


def test_recompute_false_leaves_stats(reg_path):
    stale = json.loads(reg_path.read_text())["stats"]
    with ops.registry_transaction(reg_path, recompute=False) as reg:
        ops.find_task(reg, "T1")["name"] = "renamed"
    assert json.loads(reg_path.read_text())["stats"] == stale


def test_refused_op_through_a_converted_site_writes_nothing(reg_path):
    before = reg_path.read_text()
    with pytest.raises(ops.IllegalTransition):
        ops.complete_task(reg_path, reg_path.parents[2], "T1")
    assert reg_path.read_text() == before


def test_only_conditional_save_sites_lock_by_hand():
    src = OPS.read_text(encoding="utf-8")
    hand = [m.group(1) for m in re.finditer(
        r"^def (\w+)\((?:(?!^def ).)*?^\s+with registry_write_lock\(registry_path\):",
        src, re.S | re.M)]
    assert sorted(hand) == ["complete_epic", "move_task", "reconcile_orphan_files", "registry_transaction"]
