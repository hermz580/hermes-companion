"""The overlay must never park the pet where no monitor exists.

The bug this guards: `set_x` clamped against the VIRTUAL SCREEN bounding box.
On a desk with panels at vertical offsets that box covers regions no monitor
occupies, so a left-running chain clamped the pet to the box's far edge
(x=-2102, y=620 on the machine where this was found) — below every physical
panel. The window was alive, always-on-top, and completely invisible.

Rules tested here:
  * a requested position always lands inside a REAL monitor rectangle,
  * a long run stays on the panel the pet was placed on (no teleporting),
  * a home requested in dead space is corrected at start,
  * no monitor information at all degrades to the old behaviour, not a crash.
"""
from __future__ import annotations

import unittest

from hermes_companion.renderer.overlay import (
    clamp_into, clamp_to_monitors, monitor_for_point)

# The layout that produced the bug: a 1600x900 primary with three 1920x1080
# panels above/beside it. The virtual bounding box is (-2102,-1087)-(3658,900)
# and large parts of it belong to no monitor.
REAL_LAYOUT = [
    (0, 0, 1600, 900),
    (-2102, -1086, -182, -6),
    (1738, -1087, 3658, -7),
    (-182, -1080, 1738, 0),
]
PET_W, PET_H = 200, 220


def _on_a_monitor(x: int, y: int, rects=REAL_LAYOUT) -> bool:
    return any(l <= x and x + PET_W <= r and t <= y and y + PET_H <= b
               for (l, t, r, b) in rects)


class OverlayClampTests(unittest.TestCase):
    def test_a_requested_position_always_lands_on_a_real_monitor(self):
        """Sweep, including the exact coordinates that swallowed the pet."""
        cases = [(1360, 620), (-3000, 620), (-2102, 620), (9999, 620),
                 (0, 0), (-9999, -9999), (2000, -1200), (700, 616)]
        for x, y in cases:
            with self.subTest(x=x, y=y):
                cx, cy = clamp_to_monitors(x, y, PET_W, PET_H, REAL_LAYOUT)
                self.assertTrue(_on_a_monitor(cx, cy),
                                f"({x},{y}) -> ({cx},{cy}) is off every monitor")

    def test_the_reported_bug_position_is_not_reachable(self):
        """(-2102, 620) was the invisible spot; it must correct to a panel."""
        cx, cy = clamp_to_monitors(-2102, 620, PET_W, PET_H, REAL_LAYOUT)
        self.assertNotEqual((cx, cy), (-2102, 620))
        self.assertTrue(_on_a_monitor(cx, cy))

    def test_a_long_run_stays_on_the_home_panel(self):
        """Staying on the home monitor is what stops cross-screen teleporting."""
        home = monitor_for_point(1360, 620, REAL_LAYOUT)
        self.assertEqual(home, (0, 0, 1600, 900))
        for dash in (-4000, -600, 0, 1200, 5000):
            with self.subTest(dash=dash):
                cx, cy = clamp_into(home, 1360 + dash, 620, PET_W, PET_H)
                self.assertGreaterEqual(cx, 0)
                self.assertLessEqual(cx + PET_W, 1600)
                self.assertEqual(cy, 620)

    def test_home_requested_in_dead_space_is_corrected(self):
        """A user can type --x/--y; dead space must not be honoured as home."""
        rect = monitor_for_point(-2102, 620, REAL_LAYOUT)
        self.assertIsNotNone(rect)
        cx, cy = clamp_into(rect, -2102, 620, PET_W, PET_H)
        self.assertTrue(_on_a_monitor(cx, cy))

    def test_the_primary_panel_is_the_one_containing_the_origin(self):
        self.assertEqual(monitor_for_point(10, 10, REAL_LAYOUT), (0, 0, 1600, 900))

    def test_clamp_never_exceeds_a_monitor_even_when_it_is_smaller_than_the_pet(self):
        tiny = [(0, 0, 100, 100)]
        cx, cy = clamp_into(tiny[0], 500, 500, PET_W, PET_H)
        self.assertEqual((cx, cy), (0, 0))

    def test_no_monitor_information_degrades_instead_of_crashing(self):
        self.assertEqual(clamp_to_monitors(1234, 567, PET_W, PET_H, []), (1234, 567))
        self.assertIsNone(monitor_for_point(0, 0, []))


if __name__ == "__main__":
    unittest.main()
