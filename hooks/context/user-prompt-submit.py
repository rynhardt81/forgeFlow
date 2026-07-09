#!/usr/bin/env python3
"""
user-prompt-submit.py
UserPromptSubmit hook - runs before Claude processes user prompts
Cross-platform Python version

Provides pre-processing context and gate reminders.
Uses JSON output format for structured control.

Exit codes:
  0 - Success (stdout added as context)
  2 - Block prompt (stderr shown as error)

NOTE: When deployed to a target project, this script lives at:
  {project}/.claude/hooks/context/user-prompt-submit.py
"""

import json
import os
import re
import subprocess
import sys
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
        sessions.sort(key=lambda f: f.stat().st_mtime, reverse=True)
        return sessions[0]
    except (OSError, IOError):
        return None


def extract_from_table(content, section, field):
    """Extract a value from a markdown table within a section."""
    section_pattern = rf'## {re.escape(section)}[\s\S]*?(?=##|$)'
    section_match = re.search(section_pattern, content, re.IGNORECASE)
    if not section_match:
        return None

    field_pattern = rf'\*\*{re.escape(field)}\*\*\s*\|\s*([^|\n]+)'
    field_match = re.search(field_pattern, section_match.group(0), re.IGNORECASE)
    if not field_match:
        return None

    value = field_match.group(1).strip().replace('`', '')
    if value in ('none', '-', ''):
        return None
    return value


def main():
    project_root = get_project_root()
    claude_dir = get_claude_dir(project_root)

    # Read input from stdin (JSON with prompt info) — value is unused,
    # but consuming stdin is part of the hook contract.
    try:
        json.load(sys.stdin)
    except (json.JSONDecodeError, EOFError):
        pass

    context_parts = []

    # Check session status
    active_session = find_active_session(claude_dir)
    if not active_session:
        context_parts.append('No active session.')

    # Check registry status
    registry_path = project_root / 'docs' / 'tasks' / 'registry.json'
    if not registry_path.exists():
        context_parts.append('No task registry.')

    # Check for active skill
    if active_session:
        try:
            session_content = active_session.read_text(encoding='utf-8')

            active_skill = extract_from_table(session_content, 'Active Skill', 'Skill')
            if active_skill:
                context_parts.append(f'Active skill: {active_skill} (re-invoke if resuming).')

            # Check for active agent
            active_agent = extract_from_table(session_content, 'Active Agent', 'Agent')
            if active_agent:
                context_parts.append(f'Active agent: {active_agent} (reload summary if resuming).')
        except (OSError, IOError):
            pass

    # Output context if any
    if context_parts:
        print(' '.join(context_parts))

    sys.exit(0)


if __name__ == '__main__':
    main()
