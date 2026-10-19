"""Which companion is on the desktop right now: one at a time, visible to Home.

A running ``play`` or ``live`` companion *claims* ``running.json`` next to the
saved settings and refreshes a heartbeat in it every few seconds. That gives
three things without process IDs (which get reused, and which Windows can't
probe safely):

* **Home can tell what's running**, even a companion it didn't start (from the
  .exe, the tray or a terminal): a fresh heartbeat means running.
* **One companion at a time.** A new claim replaces the old one, and the old
  companion notices within a second and closes itself gracefully (memory
  saved, helpers stopped), so Start never leaves two on screen.
* **Stop from anywhere.** Home marks the claim ``stop`` and the companion
  closes itself.

A crashed companion simply stops beating, and its claim goes stale on its own.
Only lifecycle facts are stored: mode, companion name, times, a random token.
"""
from __future__ import annotations

import json
import os
import secrets
import time
from contextlib import contextmanager
from pathlib import Path

BEAT_S = 4.0          # how often a running companion refreshes its claim
STALE_S = 15.0        # a claim older than this belongs to nobody
WATCH_MS = 1000       # how often a running companion checks its claim


def presence_path() -> Path:
    from hermes_companion.core.settings import settings_path
    return settings_path().parent / "running.json"


@contextmanager
def _ownership_lock(path: Path):
    """Serialize claim replacement, heartbeat and release across processes."""
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.with_suffix('.lock').open('a+b') as handle:
        handle.seek(0, 2)
        if handle.tell() == 0:
            handle.write(b'0')
            handle.flush()
        handle.seek(0)
        if os.name == 'nt':
            import msvcrt
            msvcrt.locking(handle.fileno(), msvcrt.LK_LOCK, 1)
        else:
            import fcntl
            fcntl.flock(handle.fileno(), fcntl.LOCK_EX)
        try:
            yield
        finally:
            handle.seek(0)
            if os.name == 'nt':
                msvcrt.locking(handle.fileno(), msvcrt.LK_UNLCK, 1)
            else:
                fcntl.flock(handle.fileno(), fcntl.LOCK_UN)


def _read(path: Path) -> dict | None:
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return None
    return data if isinstance(data, dict) and isinstance(data.get("token"), str) else None


def _write(path: Path, data: dict) -> None:
    try:
        path.parent.mkdir(parents=True, exist_ok=True)
        tmp = path.with_name(f"{path.name}.{os.getpid()}.tmp")
        tmp.write_text(json.dumps(data), encoding="utf-8")
        os.replace(tmp, path)                 # readers never see half a file
    except OSError:
        pass


def current(path: Path | None = None, now: float | None = None) -> dict | None:
    """The live claim ({mode, companion, since, ...}) or None if nothing is running."""
    data = _read(path or presence_path())
    if data is None or data.get("stop"):
        return None
    now = time.time() if now is None else now
    try:
        fresh = now - float(data.get("beat", 0)) <= STALE_S
    except (TypeError, ValueError):
        return None
    return data if fresh else None


def request_stop(path: Path | None = None) -> bool:
    """Ask whatever companion is running to close itself. True if one was asked."""
    path = path or presence_path()
    with _ownership_lock(path):
        data = current(path)
        if data is None:
            return False
        _write(path, dict(data, stop=True))
        return True


class Claim:
    """This process's hold on running.json. Pure apart from file I/O; testable."""

    def __init__(self, mode: str, companion: str, path: Path | None = None,
                 clock=time.time) -> None:
        self.path = path or presence_path()
        self.clock = clock
        self.token = secrets.token_hex(8)
        now = clock()
        self.data = {"token": self.token, "mode": mode, "companion": companion,
                     "since": now, "beat": now}
        self._last_beat = now
        with _ownership_lock(self.path):
            _write(self.path, self.data)

    def check(self) -> bool:
        """Refresh the heartbeat. False means: hand over and close."""
        with _ownership_lock(self.path):
            now = self.clock()
            on_disk = _read(self.path)
            if on_disk is not None and on_disk.get("token") != self.token:
                try:
                    taken = now - float(on_disk.get("beat", 0)) <= STALE_S
                except (TypeError, ValueError):
                    taken = False
                if taken:
                    return False                   # a newer companion took over
            if on_disk is not None and on_disk.get("token") == self.token and on_disk.get("stop"):
                return False                       # Home asked us to stop
            if on_disk is None or now - self._last_beat >= BEAT_S or \
                    on_disk.get("token") != self.token:
                self.data["beat"] = self._last_beat = now
                _write(self.path, self.data)
            return True

    def release(self) -> None:
        """Remove the claim if it is still ours."""
        with _ownership_lock(self.path):
            on_disk = _read(self.path)
            if on_disk is not None and on_disk.get("token") == self.token:
                try:
                    self.path.unlink()
                except OSError:
                    pass


def hold(root, mode: str, companion: str, on_stop) -> Claim | None:
    """Claim the desktop for a running overlay and watch for hand-over or stop."""
    try:
        claim = Claim(mode, companion)
    except Exception:                          # presence is a nicety, never a blocker
        return None

    def watch():
        try:
            keep = claim.check()
        except Exception:
            keep = True
        if not keep:
            print("PRESENCE handing over: another companion started or Home asked to stop",
                  flush=True)
            on_stop()
            return
        try:
            root.after(WATCH_MS, watch)
        except Exception:
            pass

    import atexit
    atexit.register(claim.release)
    root.after(WATCH_MS, watch)
    return claim
