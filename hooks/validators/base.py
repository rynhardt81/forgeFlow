#!/usr/bin/env python3
"""
Base validator class for Claude Forge v2 helper hooks.

All domain-specific validators inherit from BaseValidator and implement:
- prefix: Short identifier for output (e.g., "SECURITY", "ADR")
- validate(): Returns ValidationResult

Input: JSON via stdin with tool_name, tool_input, etc.
Output: Exit code 0 always (never blocks). On PostToolUse events, warnings
are emitted as `hookSpecificOutput.additionalContext` JSON on stdout so the
model actually sees them; on other events they fall back to stderr.

Philosophy: Validators provide helpful suggestions, never block operations.
All guidance is advisory — but advisory only works if the model receives it.
"""

import json
import sys
from abc import ABC, abstractmethod


class ValidationResult:
    """Result of a validation check."""

    def __init__(
        self,
        warning: bool = False,
        message: str = ""
    ):
        self.warning = warning
        self.message = message

    @classmethod
    def ok(cls) -> "ValidationResult":
        """Validation passed."""
        return cls()

    @classmethod
    def warn(cls, message: str) -> "ValidationResult":
        """Validation concern - warn but allow."""
        return cls(warning=True, message=message)


class BaseValidator(ABC):
    """
    Base class for domain-specific validators.

    Subclasses implement:
    - prefix: Property returning short identifier (e.g., "SECURITY")
    - validate(): Method returning ValidationResult

    Usage:
        class MyValidator(BaseValidator):
            @property
            def prefix(self) -> str:
                return "MYVAL"

            def validate(self) -> ValidationResult:
                # Check self.input_data
                return ValidationResult.ok()

        if __name__ == "__main__":
            sys.exit(MyValidator().run())
    """

    def __init__(self):
        self.input_data: dict = {}
        self.is_final: bool = "--final" in sys.argv

    def run(self) -> int:
        """
        Main entry point. Parses input, runs validation, returns exit code.

        Claude Forge v2: Always returns 0 (never blocks).
        Warnings are printed to stderr for informational purposes.
        """
        # Parse JSON from stdin
        try:
            stdin_content = sys.stdin.read()
            if stdin_content.strip():
                self.input_data = json.loads(stdin_content)
        except json.JSONDecodeError:
            return 0
        except Exception:
            return 0

        # Run validation
        try:
            result = self.validate()
        except Exception as e:
            print(f"{self.prefix}:ERROR", file=sys.stderr)
            print(f"->Validator error: {e}", file=sys.stderr)
            return 0  # Never block

        # Output result (advisory, never blocking). PostToolUse ignores
        # stderr on exit 0, so route the message through additionalContext —
        # the only channel that reaches the model on this event.
        if result.warning:
            event = self.input_data.get("hook_event_name", "")
            if event == "PostToolUse":
                print(json.dumps({
                    "hookSpecificOutput": {
                        "hookEventName": "PostToolUse",
                        "additionalContext": f"[{self.prefix}] {result.message}",
                    }
                }))
            else:
                print(f"{self.prefix}:NOTE", file=sys.stderr)
                print(f"->{result.message}", file=sys.stderr)

        return 0  # Always allow — never blocks

    @property
    @abstractmethod
    def prefix(self) -> str:
        """Short prefix for output messages (e.g., 'SECURITY', 'ADR')."""
        pass

    @abstractmethod
    def validate(self) -> ValidationResult:
        """
        Perform validation logic.

        Access self.input_data for hook input:
        - tool_name: "Read", "Write", "Edit", "Bash"
        - tool_input: {"file_path": "...", "content": "..."}
        - hook_event_name: "PreToolUse", "PostToolUse", "Stop"

        Returns:
            ValidationResult.ok() - No message
            ValidationResult.warn(msg) - Show helpful note
        """
        pass

    # Helper methods for common checks

    def get_tool_name(self) -> str:
        """Get the tool being called (Read, Write, Edit, Bash)."""
        return self.input_data.get("tool_name", "")

    def get_file_path(self) -> str:
        """Get file path from tool input."""
        return self.input_data.get("tool_input", {}).get("file_path", "")

    def get_content(self) -> str:
        """Get content from tool input (for Write operations)."""
        return self.input_data.get("tool_input", {}).get("content", "")

    def get_command(self) -> str:
        """Get command from tool input (for Bash operations)."""
        return self.input_data.get("tool_input", {}).get("command", "")

    def is_write_operation(self) -> bool:
        """Check if this is a Write operation."""
        return self.get_tool_name() == "Write"

    def is_edit_operation(self) -> bool:
        """Check if this is an Edit operation."""
        return self.get_tool_name() == "Edit"

    def file_matches(self, *patterns: str) -> bool:
        """
        Check if file path matches any of the given patterns.

        Patterns can be:
        - Exact match: "package.json"
        - Extension: ".py"
        - Contains: "test"
        - Prefix: "test_"
        """
        file_path = self.get_file_path().lower()
        if not file_path:
            return False

        for pattern in patterns:
            pattern = pattern.lower()
            if pattern.startswith("."):
                # Extension match
                if file_path.endswith(pattern):
                    return True
            elif "/" in pattern or "\\" in pattern:
                # Path contains
                if pattern in file_path:
                    return True
            else:
                # Filename contains or exact
                filename = file_path.split("/")[-1].split("\\")[-1]
                if pattern in filename:
                    return True

        return False
