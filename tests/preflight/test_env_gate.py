"""T077 — `.env` discovery is gated on the source-block being load-bearing.

Ported upstream 2026-09-07 from a consumer that had been carrying it as a
project-local patch and re-applying it by hand after every refresh (three
times: v4.2.0, v4.4.1, v4.5.1). Framework code cannot be patched in a
consumer -- refresh always wins -- so the gate has to live here.

The generator sourced every discovered `.env` into every generated job
unconditionally. `set -a` exports into the process environment, so the real
consumers were npm lifecycle scripts and bundler plugins, not the named steps:
an ungated root `.env` handed JWT_SECRET, SERVICE_ROLE_KEY, POSTGRES_PASSWORD
and VAULT_ENC_KEY to every step of every job, whether or not anything asked.

The gate is on *discovery*, not on the mechanism. Two behaviours have to hold
together, and they fail in opposite directions:

  * ambient discovery OFF when nothing reads it -- the exposure this closes;
  * an explicit `[tool.forge.preflight] env_files` STILL honoured -- otherwise
    the fix silently breaks the one consumer who read the docs and configured
    a layer on purpose.

A test for either alone passes while the other regresses, which is exactly how
`explicit_only` would get collapsed back into a plain call by a later
refactor. The last test pins the CALL SITE for the same reason: in the
consumer, the parameter and the argument were reverted independently, and a
unit test of `discover_env_files` alone stayed green while the generator had
gone back to sourcing everything.
"""
from __future__ import annotations

import sys
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO_ROOT / "scripts" / "preflight"))

from compose_introspector import discover_env_files  # noqa: E402
from script_generator import generate_scripts  # noqa: E402
from workflow_parser import Job, Step  # noqa: E402


@pytest.fixture
def project(tmp_path: Path) -> Path:
    """A synthetic project root with a root .env and nothing else."""
    (tmp_path / ".env").write_text("SECRET_DB_URL=postgresql://user:pw@host/db\n")
    return tmp_path


def test_discovers_root_dotenv_when_the_source_block_is_load_bearing(project: Path):
    """Unchanged behaviour: password-refs were emitted, so the layer is what
    makes them resolve. Guards against over-correcting into never sourcing."""
    assert discover_env_files(project, explicit_only=False) == [
        (project / ".env").resolve()
    ]


def test_does_not_discover_root_dotenv_when_nothing_reads_it(project: Path):
    """The defect. No password-refs emitted -> no ambient layer, even though a
    root .env exists and the old code would have found it."""
    assert discover_env_files(project, explicit_only=True) == []


def test_explicit_pyproject_override_survives_the_gate(project: Path):
    """The half a comment-only fix would have missed. An operator who named the
    layer asked for it; the gate is about ambient discovery, not about refusing
    a configured one."""
    named = project / "secrets" / "ci.env"
    named.parent.mkdir()
    named.write_text("CI_ONLY=1\n")
    (project / "pyproject.toml").write_text(
        '[tool.forge.preflight]\nenv_files = ["secrets/ci.env"]\n'
    )

    assert discover_env_files(project, explicit_only=True) == [named.resolve()]
    # ...and the override still wins over canonical discovery in the ungated
    # path, i.e. the gate did not reorder precedence.
    assert discover_env_files(project, explicit_only=False) == [named.resolve()]


def test_gate_defaults_to_discovering(project: Path):
    """`explicit_only` defaults False, so a caller that never heard of this
    parameter keeps the pre-T077 behaviour. The gate is opt-in at the call
    site, which is where the flag that justifies it is computed."""
    assert discover_env_files(project) == [(project / ".env").resolve()]


def test_generator_does_not_source_ambient_dotenv_when_no_password_refs(project: Path):
    """The call site, end to end. A job with no password env-refs must produce
    a script with no source-block at all -- this is the assertion that stayed
    absent in the consumer, letting the argument be dropped while the
    parameter survived."""
    job = Job(
        name="build",
        file=".github/workflows/ci.yml",
        runs_on="ubuntu-latest",
        steps=[Step(name="build", run="npm run build")],
    )
    out = project / "out"
    written = generate_scripts([job], out, project_root=project)
    script = written[0].read_text(encoding="utf-8")
    assert "_env_layer" not in script, (
        "generated script sources an ambient .env although nothing reads it:\n"
        + script
    )
    assert ".env" not in script
