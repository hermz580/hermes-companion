"""The procedural live overlay must keep ticking when no chain is active.

The bug: `_tick` only stepped the director while `director.chain is not None`.
A chain therefore ended and the companion froze exactly where it stopped —
idle progression never advanced and the return-to-anchor walk could never run
(it happens precisely when there is no active chain). On a multi-monitor desk
that left the pet parked at the far edge of the virtual desktop, alive,
always-on-top, and invisible.

This is tested without opening a window: the overlay's tick body is exercised
against a stub root, which is where the defect lived.
"""
from __future__ import annotations

import types
import unittest

from hermes_companion.renderer.overlay import ProceduralLiveOverlay


class _RecordingDirector:
    def __init__(self, chain=None) -> None:
        self.chain = chain
        self.steps = 0
        self.dts: list[float] = []

    def step(self, dt: float) -> None:
        self.steps += 1
        self.dts.append(dt)


def _overlay(director) -> ProceduralLiveOverlay:
    """An overlay with a stub root: no Tk window, same tick code path."""
    overlay = ProceduralLiveOverlay.__new__(ProceduralLiveOverlay)
    overlay._director = director
    overlay.root = types.SimpleNamespace(after=lambda _ms, _fn: None)
    return overlay


class ProceduralTickTests(unittest.TestCase):
    def test_the_director_is_stepped_even_with_no_active_chain(self):
        director = _RecordingDirector(chain=None)
        overlay = _overlay(director)
        overlay._tick()
        self.assertEqual(director.steps, 1,
                         "idle/return work is skipped when the chain is None")

    def test_the_director_is_stepped_while_a_chain_is_active(self):
        director = _RecordingDirector(chain=object())
        overlay = _overlay(director)
        overlay._tick()
        self.assertEqual(director.steps, 1)

    def test_a_missing_director_does_not_raise(self):
        overlay = _overlay(None)
        overlay._tick()  # must not raise before the engine is bound

    def test_the_tick_reschedules_itself(self):
        scheduled = []
        director = _RecordingDirector(chain=None)
        overlay = _overlay(director)
        overlay.root = types.SimpleNamespace(
            after=lambda ms, fn: scheduled.append((ms, fn)))
        overlay._tick()
        self.assertEqual(len(scheduled), 1)
        self.assertEqual(scheduled[0][0], 33)


if __name__ == "__main__":
    unittest.main()
