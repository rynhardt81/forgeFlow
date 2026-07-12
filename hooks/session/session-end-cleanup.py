#!/usr/bin/env python3
"""
session-end-cleanup.py
SessionEnd hook - runs when session truly ends (logout, clear, exit)
Cross-platform Python version

Handles:
1. Logging session end to progress notes
2. Cleaning up stale task locks

Input JSON includes:
  - reason: "clear" | "logout" | "prompt_input_exit" | "other"

Exit codes:
  0 - Success
  2 - Error (logged but doesn't block exit)

NOTE: When deployed to a target project, this script lives at:
  {project}/.claude/hooks/session/session-end-cleanup.py
"""

import json
import os
import subprocess
import sys
from datetime import datetime
from pathlib import Path

# Non-blocking stdin read (a plain json.load(sys.stdin) hangs forever on an
# open, idle pipe).
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from _hooklib import read_stdin_input  # noqa: E402


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
        sessions.sort(key=lambda f: f.stat().st_mtime, reverse=True)
        return sessions[0]
    except (OSError, IOError):
        return None


def read_json_safe(file_path):
    """Read a JSON file safely, returning None on error."""
    try:
        with open(file_path, 'r', encoding='utf-8') as f:
            return json.load(f)
    except (OSError, json.JSONDecodeError):
        return None


def main():
    project_root = get_project_root()
    claude_dir = get_claude_dir(project_root)

    # Read input from stdin (JSON with session end info); non-blocking so a
    # manual / open-pipe invocation can't hang the SessionEnd hook.
    input_data = read_stdin_input()

    reason = input_data.get('reason', 'unknown')
    timestamp = datetime.now().strftime('%Y-%m-%d %H:%M:%S')

    # Log session end to progress notes
    progress_file = claude_dir / 'memories' / 'progress-notes.md'

    if progress_file.exists():
        # Check for active session to clean up
        active_session = find_active_session(claude_dir)

        if active_session:
            sid = active_session.stem.replace('session-', '')

            # Append session end marker
            entry = f'''
---
### Session End - {timestamp}
**Session ID**: {sid}
**Reason**: {reason}
**Status**: Auto-closed by SessionEnd hook

> Note: Session file may still be in active/ - check for pending work.
---
'''
            try:
                with open(progress_file, 'a', encoding='utf-8') as f:
                    f.write(entry)
            except (OSError, IOError):
                pass

    # Clean up stale locks in registry if reason is logout or clear
    if reason in ('logout', 'clear'):
        registry_path = project_root / 'docs' / 'tasks' / 'registry.json'
        registry = read_json_safe(registry_path)

        if registry and 'tasks' in registry:
            locked_tasks = [
                t.get('id') for t in registry['tasks']
                if t.get('lock') is not None
            ]
            if locked_tasks:
                print(f"Warning: Tasks still locked: {', '.join(locked_tasks)}", file=sys.stderr)
                print("Run /reflect unlock to clear stale locks", file=sys.stderr)


    sys.exit(0)


if __name__ == '__main__':
    main()
