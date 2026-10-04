"""Masque: every part of her is driven by real Hermes signals."""
from __future__ import annotations

import pytest

from hermes_companion.animation import masque as M
from hermes_companion.core.events import EventKind, SemanticEvent


@pytest.fixture
def st():
    now = [100.0]
    s = M.MasqueState(clock=lambda: now[0])
    s.now = now
    return s


def ev(kind, category=""):
    return SemanticEvent(EventKind(kind), category=category)


def test_tools_in_flight_raise_tendrils_and_set_colour(st):
    st.observe(ev("tool.started", "terminal"))
    st.observe(ev("tool.started", "web"))
    assert st.running == 2 and st.category == "web" and st.work == 2
    st.observe(ev("tool.finished", "web"))
    assert st.running == 1


def test_failures_crack_the_mask_and_successes_heal_it(st):
    for _ in range(4):
        st.observe(ev("tool.failed", "terminal"))
    assert st.cracks == 3                                   # broken is the most it gets
    for _ in range(3):
        st.observe(ev("tool.finished", "terminal"))
    assert st.cracks == 2


def test_thinking_opens_the_eyes_for_a_while(st):
    st.observe(ev("user.prompt_submitted"))
    assert st.thinking
    st.now[0] += 5
    assert not st.thinking


def test_helpers_bud_off_and_return(st):
    st.observe(ev("agent.subagent_spawned"))
    st.observe(ev("agent.subagent_spawned"))
    assert st.helpers == 2 and st.category == "delegation"
    st.observe(ev("agent.subagent_failed"))
    assert st.helpers == 1 and st.cracks == 1


def test_dangerous_approval_is_evil_plain_one_is_questioning(st):
    st.observe(ev("approval.required", "dangerous"))
    assert M.expression_for("wait", set(), st) == "evil"
    st.observe(ev("approval.approved"))
    st.observe(ev("approval.required"))
    assert M.expression_for("wait", set(), st) == "confused"


def test_mask_faces_follow_meaning(st):
    assert M.expression_for("idle_bob", set(), st) == "cute"
    assert M.expression_for("sleep", set(), st) == "blank"
    assert M.expression_for("shock", set(), st) == "sad"
    st.running = 4
    assert M.expression_for("work", set(), st) == "scary"
    assert M.expression_for("tendril_type", M.MASQUE_MOVES["tendril_type"][1], st) == "focused"


def test_every_expression_and_damage_state_draws():
    from hermes_companion.renderer.smooth import PILCanvas
    for face in M.EXPRESSIONS:
        for cracks in range(4):
            c = PILCanvas(*M.FRAME)
            M.draw_mask(c, 160, 118, 38, 50, face, cracks=cracks)
            assert c.img.getbbox() is not None


def test_state_changes_change_the_frame():
    from hermes_companion.renderer.smooth import FrameRenderer
    saved = dict(M.STATE.__dict__)
    try:
        r = FrameRenderer("masque", glow=False, squash=False)
        M.STATE.__dict__.update(running=0, cracks=0, category="general", helpers=0)
        a = r.frame("idle_bob", 0.3)
        M.STATE.__dict__.update(running=2, category="terminal")
        b = r.frame("idle_bob", 0.3)
        assert a is not b and a.tobytes() != b.tobytes()
        assert a.size == M.FRAME
    finally:
        M.STATE.__dict__.update(saved)


def test_every_own_move_and_spook_level_renders():
    from hermes_companion.renderer.smooth import FrameRenderer
    for pal in M.PALETTES:
        r = FrameRenderer("masque", pal, glow=False, squash=False)
        for pose in list(M.MASQUE_MOVES)[:8] + ["idle_bob", "terminal_work", "wait", "sleep"]:
            assert r.frame(pose, 0.3).getbbox() is not None


def test_travel_and_registry():
    import random
    from hermes_companion.animation.characters import traits
    t = traits("masque")
    assert t["observe"] is M.observe and t["travel"] is M.travel
    step = {"pose": "run_to_user", "duration_ms": 800, "move": {"type": "run", "dx": -320}}
    assert M.travel(step, random.Random(1))["pose"] == "lunge_back"
    seen = {M.travel({"pose": "x", "duration_ms": 500, "move": {"type": "dash", "dx": 520}},
                     random.Random(i))["pose"] for i in range(40)}
    assert seen == {"ink_slide", "crack_portal"}
