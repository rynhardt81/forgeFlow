"""Orchestrator: derive → generate → drift-check → execute → report.

Single entry point reused by `/preflight-ci`, the pre-push git hook, and
`/create-pr --preflight`. Exit codes:

    0 — all gating jobs green
    2 — drift detected (refuses to execute until --regenerate)
    3 — at least one gating job red
    4 — degraded (e.g. no workflows found, pr-review-toolkit absent on red)
    5 — nothing failed, but a job self-skipped: green is NOT the whole story,
        that job's coverage did not run (see JOB_SKIP_MARKER)

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

from hook_installer import refresh_if_stale  # noqa: E402
from script_generator import (  # noqa: E402
    JOB_SKIP_MARKER,
    compute_drift,
    generate_scripts,
    write_lockfile,
)
from workflow_parser import derive_gating_jobs, load_protection_required  # noqa: E402


DEFAULT_WORKFLOWS_DIR = Path(".github/workflows")
DEFAULT_OUT_DIR = Path(".forge/preflight")


def _extract_skip_reason(stderr: str) -> str | None:
    """First `JOB_SKIP_MARKER` line in stderr, marker stripped, else None.

    Takes FULL stderr, never `stderr_tail` — the tail keeps only the last 40
    lines, so deriving this from the tail would lose the marker for any job that
    self-skips and then emits more than 40 further stderr lines, silently
    restoring the plain-green bug. The one built-in emitter exits immediately so
    its marker is always last, but `JOB_SKIP_MARKER` is a published contract and
    the next emitter need not.
    """
    for line in stderr.splitlines():
        stripped = line.strip()
        if stripped.startswith(JOB_SKIP_MARKER):
            return stripped[len(JOB_SKIP_MARKER):].strip()
    return None


@dataclass
class JobResult:
    name: str
    exit_code: int
    duration_seconds: float
    stdout_tail: str
    stderr_tail: str
    # Set only for a job that exited 0 after announcing JOB_SKIP_MARKER. A
    # failing job is reported as a failure regardless of what its stderr says,
    # so this stays None there — failure is strictly louder than skip.
    skip_reason: str | None = None

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

    @property
    def jobs_skipped(self) -> list[JobResult]:
        """Jobs that exited 0 after announcing JOB_SKIP_MARKER on stderr.

        The only emitter today is the pg-reachability guard, which exits before
        any step runs — so these jobs contributed zero coverage, which is what
        the summary tells the user. A future guard that skipped only *part* of a
        job would be over-reported here as a whole-job skip; that direction is
        deliberate (over-warn, never under-warn).
        """
        return [j for j in self.jobs_run if j.skip_reason is not None]

    def to_dict(self) -> dict[str, Any]:
        return {
            **{k: v for k, v in asdict(self).items() if k != "jobs_run"},
            "jobs_run": [asdict(j) for j in self.jobs_run],
            "all_green": self.all_green,
            "jobs_skipped": [j.name for j in self.jobs_skipped],
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
        # A job's output is arbitrary bytes from arbitrary tools, and at least
        # one (gitleaks) truncates a finding mid-character and emits invalid
        # UTF-8. Without this the decode raises inside subprocess.run and takes
        # down the whole preflight run with a traceback — turning "one job is
        # red" into "the runner crashed", which is strictly less useful.
        errors="replace",
        env={**os.environ, "FORGE_PREFLIGHT": "1"},
    )
    return JobResult(
        name=script.stem,
        exit_code=proc.returncode,
        duration_seconds=round(time.monotonic() - start, 2),
        stdout_tail=_tail(proc.stdout),
        stderr_tail=_tail(proc.stderr),
        # Derived from FULL stderr, before truncation — see _extract_skip_reason.
        skip_reason=(
            _extract_skip_reason(proc.stderr) if proc.returncode == 0 else None
        ),
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

    # Regenerate on an explicit request, a missing lockfile, or a generator
    # contract bump. The last one matters most: scripts built against an older
    # contract still *run*, so without this the runner silently misreads them.
    if regenerate or not (out / "drift.lock").exists() or drift.contract_stale:
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
        if j.skip_reason is not None:
            lines.append(f"⏭️  {j.name}  ({j.duration_seconds}s) — SKIPPED")
            lines.append(f"   {j.skip_reason}")
            continue
        mark = "✅" if j.passed else "❌"
        lines.append(f"{mark} {j.name}  ({j.duration_seconds}s)")
        if not j.passed:
            lines.append("   --- stderr tail ---")
            lines.append("   " + j.stderr_tail.replace("\n", "\n   "))
    if report.all_green:
        lines.append("")
        skipped = report.jobs_skipped
        if skipped:
            names = ", ".join(j.name for j in skipped)
            lines.append(
                f"✓ no gating job failed — but {len(skipped)} SKIPPED ({names});"
                " that coverage did NOT run"
            )
        else:
            lines.append("✓ all gating jobs passed — safe to push")
    elif report.jobs_run:
        lines.append("")
        lines.append("✗ preflight failed — fix above before pushing")
        lines.append("  failure routing: see skills/_shared/ci-failure-classifier.md")
    return "\n".join(lines)


def exit_code_for(report: PreflightReport) -> int:
    """Map a report to the process exit code.

    Load-bearing: the pre-push hook and `/create-pr --preflight` read ONLY this,
    never the printed summary. Kept a pure function so the mapping is directly
    testable rather than buried in main().
    """
    if report.skipped_reason:
        return 4
    if report.drift_detected:
        return 2
    if not report.all_green and report.jobs_run:
        return 3
    # Nothing failed, but a job self-skipped, so coverage is incomplete. Distinct
    # from 0 because the machine consumers read only this value — collapsing it
    # into 0 leaves them seeing the plain green this feature exists to remove.
    # Deliberately NOT folded into 3 either: the pre-push hook must keep allowing
    # the push (T600 — an absent local stack must not block one), so a skip needs
    # its own code the hook can wave through while a PR gate blocks on it.
    if report.jobs_skipped:
        return 5
    return 0


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

    # The installed pre-push hook is a COPY of the template, so nothing else
    # updates it when the template's contract changes. Heal it here — this is the
    # one code path every hook invocation reaches. `hook_was_stale` matters for
    # the exit code below: if we just refreshed, the hook running RIGHT NOW is
    # still the old one, which blocks on any non-zero.
    try:
        hook_was_stale = refresh_if_stale(args.project_root)
    except OSError:
        # Read-only .git, permissions, exotic worktree layout — a hook we could
        # not refresh must never take down the preflight run itself.
        hook_was_stale = False

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
            skipped = report.jobs_skipped
            if skipped:
                # Deliberately NOT "✓ … green". This line scrolls past during a
                # push; a green-shaped signal here is the bug this reports on.
                names = ", ".join(j.name for j in skipped)
                print(
                    f"⚠️  preflight: {len(skipped)} job(s) DID NOT RUN ({names}); "
                    f"{len(report.jobs_run) - len(skipped)} passed"
                )
            else:
                print(f"✓ preflight green ({len(report.jobs_run)} jobs)")
        else:
            print(text)

    code = exit_code_for(report)
    if code == 5 and hook_was_stale:
        # Backward compatibility, exactly once. The hook executing this run is
        # the pre-refresh copy, whose catch-all branch blocks the push on ANY
        # non-zero — so returning 5 here would break the documented "a skip never
        # blocks a push" contract for the very users being migrated. The refresh
        # above already landed, so the next push gets the real 5.
        print(
            "preflight: pre-push hook was out of date and has been refreshed; "
            "treating this run's skip as non-blocking. Next push reports it "
            "properly.",
            file=sys.stderr,
        )
        return 0
    return code


if __name__ == "__main__":
    sys.exit(main())
