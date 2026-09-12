"""T917: the eval runner spawns `claude`, so nothing may invoke it implicitly.

A loop of `claude` subprocesses on subscription billing once cost R9,000. This is
the test to keep if every other eval test is thrown away: it does not check that
the evals are good, it checks that they cannot run behind your back.
"""

from __future__ import annotations

import re
import subprocess
import sys
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[2]
RUNNER = REPO_ROOT / "scripts" / "forge" / "evals.py"
sys.path.insert(0, str(RUNNER.parent))


def test_no_hook_invokes_the_eval_runner():
    offenders = [
        str(f.relative_to(REPO_ROOT))
        for f in (REPO_ROOT / "hooks").rglob("*")
        if f.is_file() and f.suffix in {".py", ".json", ".sh"}
        and "evals" in f.read_text(errors="replace")
    ]
    assert not offenders, (
        f"hooks fire on every tool call; these reference the eval runner: {offenders}"
    )


def test_no_hook_spawns_claude_at_all():
    """The framework's own standing rule, enforced rather than asserted."""
    offenders = []
    for f in (REPO_ROOT / "hooks").rglob("*"):
        if not f.is_file() or f.suffix not in {".py", ".json", ".sh"}:
            continue
        text = f.read_text(errors="replace")
        if re.search(r"""subprocess\.[a-z_]+\(\s*\[?\s*["']claude["']""", text):
            offenders.append(str(f.relative_to(REPO_ROOT)))
    assert not offenders, f"no hook may spawn an LLM subprocess: {offenders}"


def test_runner_refuses_without_explicit_api_billing():
    r = subprocess.run(
        [sys.executable, str(RUNNER), "run"],
        capture_output=True, text=True, env={"PATH": "/usr/bin:/bin"},
    )
    assert r.returncode == 2, "must refuse, not proceed"
    assert "FORGE_EVALS_BILLING" in r.stderr


@pytest.mark.parametrize(
    "var", ["CLAUDE_HOOK_EVENT", "CLAUDE_TOOL_NAME", "FORGE_LOOP_ACTIVE", "CLAUDE_AGENT_ID"]
)
def test_runner_refuses_inside_a_hook_or_loop_even_with_billing_declared(var):
    """Declaring API billing must not be a way to smuggle it into a loop."""
    import evals
    with pytest.raises(evals.Refused, match="hook or agent-loop"):
        evals.guard_billing({"FORGE_EVALS_BILLING": "api", var: "1"})


def test_check_subcommand_costs_nothing():
    """`check` must never reach guard_billing — it is the free path, and if it
    ever required billing the checks could not be tested."""
    import evals
    src = Path(evals.__file__).read_text()
    check_block = src[src.index('if a.cmd == "check"'):src.index("    # run")]
    assert "guard_billing" not in check_block
    assert "subprocess" not in check_block


def test_every_case_names_the_gate_it_guards():
    import evals
    for case in evals.load_cases():
        assert case.touches, f"{case.id} guards no config file"
        for c in case.checks:
            assert c.reason and len(c.reason) > 15, f"{case.id}: weak reason {c.reason!r}"


def test_dropped_gate_produces_a_red_run():
    """The acceptance criterion, proved offline against a recorded transcript."""
    import evals
    case = next(c for c in evals.load_cases() if c.id == "fix-bug-reproduces-first")
    fixtures = REPO_ROOT / "tests" / "evals" / "fixtures"
    healthy = evals.apply_checks(case, (fixtures / "fix-bug-healthy.txt").read_text(), REPO_ROOT)
    dropped = evals.apply_checks(case, (fixtures / "fix-bug-gate-dropped.txt").read_text(), REPO_ROOT)
    assert all(c["passed"] for c in healthy), "a compliant run must be green"
    assert not any(c["passed"] for c in dropped), "a run that skipped the gates must be red"


def test_patterns_are_raw_not_double_escaped():
    """A doubled backslash never matches, which reads as a pass on an absent
    check — the checks would fail open and nobody would know."""
    bad = []
    for f in sorted((REPO_ROOT / "tests" / "evals" / "cases").glob("*.yaml")):
        for i, line in enumerate(f.read_text().splitlines(), 1):
            if "pattern:" in line and "\\\\" in line:
                bad.append(f"{f.name}:{i}")
    assert not bad, f"double-escaped regex, will silently never match: {bad}"
