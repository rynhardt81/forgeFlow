"""Pytest config: locate the dashboard module + shared helpers."""
from __future__ import annotations

import sys
from pathlib import Path

_REPO_ROOT = Path(__file__).resolve().parents[2]
_DASHBOARD_PARENT = _REPO_ROOT / "scripts" / "forge"
if str(_DASHBOARD_PARENT) not in sys.path:
    sys.path.insert(0, str(_DASHBOARD_PARENT))
