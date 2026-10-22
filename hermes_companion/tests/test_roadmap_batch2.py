"""Roadmap batch 2: speech bubbles, opt-in sound, personality memory."""
import io
import wave

from hermes_companion.core.personality import Personality
from hermes_companion.renderer.voice import NOTES, SAY, Chimes, Voice, bubble_image, synth


class Clock:
    def __init__(self):
        self.t = 0.0

    def __call__(self):
        return self.t


def test_voice_speaks_hermes_states_truthfully_and_once():
    shown, played, clock = [], [], Clock()
    v = Voice(shown.append, played.append, clock=clock)
    v.on_attention("working", "Working with terminal")
    v.on_attention("needs-you", "Decision needed")
    v.on_attention("needs-you", "Decision needed")          # no repeat
    v.on_attention("complete", "Task complete")
    assert shown == ["Working with terminal…", "I need your OK!", "All done!"]
    assert played == ["attention", "done"]
    clock.t = 10
    v.tick()
    assert shown[-1] is None                                  # bubble hides


def test_voice_never_invents_content():
    # Every template only uses the fixed attention label - no free text slot.
    for template in SAY.values():
        assert template.replace("{label}", "") .count("{") == 0


def test_curiosity_quips_are_rate_limited():
    shown, clock = [], Clock()
    v = Voice(shown.append, None, clock=clock)
    v.on_curious("user.back")
    v.on_curious("cursor.circling")
    assert shown == ["Welcome back!"]
    clock.t = 30
    v.on_curious("cursor.circling")
    assert shown[-1] == "Hi there!"


def test_bubble_image_wraps_and_has_a_tail():
    img = bubble_image("A very long status line that certainly needs to wrap onto two lines")
    assert img.height > 50 and img.width <= 220
    assert img.getpixel((img.width // 2, img.height - 4))[3] > 0


def test_chimes_are_valid_wav_and_rate_limited():
    for name in NOTES:
        with wave.open(io.BytesIO(synth(name))) as w:
            assert w.getnframes() > 500 and w.getframerate() == 22050
    clock = Clock()
    c = Chimes(clock=clock)
    c.enabled = False
    c("done")
    c("start")                                                # too soon
    clock.t = 2
    c("start")
    assert c.played == ["done", "start"]


def test_personality_learns_rhythm_only(tmp_path):
    path = tmp_path / "p.json"
    p = Personality.load(path)
    day = 1_700_000_000.0
    assert p.start(day) == "Hello! I'm here when you need me."
    for i in range(40):
        p.activity(day + i * 60)
    # a long break, then a welcome back
    assert p.activity(day + 40 * 60 + 25 * 60) == "Welcome back - nice break."
    p.save()
    raw = path.read_text()
    for forbidden in ("title", "key", "text", "clipboard", "path"):
        assert forbidden not in raw.lower()
    q = Personality.load(path)
    assert q.breaks == 1 and sum(q.hours) == 41
    assert q.start(day + 2 * 86400).startswith("Good ")


def test_stretch_reminder_after_a_longer_than_usual_session(tmp_path):
    p = Personality.load(tmp_path / "p.json")
    p.session_minutes = [30.0, 30.0, 30.0]
    p.session_start = p.last_active = 1_000_000.0
    said = [p.activity(1_000_000.0 + m * 60) for m in range(1, 60)]
    assert "Longer than usual today - time for a stretch?" in said
    assert said.count("Longer than usual today - time for a stretch?") == 1


def test_chimes_go_quiet_without_an_audio_device(monkeypatch):
    import sys
    import types
    fake = types.SimpleNamespace(SND_MEMORY=4)

    def fail(*_a):
        raise RuntimeError("Failed to play sound")

    fake.PlaySound = fail
    monkeypatch.setitem(sys.modules, "winsound", fake)
    c = Chimes()
    c.enabled = True
    c._play(b"RIFF")                      # must not raise
    assert c.enabled is False
