#!/usr/bin/env python3
"""
forge.py
Claude Forge CLI — atomic task state operations.

Replaces hand-edits of registry.json + task file frontmatter that
historically were the source of registry/disk drift. Every operation
mutates both sides in one atomic write each and recomputes stats.

Usage (typical agent invocation pattern):

  python3 .claude/scripts/forge/forge.py task add T015 \\
      --epic E01 --name "Add chart component" \\
      --deps T010,T012 --scope-dirs src/components/charts/

  python3 .claude/scripts/forge/forge.py task lock T015 --session 20260504-abc
  python3 .claude/scripts/forge/forge.py task pr T015
  python3 .claude/scripts/forge/forge.py task complete T015

  python3 .claude/scripts/forge/forge.py task ls --ready
  python3 .claude/scripts/forge/forge.py task show T015

The CLI is a thin wrapper around scripts/forge/registry_ops.py — the
logic lives there so it's testable and re-usable from skill flows or
from the consistency checker's auto-fix paths.
"""

from __future__ import annotations

import argparse
import json
import os
import re
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path

# Allow running as a script without packaging
sys.path.insert(0, str(Path(__file__).resolve().parent))

import registry_ops as ops  # noqa: E402


def get_project_root(override: Path | None = None) -> Path:
    """Resolve project root.

    Order: explicit override -> CLAUDE_PROJECT_DIR env -> docs/tasks/registry.json
    walk -> git toplevel -> cwd.
    """
    if override is not None:
        return override
    env_root = os.environ.get("CLAUDE_PROJECT_DIR")
    if env_root and Path(env_root).exists():
        return Path(env_root)
    current = Path(__file__).resolve().parent
    while current != current.parent:
        if (current / "docs" / "tasks" / "registry.json").exists():
            return current
        current = current.parent
    try:
        out = subprocess.run(
            ["git", "rev-parse", "--show-toplevel"],
            capture_output=True, text=True, check=True
        )
        return Path(out.stdout.strip())
    except (subprocess.CalledProcessError, FileNotFoundError):
        return Path.cwd()


def _registry_path(project_root: Path) -> Path:
    return project_root / "docs" / "tasks" / "registry.json"


def _split_csv(value: str | None) -> list[str]:
    if not value:
        return []
    return [p.strip() for p in value.split(",") if p.strip()]


# --- Subcommand handlers ---------------------------------------------------


def cmd_add(args, project_root: Path) -> int:
    try:
        task = ops.add_task(
            _registry_path(project_root),
            task_id=args.id,
            epic_id=args.epic,
            name=args.name,
            dependencies=_split_csv(args.deps),
            scope_directories=_split_csv(args.scope_dirs),
            scope_files=_split_csv(args.scope_files),
            file_path=args.file,
            priority=args.priority,
            category=args.category or "",
            preflight=args.preflight,
            allow_missing_epic=args.allow_missing_epic,
        )
    except (ops.TaskAlreadyExists, ops.EpicNotFound) as e:
        print(f"error: {e}", file=sys.stderr)
        return 1
    except ops.RegistryLockTimeout as e:
        print(f"error: registry is locked by another process; retry ({e})", file=sys.stderr)
        return 1

    body_file: Path | None = None
    isa_file: Path | None = None

    # Default: create the task body file. --no-file opts out (tests, tooling
    # that only want the registry mutation).
    if not args.no_file:
        try:
            body_file = ops.create_task_body_file(project_root, task)
        except FileExistsError:
            # A file already lives at the expected path — leave it; the user
            # is likely adding a registry entry for an existing file.
            pass
        except Exception as exc:  # noqa: BLE001
            print(
                f"warning: registry entry added but task body file "
                f"creation failed: {exc}",
                file=sys.stderr,
            )

    # --isa scaffolds the per-task ISA at docs/tasks/<id>/ISA.md and records
    # its path on the registry task so spec-state is queryable.
    if args.isa:
        try:
            isa_file = ops.scaffold_task_isa(project_root, task)
        except FileExistsError:
            isa_file = ops.task_isa_path(project_root, task["id"])
        except Exception as exc:  # noqa: BLE001
            print(
                f"warning: registry entry added but ISA scaffold failed: {exc}",
                file=sys.stderr,
            )
        if isa_file is not None:
            try:
                rel = str(isa_file.relative_to(project_root))
                ops.set_task_isa(_registry_path(project_root), task["id"], rel)
                task["isa"] = rel
            except Exception as exc:  # noqa: BLE001
                print(
                    f"warning: ISA scaffolded but registry link not set: {exc}",
                    file=sys.stderr,
                )

    if args.json:
        payload = dict(task)
        if body_file is not None:
            payload["_body_file"] = str(body_file.relative_to(project_root))
        if isa_file is not None:
            payload["_isa_file"] = str(isa_file.relative_to(project_root))
        print(json.dumps(payload, indent=2))
    else:
        pf = "yes" if task.get("preflight_required") else "no"
        msg = (
            f"added {task['id']}: {task['name']} "
            f"(status={task['status']}, preflight={pf})"
        )
        if body_file is not None:
            msg += f"\n  body: {body_file.relative_to(project_root)}"
        if isa_file is not None:
            msg += f"\n  isa:  {isa_file.relative_to(project_root)}"
        print(msg)
    return 0


def cmd_epic_add(args, project_root: Path) -> int:
    """Create an epic: registry entry + on-disk dir/body file.

    Fills the gap that forced hand-editing of registry.json — there was no
    sanctioned path to create an epic, yet `task add` requires its epic to
    exist. Mirrors `task add`'s compose shape (atomic op + on-disk artifact).
    """
    try:
        epic = ops.add_epic(
            _registry_path(project_root),
            epic_id=args.id,
            name=args.name,
            description=args.description or "",
            dependencies=_split_csv(args.deps),
            priority=args.priority,
            category=args.category or "",
            status=args.status,
        )
    except ops.EpicAlreadyExists as e:
        print(f"error: {e}", file=sys.stderr)
        return 1
    except ops.RegistryLockTimeout as e:
        print(f"error: registry is locked by another process; retry ({e})", file=sys.stderr)
        return 1

    epic_dir: Path | None = None
    if not args.no_file:
        try:
            epic_dir = ops.create_epic_dir(project_root, epic)
        except Exception as exc:  # noqa: BLE001
            print(
                f"warning: registry entry added but epic dir/body file "
                f"creation failed: {exc}",
                file=sys.stderr,
            )

    if args.json:
        payload = dict(epic)
        if epic_dir is not None:
            payload["_epic_dir"] = str(epic_dir.relative_to(project_root))
        print(json.dumps(payload, indent=2))
    else:
        msg = f"added {epic['id']}: {epic['name']} (status={epic['status']})"
        if epic_dir is not None:
            msg += f"\n  dir: {epic_dir.relative_to(project_root)}"
        print(msg)
    return 0


def cmd_reconcile_files(args, project_root: Path) -> int:
    """Create stub body files for registry-tracked tasks missing on disk."""
    result = ops.reconcile_task_files(
        _registry_path(project_root), project_root, apply=args.apply,
    )
    if args.json:
        print(json.dumps(result, indent=2))
        return 0 if not result["errors"] else 1

    missing = result["missing"]
    created = result["created"]
    errors = result["errors"]

    if not missing:
        print("no drift: every registry-tracked task has a body file on disk")
        return 0

    if not args.apply:
        print(
            f"{len(missing)} registry-tracked task(s) have no body file on disk. "
            f"Re-run with --apply to create stubs.\n"
        )
        for task_id in missing:
            print(f"  would create stub for: {task_id}")
        return 0

    print(f"created {len(created)} stub body file(s):")
    for path in created:
        print(f"  {path}")
    if errors:
        print(f"\n{len(errors)} error(s):", file=sys.stderr)
        for err in errors:
            print(f"  {err['task']}: {err['error']}", file=sys.stderr)
        return 1
    return 0


def cmd_lock(args, project_root: Path) -> int:
    try:
        task = ops.lock_task(
            _registry_path(project_root), project_root, args.id,
            session_id=args.session,
        )
    except ops.TaskNotFound as e:
        print(f"error: {e}", file=sys.stderr)
        return 1
    except ops.IllegalTransition as e:
        print(f"error: {e}", file=sys.stderr)
        return 2
    except ops.RegistryLockTimeout as e:
        print(f"error: registry is locked by another process; retry ({e})", file=sys.stderr)
        return 1
    if args.json:
        print(json.dumps(task, indent=2))
    else:
        lock = task.get("lock") or {}
        print(f"locked {task['id']} (session={lock.get('session')})")
    # Non-blocking spec nudge: starting work on a task with no ISA. Advisory
    # only — never changes the exit code or blocks the lock.
    if not ops.task_has_isa(project_root, task):
        print(
            f"⚠ {task['id']} has no ISA. Substantial work should have a "
            f"spec.\n"
            f"  Attach one:  forge task add {task['id']} ... --isa\n"
            f"          or:  /ISA scaffold \"...\"   (then it's picked up on "
            f"disk)\n"
            f"  (non-blocking — this is a reminder, not a gate)",
            file=sys.stderr,
        )
    return 0


def cmd_unlock(args, project_root: Path) -> int:
    try:
        task = ops.unlock_task(
            _registry_path(project_root), project_root, args.id,
            to_status=args.to_status,
        )
    except ops.TaskNotFound as e:
        print(f"error: {e}", file=sys.stderr)
        return 1
    except ops.IllegalTransition as e:
        print(f"error: {e}", file=sys.stderr)
        return 2
    except ops.RegistryLockTimeout as e:
        print(f"error: registry is locked by another process; retry ({e})", file=sys.stderr)
        return 1
    if args.json:
        print(json.dumps(task, indent=2))
    else:
        print(f"unlocked {task['id']} (status={task['status']})")
    return 0


def cmd_complete(args, project_root: Path) -> int:
    try:
        task, unblocked = ops.complete_task(
            _registry_path(project_root), project_root, args.id,
        )
    except ops.TaskNotFound as e:
        print(f"error: {e}", file=sys.stderr)
        return 1
    except ops.IllegalTransition as e:
        print(f"error: {e}", file=sys.stderr)
        return 2
    except ops.RegistryLockTimeout as e:
        print(f"error: registry is locked by another process; retry ({e})", file=sys.stderr)
        return 1
    if args.json:
        print(json.dumps({"task": task, "unblocked": unblocked}, indent=2))
    else:
        print(f"completed {task['id']}")
        if unblocked:
            print(f"unblocked: {', '.join(unblocked)}")
    return 0


def cmd_pr(args, project_root: Path) -> int:
    try:
        task, unblocked = ops.pr_task(
            _registry_path(project_root), project_root, args.id,
        )
    except ops.TaskNotFound as e:
        print(f"error: {e}", file=sys.stderr)
        return 1
    except ops.IllegalTransition as e:
        print(f"error: {e}", file=sys.stderr)
        return 2
    except ops.RegistryLockTimeout as e:
        print(f"error: registry is locked by another process; retry ({e})", file=sys.stderr)
        return 1
    if args.json:
        print(json.dumps({"task": task, "unblocked": unblocked}, indent=2))
    else:
        print(f"{task['id']} → pr_pending")
        if unblocked:
            print(f"unblocked: {', '.join(unblocked)}")
    return 0


def cmd_status(args, project_root: Path) -> int:
    try:
        task = ops.transition_task(
            _registry_path(project_root), project_root, args.id, args.new_status,
        )
    except ops.TaskNotFound as e:
        print(f"error: {e}", file=sys.stderr)
        return 1
    except ops.IllegalTransition as e:
        print(f"error: {e}", file=sys.stderr)
        return 2
    except ops.RegistryLockTimeout as e:
        print(f"error: registry is locked by another process; retry ({e})", file=sys.stderr)
        return 1
    if args.json:
        print(json.dumps(task, indent=2))
    else:
        print(f"{task['id']} → {task['status']}")
    return 0


def cmd_ls(args, project_root: Path) -> int:
    status = None
    if args.ready: status = "ready"
    elif args.pending: status = "pending"
    elif args.in_progress: status = "in_progress"
    elif args.pr_pending: status = "pr_pending"
    elif args.completed: status = "completed"
    elif args.continuation: status = "continuation"
    elif args.status:
        status = args.status

    try:
        tasks = ops.list_tasks(
            _registry_path(project_root),
            status_filter=status,
            epic_filter=args.epic,
            locked_only=args.locked,
        )
    except FileNotFoundError:
        print(f"error: registry not found at {_registry_path(project_root)}", file=sys.stderr)
        return 1

    if args.json:
        print(json.dumps(tasks, indent=2))
        return 0

    if not tasks:
        print("(no tasks match)")
        return 0
    width = max(len(t.get("id", "")) for t in tasks)
    for t in tasks:
        tid = t.get("id", "?").ljust(width)
        st = t.get("status", "?")
        nm = t.get("name", "")
        ep = t.get("epic", "")
        lock = "🔒 " if t.get("lock") else "  "
        print(f"{lock}{tid}  {st:<14} [{ep}] {nm}")
    return 0


def cmd_rename(args, project_root: Path) -> int:
    try:
        task = ops.rename_task(
            _registry_path(project_root), project_root, args.id, args.name,
        )
    except ops.TaskNotFound as e:
        print(f"error: {e}", file=sys.stderr)
        return 1
    except ValueError as e:
        print(f"error: {e}", file=sys.stderr)
        return 1
    except ops.RegistryLockTimeout as e:
        print(f"error: registry is locked by another process; retry ({e})", file=sys.stderr)
        return 1
    if args.json:
        print(json.dumps(task, indent=2))
    else:
        print(f'renamed {task["id"]} -> "{task["name"]}"')
    return 0


def cmd_set_file(args, project_root: Path) -> int:
    try:
        task = ops.set_task_file(
            _registry_path(project_root), project_root, args.id, args.file,
            require_exists=args.require_exists,
        )
    except ops.TaskNotFound as e:
        print(f"error: {e}", file=sys.stderr)
        return 1
    except (ValueError, FileNotFoundError) as e:
        print(f"error: {e}", file=sys.stderr)
        return 1
    except ops.RegistryLockTimeout as e:
        print(f"error: registry is locked by another process; retry ({e})", file=sys.stderr)
        return 1
    if args.json:
        print(json.dumps(task, indent=2))
    else:
        print(f'set {task["id"]} file -> {task["file"]}')
    return 0


def cmd_reconcile(args, project_root: Path) -> int:
    try:
        seeded = ops.reconcile_orphan_files(
            _registry_path(project_root), project_root,
        )
    except FileNotFoundError as e:
        print(f"error: {e}", file=sys.stderr)
        return 1
    except ops.RegistryLockTimeout as e:
        print(f"error: registry is locked by another process; retry ({e})", file=sys.stderr)
        return 1
    if args.json:
        print(json.dumps({"seeded": seeded}, indent=2))
    else:
        if not seeded:
            print("reconcile: no orphan task files found")
        else:
            print(f"reconcile: seeded {len(seeded)} task(s) from disk")
            for tid in seeded:
                print(f"  + {tid}")
    return 0


def cmd_show(args, project_root: Path) -> int:
    try:
        registry = ops.load_registry(_registry_path(project_root))
        task = ops.find_task(registry, args.id)
    except FileNotFoundError:
        print(f"error: registry not found at {_registry_path(project_root)}", file=sys.stderr)
        return 1
    except ops.TaskNotFound as e:
        print(f"error: {e}", file=sys.stderr)
        return 1
    print(json.dumps(task, indent=2))
    return 0


# --- Specialist subcommand -------------------------------------------------

_VALID_SPECIALIST_NAME = re.compile(r"^[a-z][a-z0-9-]*$")


def _find_template(template_name: str, project_root: Path) -> Path:
    """Locate a template file. Tries forge-relative (framework dev),
    then project_root/templates/, then project_root/.claude/templates/.
    """
    here = Path(__file__).resolve()
    candidates = [
        here.parent.parent.parent / "templates" / template_name,
        project_root / "templates" / template_name,
        project_root / ".claude" / "templates" / template_name,
    ]
    for c in candidates:
        if c.exists():
            return c
    raise FileNotFoundError(
        f"template '{template_name}' not found; tried: "
        + ", ".join(str(c) for c in candidates)
    )


def _render_template(template: str, mapping: dict[str, str]) -> str:
    out = template
    for key, value in mapping.items():
        out = out.replace("{{" + key + "}}", value)
    return out


def cmd_agent_heartbeat(args, project_root: Path) -> int:
    """Report the freshest commit + checkpoint on a branch.

    Reads commit log via `git log` and emits human-readable (default) or JSON
    output. Designed for parents to poll background-agent worktree branches
    without reading the agent's JSONL transcript.

    Output JSON shape:
      {
        "branch": str,
        "head_sha": str,
        "head_subject": str,
        "head_age_seconds": int,
        "stale": bool,
        "stale_threshold_seconds": int,
        "latest_checkpoint": {
          "sha": str,
          "subject": str,
          "age_seconds": int,
        } | None
      }
    """
    branch = args.branch
    threshold = args.stale_threshold

    # Validate branch exists (refs/heads, refs/remotes, or detached SHA)
    check = subprocess.run(
        ["git", "rev-parse", "--verify", "--quiet", branch],
        cwd=project_root, capture_output=True, text=True, check=False,
    )
    if check.returncode != 0:
        msg = f"error: unknown branch or ref: {branch}"
        if args.json:
            print(json.dumps({"error": msg, "branch": branch}))
        else:
            print(msg, file=sys.stderr)
        return 2

    # Head commit
    head = subprocess.run(
        ["git", "log", "-1", "--format=%H%x1f%ct%x1f%s", branch],
        cwd=project_root, capture_output=True, text=True, check=False,
    )
    if head.returncode != 0 or not head.stdout.strip():
        msg = f"error: failed to read commit log for {branch}"
        if args.json:
            print(json.dumps({"error": msg, "branch": branch}))
        else:
            print(msg, file=sys.stderr)
        return 2

    head_sha, head_ct, head_subject = head.stdout.strip().split("\x1f", 2)
    head_ct_i = int(head_ct)
    now = int(datetime.now(timezone.utc).timestamp())
    head_age = now - head_ct_i
    stale = head_age > threshold

    # Latest checkpoint commit (wip: or checkpoint:)
    checkpoint = subprocess.run(
        [
            "git", "log", "-1",
            "--grep=^(wip|checkpoint)(\\(.+\\))?:",
            "--extended-regexp",
            "--format=%H%x1f%ct%x1f%s",
            branch,
        ],
        cwd=project_root, capture_output=True, text=True, check=False,
    )

    latest_checkpoint: dict[str, object] | None = None
    if checkpoint.returncode == 0 and checkpoint.stdout.strip():
        c_sha, c_ct, c_subject = checkpoint.stdout.strip().split("\x1f", 2)
        latest_checkpoint = {
            "sha": c_sha,
            "subject": c_subject,
            "age_seconds": now - int(c_ct),
        }

    result = {
        "branch": branch,
        "head_sha": head_sha,
        "head_subject": head_subject,
        "head_age_seconds": head_age,
        "stale": stale,
        "stale_threshold_seconds": threshold,
        "latest_checkpoint": latest_checkpoint,
    }

    if args.json:
        print(json.dumps(result))
    else:
        flag = " [STALE]" if stale else ""
        print(f"branch: {branch}{flag}")
        print(f"head: {head_sha[:10]}  ({head_age}s ago)  {head_subject}")
        if latest_checkpoint:
            cp_sha = str(latest_checkpoint["sha"])[:10]
            cp_age = latest_checkpoint["age_seconds"]
            cp_subject = latest_checkpoint["subject"]
            print(f"checkpoint: {cp_sha}  ({cp_age}s ago)  {cp_subject}")
        else:
            print("checkpoint: (none — no wip:/checkpoint: commit found)")
    return 0


def cmd_preflight_enable_hook(args, project_root: Path) -> int:
    # Import lazily so forge.py works in projects that haven't installed preflight scripts.
    sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
    from preflight.hook_installer import install

    result = install(project_root, force=args.force)

    if args.json:
        payload = {
            "status": result.status,
            "hook": str(result.hook_path),
            "message": result.message,
        }
        if result.venv is not None:
            payload["venv"] = {
                "status": result.venv.status,
                "python": str(result.venv.python) if result.venv.python else None,
                "message": result.venv.message,
            }
        print(json.dumps(payload, indent=2))
    else:
        hook_marker = {
            "installed": "✓",
            "overwrote-forge": "↻",
            "skipped-foreign-hook": "⚠️",
        }.get(result.status, "?")
        print(f"{hook_marker} {result.message}")
        if result.venv is not None:
            venv_marker = {
                "created": "✓",
                "rebuilt": "↻",
                "present": "·",
                "deps-installed": "✓",
                "no-python": "❌",
                "venv-failed": "❌",
                "pip-failed": "⚠️",
                "import-failed": "❌",
            }.get(result.venv.status, "?")
            print(f"{venv_marker} {result.venv.message}")

    if result.status == "skipped-foreign-hook":
        return 2
    if result.venv is not None and result.venv.status in (
        "no-python",
        "venv-failed",
        "import-failed",
    ):
        return 2
    return 0


def cmd_preflight_disable_hook(args, project_root: Path) -> int:
    sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
    from preflight.hook_installer import uninstall

    result = uninstall(project_root)
    if args.json:
        print(json.dumps({"status": result.status, "hook": str(result.hook_path), "message": result.message}, indent=2))
    else:
        marker = {"removed": "✓", "absent": "·", "skipped-foreign-hook": "⚠️"}.get(result.status, "?")
        print(f"{marker} {result.message}")
    return 0 if result.status != "skipped-foreign-hook" else 2


def cmd_specialist_add(args, project_root: Path) -> int:
    name = args.name
    if not _VALID_SPECIALIST_NAME.match(name):
        print(
            f"error: name '{name}' invalid; must match [a-z][a-z0-9-]*",
            file=sys.stderr,
        )
        return 1

    export_rel = Path(args.export_path)
    export_path = (project_root / export_rel) if not export_rel.is_absolute() else export_rel

    agent_path = project_root / ".claude" / "agents" / "specialists" / f"{name}.md"

    if agent_path.exists():
        print(f"error: specialist '{name}' already exists at {agent_path}", file=sys.stderr)
        return 1
    if export_path.exists():
        print(f"error: export path already exists at {export_path}", file=sys.stderr)
        return 1

    try:
        agent_template = _find_template("specialist-agent.md", project_root).read_text()
        expert_template = _find_template("EXPERT.md", project_root).read_text()
    except FileNotFoundError as e:
        print(f"error: {e}", file=sys.stderr)
        return 1

    project_name = project_root.name
    timestamp = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    export_rel_str = str(export_rel)

    mapping_agent = {
        "NAME": name,
        "DOMAIN": args.domain,
        "EXPORT_PATH": export_rel_str,
    }
    mapping_expert = {
        "NAME": name,
        "DOMAIN": args.domain,
        "PROJECT": project_name,
        "TIMESTAMP": timestamp,
    }

    agent_content = _render_template(agent_template, mapping_agent)
    expert_content = _render_template(expert_template, mapping_expert)

    agent_path.parent.mkdir(parents=True, exist_ok=True)
    export_path.parent.mkdir(parents=True, exist_ok=True)
    agent_path.write_text(agent_content)
    export_path.write_text(expert_content)

    if args.json:
        print(json.dumps({
            "name": name,
            "agent": str(agent_path.relative_to(project_root)),
            "export": str(export_path.relative_to(project_root)),
        }, indent=2))
    else:
        print(f"created specialist '{name}'")
        print(f"  agent:  {agent_path.relative_to(project_root)}")
        print(f"  export: {export_path.relative_to(project_root)}")
        print(f"hint: reference @{name} in your CLAUDE.md so Claude knows to invoke it")
    return 0


def cmd_dashboard(args, project_root: Path) -> int:
    """Start the local Forge dashboard HTTP server.

    Imports lazily so `forge --help` doesn't load the dashboard module — most
    invocations of forge are task ops, not dashboard.
    """
    # Lazy import — the dashboard package is sibling to this file (when forge
    # is invoked as `python3 scripts/forge/forge.py`, `scripts/forge/` is on
    # sys.path automatically; for `python3 -m forge.forge` it works too).
    here = Path(__file__).resolve().parent
    if str(here) not in sys.path:
        sys.path.insert(0, str(here))
    from dashboard import server as dashboard_server  # noqa: PLC0415
    return dashboard_server.run(
        host=args.host,
        port=args.port,
        auto_open=not args.no_open,
        once=args.once,
    )


def cmd_specialist_list(args, project_root: Path) -> int:
    specialists_dir = project_root / ".claude" / "agents" / "specialists"
    if not specialists_dir.exists():
        if args.json:
            print(json.dumps([]))
        else:
            print("(no specialists)")
        return 0
    items = sorted(p.stem for p in specialists_dir.glob("*.md"))
    if args.json:
        print(json.dumps(items, indent=2))
    else:
        if not items:
            print("(no specialists)")
        else:
            for n in items:
                print(n)
    return 0


def cmd_version(args, project_root: Path) -> int:
    """Print the framework version from the repo-root VERSION file.

    Older consumer installs (pre-4.2) won't have a VERSION file yet — that's
    not an error, just print an explanatory placeholder.
    """
    version_file = Path(__file__).resolve().parent.parent.parent / "VERSION"
    if version_file.exists():
        print(version_file.read_text().strip())
    else:
        print("unknown (VERSION file not found — pre-4.2 install?)")
    return 0


def cmd_doctor(args, project_root: Path) -> int:
    """Read-only install health check — see scripts/forge/doctor.py."""
    import doctor

    if args.banner:
        return doctor.run_banner(project_root)
    if args.all is not None:
        return doctor.run_all(project_root, args.all, as_json=args.json)
    return doctor.run(project_root, as_json=args.json)


# --- Argparse wiring -------------------------------------------------------


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(
        prog="forge",
        description="Claude Forge CLI — atomic task state operations.",
    )
    p.add_argument(
        "--project-root", type=Path, default=None,
        help="Override project root detection (mostly for testing)."
    )

    sub = p.add_subparsers(dest="group", required=True)

    # task
    task = sub.add_parser("task", help="Task operations").add_subparsers(
        dest="action", required=True
    )

    a = task.add_parser("add", help="Add a new task to the registry")
    a.add_argument("id", help="Task ID, e.g. T015")
    a.add_argument("--epic", required=True, help="Epic ID, e.g. E01")
    a.add_argument("--name", required=True, help="Task name (one line)")
    a.add_argument("--deps", help="Comma-separated dependency task IDs")
    a.add_argument("--scope-dirs", help="Comma-separated directories the task touches")
    a.add_argument("--scope-files", help="Comma-separated specific files the task touches")
    a.add_argument("--file", help="Relative path to the task markdown file")
    a.add_argument("--priority", type=int, default=1, help="Priority (lower = higher)")
    a.add_argument("--category", default="", help="Category code (A-T)")
    a.add_argument(
        "--preflight",
        choices=["auto", "required", "skip"],
        default="auto",
        help=(
            "Whether the pre-push hook should run /preflight-ci for this task. "
            "auto (default) = required iff scope-dirs/files touch non-doc paths."
        ),
    )
    a.add_argument(
        "--no-file",
        action="store_true",
        help=(
            "Skip creating the task body file at docs/epics/<epic>-*/tasks/<id>-<slug>.md. "
            "Default behavior is to create it. Use this flag when adding a registry entry "
            "for an existing file or for test fixtures."
        ),
    )
    a.add_argument(
        "--isa",
        action="store_true",
        help=(
            "Also scaffold a per-task ISA at docs/tasks/<id>/ISA.md from "
            "templates/isa.md. Recommended for E2+ tasks."
        ),
    )
    a.add_argument(
        "--allow-missing-epic",
        action="store_true",
        help=(
            "Permit adding a task whose epic is not yet in the registry. Off by "
            "default — a missing epic orphans the task and produces a blocking, "
            "non-auto-fixable consistency finding. Create the epic first with "
            "`forge epic add`. Use this only for staged imports or test fixtures."
        ),
    )
    a.add_argument("--json", action="store_true")
    a.set_defaults(func=cmd_add)

    rf = task.add_parser(
        "reconcile-files",
        help=(
            "Create stub body files for registry-tracked tasks that have no .md "
            "file on disk. Dry-run by default; pass --apply to actually create."
        ),
    )
    rf.add_argument(
        "--apply",
        action="store_true",
        help="Create the stub files. Without this flag, prints what WOULD be created.",
    )
    rf.add_argument("--json", action="store_true")
    rf.set_defaults(func=cmd_reconcile_files)

    L = task.add_parser("lock", help="Lock task and set status=in_progress")
    L.add_argument("id")
    L.add_argument("--session", required=True, help="Session ID for the lock")
    L.add_argument("--json", action="store_true")
    L.set_defaults(func=cmd_lock)

    U = task.add_parser("unlock", help="Clear lock; default new status=continuation")
    U.add_argument("id")
    U.add_argument(
        "--to-status", default="continuation",
        choices=["continuation", "ready", "in_progress"],
        help="Status after unlock (default: continuation)",
    )
    U.add_argument("--json", action="store_true")
    U.set_defaults(func=cmd_unlock)

    C = task.add_parser("complete", help="Mark task completed and unblock dependents")
    C.add_argument("id")
    C.add_argument("--json", action="store_true")
    C.set_defaults(func=cmd_complete)

    P = task.add_parser("pr", help="Transition in_progress -> pr_pending and unblock dependents")
    P.add_argument("id")
    P.add_argument("--json", action="store_true")
    P.set_defaults(func=cmd_pr)

    S = task.add_parser("status", help="Generic status transition (with legality check)")
    S.add_argument("id")
    S.add_argument("new_status", help="Target status")
    S.add_argument("--json", action="store_true")
    S.set_defaults(func=cmd_status)

    ls = task.add_parser("ls", help="List tasks (read-only)")
    ls.add_argument("--ready", action="store_true")
    ls.add_argument("--pending", action="store_true")
    ls.add_argument("--in-progress", dest="in_progress", action="store_true")
    ls.add_argument("--pr-pending", dest="pr_pending", action="store_true")
    ls.add_argument("--completed", action="store_true")
    ls.add_argument("--continuation", action="store_true")
    ls.add_argument("--status", help="Filter by arbitrary status")
    ls.add_argument("--epic", help="Filter by epic ID")
    ls.add_argument("--locked", action="store_true", help="Only locked tasks")
    ls.add_argument("--json", action="store_true")
    ls.set_defaults(func=cmd_ls)

    sh = task.add_parser("show", help="Show full registry entry for a task")
    sh.add_argument("id")
    sh.set_defaults(func=cmd_show)

    rn = task.add_parser(
        "rename",
        help="Rename a task (atomic update of registry name + frontmatter name)",
    )
    rn.add_argument("id", help="Task ID, e.g. T015")
    rn.add_argument("name", help="New task name (one line)")
    rn.add_argument("--json", action="store_true")
    rn.set_defaults(func=cmd_rename)

    sf = task.add_parser(
        "set-file",
        help="Record (or update) the registry's file: field for a task",
    )
    sf.add_argument("id", help="Task ID, e.g. T015")
    sf.add_argument("--file", required=True, help="Relative path to the task markdown file")
    sf.add_argument(
        "--require-exists", action="store_true",
        help="Fail if the target file does not exist on disk",
    )
    sf.add_argument("--json", action="store_true")
    sf.set_defaults(func=cmd_set_file)

    rc = task.add_parser(
        "reconcile-from-files",
        help=(
            "Seed registry entries from orphan task files on disk "
            "(v2 -> v3 migration recovery). Idempotent."
        ),
    )
    rc.add_argument("--json", action="store_true")
    rc.set_defaults(func=cmd_reconcile)

    # epic
    epic = sub.add_parser("epic", help="Epic operations").add_subparsers(
        dest="action", required=True
    )

    ea = epic.add_parser(
        "add",
        help=(
            "Create an epic: registry entry + docs/epics/<id>-<slug>/ dir and "
            "body file. The sanctioned path for epic creation — `task add` "
            "requires the epic to exist first."
        ),
    )
    ea.add_argument("id", help="Epic ID, e.g. E14")
    ea.add_argument("--name", required=True, help="Epic name (one line)")
    ea.add_argument("--description", default="", help="One-paragraph epic summary")
    ea.add_argument("--deps", help="Comma-separated dependency epic IDs")
    ea.add_argument("--priority", type=int, default=1, help="Priority (lower = higher)")
    ea.add_argument("--category", default="", help="Category code (A-T)")
    ea.add_argument(
        "--status",
        choices=["pending", "in_progress", "completed"],
        default="pending",
        help="Initial epic status (default: pending)",
    )
    ea.add_argument(
        "--no-file",
        action="store_true",
        help="Skip creating the on-disk epic dir/body file; registry entry only.",
    )
    ea.add_argument("--json", action="store_true")
    ea.set_defaults(func=cmd_epic_add)

    # agent
    agent = sub.add_parser(
        "agent", help="Background-agent operations (heartbeat, etc.)"
    ).add_subparsers(dest="action", required=True)

    hb = agent.add_parser(
        "heartbeat",
        help=(
            "Report the freshest commit + checkpoint on a branch. Used by "
            "parent sessions to poll background-agent worktree progress "
            "without tailing the agent's transcript."
        ),
    )
    hb.add_argument(
        "branch",
        help="Branch name (or any ref) the background agent is committing to",
    )
    hb.add_argument(
        "--stale-threshold", type=int, default=300,
        help="Seconds after which the head commit is flagged STALE (default 300)",
    )
    hb.add_argument("--json", action="store_true")
    hb.set_defaults(func=cmd_agent_heartbeat)

    # preflight
    pf = sub.add_parser(
        "preflight", help="Pre-push hook installer for /preflight-ci"
    ).add_subparsers(dest="action", required=True)

    pf_enable = pf.add_parser(
        "enable-git-hook",
        help="Install the pre-push hook that runs /preflight-ci when locked tasks require it",
    )
    pf_enable.add_argument(
        "--force",
        action="store_true",
        help="Overwrite an existing non-Forge pre-push hook (default refuses)",
    )
    pf_enable.add_argument("--json", action="store_true")
    pf_enable.set_defaults(func=cmd_preflight_enable_hook)

    pf_disable = pf.add_parser(
        "disable-git-hook",
        help="Remove the Forge pre-push hook (idempotent; only removes if Forge-owned)",
    )
    pf_disable.add_argument("--json", action="store_true")
    pf_disable.set_defaults(func=cmd_preflight_disable_hook)

    # specialist
    spec = sub.add_parser(
        "specialist", help="Project specialist agent operations"
    ).add_subparsers(dest="action", required=True)

    spec_add = spec.add_parser(
        "add", help="Scaffold a new specialist agent + paired EXPERT.md skeleton"
    )
    spec_add.add_argument("name", help="Specialist name (e.g. gateway-expert)")
    spec_add.add_argument(
        "--domain", required=True,
        help="Short description of the domain (e.g. 'API gateway — routing, auth, rate limiting')"
    )
    spec_add.add_argument(
        "--export-path", default="EXPERT.md",
        help="Path for EXPERT.md (relative to project root). Default: EXPERT.md"
    )
    spec_add.add_argument("--json", action="store_true")
    spec_add.set_defaults(func=cmd_specialist_add)

    spec_list = spec.add_parser("list", help="List specialists in this project")
    spec_list.add_argument("--json", action="store_true")
    spec_list.set_defaults(func=cmd_specialist_list)

    # dashboard — local HTTP server serving a unified Forge Flow view
    dash = sub.add_parser(
        "dashboard",
        help="Start the local Forge Flow dashboard (http://127.0.0.1:4847/)",
        description=(
            "Start a local HTTP server serving a tabbed view of this project's "
            "Forge Flow artifacts: Tasks (kanban), Code Map, ISAs, Memory, "
            "Daily logs, raw Registry, and Burndown. Live-reloads via SSE when "
            "underlying files change. Read-only — mutation flows through the "
            "forge CLI per CLAUDE.md."
        ),
    )
    dash.add_argument("--host", default="127.0.0.1",
                      help="bind host (default: 127.0.0.1)")
    dash.add_argument("--port", type=int, default=4847,
                      help="bind port (default: 4847)")
    dash.add_argument("--no-open", action="store_true",
                      help="do not auto-open the browser")
    dash.add_argument("--once", action="store_true",
                      help="render the index page to stdout once and exit (no server)")
    dash.set_defaults(func=cmd_dashboard)

    # version — print the framework version from the repo-root VERSION file
    ver = sub.add_parser(
        "version",
        help="Print the installed framework version",
    )
    ver.set_defaults(func=cmd_version)

    # doctor — read-only install health check
    doc = sub.add_parser(
        "doctor",
        help="Read-only install health check (version, orphans, registry, hook wiring)",
        description=(
            "Report the health of this Forge Flow install: installed version, "
            "retired paths (cut-paths.txt) still on disk, task-registry "
            "consistency, and hook wiring. Read-only and offline — reports, "
            "never mutates. Exit 0 healthy, 1 findings, 2 no install found."
        ),
    )
    doc.add_argument("--json", action="store_true", help="emit machine-readable JSON")
    doc.add_argument("--all", type=Path, default=None, metavar="DIR",
                      help="fleet sweep: discover installs under DIR and print one summary "
                           "row per install (depth-bounded, immediate + one level of children)")
    doc.add_argument("--banner", action="store_true",
                      help="SessionStart banner: cheap version+orphans check, silent when "
                           "healthy, one line when not, always exits 0")
    doc.set_defaults(func=cmd_doctor)

    return p


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    project_root = get_project_root(args.project_root)
    return args.func(args, project_root)


if __name__ == "__main__":
    sys.exit(main())
