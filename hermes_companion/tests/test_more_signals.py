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


def test_travel_keeps_distance_and_gets_signature_moves():
    import random
    from hermes_companion.animation.nyamekra import travel
    rng = random.Random(1)
    run = {"pose": "dash_to_workspace", "duration_ms": 480,
           "move": {"type": "dash", "dx": 520, "dy": 0, "easing": "easeOutCubic"}}
    seen = {travel(run, rng)["pose"] for _ in range(60)}
    assert seen == {"wing_dash", "feather_teleport"}
    home = dict(run, move=dict(run["move"], dx=-520))
    assert all(travel(home, rng)["pose"].endswith("_back") for _ in range(20))
    to_user = {"pose": "run_to_user", "duration_ms": 800, "move": {"type": "run", "dx": -320}}
    assert travel(to_user, rng)["pose"] == "swoop_back"
    for _ in range(40):
        out = travel(run, rng)
        assert out["move"]["dx"] == 520                  # still goes exactly where Hermes sent it
        if out["pose"] == "feather_teleport":
            assert out["move"]["easing"] == "teleport" and out["duration_ms"] >= 900
    still = {"pose": "work", "duration_ms": 900, "move": None}
    assert travel(still, rng) is still


def test_teleport_hides_the_body_midway():
    from hermes_companion.renderer.smooth import FrameRenderer
    r = FrameRenderer("nyamekra", None, glow=False, squash=False)
    full = sum(1 for a in r.frame("feather_teleport", 0.1).getchannel("A").getdata() if a > 128)
    mid = sum(1 for a in r.frame("feather_teleport", 0.5).getchannel("A").getdata() if a > 128)
    assert mid < full * 0.25


def test_teleport_easing_jumps_at_halfway():
    from hermes_companion.movement.easing import apply
    assert apply("teleport", 0.49) == 0.0 and apply("teleport", 0.5) == 1.0


def test_live_and_play_engines_use_nyamekra_travel():
    from hermes_companion.animation.characters import traits
    from hermes_companion.behavior.behavior_engine import BehaviorEngine
    from hermes_companion.core.events import EventKind, SemanticEvent
    t = traits("nyamekra")
    e = BehaviorEngine(seed=2, variety=True, travel=t["travel"])
    poses = []
    for _ in range(6):
        e._cooldown_until.clear()
        chain = e.handle(SemanticEvent(EventKind.APPROVAL_REQUIRED))
        poses += [s["pose"] for s in chain.steps if s.get("move")]
    assert any(p.startswith(("swoop", "wing_dash", "feather_teleport")) for p in poses)
    assert traits("samurai")["travel"] is None


class _Surface:
    def __init__(self):
        self.x, self.home_x, self.home_y, self.w, self.h = 500, 500, 800, 200, 220
        self.lifts, self.poses = [], []

    def set_x(self, x):
        self.x = x

    def lift(self, dy):
        self.lifts.append(dy)

    def set_y(self, y):
        self.home_y = y

    def place_at(self, x, y):
        self.x, self.home_y = x, y

    def set_pose(self, pose, progress):
        self.poses.append((pose, progress))

    def set_state(self, s):
        pass


def test_flying_travel_arcs_through_the_air_and_lands():
    from hermes_companion.animation.director import Director, arc_height
    from hermes_companion.behavior.behavior_engine import BehaviorEngine, Chain
    from hermes_companion.core.state import State
    now = [0.0]
    surf = _Surface()
    d = Director(BehaviorEngine(seed=1), surf, clock=lambda: now[0])
    step = {"pose": "soar", "duration_ms": 1000, "move": {"type": "hop", "dx": 300}}
    d.start_chain(Chain("t", State.WORKING, 3, [step]))
    for i in range(12):
        now[0] = i * 0.1
        d.step(0.1)
    assert min(surf.lifts) <= -110                      # high in the air mid-flight
    assert surf.lifts[-1] == 0                          # and back on the ground after
    assert arc_height({"pose": "feather_teleport_back",
                       "move": {"dx": 1, "easing": "teleport"}}) == 0
    assert arc_height({"pose": "work", "move": {"type": "walk", "dx": 50}}) == 0


def test_far_window_hops_become_feather_teleports():
    from hermes_companion.behavior.perch import PerchDriver, PerchMotion
    surf = _Surface()

    class Dir:
        chain = None
        idle_pose = "idle_bob"
        idle_progress = None
        _x = 500
        _returning = False
    drv = PerchDriver(surf, Dir(), None, poses={"hop": "soar", "drop": "landing",
                                                "teleport": "feather_teleport"})
    m = PerchMotion(500, 800, 1600, 200, 0.0, "teleport")
    assert m.at(0.2)[:2] == (500, 800) and m.at(0.6)[:2] == (1600, 200)
    assert drv._pose_for(m) == "feather_teleport"
    assert drv._pose_for(PerchMotion(900, 800, 300, 400, 0.0, "hop")) == "soar_back"
    assert drv._pose_for(PerchMotion(300, 300, 300, 800, 0.0, "drop")) == "landing"
    plain = PerchDriver(surf, Dir(), None)
    assert plain._pose_for(PerchMotion(0, 0, 10, 0, 0.0, "hop")) == "leap"
