"""Parse GitHub Actions workflow files and derive the gating job set.

Public entry points:
    derive_gating_jobs(workflows_dir, default_branch, protection_required=None) -> list[Job]
    Job: TypedDict { name, file, env, steps, runs_on }

CLI:
    python3 -m scripts.preflight.workflow_parser <workflows-dir> [--default-branch main]
                                                  [--protection-mock PATH]
                                                  [--emit-jobs] [--json]

When --protection-mock is given, the JSON file is read in place of calling
`gh api ... /protection` (used by tests and offline runs). The mock format
mirrors the GitHub API response: an object with a 'required_status_checks.contexts'
list of required check names.
"""

from __future__ import annotations

import argparse
import json
import sys
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import yaml


@dataclass
class Step:
    """One workflow step. We only model `run:` and `uses:` here."""

    run: str | None = None
    uses: str | None = None
    name: str | None = None
    env: dict[str, str] = field(default_factory=dict)

    @classmethod
    def from_dict(cls, raw: dict[str, Any]) -> "Step":
        run = raw.get("run")
        uses = raw.get("uses")
        name = raw.get("name")
        # YAML 1.1 deserializes `run: true` / `run: false` as Python bool —
        # coerce scalar non-strings to lowercase string so generated bash is valid.
        if run is not None and not isinstance(run, str):
            run = "true" if run is True else "false" if run is False else str(run)
        if uses is not None and not isinstance(uses, str):
            uses = str(uses)
        if name is not None and not isinstance(name, str):
            name = str(name)
        return cls(run=run, uses=uses, name=name, env=dict(raw.get("env") or {}))


@dataclass
class Job:
    name: str
    file: str
    runs_on: str
    env: dict[str, str] = field(default_factory=dict)
    steps: list[Step] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return {
            "name": self.name,
            "file": self.file,
            "runs_on": self.runs_on,
            "env": self.env,
            "steps": [
                {"name": s.name, "run": s.run, "uses": s.uses, "env": s.env}
                for s in self.steps
            ],
        }


def _trigger_targets_branch(trigger: Any, default_branch: str) -> bool:
    """Return True if `on:` declares a pull_request trigger that hits default_branch.

    Accepts string form (`on: pull_request`), list form, dict form with explicit
    branch filters. Default-branch filtering is conservative: an explicit
    branches filter that excludes the default branch returns False; absence of
    a filter is treated as "all branches" → True.
    """
    if trigger is None:
        return False
    if isinstance(trigger, str):
        return trigger == "pull_request"
    if isinstance(trigger, list):
        return "pull_request" in trigger
    if isinstance(trigger, dict):
        pr = trigger.get("pull_request")
        if pr is None:
            return False
        if pr is True or pr == {} or pr is None:
            return True
        if isinstance(pr, dict):
            branches = pr.get("branches") or pr.get("branches-ignore")
            if branches is None:
                return True
            if isinstance(branches, list):
                key = "branches" if "branches" in pr else "branches-ignore"
                hits = any(_branch_pattern_matches(b, default_branch) for b in branches)
                return hits if key == "branches" else not hits
        return False
    return False


def _branch_pattern_matches(pattern: str, branch: str) -> bool:
    """Very small glob-equivalence: '*' matches anything, exact match otherwise."""
    if pattern in ("*", "**"):
        return True
    return pattern == branch


def parse_workflow_file(path: Path) -> list[Job]:
    """Load one workflow YAML and return its job list.

    Returns [] if the file is unparseable or has no jobs.
    """
    try:
        raw = yaml.safe_load(path.read_text())
    except yaml.YAMLError:
        return []
    if not isinstance(raw, dict):
        return []

    workflow_env = dict(raw.get("env") or {})
    jobs_raw = raw.get("jobs") or {}
    out: list[Job] = []
    for name, body in jobs_raw.items():
        if not isinstance(body, dict):
            continue
        steps_raw = body.get("steps") or []
        steps = [Step.from_dict(s) for s in steps_raw if isinstance(s, dict)]
        merged_env = dict(workflow_env)
        merged_env.update(body.get("env") or {})
        out.append(
            Job(
                name=name,
                file=str(path),
                runs_on=str(body.get("runs-on") or ""),
                env=merged_env,
                steps=steps,
            )
        )
    return out


def derive_gating_jobs(
    workflows_dir: Path,
    default_branch: str = "main",
    protection_required: list[str] | None = None,
) -> list[Job]:
    """Return jobs that gate PRs to default_branch.

    Algorithm:
      1. Read every *.yml / *.yaml under workflows_dir.
      2. Keep workflow files whose `on:` declares pull_request targeting default_branch.
      3. Collect all jobs from those files.
      4. If protection_required is provided (not None), narrow to jobs whose
         name appears in that list. If None, return the full set (default
         behavior — works without any branch-protection config).
    """
    out: list[Job] = []
    if not workflows_dir.exists():
        return out

    files = sorted(
        list(workflows_dir.glob("*.yml")) + list(workflows_dir.glob("*.yaml"))
    )
    for f in files:
        try:
            raw = yaml.safe_load(f.read_text())
        except yaml.YAMLError:
            continue
        if not isinstance(raw, dict):
            continue
        trigger = raw.get("on") or raw.get(True)  # YAML 'on' can deserialize to True
        if not _trigger_targets_branch(trigger, default_branch):
            continue
        out.extend(parse_workflow_file(f))

    if protection_required is not None:
        wanted = set(protection_required)
        out = [j for j in out if j.name in wanted]
    return out


def load_protection_required(path: Path) -> list[str]:
    """Read a mocked branch-protection JSON file and return the required check names.

    Format matches `gh api repos/:owner/:repo/branches/:branch/protection`:
        { "required_status_checks": { "contexts": ["typecheck", "test"] } }
    """
    raw = json.loads(path.read_text())
    rsc = (raw.get("required_status_checks") or {})
    return list(rsc.get("contexts") or [])


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(prog="workflow_parser")
    p.add_argument("workflows_dir", type=Path, help="Path to .github/workflows/ (or fixture dir)")
    p.add_argument("--default-branch", default="main")
    p.add_argument(
        "--protection-mock",
        type=Path,
        help="JSON file mocking gh branch-protection API output",
    )
    p.add_argument("--emit-jobs", action="store_true", help="Emit derived job list to stdout")
    p.add_argument("--json", action="store_true", help="JSON output (default: text)")
    args = p.parse_args(argv)

    required = None
    if args.protection_mock and args.protection_mock.exists():
        required = load_protection_required(args.protection_mock)

    jobs = derive_gating_jobs(args.workflows_dir, args.default_branch, required)

    if args.emit_jobs or args.json:
        payload = [j.to_dict() for j in jobs]
        if args.json:
            print(json.dumps(payload, indent=2))
        else:
            print(json.dumps({"jobs": payload}, indent=2))
        return 0

    for j in jobs:
        print(f"{j.name}\t{j.file}\t({len(j.steps)} steps)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
