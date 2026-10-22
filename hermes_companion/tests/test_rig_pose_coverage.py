"""The rigged (procedural) companions must actually LOOK like every move.

The rig has no art ceiling, so the only way it under-delivers is code: a pose
that the chains emit but `pose_params` does not know falls through to the
neutral default and the character stands still in a plain stance while the
engine thinks it is doing something. That is exactly what happened to
channel / point / sneak, and what happened to every gaze pose on astro (its LED
block had no left/right state, so all of them drew the same neutral dot).

These tests are the class-kill for that bug: every pose the behavior engine can
emit must render as a distinct move on every companion, not as the fallback.
"""
from __future__ import annotations

import importlib.util
import pathlib
import unittest

_SCRIPT = (pathlib.Path(__file__).resolve().parents[1]
           / "scripts" / "render_pose_sheet.py")
_spec = importlib.util.spec_from_file_location("render_pose_sheet", _SCRIPT)
_sheet = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(_sheet)

COMPANIONS = ("pet", "samurai", "astro", "herald", "nia", "nyamekra", "duet", "master", "skater")


class RigVocabularyTests(unittest.TestCase):
    def test_the_engine_pose_list_is_not_empty(self):
        poses = _sheet.engine_poses()
        self.assertGreater(len(poses), 60, poses)

    def test_no_emitted_pose_renders_as_the_unknown_pose_fallback(self):
        """A pose that renders identically to a nonsense pose name is dead."""
        poses = _sheet.engine_poses()
        for companion in COMPANIONS:
            with self.subTest(companion=companion):
                fallback = _sheet.signatures(companion, _sheet.FALLBACK_PROBE)
                dead = [p for p in poses
                        if _sheet.signatures(companion, p) == fallback]
                self.assertEqual(dead, [], f"{companion} draws these as a "
                                           f"neutral body: {dead}")

    def test_the_previously_dead_martial_moves_are_alive(self):
        """Regression names: these three shipped as neutral-body fallbacks."""
        fallback = _sheet.signatures("pet", _sheet.FALLBACK_PROBE)
        for pose in ("channel", "point", "sneak"):
            with self.subTest(pose=pose):
                self.assertNotEqual(_sheet.signatures("pet", pose), fallback)

    def test_astro_honours_gaze_direction(self):
        """astro's LED block must not collapse left/right into neutral."""
        left = _sheet.signatures("astro", "look_at_user")
        right = _sheet.signatures("astro", "look_at_input")
        self.assertNotEqual(left, right)
        self.assertNotEqual(left, _sheet.signatures("astro", _sheet.FALLBACK_PROBE))

    def test_every_pose_renders_without_error_on_every_companion(self):
        for companion in COMPANIONS:
            for pose in _sheet.engine_poses():
                with self.subTest(companion=companion, pose=pose):
                    canvas = _sheet.render(companion, pose, 0.5)
                    self.assertGreater(canvas.opaque(), 200)

    def test_vocabulary_stays_broad(self):
        """Floor, so a mass collapse onto a few signatures fails loudly."""
        for companion in COMPANIONS:
            with self.subTest(companion=companion):
                poses = _sheet.engine_poses()
                distinct = {_sheet.signatures(companion, p) for p in poses}
                self.assertGreaterEqual(len(distinct), 70,
                                        f"{companion}: only {len(distinct)} looks")


if __name__ == "__main__":
    unittest.main()
