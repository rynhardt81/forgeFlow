#!/usr/bin/env python3
"""
session-context.py
SessionStart hook to provide context on startup/resume/compact (cross-platform Python)

Outputs:
- Session status and active skill/agent detection
- Task registry status
- Project memory index (accumulated knowledge from prior sessions)
- Recent conversation digest (last session's learnings)

Uses CLAUDE_ENV_FILE to persist environment variables for subsequent bash commands.

NOTE: When deployed to a target project, this script lives at:
  {project}/.claude/hooks/session/session-context.py
"""

import json
import os
import re
import secrets
import string
import subprocess
import sys
from datetime import datetime
from pathlib import Path


def get_project_root():
    """Get the project root directory."""
    if os.environ.get('CLAUDE_PROJECT_DIR'):
        return Path(os.environ['CLAUDE_PROJECT_DIR'])
    try:
        result = subprocess.run(
            ['git', 'rev-parse', '--show-toplevel'],
            capture_output=True, text=True, check=True
        )
        return Path(result.stdout.strip())
    except (subprocess.CalledProcessError, FileNotFoundError):
        return Path.cwd()


def get_claude_dir(project_root):
    """Get the Claude directory based on project structure."""
    claude_memories = project_root / '.claude' / 'memories'
    if claude_memories.exists():
        return project_root / '.claude'
    return project_root


def find_active_session(claude_dir):
    """Find the most recent active session file."""
    active_dir = claude_dir / 'memories' / 'sessions' / 'active'
    if not active_dir.exists():
        return None

    try:
        sessions = [
            f for f in active_dir.iterdir()
            if f.name.startswith('session-') and f.suffix == '.md'
        ]
        if not sessions:
            return None
        # Sort by modification time, newest first
        sessions.sort(key=lambda f: f.stat().st_mtime, reverse=True)
        return sessions[0]
    except (OSError, IOError):
        return None


def _current_branch(project_root):
    """Best-effort current branch lookup. Returns 'unknown' on failure."""
    try:
        result = subprocess.run(
            ['git', 'rev-parse', '--abbrev-ref', 'HEAD'],
            cwd=project_root, capture_output=True, text=True, check=False,
        )
        if result.returncode == 0 and result.stdout.strip():
            return result.stdout.strip()
    except (OSError, subprocess.SubprocessError):
        pass
    return 'unknown'


def _generate_session_id():
    """Format: {YYYYMMDD-HHMMSS}-{4-random-chars}. Matches reference/12."""
    now = datetime.now()
    stamp = now.strftime('%Y%m%d-%H%M%S')
    alphabet = string.ascii_lowercase + string.digits
    suffix = ''.join(secrets.choice(alphabet) for _ in range(4))
    return f'{stamp}-{suffix}'


def _auto_create_session_file(claude_dir, project_root):
    """Create a minimal session file when active/ is empty.

    Enforces 'Session Protocol First' from skills/reflect/SKILL.md by making
    the framework — not the user — responsible for ensuring a session file
    exists. The created file is intentionally minimal: scope is left empty
    (to be filled in by /reflect resume or by the agent when work starts);
    Active Skill / Active Agent are 'none'. Conflict check is deferred.

    Returns the Path to the created file, or None if creation failed (in
    which case session-context falls back to S:NONE, same as before — the
    hook never blocks SessionStart).
    """
    active_dir = claude_dir / 'memories' / 'sessions' / 'active'
    try:
        active_dir.mkdir(parents=True, exist_ok=True)
    except OSError:
        return None

    # Re-check inside the create path — race-safe against parallel hooks
    try:
        existing = [
            f for f in active_dir.iterdir()
            if f.name.startswith('session-') and f.suffix == '.md'
        ]
        if existing:
            return None  # someone beat us to it; back off cleanly
    except OSError:
        return None

    sid = _generate_session_id()
    branch = _current_branch(project_root)
    started = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
    target = active_dir / f'session-{sid}.md'

    body = (
        f"# Session {sid}\n"
        f"\n"
        f"**Started**: {started}\n"
        f"**Branch**: {branch}\n"
        f"**Status**: active\n"
        f"**Created by**: session-context.py auto-create (SessionStart)\n"
        f"\n"
        f"> This file was auto-created at SessionStart so the 'Session Protocol\n"
        f"> First' rule is always true. Scope is empty until work begins — when\n"
        f"> the agent or `/reflect resume` starts a real task, the Scope\n"
        f"> Declaration, Conflict Check, and skill/agent tables get filled in.\n"
        f"\n"
        f"---\n"
        f"\n"
        f"## Scope Declaration\n"
        f"\n"
        f"**Branch**: `{branch}`\n"
        f"\n"
        f"**Directories**:\n"
        f"- (none declared — fill in when work begins)\n"
        f"\n"
        f"**Files** (if specific):\n"
        f"- (none)\n"
        f"\n"
        f"**Features/Areas**:\n"
        f"- (none declared)\n"
        f"\n"
        f"---\n"
        f"\n"
        f"## Conflict Check\n"
        f"\n"
        f"_Deferred — no scope declared yet. `/reflect resume` runs the conflict\n"
        f"scan when scope is set._\n"
        f"\n"
        f"---\n"
        f"\n"
        f"## Active Skill\n"
        f"\n"
        f"| Field | Value |\n"
        f"|-------|-------|\n"
        f"| **Skill** | none |\n"
        f"| **Phase** | - |\n"
        f"\n"
        f"---\n"
        f"\n"
        f"## Active Agent\n"
        f"\n"
        f"| Field | Value |\n"
        f"|-------|-------|\n"
        f"| **Agent** | none |\n"
        f"| **Workflow** | - |\n"
        f"| **Phase** | - |\n"
        f"\n"
        f"---\n"
        f"\n"
        f"## Completed\n"
        f"\n"
        f"_(filled in as work lands)_\n"
        f"\n"
        f"## Continuation Context\n"
        f"\n"
        f"_(filled in if the session ends with in-progress work)_\n"
    )
    try:
        target.write_text(body, encoding='utf-8')
        return target
    except OSError:
        return None


def extract_from_table(content, section, field):
    """Extract a value from a markdown table within a section."""
    # Find the section
    section_pattern = rf'## {re.escape(section)}[\s\S]*?(?=##|$)'
    section_match = re.search(section_pattern, content, re.IGNORECASE)
    if not section_match:
        return None

    # Find the field in the table
    field_pattern = rf'\*\*{re.escape(field)}\*\*\s*\|\s*([^|\n]+)'
    field_match = re.search(field_pattern, section_match.group(0), re.IGNORECASE)
    if not field_match:
        return None

    value = field_match.group(1).strip().replace('`', '')
    if value in ('none', '-', ''):
        return None
    return value


def read_json_safe(file_path):
    """Read a JSON file safely, returning None on error."""
    try:
        with open(file_path, 'r', encoding='utf-8') as f:
            return json.load(f)
    except (OSError, json.JSONDecodeError):
        return None


def write_env_var(env_file, name, value):
    """Write an environment variable to the env file."""
    if env_file and value:
        with open(env_file, 'a', encoding='utf-8') as f:
            f.write(f'export {name}="{value}"\n')


def main():
    project_root = get_project_root()
    claude_dir = get_claude_dir(project_root)
    env_file = os.environ.get('CLAUDE_ENV_FILE')

    context = ['=== FORGE ===']

    # Session status — auto-create if active/ is empty, then re-scan.
    # This is what makes "Session Protocol First" actually enforced: the
    # framework owns ensuring a session file exists at SessionStart.
    if find_active_session(claude_dir) is None:
        _auto_create_session_file(claude_dir, project_root)

    active_session = find_active_session(claude_dir)
    if active_session:
        sid = active_session.stem.replace('session-', '')
        context.append(f'S:{sid}')
        write_env_var(env_file, 'FORGE_SESSION_ID', sid)

        # Read session content for skill/agent detection
        session_content = ''
        try:
            session_content = active_session.read_text(encoding='utf-8')
        except (OSError, IOError):
            pass

        # Check for Phase 3 in-progress
        phase3_file = claude_dir / 'memories' / 'phase3-progress.json'
        phase3_data = read_json_safe(phase3_file)
        if phase3_data and phase3_data.get('status') == 'in_progress':
            ep = phase3_data.get('epicsPlanned', 0)
            ec = phase3_data.get('epicsCreated', 0)
            tp = phase3_data.get('tasksPlanned', 0)
            tc = phase3_data.get('tasksCreated', 0)
            context.append(f'P3:INCOMPLETE E{ec}/{ep} T{tc}/{tp}')
            context.append('->Resume Phase 3: Read .claude/memories/phase3-progress.json')

        # Check for active skill
        active_skill = extract_from_table(session_content, 'Active Skill', 'Skill')
        if active_skill:
            skill_phase = extract_from_table(session_content, 'Active Skill', 'Phase') or 'unknown'
            context.append(f'SK:{active_skill}@{skill_phase}')
            context.append(f'->Re-invoke {active_skill} via Skill tool to resume')
            write_env_var(env_file, 'FORGE_ACTIVE_SKILL', active_skill)
            write_env_var(env_file, 'FORGE_SKILL_PHASE', skill_phase)

        # Check for active agent
        active_agent = extract_from_table(session_content, 'Active Agent', 'Agent')
        if active_agent:
            agent_workflow = extract_from_table(session_content, 'Active Agent', 'Workflow') or 'unknown'
            agent_phase = extract_from_table(session_content, 'Active Agent', 'Phase') or 'unknown'
            context.append(f'AG:{active_agent}@{agent_workflow}:{agent_phase}')
            context.append(f'->Reload {active_agent} summary to resume')
            write_env_var(env_file, 'FORGE_ACTIVE_AGENT', active_agent)
    else:
        context.append('S:NONE')

    # Registry status
    registry_path = project_root / 'docs' / 'tasks' / 'registry.json'
    registry = read_json_safe(registry_path)

    if registry and 'tasks' in registry:
        tasks = registry['tasks']
        ready = sum(1 for t in tasks if t.get('status') == 'ready')
        prog = sum(1 for t in tasks if t.get('status') == 'in_progress')
        done = sum(1 for t in tasks if t.get('status') == 'completed')
        total = len(tasks)

        context.append(f'T:{done}/{total}|R{ready}|A{prog}')
        write_env_var(env_file, 'FORGE_TASKS_READY', str(ready))
        write_env_var(env_file, 'FORGE_TASKS_IN_PROGRESS', str(prog))
        write_env_var(env_file, 'FORGE_TASKS_COMPLETED', str(done))
    else:
        context.append('T:NONE')

    # --- Project Memory Injection ---
    # Inject accumulated knowledge so Claude starts aware of project context
    memory_index = project_root / 'docs' / 'project-memory' / 'index.md'
    if memory_index.exists():
        try:
            index_content = memory_index.read_text(encoding='utf-8')
            if index_content.strip() and '_No entries yet._' not in index_content:
                # Truncate to stay within reasonable token budget
                max_chars = 20000
                if len(index_content) > max_chars:
                    index_content = index_content[:max_chars] + '\n[...truncated]'
                context.append('')
                context.append('=== PROJECT MEMORY ===')
                context.append(index_content)
                context.append('===')
                write_env_var(env_file, 'FORGE_MEMORY_LOADED', 'true')
        except (OSError, IOError):
            pass

    # Inject recent daily log for latest conversation context
    daily_dir = project_root / 'daily'
    if daily_dir.exists():
        try:
            logs = sorted(daily_dir.glob('*.md'), reverse=True)
            if logs:
                recent_log = logs[0].read_text(encoding='utf-8')
                # Take last ~30 lines to keep it compact
                lines = recent_log.splitlines()
                if len(lines) > 30:
                    lines = lines[-30:]
                recent_text = '\n'.join(lines)
                if recent_text.strip():
                    context.append('')
                    context.append('=== RECENT SESSION LOG ===')
                    context.append(recent_text)
                    context.append('===')
        except (OSError, IOError):
            pass

    # Also load key-facts.md fully (small file, always relevant)
    key_facts = project_root / 'docs' / 'project-memory' / 'key-facts.md'
    if key_facts.exists():
        try:
            facts_content = key_facts.read_text(encoding='utf-8')
            # Only inject if it has real content (not just template comments)
            has_content = any(
                line.strip().startswith('- **')
                for line in facts_content.splitlines()
            )
            if has_content:
                context.append('')
                context.append('=== KEY FACTS ===')
                context.append(facts_content)
                context.append('===')
        except (OSError, IOError):
            pass

    # --- Code Map Injection ---
    # Auto-regenerate if stale and inject summary block so Claude knows project
    # structure on every session start. Cap runtime so a slow regen never blocks.
    # Try both layouts: deployed (skills under .claude/) and framework-dev (skills at root).
    code_map_tool = None
    for candidate in (
        claude_dir / 'skills' / 'audit-code-map' / 'Tools' / 'code_map.py',
        project_root / 'skills' / 'audit-code-map' / 'Tools' / 'code_map.py',
    ):
        if candidate.exists():
            code_map_tool = candidate
            break
    if code_map_tool:
        try:
            result = subprocess.run(
                ['python3', str(code_map_tool), '--ensure-fresh', '--root', str(project_root)],
                capture_output=True, text=True, timeout=8,
            )
            map_summary = (result.stdout or result.stderr).strip()
            if map_summary:
                context.append('')
                context.append(map_summary)
        except (subprocess.SubprocessError, OSError):
            # Never block SessionStart on code-map issues
            pass

    # --- Path-Scoped Skills Surfacing ---
    # Skills with a "paths" field in skills-manifest.json are scoped to certain
    # directories. When the session's cwd lives inside one of those paths,
    # surface those skills so the model knows they're available without
    # exhaustively listing every skill on every session start.
    manifest_file = None
    for candidate in (
        claude_dir / 'skills' / 'skills-manifest.json',
        project_root / 'skills' / 'skills-manifest.json',
    ):
        if candidate.exists():
            manifest_file = candidate
            break
    if manifest_file:
        try:
            manifest = json.loads(manifest_file.read_text(encoding='utf-8'))
            cwd = Path.cwd()
            try:
                rel = cwd.relative_to(project_root).as_posix()
            except ValueError:
                rel = ''
            # If cwd is the project root, rel is '.' — fnmatch against '.' won't
            # match component-prefixed globs, so use '' as the comparable form.
            if rel == '.':
                rel = ''
            relevant = []
            for skill in manifest.get('skills', []):
                paths = skill.get('paths') or []
                if not paths:
                    continue
                # Match if any glob matches either the cwd-relative path or any
                # of its parent path segments (so "components/" matches when
                # cwd is "components/foo/bar").
                import fnmatch
                hit = False
                for pat in paths:
                    # Strip trailing /** for prefix-style match
                    prefix = pat.rstrip('*').rstrip('/')
                    if rel and (rel == prefix or rel.startswith(prefix + '/')):
                        hit = True
                        break
                    if fnmatch.fnmatch(rel, pat):
                        hit = True
                        break
                if hit:
                    relevant.append(skill.get('command') or f"/{skill.get('name')}")
            if relevant:
                context.append('')
                context.append('=== PATH-SCOPED SKILLS ===')
                context.append(f"cwd: {rel or '<root>'}")
                context.append('available here: ' + ', '.join(relevant))
                context.append('===')
        except (OSError, json.JSONDecodeError):
            # Never block SessionStart on a malformed manifest
            pass

    # Compact context reminder
    context.append('CTX:s+r+t+sk+ag+mem+map+psk')
    context.append('===')

    print('\n'.join(context))
    sys.exit(0)


if __name__ == '__main__':
    main()
