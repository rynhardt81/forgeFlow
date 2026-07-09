"""Dashboard index page — tab bar + iframe-embedded current tab."""

from __future__ import annotations

# Tab registry: id, label, route, description (shown in title attr).
# Order here = order in the tab bar.
TABS = [
    ("tasks",    "Tasks",    "/tasks",    "Kanban: epics → tasks by status"),
    ("code-map", "Code Map", "/code-map", "Module / file / symbol graph"),
    ("isas",     "ISAs",     "/isas",     "Feature ideal-state articulations"),
    ("memory",   "Memory",   "/memory",   "Bugs, decisions, patterns, facts"),
    ("daily",    "Daily",    "/daily",    "Recent daily-log entries"),
    ("registry", "Registry", "/registry", "Raw registry.json as a tree"),
    ("burndown", "Burndown", "/burndown", "Tasks completed per day (git history)"),
]

DEFAULT_TAB = "tasks"


_TEMPLATE = """<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<title>Forge Dashboard</title>
<link rel="stylesheet" href="/static/dashboard.css">
</head>
<body>
  <header class="dash-header">
    <div class="brand">
      <span class="brand-mark">◆</span>
      <span class="brand-name">Forge</span>
      <span class="brand-sub">dashboard</span>
    </div>
    <nav class="tab-bar" id="tab-bar">
__TAB_BUTTONS__
    </nav>
    <div class="actions">
      <button class="action-btn" id="reload-btn" title="Reload current tab">
        <span aria-hidden="true">⟳</span>
      </button>
    </div>
  </header>

  <main class="tab-frame">
    <iframe id="tab-iframe" src="__DEFAULT_ROUTE__"
            title="active dashboard tab"
            referrerpolicy="no-referrer"></iframe>
  </main>

  <div id="live-indicator" title="live reload connected">
    <span class="live-dot"></span><span class="live-label">live</span>
  </div>

  <script>
  (function() {
    const TABS = __TABS_JSON__;
    const DEFAULT = "__DEFAULT_TAB__";
    const iframe = document.getElementById("tab-iframe");
    const bar = document.getElementById("tab-bar");
    let activeTab = null;

    // Selective-reload map: when a file path changes, reload these tabs
    // (if currently visible). Prefix-matched in order — first match wins.
    const RELOAD_MAP = [
      ["docs/tasks/registry.json",  ["tasks", "registry", "burndown"]],
      ["docs/code-map.json",        ["code-map"]],
      ["docs/tasks/F-",             ["isas"]],
      ["docs/project-memory/",      ["memory"]],
      ["daily/",                    ["daily"]],
    ];

    function reloadCurrent() {
      const url = iframe.src;
      iframe.src = "about:blank";
      setTimeout(() => { iframe.src = url; }, 30);
    }

    function activate(id) {
      const tab = TABS.find(t => t.id === id);
      if (!tab) return;
      activeTab = id;
      iframe.src = tab.route;
      [...bar.querySelectorAll(".tab")].forEach(el => {
        el.classList.toggle("active", el.dataset.tab === id);
      });
      try { history.replaceState(null, "", "/#" + id); } catch (e) {}
    }

    bar.addEventListener("click", (evt) => {
      const btn = evt.target.closest(".tab");
      if (!btn) return;
      activate(btn.dataset.tab);
    });

    document.getElementById("reload-btn").addEventListener("click", reloadCurrent);

    const fromHash = (location.hash || "").replace(/^#/, "");
    activate(fromHash && TABS.some(t => t.id === fromHash) ? fromHash : DEFAULT);

    // ---- SSE subscription for live reload ----
    const indicator = document.getElementById("live-indicator");
    function setIndicator(state) {
      indicator.dataset.state = state;
    }
    setIndicator("connecting");

    let es = null;
    function connectSSE() {
      try {
        es = new EventSource("/events");
      } catch (e) {
        setIndicator("error");
        return;
      }
      es.onopen = () => setIndicator("connected");
      es.onerror = () => {
        setIndicator("reconnecting");
        // EventSource retries automatically; nothing to do here
      };
      es.addEventListener("file-changed", (evt) => {
        const path = evt.data;
        const tabsToReload = matchTabs(path);
        if (tabsToReload.includes(activeTab)) {
          reloadCurrent();
        }
        // Visual pulse on the indicator
        indicator.classList.add("pulse");
        setTimeout(() => indicator.classList.remove("pulse"), 600);
      });
    }
    function matchTabs(path) {
      for (const [prefix, tabs] of RELOAD_MAP) {
        if (path.startsWith(prefix)) return tabs;
      }
      return [];
    }
    connectSSE();
  })();
  </script>
</body>
</html>
"""


def render_index() -> str:
    tab_buttons = "\n".join(
        '      <button class="tab" data-tab="{tid}" title="{desc}">'
        '<span class="tab-label">{label}</span></button>'.format(
            tid=tid,
            desc=escape_attr(desc),
            label=escape_html(label),
        )
        for (tid, label, _route, desc) in TABS
    )
    default_route = next(r for (tid, _, r, _) in TABS if tid == DEFAULT_TAB)

    return (_TEMPLATE
            .replace("__TAB_BUTTONS__", tab_buttons)
            .replace("__DEFAULT_ROUTE__", default_route)
            .replace("__DEFAULT_TAB__", DEFAULT_TAB)
            .replace("__TABS_JSON__", _tabs_as_js()))


def _tabs_as_js() -> str:
    parts = []
    for (tid, label, route, desc) in TABS:
        parts.append(
            '{'
            f'id:"{tid}",label:"{escape_js(label)}",'
            f'route:"{route}",desc:"{escape_js(desc)}"'
            '}'
        )
    return "[" + ",".join(parts) + "]"


def escape_html(s: str) -> str:
    return (s.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")
            .replace('"', "&quot;").replace("'", "&#39;"))


def escape_attr(s: str) -> str:
    return escape_html(s)


def escape_js(s: str) -> str:
    # For embedding in a JS string literal between double quotes
    return s.replace("\\", "\\\\").replace('"', '\\"').replace("\n", "\\n")
