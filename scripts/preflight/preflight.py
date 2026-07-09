"""Orchestrator: derive → generate → drift-check → execute → report.

Single entry point reused by `/preflight-ci`, the pre-push git hook, and
`/create-pr --preflight`. Exit codes:

    0 — all gating jobs green
    2 — drift detected (refuses to execute until --regenerate)
    3 — at least one gating job red
    4 — degraded (e.g. no workflows found, pr-review-toolkit absent on red)

Outputs JSON when --json is passed; otherwise human-readable.
"""

from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
import time
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any

# Run-as-script support: the pre-push hook invokes this file directly
# (python3 .../preflight.py), where relative imports fail. Prepend our
# own directory so sibling modules resolve under both forms.
sys.path.insert(0, str(Path(__file__).resolve().parent))

from script_generator import (  # noqa: E402
    compute_drift,
    generate_scripts,
    write_lockfile,
)
from workflow_parser import derive_gating_jobs, load_protection_required  # noqa: E402


DEFAULT_WORKFLOWS_DIR = Path(".github/workflows")
DEFAULT_OUT_DIR = Path(".forge/preflight")


@dataclass
class JobResult:
    name: str
    exit_code: int
    duration_seconds: float
    stdout_tail: str
    stderr_tail: str

    @property
    def passed(self) -> bool:
        return self.exit_code == 0


@dataclass
class PreflightReport:
    project_root: str
    workflows_dir: str
    out_dir: str
    drift_detected: bool
    drift_changed: list[str]
    drift_new: list[str]
    drift_removed: list[str]
    jobs_run: list[JobResult] = field(default_factory=list)
    skipped_reason: str | None = None

    @property
    def all_green(self) -> bool:
        return bool(self.jobs_run) and all(j.passed for j in self.jobs_run)

    def to_dict(self) -> dict[str, Any]:
        return {
            **{k: v for k, v in asdict(self).items() if k != "jobs_run"},
            "jobs_run": [asdict(j) for j in self.jobs_run],
            "all_green": self.all_green,
        }


def _tail(text: str, lines: int = 40) -> str:
    parts = text.splitlines()
    if len(parts) <= lines:
        return text
    return "\n".join(parts[-lines:])


def run_one_script(script: Path, cwd: Path) -> JobResult:
    start = time.monotonic()
    proc = subprocess.run(
        ["bash", str(script)],
        cwd=cwd,
        capture_output=True,
        text=True,
        env={**os.environ, "FORGE_PREFLIGHT": "1"},
    )
    return JobResult(
        name=script.stem,
        exit_code=proc.returncode,
        duration_seconds=round(time.monotonic() - start, 2),
        stdout_tail=_tail(proc.stdout),
        stderr_tail=_tail(proc.stderr),
    )


def run_preflight(
    project_root: Path,
    *,
    workflows_dir: Path | None = None,
    out_dir: Path | None = None,
    default_branch: str = "main",
    protection_mock: Path | None = None,
    regenerate: bool = False,
    only: list[str] | None = None,
    fail_fast: bool = True,
) -> PreflightReport:
    wf_dir = workflows_dir or (project_root / DEFAULT_WORKFLOWS_DIR)
    out = out_dir or (project_root / DEFAULT_OUT_DIR)

    report = PreflightReport(
        project_root=str(project_root),
        workflows_dir=str(wf_dir),
        out_dir=str(out),
        drift_detected=False,
        drift_changed=[],
        drift_new=[],
        drift_removed=[],
    )

    if not wf_dir.exists():
        report.skipped_reason = f"no workflows directory at {wf_dir}"
        return report

    drift = compute_drift(wf_dir, out / "drift.lock")
    if drift.has_drift and not regenerate:
        report.drift_detected = True
        report.drift_changed = drift.changed
        report.drift_new = drift.new
        report.drift_removed = drift.removed
        return report

    required = None
    if protection_mock and protection_mock.exists():
        required = load_protection_required(protection_mock)

    jobs = derive_gating_jobs(wf_dir, default_branch, required)
    if not jobs:
        report.skipped_reason = "no gating jobs derived from workflows"
        return report

    if regenerate or not (out / "drift.lock").exists():
        generate_scripts(jobs, out, project_root=project_root)
        write_lockfile(wf_dir, out / "drift.lock")

    selected = jobs if not only else [j for j in jobs if j.name in set(only)]
    for job in selected:
        script = out / f"{job.name}.sh"
        if not script.exists():
            generate_scripts([job], out, project_root=project_root)
        result = run_one_script(script, cwd=project_root)
        report.jobs_run.append(result)
        if fail_fast and not result.passed:
            break

    return report


def format_human(report: PreflightReport) -> str:
    lines: list[str] = []
    if report.skipped_reason:
        lines.append(f"⏭️  preflight skipped: {report.skipped_reason}")
        return "\n".join(lines)
    if report.drift_detected:
        lines.append("⚠️  Preflight drift detected — local scripts are stale")
        if report.drift_changed:
            lines.append(f"   changed:  {', '.join(report.drift_changed)}")
        if report.drift_new:
            lines.append(f"   new:      {', '.join(report.drift_new)}")
        if report.drift_removed:
            lines.append(f"   removed:  {', '.join(report.drift_removed)}")
        lines.append("   run: /preflight-ci --regenerate")
        return "\n".join(lines)
    for j in report.jobs_run:
        mark = "✅" if j.passed else "❌"
        lines.append(f"{mark} {j.name}  ({j.duration_seconds}s)")
        if not j.passed:
            lines.append("   --- stderr tail ---")
            lines.append("   " + j.stderr_tail.replace("\n", "\n   "))
    if report.all_green:
        lines.append("")
        lines.append("✓ all gating jobs passed — safe to push")
    elif report.jobs_run:
        lines.append("")
        lines.append("✗ preflight failed — fix above before pushing")
        lines.append("  failure routing: see skills/_shared/ci-failure-classifier.md")
    return "\n".join(lines)


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(prog="preflight")
    p.add_argument("--project-root", type=Path, default=Path.cwd())
    p.add_argument("--workflows-dir", type=Path)
    p.add_argument("--out", type=Path, dest="out_dir")
    p.add_argument("--default-branch", default="main")
    p.add_argument("--protection-mock", type=Path)
    p.add_argument("--regenerate", action="store_true", help="Re-derive + re-write local scripts")
    p.add_argument("--only", help="Comma-separated job names to run")
    p.add_argument("--keep-going", action="store_true", help="Don't stop at first failure")
    p.add_argument("--quick", action="store_true", help="Pre-push hook mode — terse output")
    p.add_argument("--json", action="store_true")
    args = p.parse_args(argv)

    only = [s.strip() for s in args.only.split(",")] if args.only else None

    report = run_preflight(
        args.project_root,
        workflows_dir=args.workflows_dir,
        out_dir=args.out_dir,
        default_branch=args.default_branch,
        protection_mock=args.protection_mock,
        regenerate=args.regenerate,
        only=only,
        fail_fast=not args.keep_going,
    )

    if args.json:
        print(json.dumps(report.to_dict(), indent=2))
    else:
        text = format_human(report)
        if args.quick and report.all_green:
            print(f"✓ preflight green ({len(report.jobs_run)} jobs)")
        else:
            print(text)

    if report.skipped_reason:
        return 4
    if report.drift_detected:
        return 2
    if not report.all_green and report.jobs_run:
        return 3
    return 0


if __name__ == "__main__":
    sys.exit(main())
