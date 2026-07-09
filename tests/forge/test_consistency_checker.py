"""Tests for scripts/forge/check_consistency.py.

Covers:
  - All 7 drift classes (detection)
  - Auto-fix correctness for the 4 fixable classes
  - Strict-mode exit codes (the contract that the wrapper translates to exit 2)
  - Token-budget guards (silent-on-clean, max-300-char banner)
  - Perf budget on a 500-task synthetic registry
  - Schema-specific behavior (pr_pending counts as done; single lock object)
"""

from __future__ import annotations

import json
import time
from datetime import datetime, timedelta, timezone

import pytest

import check_consistency as cc
from conftest import base_registry, make_repo


# --- Helpers -------------------------------------------------------------


def rfc3339(dt):
    return dt.astimezone(timezone.utc).isoformat().replace("+00:00", "Z")


def now():
    return datetime.now(timezone.utc)


def task(id_, status="pending", **extra):
    t = {"id": id_, "status": status, "dependencies": []}
    t.update(extra)
    return t


def epic(id_, status="pending", tasks=None):
    return {"id": id_, "status": status, "tasks": tasks or []}


# --- Drift #1: file on disk, missing from registry ----------------------


def test_drift1_blocking(tmp_path):
    registry = base_registry()
    make_repo(tmp_path, registry, task_files={"E12/T999": {"id": "T999", "status": "ready"}})
    rc = cc.main(["--strict", "--project-root", str(tmp_path)])
    assert rc == 1


def test_drift1_no_false_positive_when_in_registry(tmp_path):
    registry = base_registry(tasks=[task("T1", "ready")])
    make_repo(tmp_path, registry, task_files={"E1/T1": {"id": "T1", "status": "ready"}})
    rc = cc.main(["--strict", "--project-root", str(tmp_path)])
    assert rc == 0


# --- Drift #2: epic dir on disk, missing from registry ------------------


def test_drift2_blocking(tmp_path):
    registry = base_registry()
    make_repo(tmp_path, registry, extra_dirs=["E99-orphan"])
    rc = cc.main(["--strict", "--project-root", str(tmp_path)])
    assert rc == 1


# --- Drift #3: completedAt < createdAt ----------------------------------


def test_drift3_monotonic_violation(tmp_path):
    t = task("T1", "completed",
             createdAt="2026-04-30T10:00:00Z",
             completedAt="2026-04-23T10:00:00Z")
    registry = base_registry(tasks=[t])
    make_repo(tmp_path, registry, task_files={"E1/T1": {"id": "T1", "status": "completed"}})
    rc = cc.main(["--strict", "--project-root", str(tmp_path)])
    assert rc == 1


def test_drift3_skips_when_either_field_missing(tmp_path):
    """Legacy backfill case: monotonicity check must not flag entries
    that lack one of the two timestamps. Otherwise older registries flood."""
    t = task("T1", "completed", completedAt="2026-04-23T10:00:00Z")
    registry = base_registry(tasks=[t])
    make_repo(tmp_path, registry, task_files={"E1/T1": {"id": "T1", "status": "completed"}})
    rc = cc.main(["--strict", "--project-root", str(tmp_path)])
    assert rc == 0


# --- Drift #4: stats drift -----------------------------------------------


def test_drift4_stats_recompute(tmp_path):
    """Registry stats are wrong; --fix recomputes them from the actual list."""
    registry = base_registry(tasks=[
        task("T1", "completed"), task("T2", "completed"), task("T3", "ready"),
    ])
    # Deliberately wrong:
    registry["stats"]["tasks"]["completed"] = 0
    registry["stats"]["tasks"]["ready"] = 0
    make_repo(tmp_path, registry)
    rc = cc.main(["--fix", "--project-root", str(tmp_path)])
    assert rc == 0
    out = json.loads((tmp_path / "docs" / "tasks" / "registry.json").read_text())
    assert out["stats"]["tasks"]["completed"] == 2
    assert out["stats"]["tasks"]["ready"] == 1


# --- Drift #5: pending -> ready when deps done ---------------------------


def test_drift5_pending_flips_to_ready(tmp_path):
    registry = base_registry(tasks=[
        task("T1", "completed"),
        task("T2", "pending", dependencies=["T1"]),
    ])
    make_repo(tmp_path, registry, task_files={
        "E1/T1": {"id": "T1", "status": "completed"},
        "E1/T2": {"id": "T2", "status": "pending"},
    })
    cc.main(["--fix", "--project-root", str(tmp_path)])
    out = json.loads((tmp_path / "docs" / "tasks" / "registry.json").read_text())
    t2 = next(t for t in out["tasks"] if t["id"] == "T2")
    assert t2["status"] == "ready"
    # File frontmatter also gets patched
    t2_file = next((tmp_path / "docs" / "epics").rglob("T2-fixture.md"))
    assert "status: ready" in t2_file.read_text()


def test_drift5_pr_pending_counts_as_done(tmp_path):
    """pr_pending should unblock dependents, mirroring how teams work
    once the PR is up but not yet merged."""
    registry = base_registry(tasks=[
        task("T1", "pr_pending"),
        task("T2", "pending", dependencies=["T1"]),
    ])
    make_repo(tmp_path, registry, task_files={
        "E1/T1": {"id": "T1", "status": "pr_pending"},
        "E1/T2": {"id": "T2", "status": "pending"},
    })
    cc.main(["--fix", "--project-root", str(tmp_path)])
    out = json.loads((tmp_path / "docs" / "tasks" / "registry.json").read_text())
    t2 = next(t for t in out["tasks"] if t["id"] == "T2")
    assert t2["status"] == "ready"


def test_drift5_does_not_flip_when_deps_incomplete(tmp_path):
    registry = base_registry(tasks=[
        task("T1", "in_progress"),
        task("T2", "pending", dependencies=["T1"]),
    ])
    make_repo(tmp_path, registry, task_files={
        "E1/T1": {"id": "T1", "status": "in_progress"},
        "E1/T2": {"id": "T2", "status": "pending"},
    })
    cc.main(["--fix", "--project-root", str(tmp_path)])
    out = json.loads((tmp_path / "docs" / "tasks" / "registry.json").read_text())
    t2 = next(t for t in out["tasks"] if t["id"] == "T2")
    assert t2["status"] == "pending"


# --- Drift #6: file frontmatter vs registry status ----------------------


def test_drift6_registry_wins(tmp_path):
    """File frontmatter status differs from registry; --fix rewrites the file."""
    registry = base_registry(tasks=[task("T1", "in_progress")])
    make_repo(tmp_path, registry, task_files={
        "E1/T1": {"id": "T1", "status": "ready"},  # disagrees with registry
    })
    cc.main(["--fix", "--project-root", str(tmp_path)])
    t1_file = next((tmp_path / "docs" / "epics").rglob("T1-fixture.md"))
    assert "status: in_progress" in t1_file.read_text()
    assert "status: ready" not in t1_file.read_text()


def test_drift6_preserves_frontmatter_terminator(tmp_path):
    """Regression: the status-line regex must not consume the newline
    that separates the status field from the closing `---`. Otherwise
    `status: ready\\n---\\n` collapses to `status: ready---\\n`, breaking
    the YAML frontmatter."""
    registry = base_registry(tasks=[task("T1", "completed")])
    make_repo(tmp_path, registry, task_files={"E1/T1": {"id": "T1", "status": "pending"}})
    cc.main(["--fix", "--project-root", str(tmp_path)])
    f = next((tmp_path / "docs" / "epics").rglob("T1-fixture.md"))
    content = f.read_text()
    # Both frontmatter delimiters must still be standalone lines
    lines = content.splitlines()
    assert lines[0] == "---"
    closing_idx = next(i for i, line in enumerate(lines[1:], start=1) if line == "---")
    # Status line lives between the delimiters and is its own line
    status_lines = [l for l in lines[1:closing_idx] if l.startswith("status:")]
    assert status_lines == ["status: completed"]


def test_drift6_preserves_body_content(tmp_path):
    """Frontmatter rewrite must not corrupt the body."""
    registry = base_registry(tasks=[task("T1", "completed")])
    make_repo(tmp_path, registry)
    # Write a richer file by hand
    f = tmp_path / "docs" / "epics" / "E1-fix" / "tasks" / "T1-fix.md"
    f.parent.mkdir(parents=True)
    f.write_text(
        "---\nid: T1\nstatus: ready\npriority: 2\n---\n\n"
        "# T1\n\nSome content.\n\nstatus: not-the-frontmatter-one\n"
    )
    cc.main(["--fix", "--project-root", str(tmp_path)])
    after = f.read_text()
    assert "status: completed" in after
    assert "priority: 2" in after  # other frontmatter fields preserved
    assert "Some content." in after  # body preserved
    assert "status: not-the-frontmatter-one" in after  # body status not touched


# --- Drift #7: stale lock -----------------------------------------------


def test_drift7_clears_stale_lock_keeps_status(tmp_path):
    old = rfc3339(now() - timedelta(hours=10))
    registry = base_registry(
        tasks=[task("T1", "in_progress",
                    lock={"session": "abc", "lockedAt": old})],
        settings={"lockTimeoutSeconds": 3600},
    )
    make_repo(tmp_path, registry, task_files={"E1/T1": {"id": "T1", "status": "in_progress"}})
    cc.main(["--fix", "--project-root", str(tmp_path)])
    out = json.loads((tmp_path / "docs" / "tasks" / "registry.json").read_text())
    t1 = next(t for t in out["tasks"] if t["id"] == "T1")
    assert t1["lock"] is None
    # Critical: status must NOT flip — pr_pending exists for the
    # "PR open, awaiting merge" case, so stale-lock-on-in_progress is
    # genuinely a stuck session and should stay in_progress for resume.
    assert t1["status"] == "in_progress"


def test_drift7_does_not_clear_fresh_lock(tmp_path):
    fresh = rfc3339(now() - timedelta(seconds=60))
    registry = base_registry(
        tasks=[task("T1", "in_progress",
                    lock={"session": "abc", "lockedAt": fresh})],
        settings={"lockTimeoutSeconds": 3600},
    )
    make_repo(tmp_path, registry, task_files={"E1/T1": {"id": "T1", "status": "in_progress"}})
    cc.main(["--fix", "--project-root", str(tmp_path)])
    out = json.loads((tmp_path / "docs" / "tasks" / "registry.json").read_text())
    t1 = next(t for t in out["tasks"] if t["id"] == "T1")
    assert t1["lock"] is not None


# --- Strict mode contract ------------------------------------------------


def test_strict_clean_returns_0(tmp_path):
    registry = base_registry(tasks=[task("T1", "completed")])
    make_repo(tmp_path, registry, task_files={"E1/T1": {"id": "T1", "status": "completed"}})
    rc = cc.main(["--strict", "--project-root", str(tmp_path)])
    assert rc == 0


def test_strict_blocking_returns_1(tmp_path):
    """The wrapper translates exit 1 -> exit 2 for PreToolUse; the
    checker's own contract is exit 1 so it stays usable from CLI."""
    registry = base_registry()
    make_repo(tmp_path, registry, task_files={"E12/T999": {"id": "T999", "status": "ready"}})
    rc = cc.main(["--strict", "--project-root", str(tmp_path)])
    assert rc == 1


def test_strict_ignores_auto_fixable(tmp_path):
    """Stats drift alone shouldn't block a commit — only blocking-class
    findings should produce exit 1 in strict mode."""
    registry = base_registry(tasks=[task("T1", "completed")])
    registry["stats"]["tasks"]["completed"] = 0  # drift
    make_repo(tmp_path, registry, task_files={"E1/T1": {"id": "T1", "status": "completed"}})
    rc = cc.main(["--strict", "--project-root", str(tmp_path)])
    assert rc == 0


# --- Token-budget guards -------------------------------------------------


def test_summary_silent_when_clean(tmp_path, capsys):
    """SessionStart hook uses --fix --summary. After auto-fixes the
    registry should be consistent and the banner stays silent."""
    registry = base_registry(tasks=[task("T1", "completed")])
    make_repo(tmp_path, registry, task_files={"E1/T1": {"id": "T1", "status": "completed"}})
    cc.main(["--fix", "--summary", "--project-root", str(tmp_path)])
    out = capsys.readouterr().out
    assert out == "" or out.strip() == ""


def test_summary_under_300_chars(tmp_path, capsys):
    registry = base_registry()
    make_repo(tmp_path, registry, task_files={
        f"E12/T{i}": {"id": f"T{i}", "status": "ready"} for i in range(900, 920)
    })
    cc.main(["--summary", "--project-root", str(tmp_path)])
    out = capsys.readouterr().out.strip()
    assert len(out) <= 300, f"summary too long: {len(out)} chars"
    assert "FORGE-CONSISTENCY" in out


# --- Performance --------------------------------------------------------


def test_perf_under_2s_on_500_tasks(tmp_path):
    """Strict-mode pass on a 500-task synthetic registry must stay under 2s."""
    tasks = [task(f"T{i}", "completed") for i in range(500)]
    epics = [epic("E1", "completed", tasks=[t["id"] for t in tasks])]
    registry = base_registry(tasks=tasks, epics=epics)
    file_specs = {f"E1/T{i}": {"id": f"T{i}", "status": "completed"} for i in range(500)}
    make_repo(tmp_path, registry, task_files=file_specs)
    start = time.perf_counter()
    cc.main(["--strict", "--project-root", str(tmp_path)])
    elapsed = time.perf_counter() - start
    assert elapsed < 2.0, f"check took {elapsed:.2f}s on 500-task registry (>2s budget)"


# --- Missing registry no-op --------------------------------------------


def test_missing_registry_is_noop(tmp_path, capsys):
    """New projects without a registry shouldn't crash the hook chain."""
    rc = cc.main(["--summary", "--project-root", str(tmp_path)])
    assert rc == 0
    assert capsys.readouterr().out.strip() == ""


# --- Filename regex: split-task suffixes are not treated as duplicates --


def test_split_task_suffix_not_duplicated_against_base_id(tmp_path):
    """Split-task files like T149a-* must NOT be misread as the base ID T149.

    The filename regex deliberately excludes suffixed forms (lookahead for
    `-` or `.` after the digits). This means a sibling T149a-split.md is
    silently ignored — neither flagged as a duplicate of T149 nor as an
    orphan. If a project actually wants to track split tasks, those go
    in the registry under their full ID (T149a) and need their own file
    naming the script does match.
    """
    registry = base_registry(tasks=[task("T149", "completed")])
    repo = make_repo(tmp_path, registry, task_files={
        "E1/T149": {"id": "T149", "status": "completed"},
    })
    suffixed = repo / "docs" / "epics" / "E1-fixture" / "tasks" / "T149a-split.md"
    suffixed.write_text("---\nid: T149a\nstatus: ready\n---\n# T149a\n")
    # No false drift #1 against T149 — split file silently ignored.
    rc = cc.main(["--strict", "--project-root", str(tmp_path)])
    assert rc == 0
    import io, contextlib
    buf = io.StringIO()
    with contextlib.redirect_stdout(buf):
        cc.main(["--json", "--project-root", str(tmp_path)])
    findings = json.loads(buf.getvalue())["findings"]
    file_orphans = [f for f in findings if f["cls"] == "file-not-in-registry"]
    assert file_orphans == []


# --- Drift #8: file-vs-registry-name -------------------------------------


def test_drift8_detects_name_mismatch(tmp_path):
    """File frontmatter `name:` differs from registry name -> auto-fix finding."""
    registry = base_registry(tasks=[task("T1", "ready", name="Registry Title")])
    repo = make_repo(tmp_path, registry, task_files={
        "E1/T1": {"id": "T1", "status": "ready", "name": "File Title"},
    })
    epics_dir = repo / "docs" / "epics"
    findings, _, _ = cc.run_all_checks(registry, epics_dir, lock_timeout=3600)
    name_findings = [f for f in findings if f.cls == cc.CLS_FILE_VS_REGISTRY_NAME]
    assert len(name_findings) == 1
    assert name_findings[0].severity == cc.SEV_AUTO
    assert name_findings[0].target == "T1"


def test_drift8_autofix_rewrites_file_to_registry_name(tmp_path):
    registry = base_registry(tasks=[task("T1", "ready", name="Registry Title")])
    repo = make_repo(tmp_path, registry, task_files={
        "E1/T1": {"id": "T1", "status": "ready", "name": "File Title"},
    })
    rc = cc.main(["--fix", "--project-root", str(repo)])
    assert rc == 0
    fm = next(repo.rglob("T1-fixture.md")).read_text()
    assert "name: Registry Title" in fm
    assert "name: File Title" not in fm


def test_drift8_strict_does_not_block_on_name_drift(tmp_path):
    """Anti-criterion ISC-A3: name drift alone is auto-fix, not blocking."""
    registry = base_registry(tasks=[task("T1", "ready", name="Registry Title")])
    repo = make_repo(tmp_path, registry, task_files={
        "E1/T1": {"id": "T1", "status": "ready", "name": "File Title"},
    })
    rc = cc.main(["--strict", "--project-root", str(repo)])
    assert rc == 0


def test_drift8_skips_when_file_has_no_name_field(tmp_path):
    """Files without a `name:` frontmatter field are silently skipped."""
    registry = base_registry(tasks=[task("T1", "ready", name="Registry Title")])
    repo = make_repo(tmp_path, registry, task_files={
        "E1/T1": {"id": "T1", "status": "ready"},  # no name in frontmatter
    })
    epics_dir = repo / "docs" / "epics"
    findings, _, _ = cc.run_all_checks(registry, epics_dir, lock_timeout=3600)
    name_findings = [f for f in findings if f.cls == cc.CLS_FILE_VS_REGISTRY_NAME]
    assert name_findings == []


def test_drift8_no_finding_when_names_match(tmp_path):
    registry = base_registry(tasks=[task("T1", "ready", name="Same Title")])
    repo = make_repo(tmp_path, registry, task_files={
        "E1/T1": {"id": "T1", "status": "ready", "name": "Same Title"},
    })
    epics_dir = repo / "docs" / "epics"
    findings, _, _ = cc.run_all_checks(registry, epics_dir, lock_timeout=3600)
    name_findings = [f for f in findings if f.cls == cc.CLS_FILE_VS_REGISTRY_NAME]
    assert name_findings == []


def test_yaml_unquote_scalar_reverses_encoder():
    # check_consistency.py no longer has its own _yaml_quote_if_needed /
    # _yaml_unquote_scalar (plan 007 consolidated them into registry_ops,
    # which _parse_frontmatter_name calls directly) — exercise the shared
    # implementation via cc.registry_ops.
    #
    # Encoder writes \" then \\ (in that order on encode); decoder must
    # reverse \" before \\ to land back on the original.
    quoted = cc.registry_ops._yaml_quote_if_needed('Refactor: split "routes" handler')
    assert quoted == '"Refactor: split \\"routes\\" handler"'
    assert cc.registry_ops._yaml_unquote_scalar(quoted) == 'Refactor: split "routes" handler'

    # Backslash-then-quote — the trickiest reversal order case.
    quoted = cc.registry_ops._yaml_quote_if_needed('weird \\" name')
    assert cc.registry_ops._yaml_unquote_scalar(quoted) == 'weird \\" name'

    # Plain unquoted scalars pass through untouched.
    assert cc.registry_ops._yaml_unquote_scalar('Plain Title') == 'Plain Title'

    # Single-quoted form (only produced by hand-edits) — '' → '
    assert cc.registry_ops._yaml_unquote_scalar("'it''s fine'") == "it's fine"


def test_drift8_stable_under_repeated_fix_for_quoted_names(tmp_path):
    # Regression: names containing `"` or `\` were re-flagged on every
    # consistency pass because the parser stripped quotes without reversing
    # the encoder's escapes. After one --fix the file is canonical and a
    # second run finds zero drift.
    quirky = 'Refactor: split "routes" handler'
    registry = base_registry(tasks=[task("T1", "ready", name=quirky)])
    # File starts with a stale unquoted name; first --fix rewrites it
    # using the encoder's quoted+escaped form.
    repo = make_repo(tmp_path, registry, task_files={
        "E1/T1": {"id": "T1", "status": "ready", "name": "Stale"},
    })
    rc = cc.main(["--fix", "--project-root", str(repo)])
    assert rc == 0

    # File now contains the encoder's quoted form. A second pass — the one
    # that used to re-fire drift #8 forever — must find nothing.
    findings, _, _ = cc.run_all_checks(
        json.loads((repo / "docs" / "tasks" / "registry.json").read_text()),
        repo / "docs" / "epics",
        lock_timeout=3600,
    )
    name_findings = [f for f in findings if f.cls == cc.CLS_FILE_VS_REGISTRY_NAME]
    assert name_findings == []


# --- Crash safety: atomic write must not truncate on mid-write failure --


def test_save_registry_atomic_on_write_failure(tmp_path, monkeypatch):
    """A crash mid-write (json.dump raising) must leave the previous
    registry file byte-identical, and must not leave a stray tmp file
    behind in the registry's directory.

    check_consistency.py no longer has its own save_registry (plan 007
    consolidated it into registry_ops.save_registry, which the checker's
    --fix path now calls directly) — this test exercises that shared
    implementation via the module the checker actually uses.
    """
    registry = base_registry(tasks=[task("T1", "completed")])
    registry_path = tmp_path / "registry.json"
    original_content = json.dumps(registry, indent=2, ensure_ascii=True) + "\n"
    registry_path.write_text(original_content, encoding="utf-8")

    def boom(*args, **kwargs):
        raise RuntimeError("simulated crash mid-write")

    monkeypatch.setattr(cc.registry_ops.json, "dump", boom)

    with pytest.raises(RuntimeError):
        cc.registry_ops.save_registry(registry_path, registry)

    # Original file survives untouched.
    assert registry_path.read_text(encoding="utf-8") == original_content
    assert json.loads(registry_path.read_text(encoding="utf-8")) == registry

    # No stray tmp file left behind.
    leftovers = list(tmp_path.glob(".registry-*.tmp"))
    assert leftovers == []
