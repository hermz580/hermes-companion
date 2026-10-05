"""Chain Director (spec rev1 §10 chain execution + §32 walking skeleton).

Drives a Chain step-by-step on a fixed tick. Surface-agnostic: it calls
surface.set_pose(pose, progress) for static steps and surface.set_x(x) for
movement steps, so the exact same director runs headless (deterministic proof)
and on the Tk overlay (visual proof).

Interruption semantics (§10.1/§10.2):
  - granularity = atomic step: an interrupt only takes effect at a step
    boundary; the current step always finishes
  - an equal-or-lower-priority chain never preempts an active chain
  - a strictly-higher-priority chain is deferred to the next step boundary
"""
from __future__ import annotations

import math
import time

from hermes_companion.behavior.behavior_engine import BehaviorEngine, Chain
from hermes_companion.behavior.priorities import NON_INTERRUPTIBLE_STEPS
from hermes_companion.core.state import State
from hermes_companion.movement import easing


# How high a travel step rises mid-flight (px). Flying travels arc through the
# air; ground travels stay on the floor. Teleports jump, they never arc.
ARC_BY_POSE = {"soar": 150, "swoop": 110, "wing_dash": 60, "feather_teleport": 0,
               "hover": 150, "lunge": 110, "ink_slide": 50, "crack_portal": 0}
ARC_BY_TYPE = {"fly": 120, "leap": 100, "pounce": 90, "hop": 60, "bounce": 50,
               "pop": 80, "drift": 40, "zigzag": 30}


def arc_height(step: dict) -> int:
    move = step.get("move") or {}
    if move.get("easing") == "teleport":
        return 0
    pose = str(step.get("pose", "")).removesuffix("_back")
    if pose in ARC_BY_POSE:
        return ARC_BY_POSE[pose]
    return ARC_BY_TYPE.get(move.get("type", ""), 0)


class Director:
    def __init__(self, engine: BehaviorEngine, surface, fps: int = 30,
                 clock=time.monotonic) -> None:
        self.engine = engine
        self.surface = surface
        self.fps = fps
        self.clock = clock
        self.chain: Chain | None = None
        self.step_i = 0
        self.step_start = 0.0
        self._pending: Chain | None = None
        # Start from where the surface really is; starting at 0 made the first
        # move of every chain fling the pet toward the left screen edge.
        self._x = getattr(surface, "x", 0) or 0
        self._move_start = 0
        self._step_first = True
        self.idle_pose = "idle_bob"
        self.idle_progress: float | None = None   # set while perch travel plays
        # Quiet-time strolls: after this many seconds with nothing happening she
        # wanders across the screen (and onto the next monitor) and comes back.
        self.wander_s: float | None = None
        self.wander_blocked = lambda: False       # e.g. while perched on a window
        self._quiet_since = self.clock()
        self._wander_rng = __import__("random").Random(5)
        # Return-to-anchor phase. A chain ends wherever its last move stopped,
        # so without this the pet parks where it finished and never comes back
        # (observed: a left-running chain left it pinned at the screen edge, and
        # before the monitor clamp existed, off every panel entirely).
        self._returning = False
        self._return_from = 0.0
        self._return_start = 0.0
        self._return_ms = 0.0

    # -- chain control -----------------------------------------------------
    def start_chain(self, chain: Chain) -> None:
        if self.chain is not None:
            # Equal-or-lower priority never preempts an active chain (§10.3).
            if chain.priority >= self.chain.priority:
                return
            # Higher priority interrupts at the next step boundary: finish the
            # current atomic step first (§10.1/§10.2), then switch.
            self._pending = chain
            return
        self._activate(chain)

    def _activate(self, chain: Chain) -> None:
        self.chain = chain
        self._pending = None
        self.step_i = 0
        self.step_start = self.clock()
        self._step_first = True
        self._returning = False
        self.surface.set_state(chain.state.value)
        self._quiet_since = self.clock()

    def current_pose(self) -> str:
        if self.chain is None:
            return self.idle_pose
        return self.chain.steps[self.step_i]["pose"]

    def _step_done(self) -> bool:
        if self.chain is None:
            return True
        step = self.chain.steps[self.step_i]
        return (self.clock() - self.step_start) * 1000 >= step["duration_ms"]

    # -- per-tick driver ---------------------------------------------------
    def step(self, dt: float) -> None:
        # A deferred interrupt applies at the step boundary.
        if self._pending is not None and self.chain is not None and self._step_done():
            self._activate(self._pending)
        if self.chain is None:
            if self._wander_due():
                self._activate(self._wander_chain())
                return
            self._idle(dt)
            return

        step = self.chain.steps[self.step_i]
        t = (self.clock() - self.step_start)
        t_ms = t * 1000
        duration = step["duration_ms"]

        if self._step_first:
            if step.get("move"):
                self._move_start = self._x
            self._step_first = False

        if step.get("move"):
            self._drive_move(step, t_ms, duration)
        else:
            self.surface.set_pose(step["pose"], min(t_ms / max(duration, 1), 1.0))

        if t_ms >= duration:
            if step.get("move") and getattr(self.surface, "lift", None) is not None:
                self.surface.lift(0)                    # every travel lands
            self.step_i += 1
            self.step_start = self.clock()
            self._step_first = True
            if self.step_i >= len(self.chain.steps):
                self.chain = None
                self._quiet_since = self.clock()
                self.engine.end_chain()
                self.idle_pose = "idle_bob"
                self.surface.set_state(State.IDLE.value)
                if not self._begin_return():
                    self.surface.set_pose("idle_bob", 0.0)

    def _drive_move(self, step: dict, t_ms: float, duration: int) -> None:
        move = step["move"]
        if t_ms == 0.0:
            self._move_start = self._x
        t = min(t_ms / max(duration, 1), 1.0)
        eased = easing.apply(move.get("easing", "easeOutCubic"), t)
        self._x = self._move_start + move["dx"] * eased
        self.surface.set_x(int(self._x))
        lift = getattr(self.surface, "lift", None)
        if lift is not None:
            lift(int(-arc_height(step) * math.sin(math.pi * t)))
        self.surface.set_pose(step["pose"], t)

    # -- quiet-time wandering -------------------------------------------------
    def _wander_due(self) -> bool:
        if self.wander_s is None or self._returning or self.engine.state == State.SLEEPING \
                or self.wander_blocked():
            return False
        return self.clock() - self._quiet_since >= self.wander_s

    def _wander_chain(self) -> Chain:
        rng = self._wander_rng
        dx = rng.choice((380, 520, 680, 820)) * rng.choice((-1, 1))
        kind = rng.choice(("drift", "run", "hop", "dash"))
        steps = [{"pose": "walk_to_workspace" if dx > 0 else "return_home", "duration_ms": 1500,
                  "move": {"type": kind, "dx": dx, "dy": 0, "easing": "easeInOutCubic"}},
                 {"pose": "look_around", "duration_ms": 1600, "move": None}]
        travel = getattr(self.engine, "travel", None)
        if travel is not None:
            steps = [travel(s, rng) for s in steps]
        return Chain(name="wander", state=State.IDLE, priority=9, steps=steps)

    # -- return to anchor ---------------------------------------------------
    RETURN_SPEED_PX_S = 260.0
    RETURN_MIN_MS = 400.0

    def _home_x(self) -> float | None:
        home = getattr(self.surface, "home_x", None)
        return float(home) if isinstance(home, (int, float)) else None

    def _begin_return(self) -> bool:
        """Walk back to the anchor instead of freezing where a chain ended.

        Only engages when the surface actually has a home anchor, so headless
        and card surfaces keep their existing behaviour exactly.
        """
        home = self._home_x()
        if home is None or abs(self._x - home) <= 8:
            return False
        self._returning = True
        self._return_from = self._x
        self._return_start = self.clock()
        self._return_ms = max(
            self.RETURN_MIN_MS,
            abs(home - self._x) / self.RETURN_SPEED_PX_S * 1000.0)
        return True

    def _idle(self, dt: float) -> None:
        if self._returning:
            home = self._home_x()
            if home is None:
                self._returning = False
            else:
                t = min((self.clock() - self._return_start) * 1000.0
                        / max(self._return_ms, 1.0), 1.0)
                eased = easing.apply("easeInOutCubic", t)
                self._x = self._return_from + (home - self._return_from) * eased
                self.surface.set_x(int(self._x))
                self.surface.set_pose("return_home", t)
                if t >= 1.0:
                    self._returning = False
                    self._x = home
                    # Push the exact anchor: the eased sample just before this
                    # can end a pixel or two short, which would leave the pet
                    # slightly off home for good.
                    self.surface.set_x(int(home))
                # Idle progression is paused for the few seconds of the walk
                # back, so the pet never falls asleep mid-return.
                return
        pose = self.engine.idle_tick(dt)
        if pose is not None:
            self.idle_pose = pose
        if self.engine.state == State.SLEEPING:
            self.idle_pose = "sleep"
        progress = self.idle_progress if self.idle_progress is not None \
            else time.monotonic() % 2.0
        self.surface.set_pose(self.idle_pose, progress)
