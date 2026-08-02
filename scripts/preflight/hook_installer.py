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
import subprocess
import sys
from dataclasses import dataclass
from pathlib import Path

# Import sibling module via either `preflight.hook_installer` (forge.py
# path adds scripts/ to sys.path) or direct invocation. Adding our own
# directory makes the `venv_manager` import work either way.
sys.path.insert(0, str(Path(__file__).resolve().parent))
from venv_manager import EnsureResult, ensure_venv  # noqa: E402

# The installed hook is a COPY of the template, so a template change does not
# reach anyone who already ran `enable-git-hook`. Version the sentinel and match
# on the prefix: prefix => Forge-owned (safe to overwrite without --force), exact
# => current. Bump SENTINEL whenever the template's contract with preflight.py
# changes, so `refresh_if_stale()` can heal existing installs.
SENTINEL_PREFIX = "FORGE_PREFLIGHT_HOOK_V"
SENTINEL = f"{SENTINEL_PREFIX}2"
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
    """The ACTIVE hooks directory, resolved through git rather than assumed.

    In a linked worktree `<root>/.git` is a FILE pointing at
    `<common>/.git/worktrees/<name>`, so `<root>/.git/hooks` never exists. The
    naive join therefore reports "no hook installed", a V1 hook survives the
    migration, and its catch-all failure branch blocks the push on the new
    exit code 5 — the opposite of the non-blocking guarantee. Asking git also
    honours `core.hooksPath`.

    Falls back to the naive join when git is unavailable or errors, which keeps
    a plain (non-worktree) checkout working exactly as before.
    """
    try:
        out = subprocess.run(
            ["git", "-C", str(repo_root), "rev-parse", "--git-path", "hooks"],
            capture_output=True,
            text=True,
            timeout=5,
            check=True,
        ).stdout.strip()
        if out:
            resolved = Path(out)
            return resolved if resolved.is_absolute() else repo_root / resolved
    except (OSError, subprocess.SubprocessError):
        pass
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
        # Prefix match, not exact: an older Forge hook is still ours to replace.
        # Matching exactly would treat every previous version as a foreign hook
        # and refuse to upgrade it without --force.
        if SENTINEL_PREFIX not in existing and not force:
            return InstallResult(
                status="skipped-foreign-hook",
                hook_path=target,
                message=(
                    f"Existing {target} was not written by Forge "
                    f"(no {SENTINEL_PREFIX}* sentinel). Re-run with --force to overwrite."
                ),
            )
        prior = "overwrote-forge" if SENTINEL_PREFIX in existing else "installed"
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


def installed_is_stale(repo_root: Path) -> bool:
    """True when a Forge-owned hook is installed but predates the current SENTINEL.

    False for no hook, a foreign hook (not ours to touch), or a current one.
    """
    target = _hooks_dir(repo_root) / HOOK_NAME
    if not target.exists():
        return False
    existing = target.read_text(errors="replace")
    return SENTINEL_PREFIX in existing and SENTINEL not in existing


def refresh_if_stale(repo_root: Path) -> bool:
    """Rewrite an out-of-date Forge-owned hook from the current template.

    Returns True if a refresh happened. The installed hook is a snapshot, so
    nothing else updates it — a user who ran `enable-git-hook` once would keep a
    hook whose contract with preflight.py has since changed. Only touches hooks
    carrying our sentinel; a hand-written hook is never rewritten.
    """
    if not installed_is_stale(repo_root):
        return False
    target = _hooks_dir(repo_root) / HOOK_NAME
    shutil.copyfile(_template_path(), target)
    target.chmod(0o755)
    return True


def uninstall(repo_root: Path) -> UninstallResult:
    target = _hooks_dir(repo_root) / HOOK_NAME
    if not target.exists():
        return UninstallResult(
            status="absent", hook_path=target, message=f"No hook at {target}"
        )
    existing = target.read_text(errors="replace")
    if SENTINEL_PREFIX not in existing:
        return UninstallResult(
            status="skipped-foreign-hook",
            hook_path=target,
            message=(
                f"Hook at {target} is not Forge-owned (no {SENTINEL_PREFIX}* sentinel) "
                f"— leaving it alone."
            ),
        )
    target.unlink()
    return UninstallResult(
        status="removed", hook_path=target, message=f"Removed {target}"
    )
