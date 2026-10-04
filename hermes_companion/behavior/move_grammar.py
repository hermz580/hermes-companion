"""Generative move grammar: thousands of performances, one truth per event.

A chain from ``behavior_rules`` is the *signature*: the poses that say what
Hermes is actually doing (terminal work, approval wave, failure recoil).  The
grammar decorates a signature with *flourishes* - entry/exit gestures, a
different gait to get somewhere, a different tempo - so the same event rarely
looks identical twice.

Invariants (enforced by tests/test_move_grammar.py):

* every signature pose survives, in order, with its original duration;
* flourish moods follow the chain's state, and a mood never borrows a pose
  that only success chains (or only failure chains) use - so decoration can
  never make a failure read as a success, or work read as either;
* gait swaps keep the step's net displacement, so the pet still lands where
  the signature put it;
* choices come from a caller-supplied ``random.Random``, so a fixed seed and
  the same events give the same performance.
"""
from __future__ import annotations

import random
from collections import deque
from math import isclose

from hermes_companion.core.state import State
from hermes_companion.movement.paths import net_offset

# Poses that are body language rather than evidence. tests/test_move_grammar.py
# checks each mood against the outcome chains that use the same poses.
FLOURISH_POSES: dict[str, tuple[str, ...]] = {
    "bright": ("excited", "hop", "bounce", "spin", "smug", "nod", "eyebrow_raise", "look_up", "idle_bob"),
    "focused": ("nod", "look_up", "look_down", "crack_knuckles", "check_watch", "watch", "tilt", "idle_bob"),
    "uneasy": ("scratch_head", "shake_head", "squint", "look_down", "head_tilt",
               "think", "check_watch", "idle_bob"),
    "calm": ("tilt", "look_around", "look_up", "look_down", "nod",
             "stretch", "idle_bob", "watch"),
}

_STATE_MOOD: dict[State, str] = {
    State.CELEBRATING: "bright",
    State.FRUSTRATED: "uneasy", State.CONFUSED: "uneasy",
    State.CONCERNED: "uneasy", State.RECOVERING: "uneasy",
    State.URGENT: "uneasy", State.CALLING_USER: "uneasy",
    State.IDLE: "calm", State.SLEEPING: "calm", State.CURIOUS: "calm",
    State.OBSERVING: "calm", State.LISTENING: "calm", State.WAITING: "calm",
}

# Urgent states keep their signature bare: decorating a call for the user
# would only delay it.
NO_FLOURISH_STATES = frozenset({State.URGENT, State.CALLING_USER})

# Gaits that may stand in for each other when travelling somewhere.
GAITS: tuple[str, ...] = ("dash", "run", "walk", "creep", "sprint", "tip",
                          "hop", "leap", "pounce", "zigzag", "overshoot",
                          "anticipate")
EASINGS: tuple[str, ...] = ("easeOutCubic", "easeInOutCubic", "easeInOutQuad",
                            "easeOutQuad", "easeInOutSine")
TEMPOS: tuple[float, ...] = (0.85, 0.92, 1.0, 1.08, 1.18)
FLOURISH_MS: tuple[int, ...] = (220, 280, 340, 420)


def mood_for(state: State) -> str:
    return _STATE_MOOD.get(state, "focused")


def _same_landing(a: str, b: str, dx: float, dy: float) -> bool:
    ax, ay = net_offset(a, dx, dy)
    bx, by = net_offset(b, dx, dy)
    return isclose(ax, bx, abs_tol=0.5) and isclose(ay, by, abs_tol=0.5)


def variant_space() -> int:
    """Lower bound on distinct decorations of a one-move chain."""
    per_mood = min(len(p) for p in FLOURISH_POSES.values())
    entries = 1 + per_mood + per_mood * (per_mood - 1)   # 0, 1 or 2 openers
    exits = 1 + per_mood
    gaits = len(GAITS) * len(EASINGS) * len(TEMPOS)
    return entries * exits * gaits * len(FLOURISH_MS)


class MoveGrammar:
    """Decorates signature steps; remembers recent flourishes to avoid repeats."""

    def __init__(self, rng: random.Random, memory: int = 6,
                 extra: dict[str, tuple[str, ...]] | None = None,
                 hints: dict[str, tuple[str, ...]] | None = None) -> None:
        self.rng = rng
        self.recent: deque[str] = deque(maxlen=memory)
        self.extra = dict(extra or {})
        # category -> preferred flourishes (e.g. Nyamekra channels the pyramid
        # for terminal work); used only when they fit the chain's mood.
        self.hints = dict(hints or {})
        # A companion may bring its own body-language moves (Nia's dances).
        # They join the shared pool for the same mood only.
        self.pools = {m: tuple(p) + tuple((extra or {}).get(m, ()))
                      for m, p in FLOURISH_POSES.items()}

    def _pick_flourish(self, mood: str, hint: str | None = None) -> dict:
        pool = [p for p in self.pools[mood] if p not in self.recent]
        preferred = [p for p in self.hints.get(hint or "", ()) if p in (pool or self.pools[mood])]
        if preferred and self.rng.random() < 0.75:
            pool = preferred
        pose = self.rng.choice(pool or self.pools[mood])
        self.recent.append(pose)
        return {"pose": pose, "duration_ms": self.rng.choice(FLOURISH_MS),
                "role": "flourish"}

    def _vary_move(self, move: dict) -> dict:
        out = dict(move)
        dx, dy = float(move.get("dx", 0)), float(move.get("dy", 0))
        original = str(move.get("type", ""))
        if original in GAITS:
            options = [g for g in GAITS if _same_landing(original, g, dx, dy)]
            out["type"] = self.rng.choice(options or [original])
            out["easing"] = self.rng.choice(EASINGS)
        tempo = self.rng.choice(TEMPOS)
        out["duration_ms"] = max(180, int(round(float(move.get("duration_ms", 0)) * tempo)))
        return out

    def decorate(self, steps: list[dict], state: State, hint: str | None = None) -> list[dict]:
        signature = [dict(s, role="signature") for s in steps]
        if not signature or state in NO_FLOURISH_STATES:
            return signature
        mood = mood_for(state)
        for step in signature:
            if step.get("move"):
                step["move"] = self._vary_move(step["move"])
        openers = [self._pick_flourish(mood, hint)
                   for _ in range(self.rng.choice((0, 1, 1, 2)))]
        closers = [self._pick_flourish(mood, hint)
                   for _ in range(self.rng.choice((0, 0, 1)))]
        return openers + signature + closers


def signature_of(steps: list[dict]) -> list[tuple[str, int]]:
    return [(s["pose"], int(s.get("duration_ms", 0)))
            for s in steps if s.get("role", "signature") == "signature"]
