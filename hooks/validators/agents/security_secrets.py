#!/usr/bin/env python3
"""
Security Secrets Validator for @security-boss agent.

Detects hardcoded secrets, API keys, passwords, and tokens in Write operations.
Warns about potential secrets and suggests using environment variables.

Usage in agent frontmatter:
    hooks:
      PostToolUse:
        - matcher: "Write"
          hooks:
            - type: command
              command: "python3 $CLAUDE_PROJECT_DIR/.claude/hooks/validators/agents/security_secrets.py"
"""

import re
import sys
from pathlib import Path

# Add parent directory to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent))

from base import BaseValidator, ValidationResult


# Patterns that indicate hardcoded secrets
# Each tuple: (regex_pattern, description)
SECRET_PATTERNS = [
    # API Keys - Generic
    (r'(?i)(api[_-]?key|apikey)\s*[:=]\s*["\']?[a-zA-Z0-9_-]{20,}["\']?',
     "API key"),

    # Passwords and Secrets
    (r'(?i)(password|passwd|pwd|secret)\s*[:=]\s*["\'][^"\']{4,}["\']',
     "Hardcoded password/secret"),

    # Bearer Tokens
    (r'(?i)bearer\s+[a-zA-Z0-9_.-]{20,}',
     "Bearer token"),

    # OpenAI API Keys
    (r'sk-[a-zA-Z0-9]{32,}',
     "OpenAI API key"),

    # GitHub Personal Access Tokens
    (r'ghp_[a-zA-Z0-9]{36}',
     "GitHub personal access token"),

    # GitHub OAuth Tokens
    (r'gho_[a-zA-Z0-9]{36}',
     "GitHub OAuth token"),

    # AWS Access Keys
    (r'AKIA[0-9A-Z]{16}',
     "AWS Access Key ID"),

    # AWS Secret Keys
    (r'(?i)aws[_-]?secret[_-]?access[_-]?key\s*[:=]\s*["\']?[a-zA-Z0-9/+=]{40}["\']?',
     "AWS Secret Access Key"),

    # Private Keys
    (r'-----BEGIN\s+(RSA|EC|OPENSSH|PGP|DSA)?\s*PRIVATE KEY-----',
     "Private key"),

    # Stripe API Keys
    (r'sk_live_[a-zA-Z0-9]{24,}',
     "Stripe live API key"),
    (r'sk_test_[a-zA-Z0-9]{24,}',
     "Stripe test API key"),

    # Slack Tokens
    (r'xox[baprs]-[a-zA-Z0-9-]{10,}',
     "Slack token"),

    # Discord Tokens
    (r'[MN][A-Za-z\d]{23,}\.[\w-]{6}\.[\w-]{27}',
     "Discord token"),

    # Database Connection Strings with Passwords
    (r'(?i)(mongodb|postgres|mysql|redis)://[^:]+:[^@]+@',
     "Database connection string with embedded password"),

    # Generic Secret Assignment (high confidence patterns)
    (r'(?i)client[_-]?secret\s*[:=]\s*["\'][^"\']{8,}["\']',
     "Client secret"),
]


def _load_yaml_patterns() -> list[tuple[str, str]]:
    """Load extra secret patterns from hooks/config/secret-patterns.yaml.

    The yaml is the consumer-editable source of additional patterns. Returns
    a list of (regex, description) tuples. Bare-install safe: returns [] if
    PyYAML is unavailable or the file is missing/malformed — the validator
    then runs on the hardcoded SECRET_PATTERNS alone. Patterns are UNIONED
    with the hardcoded defaults (see below), never replace them, so the
    floor is always at least the built-in set.
    """
    try:
        import yaml  # lazy: absent on Pythons without PyYAML
    except Exception:
        return []
    # framework_root is hooks/../  → this file is hooks/validators/agents/X.py
    cfg = Path(__file__).resolve().parents[2] / "config" / "secret-patterns.yaml"
    if not cfg.exists():
        return []
    try:
        data = yaml.safe_load(cfg.read_text(encoding="utf-8")) or {}
    except Exception:
        return []
    out: list[tuple[str, str]] = []
    for entry in (data.get("secret_patterns") or []):
        pat = entry.get("pattern")
        if not pat:
            continue
        name = entry.get("name") or "secret"
        out.append((pat, name))
    return out


def _resolved_patterns() -> list[tuple[str, str]]:
    """Hardcoded defaults UNIONed with yaml patterns (deduped on regex).

    Hardcoded SECRET_PATTERNS is the always-present floor; the yaml adds
    consumer-editable extras. Dedupe on the regex string so an identical
    pattern declared in both places isn't scanned twice.
    """
    seen = {p for p, _ in SECRET_PATTERNS}
    merged = list(SECRET_PATTERNS)
    for pat, desc in _load_yaml_patterns():
        if pat not in seen:
            merged.append((pat, desc))
            seen.add(pat)
    return merged

# Files that are allowed to contain "secrets" (examples, templates)
ALLOWED_FILE_PATTERNS = [
    ".example",
    ".template",
    ".sample",
    "example.",
    "template.",
    "sample.",
    "_example",
    "_template",
    "_sample",
    "mock",
    "fixture",
    "test_data",
    "testdata",
]


class SecuritySecretsValidator(BaseValidator):
    """Validates that Write operations don't contain hardcoded secrets."""

    @property
    def prefix(self) -> str:
        return "SECURITY"

    def validate(self) -> ValidationResult:
        # Only validate Write operations
        if not self.is_write_operation():
            return ValidationResult.ok()

        file_path = self.get_file_path()
        content = self.get_content()

        if not content:
            return ValidationResult.ok()

        # Skip allowed files (examples, templates, mocks)
        file_lower = file_path.lower()
        for pattern in ALLOWED_FILE_PATTERNS:
            if pattern in file_lower:
                return ValidationResult.ok()

        # Skip .env.example but not .env
        if file_path.endswith(".env.example") or file_path.endswith(".env.local.example"):
            return ValidationResult.ok()

        # Block actual .env files
        if file_path.endswith(".env") or ".env." in file_path:
            if not any(p in file_lower for p in ["example", "template", "sample"]):
                return ValidationResult.warn(
                    f"Writing to {file_path}. Consider using environment variables and .env.example for documentation."
                )

        # Scan content for secrets. Patterns = hardcoded floor ∪ yaml extras
        # (yaml is dead-config no longer; loaded here, bare-install safe).
        detected = []
        for pattern, description in _resolved_patterns():
            if re.search(pattern, content):
                detected.append(description)

        if detected:
            # Deduplicate
            detected = list(set(detected))
            issues = ", ".join(detected[:3])  # Show max 3
            if len(detected) > 3:
                issues += f" (+{len(detected) - 3} more)"

            return ValidationResult.warn(
                f"Detected in {Path(file_path).name}: {issues}. "
                "Use environment variables instead of hardcoding secrets."
            )

        return ValidationResult.ok()


if __name__ == "__main__":
    sys.exit(SecuritySecretsValidator().run())
