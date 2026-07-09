"""Install / uninstall the Forge Flow pre-push hook.

Sentinel comment `FORGE_PREFLIGHT_HOOK_V1` marks Forge-owned hooks so we
never clobber a hook the user wrote by hand. Operations are idempotent —
install over an existing Forge hook is fine; disable when no hook exists
is fine.

`install()` also ensures the framework-owned `.forge/venv/` exists so the
hook's preflight scripts have PyYAML available without depending on the
consumer's global Python install. See `venv_manager.py`.
"""

from __future__ import annotations

import shutil
import sys
from dataclasses import dataclass
from pathlib import Path

# Import sibling module via either `preflight.hook_installer` (forge.py
# path adds scripts/ to sys.path) or direct invocation. Adding our own
# directory makes the `venv_manager` import work either way.
sys.path.insert(0, str(Path(__file__).resolve().parent))
from venv_manager import EnsureResult, ensure_venv  # noqa: E402

SENTINEL = "FORGE_PREFLIGHT_HOOK_V1"
HOOK_NAME = "pre-push"
TEMPLATE_NAME = "pre-push.template.sh"


@dataclass
class InstallResult:
    status: str  # "installed" | "overwrote-forge" | "skipped-foreign-hook"
    hook_path: Path
    message: str
    venv: EnsureResult | None = None  # venv outcome, None if not attempted


@dataclass
class UninstallResult:
    status: str  # "removed" | "absent" | "skipped-foreign-hook"
    hook_path: Path
    message: str


def _hooks_dir(repo_root: Path) -> Path:
    return repo_root / ".git" / "hooks"


def _template_path() -> Path:
    return Path(__file__).parent / TEMPLATE_NAME


def install(repo_root: Path, *, force: bool = False) -> InstallResult:
    hooks = _hooks_dir(repo_root)
    if not hooks.exists():
        hooks.mkdir(parents=True, exist_ok=True)
    target = hooks / HOOK_NAME

    if target.exists():
        existing = target.read_text(errors="replace")
        if SENTINEL not in existing and not force:
            return InstallResult(
                status="skipped-foreign-hook",
                hook_path=target,
                message=(
                    f"Existing {target} was not written by Forge "
                    f"(no {SENTINEL} sentinel). Re-run with --force to overwrite."
                ),
            )
        prior = "overwrote-forge" if SENTINEL in existing else "installed"
    else:
        prior = "installed"

    shutil.copyfile(_template_path(), target)
    target.chmod(0o755)

    # Ensure the framework-owned venv has PyYAML — the hook's preflight
    # scripts need it. Failure here is non-fatal for the hook install
    # itself; we surface the venv status to the caller so the user
    # learns about it before the next push event fires the hook.
    venv_result = ensure_venv(repo_root, force=force)

    return InstallResult(
        status=prior,
        hook_path=target,
        message=f"Hook written to {target}",
        venv=venv_result,
    )


def uninstall(repo_root: Path) -> UninstallResult:
    target = _hooks_dir(repo_root) / HOOK_NAME
    if not target.exists():
        return UninstallResult(
            status="absent", hook_path=target, message=f"No hook at {target}"
        )
    existing = target.read_text(errors="replace")
    if SENTINEL not in existing:
        return UninstallResult(
            status="skipped-foreign-hook",
            hook_path=target,
            message=(
                f"Hook at {target} is not Forge-owned (no {SENTINEL} sentinel) "
                f"— leaving it alone."
            ),
        )
    target.unlink()
    return UninstallResult(
        status="removed", hook_path=target, message=f"Removed {target}"
    )
