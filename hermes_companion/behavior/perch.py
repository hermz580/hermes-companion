"""Window-aware perching: the companion lives *on* your windows.

Pure decisions, no GUI. Given the latest content-free desktop snapshot
(foreground window rectangle + minimized/maximized flags) the planner says
where the pet should stand:

* **perch** on the active window's title bar while Hermes is quiet;
* **ride** along when that window is dragged (same window, new rectangle);
* **hop** to the new window when focus moves;
* **drop** to the floor when the window is minimized, maximized, closed,
  too small, or too close to the top of the screen to stand on;
* **floor** whenever Hermes is working, needs you, or failed - Hermes's
  truth plays on the floor, never mid-air.

``PerchMotion`` turns anchor changes into an arc (hop) or a gravity fall.
"""
from __future__ import annotations

import math
from dataclasses import dataclass

FEET_Y = 192          # where the feet are inside the 200x220 frame
MIN_WIDTH_EXTRA = 80  # a window must be this much wider than the pet
EDGE_MARGIN = 36


@dataclass(frozen=True)
class Anchor:
    x: int
    y: int
    kind: str           # "perch" | "floor"
    handle: int = 0
    reason: str = ""


class PerchPlanner:
    def __init__(self, pet_w: int, pet_h: int, floor_y: int, *,
                 feet_y: int = FEET_Y, screen_top: int = 0,
                 settle_s: float = 3.0) -> None:
        self.pet_w, self.pet_h = pet_w, pet_h
        self.floor_y = floor_y
        self.feet_y = feet_y
        self.screen_top = screen_top
        self.settle_s = settle_s
        self.anchor: Anchor | None = None
        self._offset_frac: float | None = None   # where along the title bar
        self._quiet_since: float | None = None

    def _perchable(self, snap) -> tuple[bool, str]:
        if snap is None or not snap.fg_handle or snap.fg_rect is None:
            return False, "no window"
        if snap.fg_minimized:
            return False, "minimized"
        if snap.fg_maximized:
            return False, "maximized"
        left, top, right, bottom = snap.fg_rect
        if right - left < self.pet_w + MIN_WIDTH_EXTRA or bottom - top < 80:
            return False, "too small"
        if top - self.feet_y < self.screen_top:
            return False, "no headroom"
        return True, ""

    def plan(self, snap, *, hermes_quiet: bool, current_x: int, now: float) -> Anchor:
        if not hermes_quiet:
            self._quiet_since = None
            return self._floor(current_x, "hermes busy")
        if self._quiet_since is None:
            self._quiet_since = now
        if now - self._quiet_since < self.settle_s and \
                (self.anchor is None or self.anchor.kind == "floor"):
            return self._floor(current_x, "settling")
        ok, why = self._perchable(snap)
        if not ok:
            self._offset_frac = None
            return self._floor(current_x, why)
        left, top, right, _bottom = snap.fg_rect
        span = max(1, (right - left) - self.pet_w - 2 * EDGE_MARGIN)
        same = self.anchor is not None and self.anchor.handle == snap.fg_handle
        if not same or self._offset_frac is None:
            # Land near where the pet already is, kept inside the title bar.
            want = current_x - (left + EDGE_MARGIN)
            self._offset_frac = min(1.0, max(0.0, want / span))
        x = int(left + EDGE_MARGIN + self._offset_frac * span)
        y = int(top - self.feet_y + 2)
        kind = "ride" if same and self.anchor.kind == "perch" else "hop"
        self.anchor = Anchor(x, y, "perch", snap.fg_handle, kind)
        return self.anchor

    def _floor(self, current_x: int, reason: str) -> Anchor:
        if self.anchor is not None and self.anchor.kind == "floor":
            return self.anchor
        self.anchor = Anchor(int(current_x), int(self.floor_y), "floor", 0, reason)
        return self.anchor


@dataclass
class PerchMotion:
    """A single hop (arc) or drop (gravity) between two anchors."""
    x0: float
    y0: float
    x1: float
    y1: float
    start: float
    style: str = "hop"           # "hop" | "drop"

    @property
    def duration(self) -> float:
        dist = math.hypot(self.x1 - self.x0, self.y1 - self.y0)
        if self.style == "drop":
            return max(0.25, math.sqrt(max(1.0, abs(self.y1 - self.y0)) / 900.0) * 1.4)
        return min(1.1, max(0.45, dist / 900.0))

    def at(self, now: float) -> tuple[int, int, float]:
        t = min(1.0, max(0.0, (now - self.start) / self.duration))
        if self.style == "drop":
            ease = t * t                                   # accelerate like gravity
            x = self.x0 + (self.x1 - self.x0) * t
            y = self.y0 + (self.y1 - self.y0) * ease
        else:
            ease = 0.5 - 0.5 * math.cos(math.pi * t)
            apex = 60 + 0.25 * abs(self.y1 - self.y0)
            x = self.x0 + (self.x1 - self.x0) * ease
            y = self.y0 + (self.y1 - self.y0) * ease - apex * math.sin(math.pi * t)
        return int(round(x)), int(round(y)), t

    def done(self, now: float) -> bool:
        return now - self.start >= self.duration


QUIET_STATES = frozenset({"quiet", "complete"})


class PerchDriver:
    """Applies PerchPlanner decisions to a surface + Director each tick.

    The surface needs ``x``, ``home_x``, ``home_y``, ``w``, ``h``, ``set_x``
    and ``set_y``; the Director keeps ownership of x while a chain plays.
    """

    def __init__(self, surface, director, sensors, *, log=print) -> None:
        self.surface, self.director, self.sensors = surface, director, sensors
        self.planner = PerchPlanner(surface.w, surface.h, floor_y=surface.home_y)
        self.applied: Anchor | None = None
        self.motion: PerchMotion | None = None
        self.log = log

    @property
    def perched(self) -> bool:
        return self.applied is not None and self.applied.kind == "perch"

    def _apply(self, x: int, y: int) -> None:
        if self.director.chain is None:
            self.surface.home_x = x
            self.director._x = x
            self.director._returning = False
            # place_at re-resolves the monitor, so perching on a window on
            # another screen doesn't get clamped back to the old one.
            self.surface.place_at(x, y)
        else:
            self.surface.set_y(y)     # a chain owns x; only lift/lower it

    def tick(self, now: float, hermes_state: str) -> None:
        snap = getattr(self.sensors, "prev", None)
        anchor = self.planner.plan(snap, hermes_quiet=hermes_state in QUIET_STATES,
                                   current_x=int(self.surface.x), now=now)
        if anchor != self.applied:
            prev = self.applied
            self.applied = anchor
            if anchor.reason == "ride" and prev is not None and prev.kind == "perch" \
                    and self.motion is None:
                self._apply(anchor.x, anchor.y)
            else:
                style = "drop" if anchor.kind == "floor" and anchor.y > self.surface.home_y + 20 \
                    else "hop"
                self.motion = PerchMotion(self.surface.x, self.surface.home_y,
                                          anchor.x, anchor.y, now, style)
                self.log(f"PERCH {style} -> {anchor.kind} ({anchor.reason})")
        if self.motion is not None:
            x, y, _t = self.motion.at(now)
            self.director.idle_pose = "leap" if self.motion.style == "hop" else "jump"
            self._apply(x, y)
            if self.motion.done(now):
                self.motion = None
                self.director.idle_pose = "idle_bob"
