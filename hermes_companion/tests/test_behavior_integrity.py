"""Headless regression tests for behavior/animation wiring integrity."""
from __future__ import annotations

import unittest
from contextlib import redirect_stdout
from io import StringIO

from hermes_companion.behavior.behavior_engine import BehaviorEngine
from hermes_companion.behavior.behavior_rules import (
    CATEGORY_TOOL_FAILED,
    CATEGORY_TOOL_FINISHED,
    CATEGORY_TOOL_STARTED,
    CHAINS,
    CHAINS_BY_CATEGORY,
    EMOTIONAL_ARCS,
    IDLE_PROGRESSION,
)
from hermes_companion.core.events import EventKind
from hermes_companion.core.state import State
from hermes_companion.renderer.petdex_overlay import POSE_ROW


CATEGORY_FAMILIES = (
    (EventKind.TOOL_STARTED, CATEGORY_TOOL_STARTED),
    (EventKind.TOOL_FINISHED, CATEGORY_TOOL_FINISHED),
    (EventKind.TOOL_FAILED, CATEGORY_TOOL_FAILED),
)


def reachable_poses() -> set[str]:
    poses = {step["pose"] for _state, steps in CHAINS.values() for step in steps}
    for _kind, specs in CATEGORY_FAMILIES:
        poses.update(step["pose"] for _state, steps in specs.values() for step in steps)
    poses.update(pose for _threshold, pose, _duration in IDLE_PROGRESSION)
    return poses


class BehaviorIntegrityTests(unittest.TestCase):
    def test_category_index_is_built_from_final_category_definitions(self):
        expected = {
            (kind, category): spec
            for kind, specs in CATEGORY_FAMILIES
            for category, spec in specs.items()
        }
        self.assertEqual(expected, CHAINS_BY_CATEGORY)

    def test_every_reachable_pose_has_an_atlas_mapping(self):
        self.assertEqual([], sorted(reachable_poses() - set(POSE_ROW)))

    def test_idle_progression_contains_only_concrete_poses_and_ends_at_sleep(self):
        poses = [pose for _threshold, pose, _duration in IDLE_PROGRESSION]
        self.assertFalse(set(poses) & set(EMOTIONAL_ARCS))
        self.assertTrue(set(poses) <= set(POSE_ROW))
        self.assertEqual((300.0, "sleep", 0), IDLE_PROGRESSION[-1])

    def test_idle_sleep_occurs_at_declared_sleep_threshold(self):
        engine = BehaviorEngine(seed=1)
        elapsed = 0.0
        for threshold, pose, _duration in IDLE_PROGRESSION[:-1]:
            self.assertIsNone(engine.idle_tick(threshold - elapsed - 0.1))
            elapsed = threshold - 0.1
            self.assertEqual(pose, engine.idle_tick(0.1))
            elapsed = threshold
        self.assertNotEqual(State.SLEEPING, engine.state)
        sleep_at = IDLE_PROGRESSION[-1][0]
        self.assertIsNone(engine.idle_tick(sleep_at - elapsed - 0.1))
        self.assertEqual("sleep", engine.idle_tick(0.1))
        self.assertEqual(State.SLEEPING, engine.state)
        self.assertIsNone(engine.idle_tick(60.0))

    def test_verifier_returns_failure_status_when_any_check_fails(self):
        from hermes_companion.tests import verify_moves

        with redirect_stdout(StringIO()):
            status = verify_moves.main(checks=[("forced failure", False)])
        self.assertEqual(1, status)


if __name__ == "__main__":
    unittest.main()
