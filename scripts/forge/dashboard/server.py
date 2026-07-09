"""HTTP server for the Forge Dashboard.

ThreadingHTTPServer + a single Handler that dispatches by URL path. Each route
returns a complete HTML document (text/html) so iframes inside the index page
can embed it directly. Generator routes (`/tasks`, `/code-map`) delegate to the
existing /visualize generators by importing their `render()` callable.
"""

from __future__ import annotations

import argparse
import errno
import importlib.util
import sys
import threading
import time
import traceback
import webbrowser
from http import HTTPStatus
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import Callable

from . import DEFAULT_HOST, DEFAULT_PORT
from .render import index as index_render
from .render import isas as isas_render
from .render import memory as memory_render
from .render import daily as daily_render
from .render import registry_view as registry_render
from .render import burndown as burndown_render
from .watcher import DEFAULT_WATCH, KEEPALIVE_INTERVAL, Watcher


# Framework vs. project root — two distinct concepts, never confuse them.
#
# framework_root(): where FRAMEWORK CODE lives — skills, generators, hooks,
#   scripts. In a vendored install: <project>/.claude/. In the framework's own
#   dev repo: the repo root. Derived from __file__, not by walking — it's a
#   structural fact of where this file is, not a heuristic.
#
# project_root(): where PROJECT DATA lives — docs/tasks/, docs/epics/, daily/,
#   docs/project-memory/, ISA.md. In a vendored install: <project>/ (one level
#   above .claude/). In the framework's own dev repo: same as framework_root().
#   Walks up from framework_root() looking for .git only; `CLAUDE.md` is NOT a
#   marker because every .claude/ directory contains one (false-positive trap
#   that previously caused the dashboard to read .claude/docs/... as project
#   data).

def framework_root() -> Path:
    """The directory where the framework's code lives.

    server.py is at <framework_root>/scripts/forge/dashboard/server.py, so
    framework_root is __file__.parents[3].
    """
    return Path(__file__).resolve().parents[3]


def project_root() -> Path:
    """The project the framework is operating on.

    In a vendored install, framework_root is `<project>/.claude/`, so the
    project root is its parent. In the framework's own dev repo,
    framework_root IS the project (it's a self-hosting setup). We detect
    "vendored" by checking whether framework_root's basename is `.claude`.
    """
    fr = framework_root()
    if fr.name == ".claude":
        return fr.parent
    # Self-hosting (framework dev repo): walk up looking for `.git`. If we
    # don't find one (unusual), fall back to fr itself rather than to cwd —
    # cwd can be anywhere the user ran the command from.
    for parent in [fr, *fr.parents]:
        if (parent / ".git").exists():
            return parent
    return fr


# ---- Generator delegation -------------------------------------------------

def _load_generator(name: str) -> Callable | None:
    """Lazily import a /visualize generator's render() callable.

    Generators live at <framework_root>/skills/visualize/Tools/generators/<name>.py.
    They expose a register() function returning {name, description, render}.
    We load by file path so we don't pollute sys.path globally.
    """
    root = framework_root()
    # Filename mapping: kebab-case module name → snake_case filename
    file_name = name.replace("-", "_") + ".py"
    path = root / "skills" / "visualize" / "Tools" / "generators" / file_name
    if not path.exists():
        return None

    # Ensure the generator's `from _shared import ...` finds Tools/
    tools_dir = str(root / "skills" / "visualize" / "Tools")
    if tools_dir not in sys.path:
        sys.path.insert(0, tools_dir)

    spec = importlib.util.spec_from_file_location(f"_dashboard_gen_{name}", path)
    if not spec or not spec.loader:
        return None
    module = importlib.util.module_from_spec(spec)
    try:
        spec.loader.exec_module(module)
    except Exception:
        traceback.print_exc()
        return None
    register = getattr(module, "register", None)
    if not callable(register):
        return None
    info = register()
    return info.get("render")


def _render_via_generator(name: str) -> bytes:
    """Render a generator's output to disk, read bytes, return for HTTP.

    Output lives under the PROJECT root's docs/visualizations/, not the
    framework root — visualizations are derived project artifacts, owned by
    the project being inspected, not by the framework copy.
    """
    render = _load_generator(name)
    if not render:
        raise FileNotFoundError(f"generator '{name}' not found")

    out_path = project_root() / "docs" / "visualizations" / f"{name}.html"
    # Reuse stable output path so the visualize CLI and dashboard share one file.
    fake = argparse.Namespace(input=None, output=out_path, open=False, extra=[])
    output = render(fake)
    return output.read_bytes()


# ---- Handler --------------------------------------------------------------

class Handler(BaseHTTPRequestHandler):
    # Quiet down stdout logging — we want clean output, not access-log spam by
    # default. Override `log_message` to keep important entries.

    def log_message(self, fmt: str, *args) -> None:
        # Only log non-200 / non-static for now.
        try:
            status = args[1] if len(args) > 1 else ""
        except Exception:
            status = ""
        if status and status[0] in ("4", "5"):
            sys.stderr.write(f"[dashboard] {self.address_string()} - {fmt % args}\n")

    def _send_html(self, html: bytes, status: int = HTTPStatus.OK) -> None:
        self.send_response(status)
        self.send_header("Content-Type", "text/html; charset=utf-8")
        self.send_header("Content-Length", str(len(html)))
        self.send_header("Cache-Control", "no-store")
        self.end_headers()
        self.wfile.write(html)

    def _send_bytes(self, body: bytes, content_type: str, status: int = HTTPStatus.OK) -> None:
        self.send_response(status)
        self.send_header("Content-Type", content_type)
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Cache-Control", "no-store")
        self.end_headers()
        self.wfile.write(body)

    def _send_error_page(self, code: int, msg: str) -> None:
        html = f"""<!DOCTYPE html><html><head><meta charset="utf-8">
<title>Error {code}</title>
<style>
  body {{ background:#0f1115;color:#e8ebf0;font-family:-apple-system,sans-serif;
          padding:40px;font-size:14px;line-height:1.5; }}
  code {{ background:#1a1d24;padding:2px 6px;border-radius:3px;font-family:ui-monospace,monospace; }}
  h1 {{ font-weight:600;letter-spacing:-0.01em; }}
</style></head><body>
<h1>{code}</h1>
<p>{msg}</p>
<p><a style="color:#0ea5e9" href="/">← back to dashboard</a></p>
</body></html>""".encode("utf-8")
        self._send_html(html, status=code)

    def do_GET(self) -> None:  # noqa: N802 — stdlib API
        path = self.path.split("?", 1)[0]

        try:
            if path == "/" or path == "":
                return self._handle_index()
            if path == "/tasks":
                return self._handle_generator("tasks")
            if path == "/code-map":
                return self._handle_generator("code-map")
            if path == "/isas":
                return self._handle_isas_index()
            if path.startswith("/isa/"):
                return self._handle_isa_one(path[len("/isa/"):])
            if path == "/memory":
                return self._handle_memory()
            if path == "/daily":
                return self._handle_daily()
            if path == "/registry":
                return self._handle_registry()
            if path == "/burndown":
                return self._handle_burndown()
            if path == "/events":
                return self._handle_events()
            if path.startswith("/static/"):
                return self._handle_static(path[len("/static/"):])
            return self._send_error_page(404, f"Unknown route: <code>{path}</code>")
        except FileNotFoundError as exc:
            self._send_error_page(404, str(exc))
        except Exception as exc:
            sys.stderr.write(f"[dashboard] {path}: {exc}\n")
            traceback.print_exc()
            self._send_error_page(500, f"{type(exc).__name__}: {exc}")

    # ---- Routes ----

    def _handle_index(self) -> None:
        html = index_render.render_index().encode("utf-8")
        self._send_html(html)

    def _handle_generator(self, name: str) -> None:
        html = _render_via_generator(name)
        # Pass-through unchanged — generator output is a complete document.
        self.send_response(HTTPStatus.OK)
        self.send_header("Content-Type", "text/html; charset=utf-8")
        self.send_header("Content-Length", str(len(html)))
        self.send_header("Cache-Control", "no-store")
        self.end_headers()
        self.wfile.write(html)

    def _handle_isas_index(self) -> None:
        html = isas_render.render_index(project_root()).encode("utf-8")
        self._send_html(html)

    def _handle_isa_one(self, feature_dir: str) -> None:
        # Strip trailing slash if present
        feature_dir = feature_dir.rstrip("/")
        html = isas_render.render_one(project_root(), feature_dir).encode("utf-8")
        self._send_html(html)

    def _handle_memory(self) -> None:
        html = memory_render.render_index(project_root()).encode("utf-8")
        self._send_html(html)

    def _handle_daily(self) -> None:
        html = daily_render.render_index(project_root()).encode("utf-8")
        self._send_html(html)

    def _handle_registry(self) -> None:
        html = registry_render.render_index(project_root()).encode("utf-8")
        self._send_html(html)

    def _handle_burndown(self) -> None:
        html = burndown_render.render_index(project_root()).encode("utf-8")
        self._send_html(html)

    def _handle_events(self) -> None:
        """SSE long-lived endpoint. Emits file-changed events as they arrive.

        Browsers close idle SSE streams after ~30s — we send `:keepalive\\n\\n`
        comments every KEEPALIVE_INTERVAL seconds when the change queue is
        empty. Catches BrokenPipeError on client disconnect.
        """
        watcher: Watcher | None = getattr(self.server, "watcher", None)
        if watcher is None:
            return self._send_error_page(500, "no watcher attached")

        self.send_response(HTTPStatus.OK)
        self.send_header("Content-Type", "text/event-stream; charset=utf-8")
        self.send_header("Cache-Control", "no-store")
        self.send_header("X-Accel-Buffering", "no")
        # Note: no Content-Length — SSE is an unbounded stream
        self.end_headers()

        q = watcher.subscribe()
        try:
            # Immediately send a "hello" event so the client knows we're alive
            self._sse_send_comment("connected")
            while True:
                try:
                    path = q.get(timeout=KEEPALIVE_INTERVAL)
                except Exception:
                    # queue.Empty — keepalive time
                    self._sse_send_comment("keepalive")
                    continue
                # Drain any queued additional paths quickly so a burst of changes
                # produces one batch of events
                payload = [path]
                while True:
                    try:
                        payload.append(q.get_nowait())
                    except Exception:
                        break
                for p in payload:
                    self._sse_send_event("file-changed", p)
        except (BrokenPipeError, ConnectionResetError):
            # Client disconnected cleanly — exit handler
            return
        finally:
            watcher.unsubscribe(q)

    def _sse_send_event(self, event: str, data: str) -> None:
        msg = f"event: {event}\ndata: {data}\n\n".encode("utf-8")
        self.wfile.write(msg)
        self.wfile.flush()

    def _sse_send_comment(self, comment: str) -> None:
        msg = f": {comment}\n\n".encode("utf-8")
        self.wfile.write(msg)
        self.wfile.flush()

    def _handle_static(self, relpath: str) -> None:
        # Block directory traversal
        if ".." in Path(relpath).parts:
            return self._send_error_page(403, "Forbidden path")
        root = Path(__file__).resolve().parent / "static"
        target = root / relpath
        if not target.is_file():
            return self._send_error_page(404, f"Static file not found: <code>{relpath}</code>")
        # Minimal content-type sniffing — only what we serve
        ext = target.suffix.lower()
        ctype = {
            ".css": "text/css; charset=utf-8",
            ".js": "application/javascript; charset=utf-8",
            ".html": "text/html; charset=utf-8",
            ".svg": "image/svg+xml",
        }.get(ext, "application/octet-stream")
        self._send_bytes(target.read_bytes(), ctype)


# ---- Server boot ----------------------------------------------------------

class _Server(ThreadingHTTPServer):
    daemon_threads = True
    allow_reuse_address = False  # we WANT a clear bind error if port is busy


def run(host: str = DEFAULT_HOST, port: int = DEFAULT_PORT,
        auto_open: bool = True, once: bool = False) -> int:
    """Start the dashboard server. Returns process exit code."""
    if once:
        # --once mode: render the index page to stdout-equivalent and exit.
        # Useful for snapshot testing / CI verification without serving.
        html = index_render.render_index()
        sys.stdout.write(html)
        return 0

    try:
        server = _Server((host, port), Handler)
    except OSError as exc:
        if exc.errno == errno.EADDRINUSE:
            sys.stderr.write(
                f"error: port {port} is already in use.\n"
                f"  another process may already be running, or pick a different port:\n"
                f"    forge dashboard --port <other-port>\n"
            )
            return 2
        if exc.errno in (errno.EACCES, errno.EPERM):
            sys.stderr.write(
                f"error: permission denied to bind on {host}:{port}.\n"
                f"  try a port > 1024 with `--port <n>`.\n"
            )
            return 2
        raise

    # Start the singleton mtime watcher + attach to server for handlers
    watcher = Watcher(project_root(), DEFAULT_WATCH)
    watcher.start()
    server.watcher = watcher  # type: ignore[attr-defined]

    url = f"http://{host}:{port}/"
    sys.stderr.write(f"[dashboard] serving on {url}\n")
    sys.stderr.write("[dashboard] press Ctrl+C to stop\n")

    if auto_open:
        # Open the browser in a background thread so the server starts serving
        # immediately. webbrowser.open() is synchronous on macOS via `open`.
        threading.Thread(
            target=lambda: (time.sleep(0.3), webbrowser.open(url)),
            daemon=True,
        ).start()

    try:
        server.serve_forever()
    except KeyboardInterrupt:
        sys.stderr.write("\n[dashboard] shutting down\n")
        server.shutdown()
        return 0
    finally:
        watcher.stop()
        server.server_close()
    return 0


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    p = argparse.ArgumentParser(prog="forge dashboard", add_help=True,
                                description="Local Forge Flow dashboard")
    p.add_argument("--host", default=DEFAULT_HOST,
                   help=f"bind host (default: {DEFAULT_HOST})")
    p.add_argument("--port", type=int, default=DEFAULT_PORT,
                   help=f"bind port (default: {DEFAULT_PORT})")
    p.add_argument("--no-open", action="store_true",
                   help="do not auto-open the browser")
    p.add_argument("--once", action="store_true",
                   help="render the index page to stdout once and exit (no server)")
    return p.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    return run(host=args.host, port=args.port,
               auto_open=not args.no_open, once=args.once)


if __name__ == "__main__":
    sys.exit(main())
