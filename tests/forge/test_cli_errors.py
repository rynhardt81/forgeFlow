"""forge CLI exit codes are a contract skills and hooks branch on (T964).

One `_cli_errors` decorator replaced ~19 hand-copied except blocks. These pin
the codes those blocks produced: a refused state change exits 2 for the task
lifecycle commands and 1 elsewhere; every other expected error exits 1.
"""

from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path

import pytest

import forge
import registry_ops as ops
from conftest import base_registry, make_repo

FORGE = Path(__file__).resolve().parents[2] / "scripts" / "forge" / "forge.py"


@pytest.fixture
def repo(tmp_path):
    reg = base_registry(tasks=[
        {"id": "T1", "status": "completed", "dependencies": [], "name": "a"},
        {"id": "T2", "status": "ready", "dependencies": [], "name": "b"},
    ])
    return make_repo(tmp_path, reg, task_files={
        "E1/T1": {"id": "T1", "status": "completed"},
        "E1/T2": {"id": "T2", "status": "ready"},
    })


@pytest.mark.parametrize("argv,code", [
    (["task", "lock", "T404", "--session", "s"], 1),
    (["task", "lock", "T1", "--session", "s"], 2),
    (["task", "complete", "T2"], 2),
    (["task", "pr", "T2"], 2),
    (["task", "unlock", "T2"], 2),
    (["task", "status", "T2", "completed"], 2),
    (["epic", "status", "E9", "backlog"], 1),
    (["task", "rename", "T2", ""], 1),
    (["task", "set-deps", "T2", "--deps", "T2"], 1),
    (["epic", "add", "E1", "--name", "x"], 1),
    (["task", "add", "T1", "--epic", "E1", "--name", "dup"], 1),
    (["task", "set-scope", "T2"], 1),
])
def test_exit_codes(repo, argv, code):
    p = subprocess.run([sys.executable, "-B", str(FORGE), *argv], capture_output=True, text=True,
                       env={**os.environ, "CLAUDE_PROJECT_DIR": str(repo)})
    assert p.returncode == code, p.stderr
    assert p.stderr.startswith("error: ")


@pytest.mark.parametrize("exc,transition_exit,code", [
    (ops.RegistryLockTimeout("held"), 2, 1),
    (ops.IllegalTransition("no"), 2, 2),
    (ops.IllegalTransition("no"), 1, 1),
    (ops.TaskNotFound("T9"), 2, 1),
    (ValueError("bad"), 2, 1),
    (FileNotFoundError("gone"), 2, 1),
])
def test_decorator_maps(exc, transition_exit, code, capsys):
    @forge._cli_errors(transition_exit=transition_exit)
    def cmd(args, root):
        raise exc

    assert cmd(None, None) == code
    err = capsys.readouterr().err
    assert ("registry is locked" in err) == isinstance(exc, ops.RegistryLockTimeout)


def test_unexpected_errors_still_raise():
    @forge._cli_errors()
    def cmd(args, root):
        raise KeyError("bug")

    with pytest.raises(KeyError):
        cmd(None, None)


def test_no_hand_copied_lock_timeout_blocks_remain():
    assert FORGE.read_text().count("except ops.RegistryLockTimeout") == 1
