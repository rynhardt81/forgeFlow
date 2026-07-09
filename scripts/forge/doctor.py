#!/usr/bin/env python3
"""
forge doctor — read-only, offline install health check (v1).

Run inside any project that vendors Forge Flow (or inside the framework
repo itself) and get a health report for the install:

  1. version  — installed framework version (.claude/VERSION / VERSION)
  2. orphans  — retired paths (cut-paths.txt) that still exist on disk
  3. registry — task registry parses; check_consistency finding counts
  4. wiring   — every hook wired in hooks/settings.json exists on disk

Exit codes: 0 = healthy, 1 = findings, 2 = cannot diagnose (no install).

Modes:
  (default)  Run all 4 checks against one install. Human or --json output.
  --all DIR  Fleet sweep: depth-bounded discovery of installs under DIR,
             one summary row per install (version/stale/orphans/findings).
             Exit 1 if any discovered install is unhealthy.
  --banner   SessionStart banner: cheap version+orphans subset only (no
             check_consistency subprocess). Silent when healthy, exactly
             one line when not, always exits 0 — informational only, a
             hook must never fail the session on doctor's account.

Binding constraints (plans/008): doctor NEVER mutates and NEVER touches
the network. It shells out to the co-located check_consistency.py rather
than importing it, and never passes --fix.

Design doc: plans/008 design (008-doctor-design.md).
"""

from __future__ import annotations

import argparse
import json
import os
import re
import subprocess
import sys
from dataclasses import asdict, dataclass, field
from pathlib import Path

SCRIPT_DIR = Path(__file__).resolve().parent

# Path of the retired-paths ledger relative to framework_root. Identical in
# both layouts: the framework repo has it natively; consumers get it once the
# designed installer change (ship the manifest, single-file copy) lands.
CUT_PATHS_REL = Path("scripts") / "install" / "cut-paths.txt"

# Transplanted from tests/wiring/test_settings_hooks_exist.py — the proven
# extractor for hook script paths inside settings.json command strings.
_WIRED_HOOK_RE = re.compile(r"\.claude/(hooks/[\w\-/]+\.py)")

OK = "ok"
ISSUES = "issues"
SKIPPED = "skipped"

_STATUS_MARK = {OK: "[ok]", ISSUES: "[!!]", SKIPPED: "[--]"}


@dataclass
class CheckResult:
    name: str
    status: str  # ok | issues | skipped
    summary: str
    findings: list[str] = field(default_factory=list)
    hint: str | None = None


@dataclass
class DoctorContext:
    project_root: Path
    framework_root: Path
    layout: str  # "consumer" | "framework-repo"


def get_project_root(override: Path | None = None) -> Path:
    """Resolve project root — same order as forge.py / check_consistency.py.

    Order: explicit override -> CLAUDE_PROJECT_DIR env -> docs/tasks/registry.json
    walk -> git toplevel -> cwd. Duplicated (not imported) so doctor.py stays
    runnable standalone; check_consistency.py sets the same precedent.
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


def resolve_framework_root(project_root: Path) -> tuple[Path, str] | None:
    """Locate the framework install relative to project_root.

    Consumer layout: framework vendored at <project_root>/.claude/.
    Framework repo:  hooks/, scripts/forge/ live at the repo root.
    Returns (framework_root, layout) or None when no install is found.
    """
    claude = project_root / ".claude"
    if (claude / "hooks" / "settings.json").is_file() or (claude / "VERSION").is_file():
        return claude, "consumer"
    if (project_root / "hooks" / "settings.json").is_file() and (
        project_root / "scripts" / "forge"
    ).is_dir():
        return project_root, "framework-repo"
    return None


# --- Checks ----------------------------------------------------------------
# A check is one function DoctorContext -> CheckResult. To add a check,
# write the function and append it to CHECKS at the bottom of this section.


def check_version(ctx: DoctorContext) -> CheckResult:
    version_file = ctx.framework_root / "VERSION"
    if not version_file.is_file():
        return CheckResult(
            name="version",
            status=ISSUES,
            summary="unknown",
            findings=["VERSION file not found (pre-4.2 install?)"],
            hint="run a framework refresh to stamp the installed version",
        )
    content = version_file.read_text().strip()
    if not re.match(r"^\d+\.\d+\.\d+$", content):
        return CheckResult(
            name="version",
            status=ISSUES,
            summary=content or "(empty)",
            findings=[f"VERSION file is not semver: {content!r}"],
            hint="run a framework refresh to restamp the version",
        )
    return CheckResult(name="version", status=OK, summary=content)


def check_orphans(ctx: DoctorContext) -> CheckResult:
    manifest = ctx.framework_root / CUT_PATHS_REL
    if not manifest.is_file():
        return CheckResult(
            name="orphans",
            status=SKIPPED,
            summary="cut-paths manifest not shipped (pre-4.2 install)",
            hint="refresh the framework to ship the manifest and enable this check",
        )
    orphans: list[str] = []
    for raw in manifest.read_text().splitlines():
        line = raw.strip()
        if not line or line.startswith("#"):
            continue
        # Defensive mirrors of the installer's manifest validation — a
        # hostile/broken entry must not let a read-only check escape root.
        if line.startswith("/") or ".." in line.split("/"):
            continue
        rel = line.rstrip("/")
        if (ctx.framework_root / rel).exists():
            orphans.append(rel)
    if orphans:
        return CheckResult(
            name="orphans",
            status=ISSUES,
            summary=f"{len(orphans)} retired path(s) still on disk",
            findings=orphans,
            hint="run a framework refresh to sweep retired paths",
        )
    return CheckResult(name="orphans", status=OK, summary="none")


def check_registry(ctx: DoctorContext) -> CheckResult:
    registry = ctx.project_root / "docs" / "tasks" / "registry.json"
    if not registry.is_file():
        return CheckResult(
            name="registry",
            status=SKIPPED,
            summary="no task registry (docs/tasks/registry.json)",
        )
    try:
        json.loads(registry.read_text())
    except (json.JSONDecodeError, OSError) as exc:
        return CheckResult(
            name="registry",
            status=ISSUES,
            summary="registry.json does not parse",
            findings=[f"registry.json unreadable: {exc}"],
        )

    checker = SCRIPT_DIR / "check_consistency.py"
    try:
        # Read-only invocation by construction: no --fix, ever.
        proc = subprocess.run(
            [sys.executable, str(checker), "--json",
             "--project-root", str(ctx.project_root)],
            capture_output=True, text=True, timeout=60,
        )
        payload = json.loads(proc.stdout)
        findings = payload.get("findings", [])
    except (subprocess.SubprocessError, OSError, json.JSONDecodeError, ValueError) as exc:
        return CheckResult(
            name="registry",
            status=ISSUES,
            summary="check_consistency could not run",
            findings=[f"check_consistency --json failed: {exc}"],
        )

    if findings:
        by_severity: dict[str, int] = {}
        for f in findings:
            sev = f.get("severity", "unknown")
            by_severity[sev] = by_severity.get(sev, 0) + 1
        breakdown = ", ".join(f"{n} {sev}" for sev, n in sorted(by_severity.items()))
        shown = [f.get("message", "(no message)") for f in findings[:10]]
        if len(findings) > 10:
            shown.append(f"... and {len(findings) - 10} more (run check_consistency.py --json)")
        return CheckResult(
            name="registry",
            status=ISSUES,
            summary=f"{len(findings)} consistency finding(s) ({breakdown})",
            findings=shown,
            hint="run check_consistency.py --fix (or let the SessionStart banner auto-fix)",
        )
    return CheckResult(name="registry", status=OK, summary="parses; 0 consistency findings")


def _load_json(path: Path) -> dict | None:
    """Best-effort JSON load. None on missing/unreadable/unparseable file —
    callers decide whether that's fatal for their candidate source."""
    if not path.is_file():
        return None
    try:
        return json.loads(path.read_text())
    except (json.JSONDecodeError, OSError):
        return None


def _wiring_source(ctx: DoctorContext) -> tuple[Path, dict] | None:
    """Locate the live hook-wiring source and return (path, hooks-merged-data).

    Framework-repo layout ships hooks/settings.json natively — use it alone.

    Consumer layout never receives hooks/settings.json (install.sh's rsync
    excludes settings.json by basename); wiring is merged into the live
    `.claude/settings.json` instead (framework_root/settings.json here,
    since framework_root == <project_root>/.claude for consumers). When a
    settings.local.json sits alongside it, its "hooks" block (if any) is
    merged in too — union by event, local entries appended after framework
    entries for that event.

    Returns None when no candidate source exists at all.
    """
    fw_settings = ctx.framework_root / "hooks" / "settings.json"
    if fw_settings.is_file():
        data = _load_json(fw_settings)
        if data is not None:
            return fw_settings, data
        # Exists but unparseable — still the source of record; report on it.
        return fw_settings, {}

    live_settings = ctx.framework_root / "settings.json"
    if live_settings.is_file():
        data = _load_json(live_settings) or {}
        local_settings = ctx.framework_root / "settings.local.json"
        local_data = _load_json(local_settings) if local_settings.is_file() else None
        if local_data:
            merged_hooks = dict(data.get("hooks", {}))
            for event, entries in local_data.get("hooks", {}).items():
                merged_hooks[event] = merged_hooks.get(event, []) + entries
            data = {**data, "hooks": merged_hooks}
        return live_settings, data

    return None


def check_wiring(ctx: DoctorContext) -> CheckResult:
    source = _wiring_source(ctx)
    if source is None:
        return CheckResult(
            name="wiring",
            status=ISSUES,
            summary="no hook wiring found (no settings.json with hooks)",
            findings=["no hook wiring found (no settings.json with hooks)"],
            hint="run a framework refresh to restore hook wiring",
        )
    settings, data = source
    if not data:
        rel = settings.relative_to(ctx.framework_root)
        return CheckResult(
            name="wiring",
            status=ISSUES,
            summary=f"{rel} does not parse",
            findings=[f"{rel} unreadable or invalid JSON"],
        )

    missing: list[str] = []
    wired_count = 0
    for event, matchers in data.get("hooks", {}).items():
        for matcher in matchers:
            for hook in matcher.get("hooks", []):
                m = _WIRED_HOOK_RE.search(hook.get("command", ""))
                if not m:
                    continue
                wired_count += 1
                rel = m.group(1)
                if not (ctx.framework_root / rel).is_file():
                    missing.append(f"{event}: {rel} (wired but not on disk)")
    if missing:
        return CheckResult(
            name="wiring",
            status=ISSUES,
            summary=f"{len(missing)} wired hook file(s) missing",
            findings=missing,
            hint="run a framework refresh to restore hook files",
        )
    return CheckResult(
        name="wiring", status=OK,
        summary=f"{wired_count} wired hook path(s), all on disk",
    )


CHECKS = [
    check_version,
    check_orphans,
    check_registry,
    check_wiring,
]


# --- Reporting ---------------------------------------------------------------


def _format_human(ctx: DoctorContext, results: list[CheckResult], healthy: bool) -> str:
    lines = [
        "forge doctor — Forge Flow install health",
        f"  layout:         {ctx.layout}",
        f"  project_root:   {ctx.project_root}",
        f"  framework_root: {ctx.framework_root}",
        "",
    ]
    for r in results:
        lines.append(f"  {_STATUS_MARK[r.status]} {r.name}: {r.summary}")
        for f in r.findings:
            lines.append(f"        - {f}")
        if r.hint and r.status != OK:
            lines.append(f"        hint: {r.hint}")
    lines.append("")
    issue_count = sum(1 for r in results if r.status == ISSUES)
    lines.append(
        "healthy: yes" if healthy else f"healthy: no ({issue_count} check(s) with findings)"
    )
    return "\n".join(lines)


def _format_json(ctx: DoctorContext, results: list[CheckResult], healthy: bool) -> str:
    version = next((r.summary for r in results if r.name == "version" and r.status == OK), None)
    return json.dumps(
        {
            "healthy": healthy,
            "layout": ctx.layout,
            "project_root": str(ctx.project_root),
            "framework_root": str(ctx.framework_root),
            "version": version,
            "checks": [asdict(r) for r in results],
        },
        indent=2,
    )


def diagnose(project_root: Path) -> tuple[DoctorContext, list[CheckResult], bool] | None:
    """Run the check suite against project_root. None when no install is found."""
    resolved = resolve_framework_root(project_root)
    if resolved is None:
        return None
    framework_root, layout = resolved
    ctx = DoctorContext(
        project_root=project_root, framework_root=framework_root, layout=layout
    )
    results = [check(ctx) for check in CHECKS]
    healthy = all(r.status != ISSUES for r in results)
    return ctx, results, healthy


def run(project_root: Path, as_json: bool = False) -> int:
    diagnosis = diagnose(project_root)
    if diagnosis is None:
        msg = f"no Forge Flow install found at {project_root} (no .claude/ install, not the framework repo)"
        if as_json:
            print(json.dumps({"healthy": False, "error": msg}, indent=2))
        else:
            print(f"forge doctor: {msg}", file=sys.stderr)
        return 2

    ctx, results, healthy = diagnosis
    print(_format_json(ctx, results, healthy) if as_json else _format_human(ctx, results, healthy))
    return 0 if healthy else 1


# --- Fleet sweep (--all) -----------------------------------------------------
#
# Discover multiple installs under one parent directory and report one
# summary row per install. Depth-bounded scan only — never unbounded
# recursion (this is a read-only tool but a fleet directory can be huge).


def discover_installs(parent: Path) -> list[Path]:
    """Find installs under parent: immediate children, and their immediate
    children (2 levels deep from parent), each tested for either
    <candidate>/.claude/VERSION or <candidate>/.claude/hooks/settings.json.

    Depth-bounded by construction — iterdir() twice, never os.walk/rglob.
    """
    found: list[Path] = []
    if not parent.is_dir():
        return found

    def is_install(candidate: Path) -> bool:
        claude = candidate / ".claude"
        return (claude / "VERSION").is_file() or (claude / "hooks" / "settings.json").is_file()

    def children(d: Path) -> list[Path]:
        try:
            return sorted(p for p in d.iterdir() if p.is_dir() and not p.name.startswith("."))
        except OSError:
            return []

    level1 = children(parent)
    for c1 in level1:
        if is_install(c1):
            found.append(c1)
            continue  # an install directory's own children aren't a nested fleet
        for c2 in children(c1):
            if is_install(c2):
                found.append(c2)

    return found


def _reference_version(project_root: Path) -> str | None:
    """The framework repo's own VERSION, when doctor is running from one.

    Offline by construction: a local file read of doctor's own checkout,
    never a network call. None when doctor itself is running from a
    consumer install (no reference available -> stale shows "n/a").
    """
    resolved = resolve_framework_root(project_root)
    if resolved is None:
        return None
    framework_root, layout = resolved
    if layout != "framework-repo":
        return None
    version_file = framework_root / "VERSION"
    if not version_file.is_file():
        return None
    content = version_file.read_text().strip()
    return content or None


@dataclass
class FleetRow:
    name: str
    path: str
    version: str | None
    stale: bool | None  # None => "n/a" (no reference version available)
    orphans_count: int
    findings_count: int
    healthy: bool
    error: str | None = None


def _fleet_row(root: Path, reference_version: str | None) -> FleetRow:
    diagnosis = diagnose(root)
    if diagnosis is None:
        return FleetRow(
            name=root.name, path=str(root), version=None, stale=None,
            orphans_count=0, findings_count=0, healthy=False,
            error="no Forge Flow install found",
        )
    ctx, results, healthy = diagnosis
    version = next((r.summary for r in results if r.name == "version" and r.status == OK), None)
    orphans = next((r for r in results if r.name == "orphans"), None)
    orphans_count = len(orphans.findings) if orphans else 0
    findings_count = sum(len(r.findings) for r in results)
    stale: bool | None
    if reference_version is None or version is None:
        stale = None
    else:
        stale = version != reference_version
    return FleetRow(
        name=root.name, path=str(root), version=version, stale=stale,
        orphans_count=orphans_count, findings_count=findings_count, healthy=healthy,
    )


def _format_fleet_human(rows: list[FleetRow], reference_version: str | None, parent: Path) -> str:
    lines = [
        "forge doctor --all — fleet sweep",
        f"  scanned:   {parent}",
        f"  reference: {reference_version if reference_version else 'n/a (not running from the framework repo)'}",
        "",
    ]
    if not rows:
        lines.append("  (no installs found)")
        lines.append("")
        lines.append("healthy: yes (nothing to check)")
        return "\n".join(lines)

    for row in rows:
        mark = "[ok]" if row.healthy else "[!!]"
        if row.error:
            lines.append(f"  {mark} {row.name}: {row.error}")
            continue
        stale_str = "n/a" if row.stale is None else ("STALE" if row.stale else "current")
        version_str = row.version or "unknown"
        lines.append(
            f"  {mark} {row.name}: version={version_str} ({stale_str})"
            f" orphans={row.orphans_count} findings={row.findings_count}"
        )
    lines.append("")
    all_healthy = all(r.healthy for r in rows)
    unhealthy_count = sum(1 for r in rows if not r.healthy)
    lines.append(
        "healthy: yes" if all_healthy else f"healthy: no ({unhealthy_count} install(s) unhealthy)"
    )
    return "\n".join(lines)


def _format_fleet_json(rows: list[FleetRow], reference_version: str | None, parent: Path) -> str:
    all_healthy = all(r.healthy for r in rows) if rows else True
    return json.dumps(
        {
            "healthy": all_healthy,
            "scanned": str(parent),
            "reference_version": reference_version,
            "installs": [asdict(r) for r in rows],
        },
        indent=2,
    )


def run_all(project_root: Path, parent: Path, as_json: bool = False) -> int:
    reference_version = _reference_version(project_root)
    roots = discover_installs(parent)
    rows = [_fleet_row(root, reference_version) for root in roots]

    print(_format_fleet_json(rows, reference_version, parent) if as_json
          else _format_fleet_human(rows, reference_version, parent))

    all_healthy = all(r.healthy for r in rows) if rows else True
    return 0 if all_healthy else 1


# --- SessionStart banner (--banner) ------------------------------------------
#
# Cheap subset only: version + orphans, both pure stat/read calls — no
# check_consistency subprocess. Silent when healthy; exactly one line when
# not. Always exits 0 — this is informational, a hook must never fail the
# session on doctor's account.


def run_banner(project_root: Path) -> int:
    resolved = resolve_framework_root(project_root)
    if resolved is None:
        return 0  # not a Forge Flow install (or none found) — nothing to say

    framework_root, layout = resolved
    ctx = DoctorContext(project_root=project_root, framework_root=framework_root, layout=layout)

    version_result = check_version(ctx)
    if version_result.status == ISSUES:
        if version_result.summary == "unknown":
            print("forge doctor: version unknown (pre-4.2) — run a refresh")
        else:
            print(f"forge doctor: version {version_result.summary!r} malformed — run a refresh")
        return 0

    orphans_result = check_orphans(ctx)
    if orphans_result.status == ISSUES:
        print(
            f"forge doctor: {len(orphans_result.findings)} retired framework file(s) "
            "present — run a refresh"
        )
        return 0

    return 0  # healthy (or skipped, e.g. no manifest yet) — silent


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Read-only Forge Flow install health check (version, orphans, registry, wiring)."
    )
    parser.add_argument("--json", action="store_true", dest="as_json",
                        help="emit machine-readable JSON")
    parser.add_argument("--project-root", type=Path, default=None,
                        help="override project root detection (mostly for testing)")
    parser.add_argument("--all", type=Path, default=None, metavar="DIR",
                        help="fleet sweep: discover installs under DIR (depth-bounded) "
                             "and print one summary row per install")
    parser.add_argument("--banner", action="store_true",
                        help="SessionStart banner: cheap version+orphans check, silent "
                             "when healthy, one line when not, always exits 0")
    args = parser.parse_args(argv)
    resolved_project_root = get_project_root(args.project_root)
    if args.banner:
        return run_banner(resolved_project_root)
    if args.all is not None:
        return run_all(resolved_project_root, args.all, as_json=args.as_json)
    return run(resolved_project_root, as_json=args.as_json)


if __name__ == "__main__":
    sys.exit(main())
