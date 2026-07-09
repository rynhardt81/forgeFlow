# /// script
# requires-python = ">=3.8"
# dependencies = ["pyyaml"]
# ///
"""
Claude Forge Security Firewall - Bash Tool Hook
================================================

Defense-in-depth protection combining:
1. Command allowlist (deny by default)
2. Pattern blocking (dangerous command patterns)
3. Path protection (zero-access, read-only, no-delete)
4. Special validators (pkill, chmod, curl)

Exit codes:
  0 = Allow command (or JSON output with permissionDecision)
  2 = Block command (stderr fed back to Claude)

JSON output for ask patterns:
  {"hookSpecificOutput": {"hookEventName": "PreToolUse", "permissionDecision": "ask", "permissionDecisionReason": "..."}}
"""

import json
import sys
import re
import os
import shlex
from pathlib import Path
from typing import Tuple, List, Dict, Any

import yaml


# ============================================================================
# OPERATION PATTERNS - For path protection
# ============================================================================

WRITE_PATTERNS = [
    (r'>\s*{path}', "write"),
    (r'\btee\s+(?!.*-a).*{path}', "write"),
]

APPEND_PATTERNS = [
    (r'>>\s*{path}', "append"),
    (r'\btee\s+-a\s+.*{path}', "append"),
]

EDIT_PATTERNS = [
    (r'\bsed\s+-i.*{path}', "edit"),
    (r'\bperl\s+-[^\s]*i.*{path}', "edit"),
]

MOVE_COPY_PATTERNS = [
    (r'\bmv\s+.*\s+{path}', "move"),
    (r'\bcp\s+.*\s+{path}', "copy"),
]

DELETE_PATTERNS = [
    (r'\brm\s+.*{path}', "delete"),
    (r'\bunlink\s+.*{path}', "delete"),
    (r'\brmdir\s+.*{path}', "delete"),
]

PERMISSION_PATTERNS = [
    (r'\bchmod\s+.*{path}', "chmod"),
    (r'\bchown\s+.*{path}', "chown"),
]

READ_ONLY_BLOCKED = (
    WRITE_PATTERNS +
    APPEND_PATTERNS +
    EDIT_PATTERNS +
    MOVE_COPY_PATTERNS +
    DELETE_PATTERNS +
    PERMISSION_PATTERNS
)

NO_DELETE_BLOCKED = DELETE_PATTERNS


# ============================================================================
# CONFIGURATION LOADING
# ============================================================================

def get_config_path() -> Path:
    """Get path to patterns.yaml, checking multiple locations."""
    # 1. Check project hooks directory (installed location)
    project_dir = os.environ.get("CLAUDE_PROJECT_DIR")
    if project_dir:
        project_config = Path(project_dir) / ".claude" / "hooks" / "damage-control" / "patterns.yaml"
        if project_config.exists():
            return project_config

    # 2. Check script's own directory (installed location)
    script_dir = Path(__file__).parent
    local_config = script_dir / "patterns.yaml"
    if local_config.exists():
        return local_config

    # 3. Check skill root directory (development location)
    skill_root = script_dir.parent.parent / "patterns.yaml"
    if skill_root.exists():
        return skill_root

    return local_config


def load_config() -> Dict[str, Any]:
    """Load patterns from YAML config file."""
    config_path = get_config_path()

    if not config_path.exists():
        print(f"Warning: Config not found at {config_path}", file=sys.stderr)
        return {
            "allowedCommands": [],
            "bashToolPatterns": [],
            "zeroAccessPaths": [],
            "readOnlyPaths": [],
            "noDeletePaths": [],
            "specialValidators": {}
        }

    with open(config_path, "r") as f:
        return yaml.safe_load(f) or {}


# ============================================================================
# COMMAND PARSING (from Claude Forge security.py)
# ============================================================================

def extract_commands(command_string: str) -> List[str]:
    """
    Extract command names from a shell command string.
    Handles pipes, command chaining (&&, ||, ;), and subshells.
    """
    commands = []
    segments = re.split(r'(?<!["\'])\s*;\s*(?!["\'])', command_string)

    for segment in segments:
        segment = segment.strip()
        if not segment:
            continue

        try:
            tokens = shlex.split(segment)
        except ValueError:
            return []

        if not tokens:
            continue

        expect_command = True
        for token in tokens:
            if token in ("|", "||", "&&", "&"):
                expect_command = True
                continue

            if token in ("if", "then", "else", "elif", "fi", "for", "while",
                        "until", "do", "done", "case", "esac", "in", "!", "{", "}"):
                continue

            if token.startswith("-"):
                continue

            if "=" in token and not token.startswith("="):
                continue

            if expect_command:
                cmd = os.path.basename(token)
                commands.append(cmd)
                expect_command = False

    return commands


# ============================================================================
# SPECIAL VALIDATORS (from Claude Forge security.py)
# ============================================================================

def validate_pkill_command(command_string: str, config: Dict[str, Any]) -> Tuple[bool, str]:
    """Validate pkill - only allow killing dev processes."""
    validators = config.get("specialValidators", {}).get("pkill", {})
    allowed_processes = set(validators.get("allowedProcesses", [
        "node", "npm", "npx", "pnpm", "vite", "next", "webpack", "jest", "vitest", "pytest"
    ]))

    try:
        tokens = shlex.split(command_string)
    except ValueError:
        return False, "Could not parse pkill command"

    if not tokens:
        return False, "Empty pkill command"

    args = [t for t in tokens[1:] if not t.startswith("-")]
    if not args:
        return False, "pkill requires a process name"

    target = args[-1]
    if " " in target:
        target = target.split()[0]

    if target in allowed_processes:
        return True, ""
    return False, f"pkill only allowed for dev processes: {allowed_processes}"


def validate_chmod_command(command_string: str, config: Dict[str, Any]) -> Tuple[bool, str]:
    """Validate chmod - only allow +x modes."""
    validators = config.get("specialValidators", {}).get("chmod", {})
    allowed_modes = set(validators.get("allowedModes", ["+x", "u+x", "g+x", "a+x"]))

    try:
        tokens = shlex.split(command_string)
    except ValueError:
        return False, "Could not parse chmod command"

    if not tokens or tokens[0] != "chmod":
        return False, "Not a chmod command"

    mode = None
    for token in tokens[1:]:
        if token.startswith("-"):
            return False, "chmod flags are not allowed"
        elif mode is None:
            mode = token
        else:
            break

    if mode is None:
        return False, "chmod requires a mode"

    if mode in allowed_modes or re.match(r"^[ugoa]*\+x$", mode):
        return True, ""

    return False, f"chmod only allowed with +x mode, got: {mode}"


def validate_curl_command(command_string: str, config: Dict[str, Any]) -> Tuple[bool, str]:
    """Validate curl - block file:// and uploads."""
    validators = config.get("specialValidators", {}).get("curl", {})
    blocked_protocols = validators.get("blockedProtocols", ["file://"])
    blocked_flags = validators.get("blockedFlags", ["--upload-file", "-T"])

    try:
        tokens = shlex.split(command_string)
    except ValueError:
        return False, "Could not parse curl command"

    command_str = " ".join(tokens)

    for protocol in blocked_protocols:
        if protocol in command_str.lower():
            return False, f"curl: {protocol} protocol not allowed"

    for flag in blocked_flags:
        if flag in tokens:
            return False, f"curl: {flag} not allowed"

    if "-F" in tokens or "--form" in tokens:
        for token in tokens:
            if token.startswith("@"):
                return False, "curl: file uploads with @ not allowed"

    return True, ""


# ============================================================================
# PATH CHECKING
# ============================================================================

def is_glob_pattern(pattern: str) -> bool:
    """Check if pattern contains glob wildcards."""
    return '*' in pattern or '?' in pattern or '[' in pattern


def glob_to_regex(glob_pattern: str) -> str:
    """Convert a glob pattern to a regex pattern."""
    result = ""
    for char in glob_pattern:
        if char == '*':
            result += r'[^\s/]*'
        elif char == '?':
            result += r'[^\s/]'
        elif char in r'\.^$+{}[]|()':
            result += '\\' + char
        else:
            result += char
    return result


def check_path_patterns(command: str, path: str, patterns: List[Tuple[str, str]], path_type: str) -> Tuple[bool, str]:
    """Check command against patterns for a specific path."""
    if is_glob_pattern(path):
        glob_regex = glob_to_regex(path)
        for pattern_template, operation in patterns:
            try:
                cmd_prefix = pattern_template.replace("{path}", "")
                if cmd_prefix and re.search(cmd_prefix + glob_regex, command, re.IGNORECASE):
                    return True, f"Blocked: {operation} operation on {path_type} {path}"
            except re.error:
                continue
    else:
        expanded = os.path.expanduser(path)
        escaped_expanded = re.escape(expanded)
        escaped_original = re.escape(path)

        for pattern_template, operation in patterns:
            pattern_expanded = pattern_template.replace("{path}", escaped_expanded)
            pattern_original = pattern_template.replace("{path}", escaped_original)
            try:
                if re.search(pattern_expanded, command) or re.search(pattern_original, command):
                    return True, f"Blocked: {operation} operation on {path_type} {path}"
            except re.error:
                continue

    return False, ""


# ============================================================================
# MAIN COMMAND CHECKER
# ============================================================================

def check_command(command: str, config: Dict[str, Any]) -> Tuple[bool, bool, str]:
    """
    Check if command should be blocked or requires confirmation.

    Returns: (blocked, ask, reason)
      - blocked=True, ask=False: Block the command
      - blocked=False, ask=True: Show confirmation dialog
      - blocked=False, ask=False: Allow the command
    """
    allowed_commands = set(config.get("allowedCommands", []))
    patterns = config.get("bashToolPatterns", [])
    zero_access_paths = config.get("zeroAccessPaths", [])
    read_only_paths = config.get("readOnlyPaths", [])
    no_delete_paths = config.get("noDeletePaths", [])

    # 1. ALLOWLIST CHECK (Claude Forge approach - deny by default)
    commands = extract_commands(command)
    if not commands:
        return True, False, "Could not parse command for security validation"

    for cmd in commands:
        if cmd not in allowed_commands:
            return True, False, f"Command '{cmd}' is not in the allowed commands list"

    # 2. PATTERN BLOCKING (damage-control approach)
    for item in patterns:
        pattern = item.get("pattern", "")
        reason = item.get("reason", "Blocked by pattern")
        should_ask = item.get("ask", False)

        try:
            if re.search(pattern, command, re.IGNORECASE):
                if should_ask:
                    return False, True, reason
                else:
                    return True, False, f"Blocked: {reason}"
        except re.error:
            continue

    # 3. SPECIAL VALIDATORS
    for cmd in commands:
        if cmd == "pkill":
            allowed, reason = validate_pkill_command(command, config)
            if not allowed:
                return True, False, reason
        elif cmd == "chmod":
            allowed, reason = validate_chmod_command(command, config)
            if not allowed:
                return True, False, reason
        elif cmd == "curl":
            allowed, reason = validate_curl_command(command, config)
            if not allowed:
                return True, False, reason

    # 4. ZERO-ACCESS PATHS (block all operations including reads)
    for zero_path in zero_access_paths:
        if is_glob_pattern(zero_path):
            glob_regex = glob_to_regex(zero_path)
            try:
                if re.search(glob_regex, command, re.IGNORECASE):
                    return True, False, f"Blocked: zero-access pattern {zero_path}"
            except re.error:
                continue
        else:
            expanded = os.path.expanduser(zero_path)
            escaped_expanded = re.escape(expanded)
            escaped_original = re.escape(zero_path)
            if re.search(escaped_expanded, command) or re.search(escaped_original, command):
                return True, False, f"Blocked: zero-access path {zero_path}"

    # 5. READ-ONLY PATHS (block modifications)
    for readonly in read_only_paths:
        blocked, reason = check_path_patterns(command, readonly, READ_ONLY_BLOCKED, "read-only path")
        if blocked:
            return True, False, reason

    # 6. NO-DELETE PATHS (block deletions only)
    for no_delete in no_delete_paths:
        blocked, reason = check_path_patterns(command, no_delete, NO_DELETE_BLOCKED, "no-delete path")
        if blocked:
            return True, False, reason

    return False, False, ""


# ============================================================================
# MAIN
# ============================================================================

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

    if tool_name != "Bash":
        sys.exit(0)

    command = tool_input.get("command", "")
    if not command:
        sys.exit(0)

    is_blocked, should_ask, reason = check_command(command, config)

    if is_blocked:
        print(f"SECURITY: {reason}", file=sys.stderr)
        print(f"Command: {command[:100]}{'...' if len(command) > 100 else ''}", file=sys.stderr)
        sys.exit(2)
    elif should_ask:
        output = {
            "hookSpecificOutput": {
                "hookEventName": "PreToolUse",
                "permissionDecision": "ask",
                "permissionDecisionReason": reason
            }
        }
        print(json.dumps(output))
        sys.exit(0)
    else:
        sys.exit(0)


if __name__ == "__main__":
    main()
