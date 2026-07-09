#!/usr/bin/env python3
"""
validate-edit.py
PreToolUse hook to warn about sensitive file edits (cross-platform Python version)

Warns when editing sensitive files:
- .env files (may contain secrets)
- package-lock.json (should be auto-generated)
- .git/ directory (internal git files)

Claude Forge v2: Informational only - never blocks.

Exit codes:
- 0: Always (Claude Forge v2 never blocks)
"""

import json
import sys


# Sensitive file patterns to warn about
SENSITIVE_PATTERNS = [
    '.env',
    '.env.local',
    '.env.production',
    'package-lock.json',
    'yarn.lock',
    'pnpm-lock.yaml',
    '.git/',
    'node_modules/',
]


def main():
    # Read JSON input from stdin
    try:
        input_data = json.load(sys.stdin)
    except (json.JSONDecodeError, EOFError):
        input_data = {}

    # Extract file path from tool input
    file_path = input_data.get('tool_input', {}).get('file_path', '')

    # If no file path, allow (not a file operation)
    if not file_path:
        sys.exit(0)

    # Check for sensitive patterns and warn
    for pattern in SENSITIVE_PATTERNS:
        if pattern in file_path:
            print(
                f"WARN: Editing '{pattern}' file. "
                "These are often auto-generated or may contain secrets.",
                file=sys.stderr
            )
            break

    # Always allow - Claude Forge v2 never blocks
    sys.exit(0)


if __name__ == '__main__':
    main()
