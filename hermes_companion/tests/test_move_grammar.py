"""Variety must never change what a chain says about Hermes."""
import random

import pytest

from hermes_companion.behavior.behavior_engine import BehaviorEngine
from hermes_companion.behavior.behavior_rules import CHAINS, CHAINS_BY_CATEGORY
from hermes_companion.behavior.move_grammar import (
    FLOURISH_POSES, NO_FLOURISH_STATES, MoveGrammar, mood_for, signature_of,
    variant_space,
)
from hermes_companion.core.events import EventKind, SemanticEvent
from hermes_companion.movement.paths import net_offset
from hermes_companion.renderer.petdex_overlay import POSE_ROW

ALL_SPECS = list(CHAINS.items()) + list(CHAINS_BY_CATEGORY.items())
POSITIVE = {EventKind.TOOL_FINISHED, EventKind.TASK_COMPLETE,
            EventKind.SUBAGENT_FINISHED, EventKind.APPROVAL_APPROVED}
NEGATIVE = {EventKind.TOOL_FAILED, EventKind.SUBAGENT_FAILED,
            EventKind.APPROVAL_REJECTED}


def _kind(key):
    return key[0] if isinstance(key, tuple) else key


def _poses_for(kinds):
    return {s["pose"] for k, (_st, steps) in ALL_SPECS if _kind(k) in kinds for s in steps}


def test_space_is_thousands():
    assert variant_space() >= 10_000


def test_flourish_poses_are_drawable():
    for pool in FLOURISH_POSES.values():
        assert set(pool) <= set(POSE_ROW)


def test_moods_never_borrow_the_opposite_outcome():
    pos, neg = _poses_for(POSITIVE), _poses_for(NEGATIVE)
    pos_only, neg_only = pos - neg, neg - pos
    assert not set(FLOURISH_POSES["bright"]) & neg_only
    assert not set(FLOURISH_POSES["uneasy"]) & pos_only
    for mood in ("focused", "calm"):
        assert not set(FLOURISH_POSES[mood]) & (pos_only | neg_only), mood


@pytest.mark.parametrize("key", [k for k, _ in ALL_SPECS], ids=str)
def test_signature_survives_1000_seeds(key):
    state, steps = dict(ALL_SPECS)[key]
    expected = [(s["pose"], int(s.get("duration_ms", 0))) for s in steps]
    expected_landing = [net_offset(s["move"].get("type", ""), s["move"].get("dx", 0),
                                   s["move"].get("dy", 0)) for s in steps if s.get("move")]
    for seed in range(1000):
        out = MoveGrammar(random.Random(seed)).decorate([dict(s) for s in steps], state)
        assert signature_of(out) == expected
        flourishes = [s["pose"] for s in out if s["role"] == "flourish"]
        assert set(flourishes) <= set(FLOURISH_POSES[mood_for(state)])
        if state in NO_FLOURISH_STATES:
            assert not flourishes
        landing = [net_offset(s["move"]["type"], s["move"]["dx"], s["move"]["dy"])
                   for s in out if s.get("move")]
        assert landing == pytest.approx(expected_landing, abs=0.5)


def test_variety_is_deterministic_and_actually_varies():
    def run(seed):
        e = BehaviorEngine(seed=seed, variety=True, clock=lambda: 0.0)
        return [p for _ in range(1) for p in
                e.handle(SemanticEvent(EventKind.TOOL_STARTED, category="terminal")).poses]
    assert run(5) == run(5)
    assert len({tuple(run(s)) for s in range(60)}) > 10


def test_variety_off_is_unchanged():
    ev = SemanticEvent(EventKind.TOOL_FINISHED, category="web")
    plain = BehaviorEngine(seed=3, clock=lambda: 0.0).handle(ev)
    spec = CHAINS_BY_CATEGORY.get((ev.kind, ev.category)) or CHAINS[ev.kind]
    assert plain.poses == [s["pose"] for s in spec[1]]
