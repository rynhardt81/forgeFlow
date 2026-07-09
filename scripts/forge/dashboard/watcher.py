"""Singleton file-mtime watcher for dashboard SSE.

One background thread polls a set of files + directories every POLL_INTERVAL
seconds; when an mtime advances, it broadcasts the changed path to every
subscriber queue. SSE handlers `subscribe()` to get their own queue, drain
it in their handler loop, and `unsubscribe()` on disconnect.

Stdlib-only — threading + queue. No fsevents/inotify.
"""

from __future__ import annotations

import queue
import threading
from pathlib import Path

POLL_INTERVAL = 2.0  # seconds
KEEPALIVE_INTERVAL = 15.0  # seconds — SSE handlers send a comment if idle


class Watcher:
    """Singleton mtime watcher. Construct once, .start() once."""

    def __init__(self, project_root: Path, watch_paths: list[str | Path]):
        """watch_paths: list of relative path strings or absolute Paths.
        Strings ending in `/` are directories (we watch all files in them
        non-recursively); strings ending in `*.md` etc. are globs.
        Other strings are individual files.
        """
        self._project_root = Path(project_root)
        self._watch_specs = list(watch_paths)
        self._subscribers: set[queue.Queue] = set()
        self._lock = threading.Lock()
        self._mtimes: dict[Path, float] = {}
        self._thread: threading.Thread | None = None
        self._stop_evt = threading.Event()

    # ---- subscriber API ----

    def subscribe(self) -> queue.Queue:
        q: queue.Queue = queue.Queue(maxsize=64)
        with self._lock:
            self._subscribers.add(q)
        return q

    def unsubscribe(self, q: queue.Queue) -> None:
        with self._lock:
            self._subscribers.discard(q)

    def subscriber_count(self) -> int:
        with self._lock:
            return len(self._subscribers)

    # ---- lifecycle ----

    def start(self) -> None:
        if self._thread is not None:
            return
        self._thread = threading.Thread(
            target=self._poll_loop, name="dashboard-watcher", daemon=True,
        )
        self._thread.start()

    def stop(self) -> None:
        self._stop_evt.set()
        if self._thread is not None:
            self._thread.join(timeout=POLL_INTERVAL + 1)

    # ---- poll loop ----

    def _resolve_watch_set(self) -> list[Path]:
        """Expand watch_specs to a concrete list of file paths to stat."""
        out: list[Path] = []
        for spec in self._watch_specs:
            spec_str = str(spec)
            if spec_str.endswith("/"):
                # directory — non-recursive
                d = self._project_root / spec_str.rstrip("/")
                if d.exists():
                    for p in d.iterdir():
                        if p.is_file():
                            out.append(p)
            elif "*" in spec_str:
                # glob from project root
                out.extend(self._project_root.glob(spec_str))
            else:
                p = self._project_root / spec_str
                out.append(p)
        return out

    def _poll_loop(self) -> None:
        # Initialize baseline mtimes silently — don't broadcast for the
        # initial discovery, only for changes after startup.
        for p in self._resolve_watch_set():
            try:
                self._mtimes[p] = p.stat().st_mtime
            except OSError:
                self._mtimes[p] = 0.0

        while not self._stop_evt.wait(POLL_INTERVAL):
            try:
                changed = self._scan_changes()
            except Exception as exc:
                # Never let the watcher die from a bad stat
                import sys
                sys.stderr.write(f"[watcher] scan error: {exc}\n")
                continue
            if not changed:
                continue
            self._broadcast(changed)

    def _scan_changes(self) -> list[str]:
        """Return list of (relative) path strings that changed since last poll."""
        seen: set[Path] = set()
        changed: list[str] = []
        for p in self._resolve_watch_set():
            seen.add(p)
            try:
                mt = p.stat().st_mtime
            except OSError:
                mt = 0.0
            prev = self._mtimes.get(p)
            if prev is None:
                # New file discovered after startup → counts as change
                self._mtimes[p] = mt
                if mt > 0:
                    changed.append(self._rel(p))
            elif mt > prev:
                self._mtimes[p] = mt
                changed.append(self._rel(p))
        # Detect deletions (file existed last poll, gone now)
        for p in list(self._mtimes.keys()):
            if p not in seen:
                del self._mtimes[p]
                changed.append(self._rel(p))
        return changed

    def _rel(self, p: Path) -> str:
        try:
            return p.relative_to(self._project_root).as_posix()
        except ValueError:
            return p.as_posix()

    def _broadcast(self, paths: list[str]) -> None:
        with self._lock:
            subs = list(self._subscribers)
        for q in subs:
            for path in paths:
                try:
                    q.put_nowait(path)
                except queue.Full:
                    # Subscriber not draining — drop oldest, push new
                    try:
                        q.get_nowait()
                        q.put_nowait(path)
                    except Exception:
                        pass


# ---- Default watch list for dashboard ----

DEFAULT_WATCH = [
    "docs/tasks/registry.json",
    "docs/code-map.json",
    "docs/tasks/F-DASHBOARD/ISA.md",  # individual ISAs (glob below adds others)
    "docs/tasks/F-*/ISA.md",
    "docs/project-memory/",
    "daily/",
]
