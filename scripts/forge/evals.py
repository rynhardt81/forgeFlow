#!/usr/bin/env python3
"""Config-regression evals — replay recorded tasks when the config changes.

A skill, rule, hook or CLAUDE.md edit is a behaviour change with no test. The
wiring suite proves the framework is wired; it cannot prove that an edit to
/fix-bug dropped the reproduce-first gate. These evals do.

COST. The `run` subcommand spawns `claude`. On a subscription account a loop of
those once cost R9,000, so this module refuses to run unless billing is
explicitly declared as API-key, refuses when it detects a hook or agent-loop
context, and is never invoked by anything under hooks/. The `check` subcommand
touches no model and is free — it applies a case's assertions to a transcript
you already have, which is how the checks themselves are tested.
"""

from __future__ import annotations

import argparse
import json
import os
import re
import subprocess
import sys
from dataclasses import dataclass, field
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
CASES_DIR = REPO_ROOT / "tests" / "evals" / "cases"

BILLING_ENV = "FORGE_EVALS_BILLING"
BILLING_REQUIRED = "api"

# Env vars the harness sets inside hooks and agent loops. Running there is the
# failure mode this guard exists for: a hook that spawns claude runs on every
# tool call, and nobody notices until the bill.
FORBIDDEN_CONTEXT = (
    "CLAUDE_HOOK_EVENT", "CLAUDE_HOOK_NAME", "CLAUDE_TOOL_NAME",
    "FORGE_LOOP_ACTIVE", "CLAUDE_AGENT_ID",
)


class Refused(RuntimeError):
    """The runner declined to spend money. Never caught and retried."""


@dataclass
class Check:
    kind: str
    reason: str
    pattern: str | None = None
    cmd: str | None = None
    path: str | None = None


@dataclass
class Case:
    id: str
    prompt: str
    checks: list[Check]
    touches: list[str] = field(default_factory=list)


def _parse_case(text: str, source: Path) -> Case:
    """Minimal YAML subset: no dependency, and the schema is fixed.

    Deliberately not pyyaml — this runs in CI on a bare checkout, and a parser
    dependency for four keys is the kind of thing rules/dependencies.md exists
    to refuse.
    """
    data: dict = {}
    checks: list[dict] = []
    current: dict | None = None
    in_checks = False
    for raw in text.splitlines():
        if not raw.strip() or raw.lstrip().startswith("#"):
            continue
        if raw.startswith("checks:"):
            in_checks = True
            continue
        if in_checks:
            stripped = raw.strip()
            if stripped.startswith("- "):
                current = {}
                checks.append(current)
                stripped = stripped[2:]
            if current is not None and ":" in stripped:
                k, v = stripped.split(":", 1)
                current[k.strip()] = _scalar(v.strip())
            continue
        if ":" in raw:
            k, v = raw.split(":", 1)
            data[k.strip()] = _scalar(v.strip())

    missing = [k for k in ("id", "prompt") if not data.get(k)]
    if missing or not checks:
        raise ValueError(f"{source}: missing {missing or 'checks'}")
    for c in checks:
        if not c.get("reason"):
            raise ValueError(
                f"{source}: check {c} has no `reason` — a red eval that cannot "
                "say which gate was dropped is one nobody can act on"
            )
    touches = data.get("touches") or []
    if isinstance(touches, str):
        touches = [t.strip() for t in touches.strip("[]").split(",") if t.strip()]
    return Case(id=data["id"], prompt=data["prompt"], touches=touches,
                checks=[Check(**c) for c in checks])


def _scalar(v: str):
    v = v.strip()
    if len(v) >= 2 and v[0] == v[-1] and v[0] in "\"'":
        return v[1:-1]
    return v


def load_cases() -> list[Case]:
    return [_parse_case(f.read_text(encoding="utf-8"), f)
            for f in sorted(CASES_DIR.glob("*.yaml"))]


def apply_checks(case: Case, transcript: str, workspace: Path) -> list[dict]:
    """Evaluate a case's checks. Pure and free — no model involved."""
    results = []
    for c in case.checks:
        if c.kind == "transcript_matches":
            ok = bool(re.search(c.pattern or "", transcript))
        elif c.kind == "transcript_absent":
            ok = not re.search(c.pattern or "", transcript)
        elif c.kind == "command_succeeds":
            ok = subprocess.run(c.cmd or "", shell=True, cwd=workspace,
                                capture_output=True).returncode == 0
        elif c.kind == "file_exists":
            ok = (workspace / (c.path or "")).exists()
        else:
            raise ValueError(f"{case.id}: unknown check kind {c.kind!r}")
        results.append({"kind": c.kind, "reason": c.reason, "passed": ok})
    return results


def guard_billing(env: dict | None = None) -> None:
    """Refuse to spend money implicitly. Raises rather than returning a flag."""
    env = os.environ if env is None else env
    declared = env.get(BILLING_ENV)
    if declared != BILLING_REQUIRED:
        raise Refused(
            f"{BILLING_ENV} must be set to {BILLING_REQUIRED!r} before this runner "
            f"will start (got {declared!r}).\n"
            "It spawns `claude` once per eval. On a subscription account that "
            "billing path is for interactive use only — a loop of these once cost "
            "R9,000. Use an API key with a spend cap, then set the variable."
        )
    hit = [k for k in FORBIDDEN_CONTEXT if env.get(k)]
    if hit:
        raise Refused(
            f"refusing to run: hook or agent-loop context detected ({', '.join(hit)}). "
            "Evals are manual or CI-only. Nothing under hooks/ may invoke this."
        )


def run_case(case: Case, workspace: Path, model: str | None) -> dict:
    cmd = ["claude", "-p", case.prompt]
    if model:
        cmd += ["--model", model]
    proc = subprocess.run(cmd, cwd=workspace, capture_output=True, text=True,
                          timeout=900)
    transcript = proc.stdout + proc.stderr
    checks = apply_checks(case, transcript, workspace)
    return {"id": case.id, "passed": all(c["passed"] for c in checks),
            "checks": checks, "transcript_bytes": len(transcript)}


def _report(results: list[dict], threshold: float) -> int:
    passed = sum(1 for r in results if r["passed"])
    total = len(results)
    rate = passed / total if total else 0.0
    for r in results:
        print(f"{'PASS' if r['passed'] else 'FAIL'}  {r['id']}")
        for c in r["checks"]:
            if not c["passed"]:
                print(f"        dropped gate: {c['reason']}")
    print(f"\n{passed}/{total} passed ({rate:.0%}); threshold {threshold:.0%}")
    return 0 if rate >= threshold else 1


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(prog="evals", description=__doc__)
    sub = p.add_subparsers(dest="cmd", required=True)

    r = sub.add_parser("run", help="run evals against the current config (SPENDS MONEY)")
    r.add_argument("--id", help="run one case")
    r.add_argument("--workspace", type=Path, default=REPO_ROOT)
    r.add_argument("--model", default=None)
    r.add_argument("--threshold", type=float, default=1.0)
    r.add_argument("--json", action="store_true")

    c = sub.add_parser("check", help="apply a case's checks to a transcript (free)")
    c.add_argument("--id", required=True)
    c.add_argument("--transcript", type=Path, required=True)
    c.add_argument("--workspace", type=Path, default=REPO_ROOT)

    sub.add_parser("list", help="list cases")
    a = p.parse_args(argv)

    cases = load_cases()
    if a.cmd == "list":
        for case in cases:
            print(f"{case.id:<40} {len(case.checks)} check(s)  guards: "
                  f"{', '.join(case.touches) or '(unscoped)'}")
        return 0

    if a.cmd == "check":
        case = next((c for c in cases if c.id == a.id), None)
        if not case:
            print(f"no such case: {a.id}", file=sys.stderr)
            return 2
        results = [{"id": case.id,
                    "checks": apply_checks(case, a.transcript.read_text(), a.workspace)}]
        results[0]["passed"] = all(c["passed"] for c in results[0]["checks"])
        return _report(results, 1.0)

    # run
    try:
        guard_billing()
    except Refused as e:
        print(f"REFUSED: {e}", file=sys.stderr)
        return 2
    selected = [c for c in cases if not a.id or c.id == a.id]
    results = [run_case(c, a.workspace, a.model) for c in selected]
    if a.json:
        print(json.dumps(results, indent=2))
        return 0
    return _report(results, a.threshold)


if __name__ == "__main__":
    sys.exit(main())
