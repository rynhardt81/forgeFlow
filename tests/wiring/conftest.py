"""Pytest config for skill->agent wiring tests.

These tests do static analysis on the skill markdown bodies + agent
frontmatter to verify the wiring graph is correct without requiring a
Claude Code runtime. They prove:

1. Every Task(subagent_type="<name>") in a skill body cites an agent
   that exists at agents/<name>.md
2. Every cited agent has a parseable frontmatter with required keys
3. Every agent that declares a hooks: PostToolUse Write binding cites
   a real validator file under hooks/validators/agents/

Run from project root:
    python3 -m pytest tests/wiring/ -v
"""
from __future__ import annotations

import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]

# Make REPO_ROOT importable so test files can do `from <module> import ...`
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))
