"""
Claude Forge Embedded Hook Validators

Domain-specific validators that can be embedded in agent and skill YAML frontmatter.
These complement centralized hooks (gates, security) with output validation.

Usage in agent/skill frontmatter:
    hooks:
      PostToolUse:
        - matcher: "Write"
          hooks:
            - type: command
              command: "python3 $CLAUDE_PROJECT_DIR/.claude/hooks/validators/agents/security_secrets.py"

Exit codes:
    0 = Success (allow operation)
    1 = Warning (show message, continue)
    2 = Block (show error, prevent operation)
"""

from .base import BaseValidator, ValidationResult

__all__ = ["BaseValidator", "ValidationResult"]
