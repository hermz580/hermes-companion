"""New Hermes signals (thinking, heartbeat) and the bigger, bolder Nyamekra."""
from __future__ import annotations

import json
import time

import pytest

from hermes_companion import plugin as hooks


@pytest.fixture
def log(tmp_path, monkeypatch):
    path = tmp_path / "events.jsonl"
    monkeypatch.setattr(hooks, "_COMPANION_DIR", str(tmp_path))
    monkeypatch.setattr(hooks, "_EVENTS_LOG", str(path))
    monkeypatch.setattr(hooks, "_EVENT_KEY", b"k" * 32)
    monkeypatch.setattr(hooks, "_ENGINE_CACHE", None)
    hooks._last_think.clear()

    def read():
        if not path.exists():
            return []
        return [json.loads(line) for line in path.read_text().splitlines()]
    return read


def test_pre_llm_call_shows_thinking_once_per_burst(log):
    assert hooks.on_pre_llm_call(session_id="s", user_message="secret prompt") is None
    hooks.on_pre_llm_call(session_id="s", user_message="secret prompt")
    recs = log()
    assert [r["event"] for r in recs] == ["user.prompt_submitted"]
    assert "secret" not in json.dumps(recs)


def test_pre_llm_call_is_registered():
    names = []

    class Ctx:
        def register_hook(self, name, fn):
            names.append(name)
    hooks.register(Ctx())
    assert "pre_llm_call" in names


def test_long_tool_sends_heartbeats_and_stops(log, monkeypatch):
    monkeypatch.setattr(hooks, "HEARTBEAT_S", 0.1)
    hooks.on_pre_tool_call(tool_name="terminal", session_id="s", tool_call_id="x")
    time.sleep(0.45)
    hooks.on_post_tool_call(tool_name="terminal", session_id="s", tool_call_id="x")
    time.sleep(0.3)
    kinds = [r["event"] for r in log()]
    beats = kinds.count("tool.progress")
    assert beats >= 2
    assert kinds[0] == "tool.started" and "tool.finished" in kinds
    after = kinds[kinds.index("tool.finished") + 1:]
    assert "tool.progress" not in after          # stopped when the tool finished
    assert not hooks._BEATS


def test_rejection_is_its_own_reaction(log):
    hooks.on_post_approval_response(command="rm -rf /", choice="deny", session_key="s")
    rec = log()[0]
    assert rec["event"] == "approval.rejected"
    assert "rm -rf" not in json.dumps(rec)


def test_symbols_are_big_and_moves_are_bold():
    from hermes_companion.animation import nyamekra as N
    assert N.SYMBOL_SIZE >= 18 and N.EMBLEM_SCALE >= 1.5
    assert N.ARM_SWING >= 20 and N.BOUNCE_GAIN >= 2


def test_symbol_badge_covers_more_of_the_frame():
    from PIL import ImageChops
    from hermes_companion.renderer.smooth import FrameRenderer
    r = FrameRenderer("nyamekra", None)
    plain = r.frame("idle_bob", 0.25).getchannel("A")
    sym = r.frame("raise_sun", 0.25).getchannel("A")
    bbox = ImageChops.difference(plain, sym).getbbox()
    assert bbox is not None
    assert (bbox[2] - bbox[0]) >= 50 and (bbox[3] - bbox[1]) >= 50


def test_head_turns_left_front_and_right():
    from hermes_companion.animation.nyamekra import head_look
    assert head_look("idle_bob", 0.2, "", set(), 0.0) == 1.0
    assert head_look("idle_bob", 0.775, "", set(), 0.0) == pytest.approx(-1.0)
    assert abs(head_look("idle_bob", 0.66, "", set(), 0.0)) < 0.45     # facing you
    assert head_look("anything", 0.0, "left", set(), 0.0) == -1.0
    assert head_look("survey_realms", 0.0, "", {"scan"}, -0.7) == -0.7


def test_symbol_badge_never_covers_the_face():
    import math
    from hermes_companion.animation.nyamekra import _clear_of_head
    for hx in range(60, 140, 5):
        x, y = _clear_of_head(hx, 40, 28, 100, 45)
        assert math.hypot(x - 100, y - 45) >= 28 + 24 or not (30 <= x <= 170)
        assert 28 <= x <= 170


def test_hands_are_drawn_after_the_head():
    from hermes_companion.animation.nyamekra import draw_nyamekra

    class Rec:
        def __init__(self):
            self.calls = []

        def delete(self, *a):
            pass

        def __getattr__(self, name):
            return lambda *a, **k: self.calls.append((name, k.get("fill"), k.get("outline")))
    from hermes_companion.animation.nyamekra import _BODY as P
    c = Rec()
    draw_nyamekra(c, "raise_sun", 0.25)
    head = max(i for i, (n, f, o) in enumerate(c.calls) if n == "create_oval" and o == P["sheen"])
    talons = [i for i, (n, f, o) in enumerate(c.calls) if n == "create_line" and f == P["talon"]]
    assert talons and min(talons) > head
