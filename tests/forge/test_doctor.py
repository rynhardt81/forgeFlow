"""Tests for `forge doctor` — read-only install health check (spike, plans/008).

Covers both field states:
  - framework-repo layout (this checkout)
  - synthetic consumer layout (.claude/ in a tmp dir) with planted problems:
    missing VERSION, a cut-paths orphan, a wired-but-missing hook file
plus the binding read-only constraint and the exit-code contract
(0 healthy / 1 findings / 2 no install).

Doctor is exercised through the CLI (subprocess), matching how it ships;
check_consistency.py is deliberately never imported (concurrent-edit
isolation — doctor shells out to it, tests shell out to doctor).
"""

from __future__ import annotations

import hashlib
import json
import subprocess
import sys
from pathlib import Path

_REPO_ROOT = Path(__file__).resolve().parents[2]
_FORGE_PY = _REPO_ROOT / "scripts" / "forge" / "forge.py"
_CUT_PATHS = _REPO_ROOT / "scripts" / "install" / "cut-paths.txt"

# A retired path from the real manifest, planted as the synthetic orphan.
_ORPHAN_REL = "hooks/context/pre-compact.py"


def run_doctor(project_root: Path, *extra: str) -> subprocess.CompletedProcess:
    return subprocess.run(
        [sys.executable, str(_FORGE_PY), "--project-root", str(project_root),
         "doctor", *extra],
        capture_output=True, text=True,
    )


def run_doctor_direct(*args: str, project_root: Path | None = None) -> subprocess.CompletedProcess:
    """Invoke doctor.py directly (not via forge.py) — used for --banner, which
    the SessionStart hook calls this way (see hooks/forge/consistency-banner.py)."""
    _DOCTOR_PY = _REPO_ROOT / "scripts" / "forge" / "doctor.py"
    cmd = [sys.executable, str(_DOCTOR_PY)]
    if project_root is not None:
        cmd += ["--project-root", str(project_root)]
    cmd += list(args)
    return subprocess.run(cmd, capture_output=True, text=True)


def make_consumer(tmp_path: Path, *, version: str | None = None,
                  orphan: bool = True, broken_wiring: bool = True,
                  manifest: bool = True) -> Path:
    """Build a synthetic consumer install under tmp_path/.claude/."""
    claude = tmp_path / ".claude"
    (claude / "hooks" / "session").mkdir(parents=True)
    (claude / "hooks" / "context").mkdir(parents=True)

    # One wired hook that exists on disk.
    (claude / "hooks" / "session" / "session-context.py").write_text("# ok\n")

    commands = [
        'python3 "$CLAUDE_PROJECT_DIR/.claude/hooks/session/session-context.py"',
    ]
    if broken_wiring:
        commands.append(
            'python3 "$CLAUDE_PROJECT_DIR/.claude/hooks/validation/validate-edit.py"'
        )
    settings = {
        "hooks": {
            "SessionStart": [
                {"hooks": [{"type": "command", "command": c} for c in commands]}
            ]
        }
    }
    (claude / "hooks" / "settings.json").write_text(json.dumps(settings, indent=2))

    if orphan:
        (claude / _ORPHAN_REL).write_text("# retired v3 hook\n")

    if manifest:
        dst = claude / "scripts" / "install"
        dst.mkdir(parents=True)
        (dst / "cut-paths.txt").write_text(_CUT_PATHS.read_text())

    if version is not None:
        (claude / "VERSION").write_text(version + "\n")

    return tmp_path


def make_live_settings_consumer(
    tmp_path: Path, *, version: str | None = "4.1.0",
    broken_wiring: bool = False, no_hooks_key: bool = False,
    local_settings_hooks: dict | None = None,
) -> Path:
    """Build a synthetic consumer matching the REAL field layout: hook wiring
    merged into the live `.claude/settings.json` (as install.sh's
    install_settings() does), with no `.claude/hooks/settings.json` at all
    (install.sh's rsync excludes settings.json by basename, so the framework
    repo's copy never reaches consumers — see Finding 1, plans field report).
    """
    claude = tmp_path / ".claude"
    (claude / "hooks" / "session").mkdir(parents=True)

    (claude / "hooks" / "session" / "session-context.py").write_text("# ok\n")

    if version is not None:
        (claude / "VERSION").write_text(version + "\n")

    settings: dict = {}
    if not no_hooks_key:
        commands = [
            'python3 "$CLAUDE_PROJECT_DIR/.claude/hooks/session/session-context.py"',
        ]
        if broken_wiring:
            commands.append(
                'python3 "$CLAUDE_PROJECT_DIR/.claude/hooks/validation/validate-edit.py"'
            )
        settings["hooks"] = {
            "SessionStart": [
                {"hooks": [{"type": "command", "command": c} for c in commands]}
            ]
        }
    (claude / "settings.json").write_text(json.dumps(settings, indent=2))

    if local_settings_hooks is not None:
        (claude / "settings.local.json").write_text(
            json.dumps({"hooks": local_settings_hooks}, indent=2)
        )

    return tmp_path


def tree_hashes(root: Path) -> dict[str, str]:
    return {
        str(p.relative_to(root)): hashlib.sha256(p.read_bytes()).hexdigest()
        for p in sorted(root.rglob("*")) if p.is_file()
    }


def check_by_name(payload: dict, name: str) -> dict:
    return next(c for c in payload["checks"] if c["name"] == name)


# --- Field state (a): framework repo ------------------------------------


def test_doctor_framework_repo_layout():
    result = run_doctor(_REPO_ROOT, "--json")
    payload = json.loads(result.stdout)

    assert payload["layout"] == "framework-repo"
    assert payload["framework_root"] == str(_REPO_ROOT)
    # VERSION is stamped and clean in this checkout.
    assert check_by_name(payload, "version")["status"] == "ok"
    assert payload["version"] == (_REPO_ROOT / "VERSION").read_text().strip()
    # Retired paths are actually gone from the framework tree.
    assert check_by_name(payload, "orphans")["status"] == "ok"
    # Wiring: the tests/wiring suite enforces this invariant; doctor agrees.
    assert check_by_name(payload, "wiring")["status"] == "ok"
    # Registry may or may not exist here (docs/tasks/registry.json is
    # gitignored — absent in CI/worktrees, present on dogfooding machines).
    assert check_by_name(payload, "registry")["status"] in ("ok", "issues", "skipped")
    # Exit-code contract mirrors the healthy flag.
    assert result.returncode == (0 if payload["healthy"] else 1)


# --- Field state (b): synthetic consumer ---------------------------------


def test_doctor_reports_all_planted_problems(tmp_path):
    root = make_consumer(tmp_path)  # no VERSION, orphan, broken wiring

    result = run_doctor(root, "--json")
    payload = json.loads(result.stdout)

    assert result.returncode == 1
    assert payload["healthy"] is False
    assert payload["layout"] == "consumer"

    version = check_by_name(payload, "version")
    assert version["status"] == "issues"
    assert any("VERSION file not found" in f for f in version["findings"])

    orphans = check_by_name(payload, "orphans")
    assert orphans["status"] == "issues"
    assert _ORPHAN_REL in orphans["findings"]

    wiring = check_by_name(payload, "wiring")
    assert wiring["status"] == "issues"
    assert any("hooks/validation/validate-edit.py" in f for f in wiring["findings"])

    # No registry in the synthetic consumer -> informational skip, not a finding.
    assert check_by_name(payload, "registry")["status"] == "skipped"


def test_doctor_healthy_consumer_exits_zero(tmp_path):
    root = make_consumer(
        tmp_path, version="4.1.0", orphan=False, broken_wiring=False
    )

    result = run_doctor(root, "--json")
    payload = json.loads(result.stdout)

    assert result.returncode == 0
    assert payload["healthy"] is True
    assert payload["version"] == "4.1.0"
    assert all(c["status"] in ("ok", "skipped") for c in payload["checks"])


def test_doctor_missing_manifest_skips_orphans_check(tmp_path):
    root = make_consumer(
        tmp_path, version="4.1.0", orphan=True, broken_wiring=False,
        manifest=False,
    )

    result = run_doctor(root, "--json")
    payload = json.loads(result.stdout)

    orphans = check_by_name(payload, "orphans")
    # Without a shipped manifest the check must degrade to skipped —
    # never crash, never claim "no orphans".
    assert orphans["status"] == "skipped"
    assert result.returncode == 0  # remaining checks are clean


def test_doctor_is_read_only(tmp_path):
    root = make_consumer(tmp_path)  # unhealthy: all three problems planted
    before = tree_hashes(root)

    run_doctor(root)
    run_doctor(root, "--json")

    assert tree_hashes(root) == before, "doctor mutated the install it examined"


def test_doctor_no_install_exits_two(tmp_path):
    result = run_doctor(tmp_path, "--json")

    assert result.returncode == 2
    payload = json.loads(result.stdout)
    assert payload["healthy"] is False
    assert "no Forge Flow install found" in payload["error"]


def test_doctor_human_output_matches_exit_code(tmp_path):
    root = make_consumer(tmp_path)

    result = run_doctor(root)

    assert result.returncode == 1
    assert "healthy: no" in result.stdout
    assert _ORPHAN_REL in result.stdout
    assert "hint: run a framework refresh" in result.stdout


# --- Wiring check: real consumer layout (Finding 1) -----------------------
#
# Real consumers never receive hooks/settings.json — install.sh's rsync
# excludes settings.json by basename (matches hooks/settings.json too), and
# hook wiring is merged into the live .claude/settings.json instead. Doctor's
# wiring check must read that live location on consumer layout, not just the
# framework-repo-native hooks/settings.json.


def test_doctor_wiring_ok_with_live_settings_no_hooks_settings_json(tmp_path):
    root = make_live_settings_consumer(tmp_path, broken_wiring=False)
    assert not (root / ".claude" / "hooks" / "settings.json").exists()
    assert (root / ".claude" / "settings.json").exists()

    result = run_doctor(root, "--json")
    payload = json.loads(result.stdout)

    wiring = check_by_name(payload, "wiring")
    assert wiring["status"] == "ok"
    assert wiring["findings"] == []


def test_doctor_wiring_issues_with_live_settings_missing_hook_file(tmp_path):
    root = make_live_settings_consumer(tmp_path, broken_wiring=True)

    result = run_doctor(root, "--json")
    payload = json.loads(result.stdout)

    wiring = check_by_name(payload, "wiring")
    assert wiring["status"] == "issues"
    assert any("hooks/validation/validate-edit.py" in f for f in wiring["findings"])


def test_doctor_wiring_issues_when_no_settings_anywhere(tmp_path):
    # VERSION alone is enough for resolve_framework_root to detect a
    # consumer install; no hooks/settings.json AND no live settings.json.
    claude = tmp_path / ".claude"
    claude.mkdir()
    (claude / "VERSION").write_text("4.1.0\n")

    result = run_doctor(tmp_path, "--json")
    payload = json.loads(result.stdout)

    wiring = check_by_name(payload, "wiring")
    assert wiring["status"] == "issues"
    assert any("no hook wiring found" in f for f in wiring["findings"])


def test_doctor_wiring_merges_settings_local_json_hooks(tmp_path):
    # settings.local.json's hooks (if present) must be honored too — a
    # locally-added hook that's missing on disk must be caught.
    root = make_live_settings_consumer(
        tmp_path, broken_wiring=False,
        local_settings_hooks={
            "PreToolUse": [
                {"hooks": [{
                    "type": "command",
                    "command": 'python3 "$CLAUDE_PROJECT_DIR/.claude/hooks/validators/does-not-exist.py"',
                }]}
            ]
        },
    )

    result = run_doctor(root, "--json")
    payload = json.loads(result.stdout)

    wiring = check_by_name(payload, "wiring")
    assert wiring["status"] == "issues"
    assert any("hooks/validators/does-not-exist.py" in f for f in wiring["findings"])


def test_doctor_framework_repo_layout_wiring_unaffected(tmp_path):
    # The framework-repo-layout tests (hooks/settings.json present) must
    # keep passing unchanged — this is a regression guard on that path.
    result = run_doctor(_REPO_ROOT, "--json")
    payload = json.loads(result.stdout)

    assert payload["layout"] == "framework-repo"
    assert check_by_name(payload, "wiring")["status"] == "ok"


# --- cut-paths.txt ledger (Finding 2) --------------------------------------


def test_cut_paths_manifest_has_pre_manifest_installer_relic_entries():
    lines = {
        line.strip().rstrip("/")
        for line in _CUT_PATHS.read_text().splitlines()
        if line.strip() and not line.strip().startswith("#")
    }
    expected = {
        "scripts/install/add-project-memory.ps1",
        "scripts/install/add-project-memory.sh",
        "scripts/install/migrate.ps1",
        "scripts/install/migrate.sh",
        "scripts/install/upgrade-template.sh",
        "scripts/install/versions",
    }
    assert expected <= lines


def test_cut_paths_manifest_never_lists_itself_or_its_own_dir():
    lines = {
        line.strip().rstrip("/")
        for line in _CUT_PATHS.read_text().splitlines()
        if line.strip() and not line.strip().startswith("#")
    }
    assert "scripts/install/cut-paths.txt" not in lines
    assert "scripts/install" not in lines


# --- Fleet sweep (--all) --------------------------------------------------


def test_doctor_all_discovers_and_flags_stale(tmp_path):
    parent = tmp_path / "fleet"
    parent.mkdir()
    make_consumer(parent / "current-clean", version="4.1.0",
                  orphan=False, broken_wiring=False)
    make_consumer(parent / "old-with-orphan", version="3.0.0",
                  orphan=True, broken_wiring=False)

    # Run from the framework repo so a reference version is available.
    result = run_doctor(_REPO_ROOT, "--all", str(parent), "--json")
    payload = json.loads(result.stdout)

    assert result.returncode == 1
    assert payload["healthy"] is False
    assert payload["reference_version"] == (_REPO_ROOT / "VERSION").read_text().strip()

    by_name = {row["name"]: row for row in payload["installs"]}
    assert set(by_name) == {"current-clean", "old-with-orphan"}

    current = by_name["current-clean"]
    assert current["version"] == "4.1.0"
    assert current["stale"] is False
    assert current["orphans_count"] == 0
    assert current["healthy"] is True

    old = by_name["old-with-orphan"]
    assert old["version"] == "3.0.0"
    assert old["stale"] is True
    assert old["orphans_count"] == 1
    assert old["healthy"] is False


def test_doctor_all_human_output_has_one_row_per_install(tmp_path):
    parent = tmp_path / "fleet"
    parent.mkdir()
    make_consumer(parent / "clean-one", version="4.1.0",
                  orphan=False, broken_wiring=False)

    result = run_doctor(_REPO_ROOT, "--all", str(parent))

    assert result.returncode == 0
    assert "clean-one" in result.stdout
    assert "healthy: yes" in result.stdout


def test_doctor_all_reference_is_na_outside_framework_repo(tmp_path):
    parent = tmp_path / "fleet"
    parent.mkdir()
    consumer_root = make_consumer(parent / "some-consumer", version="4.1.0",
                                  orphan=False, broken_wiring=False)

    # Doctor invoked with a consumer as its own project_root: no reference.
    result = run_doctor(consumer_root, "--all", str(parent), "--json")
    payload = json.loads(result.stdout)

    assert payload["reference_version"] is None
    row = next(r for r in payload["installs"] if r["name"] == "some-consumer")
    assert row["stale"] is None


def test_doctor_all_depth_bounded_scan_ignores_deeper_nesting(tmp_path):
    parent = tmp_path / "fleet"
    parent.mkdir()
    # Discoverable: immediate child.
    make_consumer(parent / "top-level", version="4.1.0",
                  orphan=False, broken_wiring=False)
    # Not discoverable: three levels deep (parent/group/nested/too-deep).
    too_deep = parent / "group" / "nested" / "too-deep" / ".claude"
    too_deep.mkdir(parents=True)
    (too_deep / "VERSION").write_text("9.9.9\n")

    result = run_doctor(_REPO_ROOT, "--all", str(parent), "--json")
    payload = json.loads(result.stdout)

    names = {row["name"] for row in payload["installs"]}
    assert names == {"top-level"}
    assert "too-deep" not in names


def test_doctor_all_no_installs_found_is_healthy(tmp_path):
    parent = tmp_path / "empty-fleet"
    parent.mkdir()

    result = run_doctor(_REPO_ROOT, "--all", str(parent), "--json")
    payload = json.loads(result.stdout)

    assert result.returncode == 0
    assert payload["healthy"] is True
    assert payload["installs"] == []


# --- SessionStart banner (--banner) ---------------------------------------


def test_doctor_banner_silent_when_healthy():
    # The framework repo checkout itself is the healthy fixture — real
    # VERSION, real (swept) cut-paths manifest.
    result = run_doctor_direct("--banner", project_root=_REPO_ROOT)

    assert result.returncode == 0
    assert result.stdout == ""


def test_doctor_banner_one_line_when_version_missing(tmp_path):
    root = make_consumer(tmp_path, version=None, orphan=False, broken_wiring=False)

    result = run_doctor_direct("--banner", project_root=root)

    assert result.returncode == 0
    lines = [line for line in result.stdout.splitlines() if line.strip()]
    assert len(lines) == 1
    assert lines[0].startswith("forge doctor:")
    assert "version unknown" in lines[0]


def test_doctor_banner_one_line_when_orphans_present(tmp_path):
    root = make_consumer(tmp_path, version="4.1.0", orphan=True, broken_wiring=False)

    result = run_doctor_direct("--banner", project_root=root)

    assert result.returncode == 0
    lines = [line for line in result.stdout.splitlines() if line.strip()]
    assert len(lines) == 1
    assert lines[0].startswith("forge doctor:")
    assert "retired framework file" in lines[0]


def test_doctor_banner_silent_when_manifest_missing_but_version_ok(tmp_path):
    # No shipped manifest -> orphans check is skipped (not issues), so the
    # banner must stay silent rather than misreport a problem.
    root = make_consumer(tmp_path, version="4.1.0", orphan=False,
                         broken_wiring=False, manifest=False)

    result = run_doctor_direct("--banner", project_root=root)

    assert result.returncode == 0
    assert result.stdout == ""


def test_doctor_banner_always_exits_zero_even_with_broken_wiring(tmp_path):
    # broken_wiring only affects the "wiring" check, which --banner never
    # runs — banner is version+orphans only, so this must still be silent.
    root = make_consumer(tmp_path, version="4.1.0", orphan=False, broken_wiring=True)

    result = run_doctor_direct("--banner", project_root=root)

    assert result.returncode == 0
    assert result.stdout == ""


def test_doctor_banner_no_install_found_is_silent(tmp_path):
    result = run_doctor_direct("--banner", project_root=tmp_path)

    assert result.returncode == 0
    assert result.stdout == ""
