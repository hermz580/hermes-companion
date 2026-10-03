"""Behavior engine (spec rev1 §17/§18). Deterministic with an injectable PRNG.

The engine maps semantic events to chains (state + atomic steps), enforces
priority + cooldown + idle progression, and records a reproducible trace for
QA (spec §34.9: same seed + same events -> identical trace).
"""
from __future__ import annotations

from collections import deque
import random
import time
from dataclasses import dataclass, field

from hermes_companion.behavior.behavior_rules import (
    CHAINS, CHAINS_BY_CATEGORY, IDLE_PROGRESSION,
)
from hermes_companion.behavior.move_grammar import MoveGrammar
from hermes_companion.behavior.priorities import EVENT_PRIORITY
from hermes_companion.core.events import EventKind, SemanticEvent
from hermes_companion.core.state import State, StateMachine


@dataclass
class Chain:
    name: str
    state: State
    priority: int
    steps: list[dict] = field(default_factory=list)

    @property
    def poses(self) -> list[str]:
        return [s["pose"] for s in self.steps]


class BehaviorEngine:
    def __init__(self, seed: int | None = None, extravagance: int = 3,
                 clock=time.monotonic, variety: bool = False,
                 extra_flourishes: dict | None = None) -> None:
        self.seed = seed
        self.rng = random.Random(seed)
        # Variety gets its own PRNG so turning it on never shifts the choices
        # the rest of the engine makes from self.rng.
        self.grammar = MoveGrammar(random.Random(f"{seed}:variety"),
                                   extra=extra_flourishes) if variety else None
        self.extravagance = extravagance
        self.clock = clock
        self.sm = StateMachine()
        self.active: Chain | None = None
        self._cooldown_until: dict[str, float] = {}
        self._recent_activity: deque[tuple[float, EventKind, str]] = deque(maxlen=32)
        self.idle_elapsed = 0.0
        self._idle_fired: set[float] = set()
        self.trace: list[dict] = []

    @property
    def state(self) -> State:
        return self.sm.state

    def end_chain(self) -> None:
        """Called by the Director when a chain finishes executing, so the
        engine's `active` stays truthful (no stale-interrupt logging)."""
        self.active = None

    def reset_context(self) -> None:
        """Clear session-scoped animation state without inventing an event."""
        self.active = None
        self._cooldown_until.clear()
        self._recent_activity.clear()
        self.idle_elapsed = 0.0
        self._idle_fired.clear()

    # -- event handling ----------------------------------------------------
    def handle(self, ev: SemanticEvent) -> Chain | None:
        prio = EVENT_PRIORITY.get(ev.kind, 5)
        now = self.clock()

        # Cooldown (spec §10.3): same-kind events suppressed within cooldown
        # unless urgency P0/P1. This is the storm rule's first half: bursts of
        # P2+ events collapse instead of restarting chains.
        key = ev.kind.value
        if now < self._cooldown_until.get(key, 0.0) and prio >= 2:
            self.trace.append({"event": "suppressed", "kind": key, "reason": "cooldown"})
            return None
        self._cooldown_until[key] = now + (0.0 if prio <= 1 else 0.8)

        # Any real activity wakes the pet (idle progression resets).
        if ev.kind not in (EventKind.AGENT_IDLE, EventKind.IDLE):
            self.idle_elapsed = 0.0
            self._idle_fired = set()
            self._recent_activity.append((now, ev.kind, ev.category or ""))
            self._prune_recent_activity(now)

        spec = CHAINS_BY_CATEGORY.get((ev.kind, ev.category)) or CHAINS.get(ev.kind)
        if spec is None:
            return None
        state, steps = spec
        combo_tier, combo_count = self._combo_tier(now)
        chain_steps = self._shape_combo_steps(list(steps), state, ev, combo_tier)
        if self.grammar is not None:
            chain_steps = self.grammar.decorate(chain_steps, state)
        chain = Chain(name=ev.kind.value, state=state, priority=prio, steps=chain_steps)

        # Interrupt check (spec §10): a higher-priority chain replaces the
        # active one. Step-level "finish current atomic step" is enforced by
        # the Director (renderer), which consults NON_INTERRUPTIBLE_STEPS.
        if self.active is not None and chain.priority < self.active.priority:
            self.trace.append({
                "event": "chain_interrupt",
                "from": self.active.name,
                "to": chain.name,
                "prio": chain.priority,
            })

        self.active = chain
        self.sm.set(chain.state)
        self.trace.append({
            "event": "chain",
            "name": chain.name,
            "state": chain.state.value,
            "category": ev.category or "",
            "combo_tier": combo_tier,
            "combo_count": combo_count,
            "steps": [s["pose"] for s in chain.steps],
        })
        return chain

    def _prune_recent_activity(self, now: float, window_s: float = 2.4) -> None:
        while self._recent_activity and (now - self._recent_activity[0][0]) > window_s:
            self._recent_activity.popleft()

    def _combo_tier(self, now: float, window_s: float = 2.4) -> tuple[int, int]:
        self._prune_recent_activity(now, window_s=window_s)
        count = sum(1 for _ts, kind, _cat in self._recent_activity
                    if kind not in (EventKind.AGENT_IDLE, EventKind.IDLE))
        if count <= 1:
            return 1, count
        if count == 2:
            return 2, count
        if count <= 4:
            return 3, count
        return 4, count

    def _shape_combo_steps(self, steps: list[dict], state: State, ev: SemanticEvent,
                           combo_tier: int) -> list[dict]:
        if combo_tier <= 1 or not steps:
            return [dict(step) for step in steps]

        shaped: list[dict] = []
        opener = self._combo_opener(state, ev, combo_tier)
        if opener is not None:
            shaped.append(opener)

        move_factor = 1.0 + 0.12 * (combo_tier - 1)
        pace_factor = max(0.72, 1.0 - 0.06 * (combo_tier - 1))
        for step in steps:
            shaped.append(self._scale_step(step, move_factor, pace_factor))

        finisher = self._combo_finisher(state, ev, combo_tier)
        if finisher is not None:
            shaped.append(finisher)
        return shaped

    def _scale_step(self, step: dict, move_factor: float, pace_factor: float) -> dict:
        out = dict(step)
        move = step.get("move")
        if move:
            scaled = dict(move)
            scaled["dx"] = int(round(float(scaled.get("dx", 0)) * move_factor))
            scaled["dy"] = int(round(float(scaled.get("dy", 0)) * move_factor))
            scaled["duration_ms"] = max(180, int(round(float(scaled.get("duration_ms", 0)) * pace_factor)))
            out["move"] = scaled
            out["duration_ms"] = max(180, int(round(float(out.get("duration_ms", 0)) * pace_factor)))
        else:
            out["duration_ms"] = max(160, int(round(float(out.get("duration_ms", 0)) * (1.0 + 0.05 * (1 if pace_factor < 1.0 else 0)))))
        return out

    def _combo_opener(self, state: State, ev: SemanticEvent, combo_tier: int) -> dict | None:
        if combo_tier < 2:
            return None
        if state in (State.FRUSTRATED, State.CONFUSED, State.CONCERNED):
            return {"pose": "scratch_head", "duration_ms": 240}
        if ev.kind in (EventKind.TOOL_STARTED, EventKind.TOOL_PROGRESS, EventKind.AGENT_STARTED):
            return {"pose": "think", "duration_ms": 260}
        if ev.kind in (EventKind.TOOL_FINISHED, EventKind.TASK_COMPLETE, EventKind.SUBAGENT_FINISHED):
            return {"pose": "check_watch", "duration_ms": 220}
        return {"pose": "think", "duration_ms": 240}

    def _combo_finisher(self, state: State, ev: SemanticEvent, combo_tier: int) -> dict | None:
        if combo_tier < 3:
            return None
        if state in (State.FRUSTRATED, State.CONFUSED, State.CONCERNED):
            return {"pose": "shake_head", "duration_ms": 260}
        if ev.kind in (EventKind.TOOL_FINISHED, EventKind.TASK_COMPLETE, EventKind.SUBAGENT_FINISHED):
            if combo_tier >= 4:
                return {"pose": "spin", "duration_ms": 520}
            return {"pose": "excited", "duration_ms": 460}
        return {"pose": "head_tilt", "duration_ms": 420}

    # -- idle progression (spec §14) ---------------------------------------
    def idle_tick(self, dt: float) -> str | None:
        """Return a new pose to play as idle_elapsed crosses thresholds, else None."""
        if self.state == State.SLEEPING:
            return None
        self.idle_elapsed += dt
        for threshold, pose, _ms in IDLE_PROGRESSION:
            if self.idle_elapsed >= threshold and threshold not in self._idle_fired:
                self._idle_fired.add(threshold)
                if pose == "sleep":
                    self.sm.set(State.SLEEPING)
                self.trace.append({"event": "idle_progression",
                                   "t": round(self.idle_elapsed, 1), "pose": pose})
                return pose
        return None
