"""Content-free desktop sensors feeding ``core.curiosity``.

Everything here is polled, diffed and thrown away. What is read:

* cursor position and mouse-button up/down state;
* the *handle*, rectangle and minimized/maximized flags of the foreground
  window - never its title, process or pixels;
* the system last-input tick (to tell typing apart from mouse use - no key
  values are ever read);
* the clipboard *sequence number* - a counter, never the contents;
* the number of attached displays and the local hour.

Levels:

* ``off``     - nothing is sampled;
* ``ambient`` - cursor, windows, displays, away/back, time of day;
* ``full``    - ambient plus clicks, typing rhythm and clipboard changes.

The platform API is injectable so the logic is testable off Windows.
"""
from __future__ import annotations

import math
import time
from collections import deque
from dataclasses import dataclass

from hermes_companion.core.curiosity import Observation, Seen

LEVELS = ("off", "ambient", "full")
FULL_ONLY = frozenset({Seen.CLICK, Seen.CLICK_BURST, Seen.DOUBLE_CLICK,
                       Seen.TYPING_STARTED, Seen.TYPING_FAST, Seen.TYPING_PAUSED,
                       Seen.CLIPBOARD_CHANGED})


@dataclass(frozen=True)
class Snapshot:
    cursor: tuple[int, int]
    buttons_down: bool
    fg_handle: int
    fg_rect: tuple[int, int, int, int] | None
    fg_minimized: bool
    fg_maximized: bool
    last_input_ms: int
    clipboard_seq: int
    displays: int
    hour: int


class WindowsDesktopApi:
    """Reads the Snapshot fields through user32 (Windows only)."""

    def __init__(self) -> None:
        import ctypes
        import ctypes.wintypes as wt

        self._ct, self._wt = ctypes, wt
        self.user32 = ctypes.windll.user32

        class LASTINPUTINFO(ctypes.Structure):
            _fields_ = [("cbSize", wt.UINT), ("dwTime", wt.DWORD)]

        self._lii = LASTINPUTINFO()
        self._lii.cbSize = ctypes.sizeof(LASTINPUTINFO)

    def snapshot(self) -> Snapshot:
        ct, wt, u = self._ct, self._wt, self.user32
        pt = wt.POINT()
        u.GetCursorPos(ct.byref(pt))
        buttons = any(u.GetAsyncKeyState(vk) & 0x8000 for vk in (0x01, 0x02, 0x04))
        hwnd = int(u.GetForegroundWindow() or 0)
        rect = None
        if hwnd:
            r = wt.RECT()
            if u.GetWindowRect(hwnd, ct.byref(r)):
                rect = (r.left, r.top, r.right, r.bottom)
        u.GetLastInputInfo(ct.byref(self._lii))
        return Snapshot(
            cursor=(pt.x, pt.y), buttons_down=bool(buttons), fg_handle=hwnd,
            fg_rect=rect,
            fg_minimized=bool(hwnd and u.IsIconic(hwnd)),
            fg_maximized=bool(hwnd and u.IsZoomed(hwnd)),
            last_input_ms=int(self._lii.dwTime),
            clipboard_seq=int(u.GetClipboardSequenceNumber()),
            displays=int(u.GetSystemMetrics(80)),  # SM_CMONITORS
            hour=time.localtime().tm_hour,
        )


class DesktopSensors:
    AWAY_S = 120.0
    REST_S = 2.5
    TYPING_GAP_S = 1.5
    LONG_STRETCH_S = 50 * 60.0

    def __init__(self, api, level: str = "full", pet_box=None) -> None:
        if level not in LEVELS:
            raise ValueError(f"level must be one of {LEVELS}")
        self.api = api
        self.level = level
        self.pet_box = pet_box or (lambda: None)   # -> (x0, y0, x1, y1) or None
        self.prev: Snapshot | None = None
        self._moved_at = 0.0
        self._rest_reported = True
        self._last_input_change = 0.0
        self._away = False
        self._typing_since: float | None = None
        self._typing_events: deque[float] = deque(maxlen=40)
        self._clicks: deque[float] = deque(maxlen=8)
        self._focus_changes: deque[float] = deque(maxlen=6)
        self._near_pet: deque[float] = deque(maxlen=12)
        self._active_since: float | None = None
        self._late_reported_day: int | None = None
        self._stretch_reported = False

    @classmethod
    def for_platform(cls, level: str = "full", pet_box=None) -> "DesktopSensors | None":
        if level == "off":
            return None
        try:
            return cls(WindowsDesktopApi(), level, pet_box)
        except Exception:
            return None   # not Windows, or user32 unavailable: no curiosity

    def sample(self, now: float | None = None) -> list[Observation]:
        if self.level == "off":
            return []
        now = time.monotonic() if now is None else now
        snap = self.api.snapshot()
        prev, self.prev = self.prev, snap
        if prev is None:
            self._moved_at = self._last_input_change = now
            self._active_since = now
            return []
        out = self._diff(prev, snap, now)
        if self.level != "full":
            out = [o for o in out if o.kind not in FULL_ONLY]
        return out

    def _diff(self, prev: Snapshot, snap: Snapshot, now: float) -> list[Observation]:
        out: list[Observation] = []
        add = lambda kind, x=None, y=None, m=1.0: out.append(Observation(kind, now, x, y, m))
        cx, cy = snap.cursor
        dist = math.hypot(cx - prev.cursor[0], cy - prev.cursor[1])
        moved = dist > 3
        input_changed = snap.last_input_ms != prev.last_input_ms

        # -- away / back --------------------------------------------------
        if input_changed:
            if self._away:
                self._away = False
                self._active_since = now
                self._stretch_reported = False
                add(Seen.USER_BACK, cx, cy)
            self._last_input_change = now
        elif not self._away and now - self._last_input_change > self.AWAY_S:
            self._away = True
            self._active_since = None
            add(Seen.USER_AWAY)

        # -- cursor ---------------------------------------------------------
        if moved:
            self._moved_at = now
            self._rest_reported = False
            speed = min(1.0, dist / 600.0)
            add(Seen.CURSOR_DASHED if dist > 500 else Seen.CURSOR_MOVED, cx, cy, speed)
            box = self.pet_box()
            if box is not None:
                x0, y0, x1, y1 = box
                margin = 80
                if x0 - margin <= cx <= x1 + margin and y0 - margin <= cy <= y1 + margin:
                    self._near_pet.append(now)
                    recent = [t for t in self._near_pet if now - t < 4.0]
                    add(Seen.CURSOR_CIRCLING if len(recent) >= 8 else Seen.CURSOR_NEAR_PET,
                        cx, cy)
        elif not self._rest_reported and now - self._moved_at > self.REST_S:
            self._rest_reported = True
            add(Seen.CURSOR_RESTED, cx, cy)

        # -- clicks (button state edges only) -----------------------------
        if snap.buttons_down and not prev.buttons_down:
            self._clicks.append(now)
            recent = [t for t in self._clicks if now - t < 1.5]
            if len(recent) >= 4:
                add(Seen.CLICK_BURST, cx, cy, min(1.0, len(recent) / 8))
            elif len(recent) >= 2 and recent[-1] - recent[-2] < 0.4:
                add(Seen.DOUBLE_CLICK, cx, cy)
            else:
                add(Seen.CLICK, cx, cy, 0.5)

        # -- typing rhythm: input happened, but no mouse movement or button --
        if input_changed and not moved and not snap.buttons_down and not prev.buttons_down:
            self._typing_events.append(now)
            if self._typing_since is None:
                self._typing_since = now
                add(Seen.TYPING_STARTED, cx, cy)
            else:
                rate = len([t for t in self._typing_events if now - t < 3.0]) / 3.0
                if rate >= 4.0:
                    add(Seen.TYPING_FAST, cx, cy, min(1.0, rate / 10.0))
        elif self._typing_since is not None and self._typing_events \
                and now - self._typing_events[-1] > self.TYPING_GAP_S:
            self._typing_since = None
            add(Seen.TYPING_PAUSED)

        # -- windows --------------------------------------------------------
        rect = snap.fg_rect
        centre = ((rect[0] + rect[2]) // 2, (rect[1] + rect[3]) // 2) if rect else (None, None)
        if snap.fg_handle != prev.fg_handle and snap.fg_handle:
            self._focus_changes.append(now)
            recent = [t for t in self._focus_changes if now - t < 6.0]
            add(Seen.FOCUS_FLIPPING if len(recent) >= 4 else Seen.FOCUS_CHANGED, *centre)
        elif snap.fg_handle and snap.fg_handle == prev.fg_handle:
            if snap.fg_minimized and not prev.fg_minimized:
                add(Seen.WINDOW_MINIMIZED, *centre)
            elif snap.fg_maximized and not prev.fg_maximized:
                add(Seen.WINDOW_MAXIMIZED, *centre)
            elif rect and prev.fg_rect and rect != prev.fg_rect:
                same_size = (rect[2] - rect[0], rect[3] - rect[1]) == \
                    (prev.fg_rect[2] - prev.fg_rect[0], prev.fg_rect[3] - prev.fg_rect[1])
                add(Seen.WINDOW_MOVED if same_size else Seen.WINDOW_RESIZED, *centre)

        # -- clipboard, displays, time ----------------------------------------
        if snap.clipboard_seq != prev.clipboard_seq:
            add(Seen.CLIPBOARD_CHANGED, cx, cy)
        if snap.displays != prev.displays:
            add(Seen.DISPLAY_CHANGED)
        day = int(now // 86400)
        if snap.hour in (0, 1, 2, 3, 4) and not self._away and self._late_reported_day != day:
            self._late_reported_day = day
            add(Seen.LATE_NIGHT)
        if self._active_since is not None and not self._stretch_reported \
                and now - self._active_since > self.LONG_STRETCH_S:
            self._stretch_reported = True
            add(Seen.LONG_STRETCH)
        return out
