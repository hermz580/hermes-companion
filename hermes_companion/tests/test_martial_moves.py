"""Martial / energy moves must mean what the event actually evidences.

A flourish is decorative; a move that reads as "powering up" or "striking" is a
claim about what Hermes did. These tests keep the vocabulary honest: each move
is bound to the event it represents, no failure may celebrate, and the power-up
belongs to a granted approval rather than to any notion of success.
"""

import pytest

from hermes_companion.behavior.behavior_rules import (
    CHAINS,
    CHANNEL,
    DASH_RIGHT,
    EVADE_ROLL,
    GUARD,
    STRIKE,
    SURGE,
)
from hermes_companion.core.events import EventKind
from hermes_companion.movement.paths import is_moving, net_offset
from hermes_companion.renderer.petdex_overlay import POSE_ROW

MARTIAL = {
    "strike": STRIKE,
    "evade_roll": EVADE_ROLL,
    "guard": GUARD,
    "surge": SURGE,
    "channel": CHANNEL,
}

# Moves that are flourishes: the pet ends the beat where it began.
IN_PLACE = ["evade_roll", "guard", "surge", "channel"]


def _moves(kind):
    return [step.get("move") for step in CHAINS[kind][1] if step.get("move")]


@pytest.mark.parametrize("name", sorted(MARTIAL))
def test_every_martial_move_is_real_motion(name):
    mv = MARTIAL[name]
    assert is_moving(mv["type"], mv["dx"], mv["dy"]), f"{name} would never animate"


@pytest.mark.parametrize("name", IN_PLACE)
def test_flourishes_leave_the_pet_where_it_stood(name):
    """Otherwise a reaction would quietly walk the pet across the screen."""
    mv = MARTIAL[name]
    assert net_offset(mv["type"], mv["dx"], mv["dy"]) == (0.0, 0.0)


def test_the_strike_covers_the_same_ground_as_the_dash_it_replaced():
    """Staging is preserved: this lunges toward the work, not somewhere else."""
    assert STRIKE["dx"] == DASH_RIGHT["dx"]
    assert net_offset(STRIKE["type"], STRIKE["dx"], STRIKE["dy"])[0] == DASH_RIGHT["dx"]


def test_each_move_is_attached_to_the_event_it_represents():
    assert STRIKE in _moves(EventKind.TOOL_STARTED)
    assert EVADE_ROLL in _moves(EventKind.TOOL_FAILED)
    assert GUARD in _moves(EventKind.APPROVAL_REQUIRED)
    assert SURGE in _moves(EventKind.APPROVAL_APPROVED)
    assert CHANNEL in _moves(EventKind.SUBAGENT_STARTED)


def test_the_power_up_belongs_to_a_granted_approval_and_nowhere_else():
    """SURGE reads as 'energy granted'. Only an approval actually says that."""
    places = [kind for kind, (_, steps) in CHAINS.items()
              if any(step.get("move") is SURGE for step in steps)]
    assert places == [EventKind.APPROVAL_APPROVED]


@pytest.mark.parametrize("kind", [EventKind.TOOL_FAILED, EventKind.SUBAGENT_FAILED])
def test_nothing_celebrates_a_failure(kind):
    moves = _moves(kind)
    assert SURGE not in moves, "a failure must not power up"
    assert CHANNEL not in moves, "a failure is not a summoning"


def test_the_guard_waits_rather_than_working():
    """Waiting on the user is a hold, not progress: no travel, no outcome."""
    assert net_offset(GUARD["type"], GUARD["dx"], GUARD["dy"]) == (0.0, 0.0)
    assert GUARD["dx"] == 0


@pytest.mark.parametrize("pose", ["sneak", "channel", "dash_to_workspace", "wait", "hop"])
def test_martial_poses_map_to_a_real_row(pose):
    """An unmapped pose silently renders as idle, which would hide the move."""
    assert pose in POSE_ROW, f"{pose} is not mapped to a sprite row"
