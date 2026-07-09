# /// script
# requires-python = ">=3.8"
# dependencies = ["pyyaml"]
# ///
"""
Claude Forge Security Firewall - Edit Tool Hook
================================================

Protects files from being edited based on path protection rules:
- zeroAccessPaths: No access at all
- readOnlyPaths: No modifications allowed

Exit codes:
  0 = Allow edit
  2 = Block edit (stderr fed back to Claude)
"""

import json
import sys
import os
import fnmatch
from pathlib import Path
from typing import Dict, Any

import yaml


def get_config_path() -> Path:
    """Get path to patterns.yaml, checking multiple locations."""
    project_dir = os.environ.get("CLAUDE_PROJECT_DIR")
    if project_dir:
        project_config = Path(project_dir) / ".claude" / "hooks" / "damage-control" / "patterns.yaml"
        if project_config.exists():
            return project_config

    script_dir = Path(__file__).parent
    local_config = script_dir / "patterns.yaml"
    if local_config.exists():
        return local_config

    skill_root = script_dir.parent.parent / "patterns.yaml"
    if skill_root.exists():
        return skill_root

    return local_config


def load_config() -> Dict[str, Any]:
    """Load patterns from YAML config file."""
    config_path = get_config_path()

    if not config_path.exists():
        print(f"Warning: Config not found at {config_path}", file=sys.stderr)
        return {"zeroAccessPaths": [], "readOnlyPaths": []}

    with open(config_path, "r") as f:
        return yaml.safe_load(f) or {}


def is_glob_pattern(pattern: str) -> bool:
    """Check if pattern contains glob wildcards."""
    return '*' in pattern or '?' in pattern or '[' in pattern


def path_matches(file_path: str, pattern: str) -> bool:
    """Check if file_path matches a pattern (glob or literal)."""
    # Expand ~ in both
    expanded_path = os.path.expanduser(file_path)
    expanded_pattern = os.path.expanduser(pattern)

    # Normalize paths
    norm_path = os.path.normpath(expanded_path)
    norm_pattern = os.path.normpath(expanded_pattern)

    if is_glob_pattern(pattern):
        # Use fnmatch for glob patterns
        # Check both the full path and basename
        if fnmatch.fnmatch(norm_path, norm_pattern):
            return True
        if fnmatch.fnmatch(os.path.basename(norm_path), pattern):
            return True
        # Also check if any component matches
        for component in norm_path.split(os.sep):
            if fnmatch.fnmatch(component, pattern.strip('/')):
                return True
        return False
    else:
        # Literal path matching
        # Check if the pattern is a prefix (directory) or exact match
        if norm_pattern.endswith('/'):
            # Directory pattern - check if path starts with it
            return norm_path.startswith(norm_pattern.rstrip('/'))
        else:
            # Check exact match or if path starts with pattern as directory
            return norm_path == norm_pattern or norm_path.startswith(norm_pattern + os.sep)


def check_file_path(file_path: str, config: Dict[str, Any]) -> tuple[bool, str]:
    """
    Check if a file path should be protected from editing.

    Returns: (blocked, reason)
    """
    zero_access_paths = config.get("zeroAccessPaths", [])
    read_only_paths = config.get("readOnlyPaths", [])

    # Check zero-access paths (no access at all)
    for protected in zero_access_paths:
        if path_matches(file_path, protected):
            return True, f"Blocked: zero-access path {protected}"

    # Check read-only paths (no modifications)
    for protected in read_only_paths:
        if path_matches(file_path, protected):
            return True, f"Blocked: read-only path {protected}"

    return False, ""


def main() -> None:
    config = load_config()

    try:
        input_data = json.load(sys.stdin)
    except json.JSONDecodeError as e:
        print(f"Error: Invalid JSON input: {e}", file=sys.stderr)
        sys.exit(1)
    except Exception as e:
        print(f"Error reading input: {e}", file=sys.stderr)
        sys.exit(1)

    tool_name = input_data.get("tool_name", "")
    tool_input = input_data.get("tool_input", {})

    if tool_name != "Edit":
        sys.exit(0)

    file_path = tool_input.get("file_path", "")
    if not file_path:
        sys.exit(0)

    is_blocked, reason = check_file_path(file_path, config)

    if is_blocked:
        print(f"SECURITY: {reason}", file=sys.stderr)
        print(f"File: {file_path}", file=sys.stderr)
        sys.exit(2)
    else:
        sys.exit(0)


if __name__ == "__main__":
    main()
