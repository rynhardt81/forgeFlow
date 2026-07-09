"""Forge Dashboard — local HTTP server serving a unified Forge Flow view.

Read-only cockpit at http://localhost:4847/ with tab navigation to the existing
/visualize generators (tasks kanban, code-map), plus ISA/memory/daily/registry
views. Live-reloads via SSE when underlying data files change.

Single entry point: forge dashboard (see scripts/forge/forge.py).
"""

DEFAULT_PORT = 4847
DEFAULT_HOST = "127.0.0.1"
