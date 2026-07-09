"""Manage the framework-owned `.forge/venv/` Python virtual environment.

The preflight pipeline (`workflow_parser.py`, `script_generator.py`,
`preflight.py`) depends on PyYAML to read GitHub Actions workflow files.
That dependency is the framework's — not the consumer's — so the framework
owns the install path. We create a dedicated venv under the consumer's
project root and install PyYAML there. The pre-push hook resolves to this
venv's Python so the framework's preflight scripts always have their deps.

Layout (consumer project):

    <project>/
    └── .forge/
        ├── preflight/        # generated scripts (existing)
        ├── cache/            # dashboard caches (existing)
        └── venv/             # NEW — framework-owned Python venv
            ├── bin/python
            └── lib/python<X.Y>/site-packages/yaml/

Lifecycle:

  * `forge preflight enable-git-hook` calls `ensure_venv()` which is
    idempotent — present-and-healthy is a no-op.
  * `forge preflight enable-git-hook --force` recreates the venv from
    scratch (use after a Python version upgrade or to recover from
    breakage).
  * Consumers can `rm -rf .forge/venv` and re-enable the hook to rebuild.
  * The venv is gitignored — per-machine, not committed.

Public API:
    ensure_venv(project_root: Path, *, force: bool = False) -> EnsureResult

The function never raises on network/install failure — degraded results
let the caller emit a clear warning while keeping the hook installable.
"""

from __future__ import annotations

import shutil
import subprocess
import sys
import venv
from dataclasses import dataclass
from pathlib import Path

VENV_REL = ".forge/venv"
RUNTIME_PACKAGES = ("PyYAML>=6.0",)


@dataclass
class EnsureResult:
    status: str
    """One of:
        "created"           — venv built from scratch + deps installed
        "rebuilt"           — existing venv removed and rebuilt (force=True)
        "deps-installed"    — venv present, deps missing, just ran pip
        "present"           — venv present and healthy, no-op
        "no-python"         — no usable `python3` on PATH; can't proceed
        "venv-failed"       — `python3 -m venv` failed
        "pip-failed"        — `pip install` failed (offline / network)
        "import-failed"     — install succeeded but `import yaml` still fails
    """

    python: Path | None
    """Path to the venv's python interpreter, or None on hard failure."""

    message: str
    """Human-readable summary suitable for printing to the user."""


def _venv_dir(project_root: Path) -> Path:
    return project_root / VENV_REL


def _venv_python(project_root: Path) -> Path:
    # `python3 -m venv` always lays out bin/python on POSIX. Windows is
    # `Scripts\python.exe` — not yet supported (Forge Flow is POSIX-only
    # today; the pre-push hook is bash).
    return _venv_dir(project_root) / "bin" / "python"


def _has_yaml(python: Path) -> bool:
    if not python.exists():
        return False
    try:
        result = subprocess.run(
            [str(python), "-c", "import yaml"],
            capture_output=True,
            timeout=10,
        )
    except (subprocess.SubprocessError, OSError):
        return False
    return result.returncode == 0


def _install_packages(python: Path) -> tuple[bool, str]:
    """Install RUNTIME_PACKAGES into the venv. Returns (ok, log_tail)."""
    try:
        result = subprocess.run(
            [str(python), "-m", "pip", "install", "--quiet", *RUNTIME_PACKAGES],
            capture_output=True,
            timeout=120,
        )
    except subprocess.SubprocessError as exc:
        return False, f"pip subprocess failed: {exc}"
    except OSError as exc:
        return False, f"pip invocation failed: {exc}"
    if result.returncode != 0:
        tail = (result.stderr or result.stdout or b"").decode("utf-8", "replace")
        return False, tail.strip().splitlines()[-3:] if tail.strip() else "pip exited non-zero"
    return True, "ok"


def ensure_venv(project_root: Path, *, force: bool = False) -> EnsureResult:
    """Ensure `.forge/venv/` exists and has the framework's runtime deps.

    Args:
        project_root: The consumer project root (one level above .claude/).
        force: If True, remove any existing venv and rebuild from scratch.

    Returns:
        EnsureResult — never raises. Hard failure surfaces via .status.
    """
    venv_dir = _venv_dir(project_root)
    python = _venv_python(project_root)

    if force and venv_dir.exists():
        shutil.rmtree(venv_dir, ignore_errors=True)

    if python.exists() and not force:
        if _has_yaml(python):
            return EnsureResult(
                status="present",
                python=python,
                message=f"{VENV_REL}/ present and healthy",
            )
        ok, tail = _install_packages(python)
        if not ok:
            return EnsureResult(
                status="pip-failed",
                python=python,
                message=(
                    f"{VENV_REL}/ exists but is missing PyYAML and pip install "
                    f"failed: {tail}. Re-run with --force to rebuild, or "
                    f"install PyYAML manually: {python} -m pip install pyyaml"
                ),
            )
        if not _has_yaml(python):
            return EnsureResult(
                status="import-failed",
                python=python,
                message=(
                    f"{VENV_REL}/ installed PyYAML but `import yaml` still fails. "
                    f"Try `rm -rf {venv_dir}` and re-run."
                ),
            )
        return EnsureResult(
            status="deps-installed",
            python=python,
            message=f"{VENV_REL}/ deps installed (PyYAML added to existing venv)",
        )

    # Build venv from scratch.
    venv_dir.parent.mkdir(parents=True, exist_ok=True)
    try:
        venv.create(venv_dir, with_pip=True, clear=False, symlinks=True)
    except (OSError, subprocess.SubprocessError) as exc:
        return EnsureResult(
            status="venv-failed",
            python=None,
            message=(
                f"Could not create {VENV_REL}/: {exc}. Check that python3 -m venv "
                f"is available on this Python: {sys.executable}"
            ),
        )

    if not python.exists():
        return EnsureResult(
            status="venv-failed",
            python=None,
            message=(
                f"venv created but {python} missing — unexpected layout. "
                f"This may be a non-POSIX Python."
            ),
        )

    ok, tail = _install_packages(python)
    if not ok:
        return EnsureResult(
            status="pip-failed",
            python=python,
            message=(
                f"{VENV_REL}/ created but pip install failed: {tail}. "
                f"The hook will still install but preflight will fail until "
                f"PyYAML is available. Re-run `forge preflight enable-git-hook "
                f"--force` once you have network access."
            ),
        )

    if not _has_yaml(python):
        return EnsureResult(
            status="import-failed",
            python=python,
            message=(
                f"{VENV_REL}/ installed but `import yaml` still fails. "
                f"Try `rm -rf {venv_dir}` and re-run."
            ),
        )

    status = "rebuilt" if force else "created"
    return EnsureResult(
        status=status,
        python=python,
        message=f"{VENV_REL}/ {status} with PyYAML",
    )
