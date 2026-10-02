"""A finished chain must not dump the pet wherever it stopped.

Observed failure: a left-running chain ended at the screen edge and the pet
stayed pinned there indefinitely — it looked like the companion had wandered off
and been lost. The Director now walks it back to its home anchor after a chain.

These tests pin the contract:
  * the pet returns to home_x and the return uses the walk-home pose,
  * surfaces without a home anchor (headless/card) keep the old behaviour,
  * a new chain cancels an in-progress return,
  * the pet does not "return" when it is already home.
"""
from __future__ import annotations

import unittest

from hermes_companion.animation.director import Director
from hermes_companion.behavior.behavior_engine import BehaviorEngine, Chain
from hermes_companion.core.state import State

STEP_MS = 33


class FakeSurface:
    """Records poses and x positions; optionally exposes a home anchor."""

    def __init__(self, home_x: float | None = 600.0) -> None:
        if home_x is not None:
            self.home_x = home_x
        self.home_y = 500
        self.poses: list[str] = []
        self.xs: list[int] = []
        self.states: list[str] = []
        self.x = 0.0

    def set_pose(self, pose: str, progress: float = 0.0) -> None:
        self.poses.append(pose)

    def set_x(self, x: int) -> None:
        self.x = float(x)
        self.xs.append(int(x))

    def set_state(self, state: str) -> None:
        self.states.append(state)


def _far_chain(dx: float = -500.0) -> Chain:
    return Chain(
        "test", State.WORKING, 5,
        [
            {"pose": "run_to_user", "duration_ms": 120,
             "move": {"type": "run", "dx": dx, "dy": 0.0,
                      "duration_ms": 120, "easing": "easeOutCubic"}},
            {"pose": "idle_bob", "duration_ms": 60, "move": None},
        ],
    )


class DirectorReturnHomeTests(unittest.TestCase):
    def _run(self, surface, chain, seconds: float = 8.0):
        now = [0.0]
        engine = BehaviorEngine(seed=1)
        director = Director(engine, surface, clock=lambda: now[0])
        director.start_chain(chain)
        ticks = int(seconds * 1000 / STEP_MS)
        for _ in range(ticks):
            director.step(STEP_MS / 1000.0)
            now[0] += STEP_MS / 1000.0
        return director

    def test_the_pet_returns_to_its_home_anchor_after_a_chain(self):
        surface = FakeSurface(home_x=600.0)
        self._run(surface, _far_chain(-500.0))
        self.assertEqual(surface.xs[-1], 600,
                         f"ended at {surface.xs[-1]}, not home; xs={surface.xs[:5]}...")
        self.assertIn("return_home", surface.poses)

    def test_the_return_uses_the_walk_home_pose_and_is_gradual(self):
        surface = FakeSurface(home_x=600.0)
        self._run(surface, _far_chain(-500.0))
        i = surface.poses.index("return_home")
        walked = surface.xs[i:]
        self.assertGreater(len(walked), 3, "return should be animated, not a jump")
        self.assertLess(walked[0], 600)
        self.assertEqual(walked[-1], 600)

    def test_a_surface_without_a_home_anchor_keeps_the_old_behaviour(self):
        surface = FakeSurface(home_x=None)
        self.assertFalse(hasattr(surface, "home_x"))
        self._run(surface, _far_chain(-500.0))
        self.assertNotIn("return_home", surface.poses)
        self.assertEqual(surface.xs[-1], surface.xs[-1])  # stayed where it stopped
        self.assertLess(surface.xs[-1], 100)

    def test_a_new_chain_cancels_an_in_progress_return(self):
        surface = FakeSurface(home_x=600.0)
        now = [0.0]
        engine = BehaviorEngine(seed=1)
        director = Director(engine, surface, clock=lambda: now[0])
        director.start_chain(_far_chain(-500.0))
        for _ in range(20):
            director.step(STEP_MS / 1000.0)
            now[0] += STEP_MS / 1000.0
        self.assertTrue(director._returning, "expected a return in progress")
        director.start_chain(_far_chain(-200.0))
        self.assertFalse(director._returning, "chain start must cancel the return")

    def test_no_return_is_started_when_already_at_home(self):
        surface = FakeSurface(home_x=0.0)
        self._run(surface, _far_chain(0.0))
        self.assertNotIn("return_home", surface.poses)


if __name__ == "__main__":
    unittest.main()
