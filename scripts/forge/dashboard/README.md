# Forge Dashboard

> A local read-only HTTP cockpit for everything Forge Flow knows about your project — tasks, code, ISAs, memory, daily logs, raw registry, burndown — under one URL, with live reload.

Run it:

```bash
forge dashboard                     # http://127.0.0.1:4847/  (auto-opens browser)
forge dashboard --port 5000         # custom port
forge dashboard --no-open           # don't open the browser
forge dashboard --once              # render index to stdout and exit (CI / snapshot)
forge dashboard --host 0.0.0.0      # bind LAN (no auth — local-only by default)
```

Stop with `Ctrl+C`. The server cleans up its watcher thread and SSE subscribers on shutdown.

---

## Why this exists

The generators under `skills/visualize/Tools/` originally backed a `/visualize` slash-skill (removed in v4) that emitted standalone HTML files into `docs/visualizations/` — you had to remember each file path and open them separately — kanban here, code-map there, ISAs by hand-navigating a directory tree, project-memory entries as raw markdown no-one re-reads.

The data isn't missing. It's *unreachable without ritual*.

The dashboard collapses every artifact into one URL with tab navigation, deep-linkable hashes, and live reload. It's a **read-only cockpit** — mutation continues to flow through the `forge` CLI per `CLAUDE.md`. There is no "mark task complete" button. There never will be.

---

## What's on the dashboard

Seven tabs, all reachable from the top tab bar. Each tab is an isolated iframe so per-tab JS contexts don't collide and right-click → open-in-new-tab works natively.

| Tab | Route | Source | Live-reload trigger |
|-----|-------|--------|---------------------|
| **Tasks** | `/tasks` | `skills/visualize/Tools/generators/tasks.py` reads `docs/tasks/registry.json` | `docs/tasks/registry.json` mtime advances |
| **Code Map** | `/code-map` | `skills/visualize/Tools/generators/code_map.py` reads `docs/code-map.json` | `docs/code-map.json` mtime advances |
| **ISAs** | `/isas` + `/isa/<feature>` | `docs/tasks/F-*/ISA.md` discovered via glob, parsed for frontmatter | Any `docs/tasks/F-*/ISA.md` mtime advances |
| **Memory** | `/memory` | `docs/project-memory/{bugs,decisions,patterns,key-facts,index}.md` | Any file in `docs/project-memory/` advances |
| **Daily** | `/daily` | `daily/YYYY-MM-DD.md` (7 newest, vertical timeline) | Any file in `daily/` advances |
| **Registry** | `/registry` | Raw `docs/tasks/registry.json` as a collapsible JSON tree | Same as Tasks |
| **Burndown** | `/burndown` | `git log` + `git show <sha>:docs/tasks/registry.json` per commit → daily completed-tasks count → SVG bars + cumulative area + line | Same as Tasks |

A bottom-right `● live` indicator changes color to show SSE connection state:

| State | Dot color |
|-------|-----------|
| `connecting` | amber |
| `connected` | green |
| `reconnecting` | orange |
| `error` | red |

When a watched file changes the indicator briefly pulses cyan; the iframe for the affected tab(s) auto-reloads if it's the active tab.

---

## How it works

```
                      ┌─────────────────────────────────────┐
                      │  forge dashboard  (CLI subcommand)  │
                      └────────────────┬────────────────────┘
                                       │
                          imports lazily
                                       ▼
              ┌──────────────────────────────────────────┐
              │   scripts/forge/dashboard/server.py      │
              │   ThreadingHTTPServer + BaseHTTP-        │
              │   Handler.do_GET → route dispatch        │
              └─┬─────────────┬─────────────┬────────────┘
                │             │             │
                ▼             ▼             ▼
       ┌──────────────┐ ┌──────────────┐ ┌────────────────┐
       │ render/*.py  │ │ /events      │ │ /static/*      │
       │ (per tab)    │ │ SSE handler  │ │ CSS files      │
       └──────┬───────┘ └──────┬───────┘ └────────────────┘
              │                │
   delegates  │                │ subscribes to
              ▼                ▼
       ┌──────────────────────────────┐
       │ skills/visualize/Tools/      │       ┌─────────────┐
       │ generators/tasks.py          │       │ watcher.py  │
       │ generators/code_map.py       │       │ singleton   │
       │ (called via importlib)       │       │ 2s mtime    │
       └──────────────────────────────┘       │ poll loop   │
                                              │ → broadcast │
                                              │ to per-     │
                                              │ subscriber  │
                                              │ Queue       │
                                              └─────────────┘
```

### Tech-stack invariants

| | |
|---|---|
| **Language** | Python 3.8+ |
| **Dependencies** | **Zero external Python deps.** Pure stdlib — `http.server.ThreadingHTTPServer`, `webbrowser`, `json`, `pathlib`, `subprocess`, `threading`, `queue`, `importlib.util`. No Flask. No FastAPI. No `pip install`. |
| **Frontend deps** | **Zero.** No React, Vue, chart libs, CDN. Inline `<style>`/`<script>`, vendored libs inside the per-tab generator HTML, native `EventSource` for SSE. |
| **Bind address** | `127.0.0.1` by default — localhost only. LAN exposure needs `--host 0.0.0.0` and is unauthenticated (you opted in). |
| **Default port** | `4847` — mnemonic and uncommon enough to dodge typical dev servers (3000, 5173, 8000, 8080, 9000). |
| **Read-only** | No route writes to source files (`docs/tasks/registry.json`, `docs/code-map.json`, any `F-*/ISA.md`, `daily/`, `docs/project-memory/`). Verified by mtime-probe in F-DASHBOARD ISA. Mutation goes through `forge` CLI per CLAUDE.md. |

### Live reload via SSE

`scripts/forge/dashboard/watcher.py` defines a singleton `Watcher` class:

- One background daemon thread polls a fixed watch-list every **2 seconds**.
- Default watch-list (`DEFAULT_WATCH` in `watcher.py`):
  - `docs/tasks/registry.json`
  - `docs/code-map.json`
  - `docs/tasks/F-*/ISA.md` (glob)
  - `docs/project-memory/` (directory, non-recursive)
  - `daily/` (directory, non-recursive)
- When `Path.stat().st_mtime` advances vs the previous poll, the new mtime overwrites the cache and the changed path is broadcast.
- Broadcast = `put_nowait` into every subscriber's `queue.Queue(maxsize=64)`; on `Queue.Full` the watcher drops the oldest entry to make room (subscriber starvation never wedges the broadcaster).
- Deletions (file existed last poll, gone now) are emitted as changes — clients reload and see the empty-state.

The SSE handler in `server.py` (`_handle_events`):

- Sends `Content-Type: text/event-stream`, `Cache-Control: no-store`, `X-Accel-Buffering: no` (defeats nginx-style buffering if anyone proxies later).
- Subscribes to the watcher's queue on connect, unsubscribes on disconnect (`BrokenPipeError` / `ConnectionResetError` are caught silently in the finally block).
- Idle-sends `:keepalive` SSE comments every 15 seconds so browsers don't kill the stream.
- On change: `event: file-changed\ndata: <relative-path>\n\n`.

The client (inline JS inside `render/index.py`) holds one `EventSource("/events")` for the whole dashboard lifetime. A `RELOAD_MAP` translates "this path changed" → "these tabs should reload":

```js
const RELOAD_MAP = [
  ["docs/tasks/registry.json",  ["tasks", "registry", "burndown"]],
  ["docs/code-map.json",        ["code-map"]],
  ["docs/tasks/F-",             ["isas"]],
  ["docs/project-memory/",      ["memory"]],
  ["daily/",                    ["daily"]],
];
```

If the currently-active tab is in the matched list, its iframe `src` is cleared and re-set on a 30ms timer (a clean re-fetch). Other tabs sit untouched — switching to them later naturally re-fetches.

### Why polling, not inotify / fsevents

A 2-second mtime poll over ~10 paths is trivial CPU and platform-independent (macOS, Linux, Windows all behave identically). Native file watchers (`watchdog`, `pyinotify`) are external deps + platform-specific code paths. The latency budget here is human-perception (a 3-second lag from `forge task pr T101` to the kanban re-rendering is fine).

### Why SSE, not WebSocket

The dashboard is read-only. The only direction we need is server → client ("a file changed"). SSE has a stdlib-clean implementation (just write `text/event-stream` lines to the response socket). WebSocket would need either an external dep or a hand-rolled framing implementation. SSE wins on simplicity.

### Why iframe-per-tab, not SPA routing

Each generator (`skills/visualize/Tools/generators/*.py`) already emits a *complete standalone HTML document* with its own vendored libs in `<head>`. Building an SPA would mean unwrapping every generator's head, deduping CSS, mediating between conflicting JS contexts (Cytoscape vs kanban click handlers). iframes give us isolation for free — and right-click → "Open in new tab" works natively. Cost: one extra HTTP round-trip per tab activation, which is fine on localhost.

### Burndown specifics

`render/burndown.py` rebuilds a daily series from git history:

1. `git log --reverse --format='%H %ct' -- docs/tasks/registry.json` → ordered `(sha, unix_ts)` pairs.
2. For each commit, `git show <sha>:docs/tasks/registry.json` → parse JSON → count tasks where `status == "completed"`.
3. Bucket by UTC day, take the last commit per day as that day's final state, compute `delta = today.completed - yesterday.completed`.
4. Cache the derived series to `.forge/cache/burndown.json` keyed by the latest commit sha; the next render is cache-hit unless that sha changes.

Three empty-state branches:

- `docs/tasks/registry.json` doesn't exist → friendly "no registry" card.
- File exists but has no git history (untracked) → friendly "no history yet" card with a hint to commit it.
- Exactly one day of history → friendly "one day of history, reload tomorrow" card with a summary chip row.

When the series has ≥2 days, the SVG renders:

- Top panel: per-day delta bars (positive = blue, negative/empty = grey).
- Bottom panel: cumulative-completed area + line + per-day dots.
- X-axis day labels (sparse stepping when >14 days).
- Hover `<title>` tooltips on every bar and dot showing exact counts.

The summary-chips row above the chart shows: Total completed · Days of history · Latest day · Latest delta · Avg per active day · Source (`fresh` or `cache`).

---

## File map

```
scripts/forge/dashboard/
├── README.md              ← you are here
├── __init__.py            ← DEFAULT_PORT = 4847, DEFAULT_HOST = "127.0.0.1"
├── server.py              ← ThreadingHTTPServer + Handler + route dispatch + SSE
├── watcher.py             ← Singleton mtime watcher with subscriber queues
├── render/
│   ├── index.py           ← tab bar + iframe shell + SSE client + RELOAD_MAP
│   ├── isas.py            ← /isas list + /isa/<feature> per-feature render
│   ├── memory.py          ← /memory project-memory feeds
│   ├── daily.py           ← /daily timeline of recent daily-log entries
│   ├── registry_view.py   ← /registry collapsible JSON tree
│   ├── burndown.py        ← /burndown git-derived SVG chart + cache
│   └── markdown.py        ← stdlib Markdown → HTML mini-renderer with frontmatter
└── static/
    ├── dashboard.css      ← chrome (header, tab bar, live indicator, iframe frame)
    ├── content.css        ← doc-page typography, ISA list, memory feeds, daily timeline
    ├── registry.css       ← JSON tree + summary chips
    └── burndown.css       ← chart panel + SVG element styles + delta colors
```

Adding a tab is one file in `render/` + one entry in `index.py`'s `TABS` list + (if it consumes a new data file) one entry in `RELOAD_MAP` and `watcher.py`'s `DEFAULT_WATCH`.

---

## Routes reference

| Route | Returns | Notes |
|-------|---------|-------|
| `/` | tab-bar shell + iframe pointing at the default tab | URL hash (`#<tab-id>`) is honored on load + updated on tab click |
| `/tasks` | kanban HTML from `tasks.py` generator | iframe target |
| `/code-map` | code-map HTML from `code_map.py` generator | iframe target |
| `/isas` | list of all `F-*` feature ISAs (newest mtime first) | clicking a row navigates to `/isa/<feature>` |
| `/isa/<feature>` | full ISA rendered via stdlib markdown → HTML + frontmatter pills | `feature` must start with `F-` (path-traversal blocked) |
| `/memory` | bugs / decisions / patterns / key-facts / index from `docs/project-memory/` | empty-state when dir missing |
| `/daily` | 7 newest `daily/YYYY-MM-DD.md` files as a vertical timeline | empty-state when none exist |
| `/registry` | `docs/tasks/registry.json` as a collapsible JSON tree | summary chips above tree; full keyboard-clickable disclosure |
| `/burndown` | SVG chart + chips + recent-days table (or one of three empty-states) | cache file at `.forge/cache/burndown.json` |
| `/events` | SSE stream | long-lived; `Content-Type: text/event-stream` |
| `/static/<file>` | CSS files | directory-traversal blocked |

All HTML routes emit `Cache-Control: no-store` — the dashboard is meant to be live.

---

## Command-line flags

| Flag | Default | Effect |
|------|---------|--------|
| `--host HOST` | `127.0.0.1` | Bind address. Set `0.0.0.0` for LAN access (unauthenticated). |
| `--port PORT` | `4847` | Bind port. Friendly error + exit code 2 on `EADDRINUSE`. |
| `--no-open` | off | Skip the `webbrowser.open()` call after binding. |
| `--once` | off | Render the index page to stdout and exit (no server). Useful for CI / snapshot tests. |
| `-h` / `--help` | — | argparse-generated help. |

---

## Verifying it works

The F-DASHBOARD ISA (`docs/tasks/F-DASHBOARD/ISA.md`) defines 12 ISCs — all verified ✅ as of 2026-05-23. Quick smoke test:

```bash
# 1. --once mode renders the index
forge dashboard --once | head -3
# → <!DOCTYPE html>\n<html lang="en">\n<head>

# 2. Boot, hit every tab, verify 7 successful responses
forge dashboard --no-open &
sleep 1
for r in / /tasks /code-map /isas /memory /daily /registry /burndown; do
  curl -s -o /dev/null -w "%{http_code} $r\n" "http://127.0.0.1:4847$r"
done

# 3. Live-reload smoke test (terminal A: SSE subscriber, terminal B: touch)
# A:
curl -sN http://127.0.0.1:4847/events
# B (within a few seconds):
touch docs/tasks/registry.json
# Expect terminal A to print:
#   event: file-changed
#   data: docs/tasks/registry.json

# 4. Port-conflict friendly error
forge dashboard --port 4847
# Expect (when one is already running):
#   error: port 4847 is already in use.
#     another process may already be running, or pick a different port:
#       forge dashboard --port <other-port>
# Exit code: 2
```

---

## Troubleshooting

**Port 4847 stuck after Ctrl+C ("address already in use" even though no server is running).**
TCP `TIME_WAIT` sockets from earlier SSE connections take ~60 seconds to drain. `allow_reuse_address = False` is intentional (D-D8 in the ISA — we want a clear error on real conflicts, not a silent steal). Either wait, or `--port 4848`.

**SSE indicator stuck on `connecting` / `reconnecting`.**
Open DevTools → Network → filter `events`. If the request is pending and headers look right (`Content-Type: text/event-stream`), the connection is alive but no events have fired — that's the steady state when nothing is changing. If the request keeps recycling, your browser is probably proxying it through a buffering layer; check `X-Accel-Buffering: no` is in the response headers (it should be).

**Tab loads but auto-reload doesn't fire when I `forge task pr T123`.**
Confirm the changed file is in `DEFAULT_WATCH` (in `scripts/forge/dashboard/watcher.py`) and the path prefix is in the inline `RELOAD_MAP` (in `scripts/forge/dashboard/render/index.py`). Polling happens every 2 s — give it up to 3 s before declaring it dead.

**Burndown shows "no history yet" but I have lots of completed tasks.**
The chart is derived from `git log` on `docs/tasks/registry.json`. If you never committed that file, there's no history. Commit it once (`git add docs/tasks/registry.json && git commit -m "..."`), and every future `forge task complete` commit will populate one more day on the chart.

**`forge dashboard` errors with `ModuleNotFoundError: No module named 'dashboard'`.**
Make sure you're running via the `forge` CLI (`python3 scripts/forge/forge.py dashboard`) — that file does the sys.path setup. Direct `python3 -m dashboard.server` works too, but only with `PYTHONPATH=scripts/forge` set.

**I want a tab the dashboard doesn't have.**
Add a `render/<your_tab>.py` exposing `render_index(project_root: Path) -> str` (or whatever signature your route handler will call), wire a `_handle_yourtab` method + `if path == "/your-tab"` branch in `server.py`, append `("your-tab", "Your Tab", "/your-tab", "<description>")` to `TABS` in `render/index.py`, and (if it depends on a data file we don't already watch) extend `DEFAULT_WATCH` in `watcher.py` and `RELOAD_MAP` in `render/index.py`. That's the whole loop.

---

## See also

- `docs/tasks/F-DASHBOARD/ISA.md` — feature ISA with all 12 ISCs verified
- `docs/tasks/F-VISUALIZE/ISA.md` — the `/visualize` skill ISA (the generators the dashboard delegates to)
- `skills/visualize/README.md` — the generators' role as the dashboard rendering engine
- `CLAUDE.md` — Forge Flow's framework-level overview (mentions `forge dashboard` in the skills/CLI table)
- `CHEATSHEET.md` — one-page reference for everything Forge Flow
