"""Auto-rescan: poll top-level entries of media_dirs, debounce, HUP minidlna.

We do NOT use watchdog/FSEvents because:
  - macOS launchd processes have a distinct TCC identity; FSEvents on external
    /Volumes/... hangs in FSEventStreamCreate.
  - watchdog's PollingObserver scheduled on huge external trees deadlocks on
    its initial DirectorySnapshot under launchd.

The user's pattern is: "I create a new subfolder under insta360/". So polling
just the top-level entries (subdir names + mtimes) on a 30s tick is enough —
any add/remove/touch triggers a debounced SIGHUP to minidlna, which then does
its own deep recursive rescan.
"""
from __future__ import annotations

import os
import threading
import time
from typing import Iterable

from . import config, status

POLL_INTERVAL_SECS = 30.0
DEBOUNCE_SECS = 30.0
MOUNT_POLL_SECS = 10.0


class _State:
    def __init__(self) -> None:
        self.enabled: bool = True
        self.last_change_at: float | None = None
        self.last_scan_at: float | None = None
        self.last_event_path: str | None = None
        self.watched: list[str] = []
        self.unmounted: list[str] = []
        self.lock = threading.Lock()


_state = _State()


def state_snapshot() -> dict:
    with _state.lock:
        return {
            "enabled": _state.enabled,
            "watched": list(_state.watched),
            "unmounted": list(_state.unmounted),
            "last_change_at": _state.last_change_at,
            "last_scan_at": _state.last_scan_at,
            "last_event_path": _state.last_event_path,
        }


def set_enabled(enabled: bool) -> None:
    with _state.lock:
        _state.enabled = enabled


def _top_level_snapshot(path: str) -> dict[str, float]:
    """Return {entry_name: mtime} for top-level entries of `path`.
    Empty dict on error or if path is missing."""
    try:
        out: dict[str, float] = {}
        with os.scandir(path) as it:
            for e in it:
                try:
                    out[e.name] = e.stat(follow_symlinks=False).st_mtime
                except OSError:
                    out[e.name] = 0.0
        return out
    except OSError:
        return {}


class WatcherDaemon:
    def __init__(self) -> None:
        self._stop = threading.Event()
        self._snapshots: dict[str, dict[str, float]] = {}
        self._poll_thread: threading.Thread | None = None
        self._debounce_thread: threading.Thread | None = None

    def start(self) -> None:
        self._poll_thread = threading.Thread(target=self._poll_loop, daemon=True, name="watcher-poll")
        self._poll_thread.start()
        self._debounce_thread = threading.Thread(target=self._debouncer, daemon=True, name="watcher-debounce")
        self._debounce_thread.start()

    def stop(self) -> None:
        self._stop.set()

    def _refresh_paths(self) -> tuple[list[str], list[str]]:
        configured = [md.path for md in config.parse_media_dirs()]
        mounted = [p for p in configured if os.path.isdir(p)]
        unmounted = [p for p in configured if p not in mounted]
        with _state.lock:
            _state.watched = sorted(mounted)
            _state.unmounted = unmounted
        # drop snapshots for paths we no longer watch
        for p in list(self._snapshots):
            if p not in mounted:
                self._snapshots.pop(p, None)
        return mounted, unmounted

    def _poll_once(self) -> None:
        mounted, _ = self._refresh_paths()
        for p in mounted:
            current = _top_level_snapshot(p)
            previous = self._snapshots.get(p)
            self._snapshots[p] = current
            if previous is None:
                # first observation — establish baseline, no change
                continue
            if current != previous:
                added = set(current) - set(previous)
                removed = set(previous) - set(current)
                changed = next(iter(added | removed), None) or "(touched)"
                with _state.lock:
                    _state.last_change_at = time.time()
                    _state.last_event_path = os.path.join(p, changed) if changed else p

    def _poll_loop(self) -> None:
        while not self._stop.is_set():
            try:
                self._poll_once()
            except Exception:
                pass
            self._stop.wait(POLL_INTERVAL_SECS)

    def _debouncer(self) -> None:
        while not self._stop.is_set():
            self._stop.wait(2.0)
            with _state.lock:
                if not _state.enabled:
                    continue
                last = _state.last_change_at
            if last is None:
                continue
            if time.time() - last < DEBOUNCE_SECS:
                continue
            with _state.lock:
                if _state.last_change_at != last:
                    continue
                _state.last_change_at = None
                _state.last_scan_at = time.time()
            status.hup_minidlna()


_daemon: WatcherDaemon | None = None
_daemon_lock = threading.Lock()


def ensure_running() -> None:
    global _daemon
    with _daemon_lock:
        if _daemon is None:
            _daemon = WatcherDaemon()
            _daemon.start()


def trigger_rescan_now() -> bool:
    with _state.lock:
        _state.last_scan_at = time.time()
        _state.last_change_at = None
    return status.hup_minidlna()
