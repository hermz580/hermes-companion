"""Curiosity notices a lot, stays content-free, and never talks over Hermes."""
from dataclasses import replace

from hermes_companion.core.curiosity import (
    REACTIONS, SALIENCE, CuriosityModel, Observation, Seen,
)
from hermes_companion.renderer.desktop_sensors import DesktopSensors, Snapshot
from hermes_companion.renderer.petdex_overlay import POSE_ROW

BASE = Snapshot(cursor=(500, 500), buttons_down=False, fg_handle=1,
                fg_rect=(0, 0, 800, 600), fg_minimized=False, fg_maximized=False,
                last_input_ms=1000, clipboard_seq=1, displays=1, hour=14)


class FakeApi:
    def __init__(self):
        self.snap = BASE

    def snapshot(self):
        return self.snap


def _sensors(level="full", pet_box=None):
    api = FakeApi()
    s = DesktopSensors(api, level, pet_box=pet_box)
    s.sample(0.0)
    return s, api


def _kinds(obs):
    return {o.kind for o in obs}


def test_every_kind_has_salience_and_drawable_reactions():
    assert set(SALIENCE) == set(Seen) == set(REACTIONS)
    for options in REACTIONS.values():
        for _approach, poses in options:
            assert all(p in POSE_ROW for p, _ in poses)


def test_notices_many_distinct_things():
    s, api = _sensors(pet_box=lambda: (480, 480, 560, 560))
    seen = set()
    steps = [
        replace(BASE, cursor=(1400, 500), last_input_ms=1100),          # dash
        replace(BASE, cursor=(510, 505), last_input_ms=1200),           # near pet
        replace(BASE, cursor=(510, 505), last_input_ms=1300),           # typing
        replace(BASE, cursor=(510, 505), last_input_ms=1300, buttons_down=True),
        replace(BASE, cursor=(510, 505), last_input_ms=1400, fg_handle=2,
                clipboard_seq=2),
        replace(BASE, cursor=(510, 505), last_input_ms=1400, fg_handle=2,
                fg_rect=(50, 50, 850, 650), clipboard_seq=2),            # moved
        replace(BASE, cursor=(510, 505), last_input_ms=1400, fg_handle=2,
                fg_rect=(50, 50, 950, 650), clipboard_seq=2, displays=2),  # resized
    ]
    for i, snap in enumerate(steps, 1):
        api.snap = snap
        seen |= _kinds(s.sample(i * 0.2))
    assert {Seen.CURSOR_DASHED, Seen.CURSOR_NEAR_PET, Seen.TYPING_STARTED,
            Seen.CLICK, Seen.FOCUS_CHANGED, Seen.CLIPBOARD_CHANGED,
            Seen.WINDOW_MOVED, Seen.WINDOW_RESIZED, Seen.DISPLAY_CHANGED} <= seen


def test_away_and_back():
    s, api = _sensors()
    assert Seen.USER_AWAY in _kinds(s.sample(200.0))
    api.snap = replace(BASE, last_input_ms=5000)
    assert Seen.USER_BACK in _kinds(s.sample(201.0))


def test_ambient_level_never_reports_input_rhythm_or_clipboard():
    s, api = _sensors("ambient")
    api.snap = replace(BASE, last_input_ms=2000, clipboard_seq=9)
    kinds = _kinds(s.sample(0.5))
    api.snap = replace(api.snap, buttons_down=True, last_input_ms=2100)
    kinds |= _kinds(s.sample(0.7))
    assert not kinds & {Seen.TYPING_STARTED, Seen.CLIPBOARD_CHANGED, Seen.CLICK}


def test_off_samples_nothing():
    s, api = _sensors("off")
    api.snap = replace(BASE, cursor=(0, 0), fg_handle=7)
    assert s.sample(1.0) == []


def test_silent_while_hermes_needs_the_user():
    m = CuriosityModel(seed=1)
    for state in ("needs-you", "issue", "stuck", "paused"):
        assert m.observe(Observation(Seen.CURSOR_NEAR_PET, 1.0), state) is None


def test_busy_hermes_only_gets_short_in_place_glances():
    m = CuriosityModel(seed=2)
    r = m.observe(Observation(Seen.CURSOR_CIRCLING, 1.0, 10, 10), "working")
    assert r is not None and r.glance and r.target is None
    assert len(r.steps) == 1 and r.steps[0]["duration_ms"] <= 600
    # rate limited while working
    assert m.observe(Observation(Seen.USER_BACK, 2.0), "working") is None


def test_habituation_then_recovery():
    m = CuriosityModel(seed=3, threshold=0.5, boredom_rate=0.0)
    hits = [m.observe(Observation(Seen.FOCUS_CHANGED, t), "quiet") is not None
            for t in (1.0, 1.5, 2.0, 2.5)]
    assert hits[0] and not all(hits)
    assert m.observe(Observation(Seen.FOCUS_CHANGED, 300.0), "quiet") is not None


def test_deterministic_for_a_seed():
    def run():
        m = CuriosityModel(seed=9)
        return [m.observe(Observation(k, i * 10.0, 5, 5), "quiet") for i, k in enumerate(Seen)]
    a, b = run(), run()
    assert [(r and r.steps) for r in a] == [(r and r.steps) for r in b]
