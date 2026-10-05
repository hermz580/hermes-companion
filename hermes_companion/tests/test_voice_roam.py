"""Spoken lines, bubbles that follow her, crossing monitors, and quiet-time strolls."""
from __future__ import annotations

from hermes_companion.renderer.voice import Speaker, Voice


def test_only_key_moments_are_said_aloud():
    shown, spoken = [], []
    v = Voice(shown.append, speak=spoken.append, clock=lambda: 0.0)
    v.on_attention("working", "Working with terminal")
    v.on_attention("needs-you", "")
    v.on_attention("complete", "")
    v.greet("Hello there")
    assert "I need your OK!" in spoken and "All done!" in spoken and "Hello there" in spoken
    assert not any(s.startswith("Working") for s in spoken)      # shown, not spoken
    assert any(s.startswith("Working") for s in shown)


def test_speaker_never_passes_unsafe_text_to_the_shell():
    cmd = Speaker().command("Hi'; Remove-Item C:\\ -Recurse; '")
    script = cmd[-1]
    assert "Remove-Item C:\\" not in script and ";" not in script.split("Speak(")[1]
    assert cmd[0] == "powershell" and "-NoProfile" in cmd


class _Pet:
    from hermes_companion.renderer.overlay import TkOverlay
    _next_monitor = TkOverlay._next_monitor
    _clamp = TkOverlay._clamp

    def __init__(self, mons):
        self.w, self.h, self.home_y, self.roam = 320, 300, 1080 - 300 - 48, True
        self._home_rect = mons[0]
        self._mon_cache, self._mon_at = mons, 1e18


def test_she_walks_onto_the_next_monitor_and_stays_on_its_floor():
    left, right = (0, 0, 1920, 1080), (1920, -200, 3840, 1240)    # second screen offset and taller
    pet = _Pet([left, right])
    x, y = pet._clamp(2100, pet.home_y)
    assert pet._home_rect == right and 1920 <= x <= 3840 - 320
    assert y == 1240 - 300 - 48                                    # same height above its floor
    pet.roam = False
    pet._home_rect = left
    assert pet._clamp(2100, 500)[0] == 1920 - 320                 # roaming off: stays put


def test_quiet_time_stroll_goes_far_and_comes_back():
    from hermes_companion.animation.director import Director
    from hermes_companion.behavior.behavior_engine import BehaviorEngine

    class Surf:
        x = home_x = 900
        home_y, w, h = 700, 320, 300

        def set_x(self, x):
            self.x = x

        def set_pose(self, *a):
            pass

        def set_state(self, *a):
            pass

    now = [0.0]
    d = Director(BehaviorEngine(seed=1), Surf(), clock=lambda: now[0])
    d.wander_s = 40.0
    xs = []
    for i in range(400):
        now[0] = i * 0.25
        d.step(0.25)
        xs.append(d.surface.x)
    assert max(abs(x - 900) for x in xs) >= 380                    # a real crossing
    assert abs(xs[-1] - 900) < 10 or d.chain is not None           # and home again
    d.wander_blocked = lambda: True
    d._quiet_since, d.chain = 0.0, None
    assert not d._wander_due()
