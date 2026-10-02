"""Curiosity: the companion notices what the user does on the desktop.

Input is a stream of content-free ``Observation`` records from
``renderer.desktop_sensors``: *that* the cursor moved, a window gained focus,
typing started, the clipboard changed - never key values, window titles,
clipboard text or screen pixels.

The drive is simple and bounded:

* each kind of observation has a base interest (salience);
* noticing something habituates the pet to it (interest drops, then recovers),
  so a constantly moving cursor stops being fascinating;
* boredom grows while nothing is noticed and lowers the bar to react.

Truth comes first. While Hermes is working, curiosity may only *glance*
(short, in place, never travelling) and only when the overlay is free. While
Hermes needs the user, has failed, or is stuck, curiosity is silent so the
signal stays unambiguous.
"""
from __future__ import annotations

import random
from dataclasses import dataclass, field
from enum import Enum


class Seen(str, Enum):
    CURSOR_MOVED = "cursor.moved"
    CURSOR_DASHED = "cursor.dashed"          # fast flick across the screen
    CURSOR_RESTED = "cursor.rested"
    CURSOR_NEAR_PET = "cursor.near_pet"
    CURSOR_CIRCLING = "cursor.circling"      # lingering around the pet
    CLICK = "input.click"
    CLICK_BURST = "input.click_burst"
    DOUBLE_CLICK = "input.double_click"
    TYPING_STARTED = "input.typing_started"
    TYPING_FAST = "input.typing_fast"
    TYPING_PAUSED = "input.typing_paused"
    FOCUS_CHANGED = "window.focus_changed"
    FOCUS_FLIPPING = "window.focus_flipping"  # rapid alt-tab style switching
    WINDOW_MOVED = "window.moved"
    WINDOW_RESIZED = "window.resized"
    WINDOW_MAXIMIZED = "window.maximized"
    WINDOW_MINIMIZED = "window.minimized"
    CLIPBOARD_CHANGED = "clipboard.changed"
    USER_AWAY = "user.away"
    USER_BACK = "user.back"
    DISPLAY_CHANGED = "display.changed"
    LATE_NIGHT = "time.late_night"
    LONG_STRETCH = "time.long_stretch"       # long unbroken activity


@dataclass(frozen=True)
class Observation:
    kind: Seen
    t: float
    x: int | None = None     # a screen point worth looking at, if any
    y: int | None = None
    magnitude: float = 1.0   # bounded 0..1 intensity (speed, rate)


# Base interest 0..1. Things that happen near the pet or rarely rank higher.
SALIENCE: dict[Seen, float] = {
    Seen.CURSOR_MOVED: 0.15, Seen.CURSOR_DASHED: 0.55, Seen.CURSOR_RESTED: 0.25,
    Seen.CURSOR_NEAR_PET: 0.85, Seen.CURSOR_CIRCLING: 0.9,
    Seen.CLICK: 0.2, Seen.CLICK_BURST: 0.6, Seen.DOUBLE_CLICK: 0.4,
    Seen.TYPING_STARTED: 0.45, Seen.TYPING_FAST: 0.6, Seen.TYPING_PAUSED: 0.3,
    Seen.FOCUS_CHANGED: 0.5, Seen.FOCUS_FLIPPING: 0.65,
    Seen.WINDOW_MOVED: 0.45, Seen.WINDOW_RESIZED: 0.4,
    Seen.WINDOW_MAXIMIZED: 0.5, Seen.WINDOW_MINIMIZED: 0.5,
    Seen.CLIPBOARD_CHANGED: 0.55, Seen.USER_AWAY: 0.7, Seen.USER_BACK: 0.95,
    Seen.DISPLAY_CHANGED: 0.8, Seen.LATE_NIGHT: 0.7, Seen.LONG_STRETCH: 0.75,
}

# Several reactions per kind; each is a list of (pose, ms). "approach" means
# travel toward the observation's point first (quiet mode only).
REACTIONS: dict[Seen, tuple[tuple[bool, tuple[tuple[str, int], ...]], ...]] = {
    Seen.CURSOR_MOVED: ((False, (("watch", 700),)), (False, (("head_tilt", 500),))),
    Seen.CURSOR_DASHED: ((False, (("notice", 300), ("look_around", 700))),
                         (False, (("eyebrow_raise", 400), ("watch", 600))),
                         (True, (("notice", 250), ("peeking", 600)))),
    Seen.CURSOR_RESTED: ((True, (("peeking", 700), ("head_tilt", 500))),
                         (False, (("watch", 900),)),
                         (True, (("tip_to_workspace", 500), ("squint", 600)))),
    Seen.CURSOR_NEAR_PET: ((False, (("look_at_user", 500), ("wave", 700))),
                           (False, (("excited", 500), ("hop", 400))),
                           (False, (("smug", 600), ("head_tilt", 400))),
                           (False, (("eyebrow_raise", 400), ("nod", 400)))),
    Seen.CURSOR_CIRCLING: ((False, (("spin", 520), ("look_at_user", 500))),
                           (False, (("dance", 1200),)),
                           (False, (("bounce", 600), ("wave", 600)))),
    Seen.CLICK: ((False, (("notice", 300),)), (False, (("look_at_input", 500),))),
    Seen.CLICK_BURST: ((False, (("notice", 300), ("eyebrow_raise", 500))),
                       (True, (("hop", 400), ("watch", 700)))),
    Seen.DOUBLE_CLICK: ((False, (("look_at_input", 500), ("nod", 300))),),
    Seen.TYPING_STARTED: ((False, (("look_at_input", 700),)),
                          (True, (("tip_to_workspace", 500), ("watch", 900)))),
    Seen.TYPING_FAST: ((False, (("look_at_input", 500), ("excited", 500))),
                       (False, (("crack_knuckles", 600), ("watch", 700))),
                       (False, (("bounce", 500),))),
    Seen.TYPING_PAUSED: ((False, (("think", 700),)), (False, (("head_tilt", 600),))),
    Seen.FOCUS_CHANGED: ((True, (("peeking", 700),)),
                         (False, (("look_around", 800),)),
                         (True, (("notice", 300), ("squint", 500)))),
    Seen.FOCUS_FLIPPING: ((False, (("look_around", 600), ("scratch_head", 600))),
                          (False, (("spin", 520), ("shrug", 500)))),
    Seen.WINDOW_MOVED: ((True, (("watch", 700),)), (False, (("look_around", 600),))),
    Seen.WINDOW_RESIZED: ((False, (("stretch", 800),)), (True, (("inspect", 700),))),
    Seen.WINDOW_MAXIMIZED: ((False, (("look_up", 600), ("eyebrow_raise", 400))),),
    Seen.WINDOW_MINIMIZED: ((False, (("look_down", 600), ("shrug", 400))),),
    Seen.CLIPBOARD_CHANGED: ((False, (("notice", 300), ("nod", 400))),
                             (False, (("eyebrow_raise", 400), ("smug", 500)))),
    Seen.USER_AWAY: ((False, (("look_around", 900), ("sit", 1500))),
                     (False, (("yawn", 1200),))),
    Seen.USER_BACK: ((False, (("wake", 400), ("wave", 900))),
                     (False, (("excited", 500), ("wave", 700)))),
    Seen.DISPLAY_CHANGED: ((False, (("shock", 300), ("look_around", 900))),),
    Seen.LATE_NIGHT: ((False, (("yawn", 1200), ("look_at_user", 600))),),
    Seen.LONG_STRETCH: ((False, (("stretch", 1000), ("look_at_user", 600))),),
}

# Hermes attention states (core.attention) in which curiosity stays silent.
SILENT_STATES = frozenset({"needs-you", "issue", "stuck", "paused"})
BUSY_STATES = frozenset({"starting", "working", "delegating", "reviewing"})


@dataclass
class Reaction:
    kind: Seen
    steps: list[dict]
    glance: bool                     # in-place only, safe while Hermes works
    target: tuple[int, int] | None = None


@dataclass
class CuriosityModel:
    seed: int | None = None
    threshold: float = 0.45
    habituation: float = 0.55        # interest multiplier after noticing
    recovery_s: float = 45.0         # time to regain full interest
    boredom_rate: float = 0.01       # per second without a reaction
    busy_gap_s: float = 8.0          # min seconds between glances while working
    rng: random.Random = field(init=False)

    def __post_init__(self) -> None:
        self.rng = random.Random(f"{self.seed}:curiosity")
        self._interest: dict[Seen, float] = {k: 1.0 for k in Seen}
        self._last_seen: dict[Seen, float] = {}
        self._last_reaction_t: float | None = None
        self.log: list[dict] = []

    def interest(self, kind: Seen, now: float) -> float:
        last = self._last_seen.get(kind)
        level = self._interest[kind]
        if last is not None and self.recovery_s > 0:
            level = min(1.0, level + (now - last) / self.recovery_s * (1.0 - level))
        return level

    def boredom(self, now: float) -> float:
        if self._last_reaction_t is None:
            return 0.25
        return min(0.35, (now - self._last_reaction_t) * self.boredom_rate)

    def observe(self, obs: Observation, hermes_state: str = "quiet") -> Reaction | None:
        now = obs.t
        if hermes_state in SILENT_STATES:
            return None
        busy = hermes_state in BUSY_STATES
        if busy and self._last_reaction_t is not None \
                and now - self._last_reaction_t < self.busy_gap_s:
            return None

        score = SALIENCE[obs.kind] * self.interest(obs.kind, now) \
            * (0.6 + 0.4 * max(0.0, min(1.0, obs.magnitude)))
        bar = self.threshold - self.boredom(now) + (0.15 if busy else 0.0)
        if score < bar:
            return None

        options = REACTIONS[obs.kind]
        if busy:
            options = tuple(o for o in options if not o[0]) or ()
            if not options:
                return None
        approach, poses = self.rng.choice(options)
        steps = [{"pose": p, "duration_ms": ms, "role": "curiosity"} for p, ms in poses]
        if busy:
            # A glance: one short pose, no travel, nothing that reads as work.
            steps = [dict(steps[0], duration_ms=min(600, steps[0]["duration_ms"]))]
        target = (obs.x, obs.y) if approach and obs.x is not None and obs.y is not None else None

        self._interest[obs.kind] = self.interest(obs.kind, now) * self.habituation
        self._last_seen[obs.kind] = now
        self._last_reaction_t = now
        self.log.append({"t": round(now, 2), "seen": obs.kind.value,
                         "poses": [s["pose"] for s in steps], "glance": busy})
        return Reaction(obs.kind, steps, glance=busy, target=target)
