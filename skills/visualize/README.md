# Dashboard rendering engine (not a skill)

The Python generators in Tools/ render Forge artifacts (code-map, tasks kanban, ISAs, CI reports) as standalone HTML. They are imported lazily by the Forge Dashboard (scripts/forge/dashboard/server.py) — use `forge dashboard` to view everything under one tabbed UI. The former /visualize slash-skill was removed in v4; the dashboard is the one rendering surface.
