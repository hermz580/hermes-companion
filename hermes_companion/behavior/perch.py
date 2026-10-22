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
        self.span = 1                            # usable length of the current title bar
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
        self.span = span
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
    style: str = "hop"           # "hop" | "drop" | "teleport"

    @property
    def duration(self) -> float:
        dist = math.hypot(self.x1 - self.x0, self.y1 - self.y0)
        if self.style == "teleport":
            return 0.9
        if self.style == "drop":
            return max(0.25, math.sqrt(max(1.0, abs(self.y1 - self.y0)) / 900.0) * 1.4)
        return min(1.1, max(0.45, dist / 900.0))

    def at(self, now: float) -> tuple[int, int, float]:
        t = min(1.0, max(0.0, (now - self.start) / self.duration))
        if self.style == "teleport":                       # gone, then there
            x, y = (self.x0, self.y0) if t < 0.5 else (self.x1, self.y1)
            return int(round(x)), int(round(y)), t
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


def _faced(pose: str, going_left: bool) -> str:
    from hermes_companion.animation.characters import has_pose
    back = pose + "_back"
    return back if going_left and has_pose(back) else pose


class PerchDriver:
    """Applies PerchPlanner decisions to a surface + Director each tick.

    The surface needs ``x``, ``home_x``, ``home_y``, ``w``, ``h``, ``set_x``
    and ``set_y``; the Director keeps ownership of x while a chain plays.
    """

    DEFAULT_POSES = {"hop": "leap", "drop": "jump"}
    TELEPORT_PX = 700          # farther than this, a character that can teleports

    def __init__(self, surface, director, sensors, *, log=print,
                 poses: dict | None = None, feet_y: int | None = None,
                 ride: dict | None = None) -> None:
        self.surface, self.director, self.sensors = surface, director, sensors
        # A character's own way of getting between windows, e.g. Nyamekra:
        # {"hop": "soar", "drop": "landing", "teleport": "feather_teleport"}
        self.poses = dict(self.DEFAULT_POSES, **(poses or {}))
        # Where its feet are in its frame; bigger stages put them lower than the
        # round pet's 192/220, and guessing made them sink into title bars.
        feet = int(feet_y) if feet_y else int(FEET_Y * surface.h / 220)
        self.planner = PerchPlanner(surface.w, surface.h, floor_y=surface.home_y, feet_y=feet)
        self.applied: Anchor | None = None
        self.motion: PerchMotion | None = None
        self.log = log
        # Riding the title bar: {"ride": pose, "rest": pose, "speed": px/s,
        # "ride_s": s, "rest_s": s}. The character rides the edge of the window
        # it's perched on, then sits a while, instead of standing still.
        self.ride = ride
        self._ride_dir = 1.0
        self._ride_since: float | None = None
        self._last_tick: float | None = None
        self._ride_pose: str | None = None

    def enter(self, now: float, top_y: int) -> None:
        """Drop in from the top of the screen down to the floor, in view the whole way."""
        x = int(self.surface.x)
        floor = Anchor(x, int(self.planner.floor_y), "floor", 0, "entrance")
        self.planner.anchor = self.applied = floor
        self.motion = PerchMotion(x, top_y, x, floor.y, now, "drop")
        self.log("PERCH drop -> floor (entrance)")

    def _ride_tick(self, now: float) -> None:
        """Ride along the title bar, bounce at its ends, then rest on the edge."""
        dt = 0.0 if self._last_tick is None else min(0.2, max(0.0, now - self._last_tick))
        if not (self.ride and self.perched and self.motion is None):
            self._ride_since = None
            if self._ride_pose is not None and self.motion is None:
                self.director.idle_pose, self.director.idle_progress = "idle_bob", None
            self._ride_pose = None
            return
        if self._ride_since is None:
            self._ride_since = now
        cycle = self.ride.get("ride_s", 7.0) + self.ride.get("rest_s", 6.0)
        riding = (now - self._ride_since) % cycle < self.ride.get("ride_s", 7.0)
        if riding and self.planner._offset_frac is not None:
            step = self._ride_dir * self.ride.get("speed", 70.0) * dt / max(1, self.planner.span)
            frac = self.planner._offset_frac + step
            if not 0.0 <= frac <= 1.0:
                self._ride_dir = -self._ride_dir
                frac = min(1.0, max(0.0, frac))
            self.planner._offset_frac = frac
        self._ride_pose = self.ride["ride"] if riding else self.ride["rest"]
        self.director.idle_pose = self._ride_pose
        self.director.idle_progress = (now * 0.7) % 1.0

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
        self._ride_tick(now)
        self._last_tick = now
        snap = getattr(self.sensors, "prev", None)
        anchor = self.planner.plan(snap, hermes_quiet=hermes_state in QUIET_STATES,
                                   current_x=int(self.surface.x), now=now)
        if anchor != self.applied:
            prev = self.applied
            self.applied = anchor
            instant = getattr(getattr(self.surface, "renderer", None), "reduced_motion", False)
            if instant or (anchor.reason == "ride" and prev is not None and prev.kind == "perch"
                           and self.motion is None):
                self._apply(anchor.x, anchor.y)
            else:
                style = "drop" if anchor.kind == "floor" and anchor.y > self.surface.home_y + 20 \
                    else "hop"
                far = math.hypot(anchor.x - self.surface.x, anchor.y - self.surface.home_y)
                if "teleport" in self.poses and far > self.TELEPORT_PX:
                    style = "teleport"
                self.motion = PerchMotion(self.surface.x, self.surface.home_y,
                                          anchor.x, anchor.y, now, style)
                self.log(f"PERCH {style} -> {anchor.kind} ({anchor.reason})")
        if self.motion is not None:
            x, y, _t = self.motion.at(now)
            self.director.idle_pose = self._pose_for(self.motion)
            self.director.idle_progress = min(_t, 0.999)
            self._apply(x, y)
            if self.motion.done(now):
                self.motion = None
                self.director.idle_pose = "idle_bob"
                self.director.idle_progress = None

    def _pose_for(self, motion: "PerchMotion") -> str:
        return _faced(self.poses.get(motion.style, "leap"), motion.x1 < motion.x0)


def make_driver(surface, director, sensors, traits: dict, *, log=print) -> "PerchDriver":
    """A PerchDriver set up from a character's traits (play and live share this)."""
    feet = traits.get("feet_y")
    frame_h = getattr(getattr(surface, "renderer", None), "fh", None) or surface.h
    scaled = int(feet * surface.h / frame_h) if feet else None   # sizes keep the same feet line
    return PerchDriver(surface, director, sensors, log=log, poses=traits.get("perch_poses"),
                       feet_y=scaled, ride=traits.get("perch_ride"))


def start_roaming(director, traits: dict, wander_s: float | None) -> None:
    """Characters that roam keep wherever they end up and wander more often."""
    if traits.get("roam") and wander_s is not None:
        director.roam = True
        director.wander_s = min(wander_s, 18.0)
    else:
        director.wander_s = wander_s
