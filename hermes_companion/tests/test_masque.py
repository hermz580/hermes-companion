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


def test_views_front_side_back():
    assert M.view_of("idle_bob", 0.2, set()) == (0.0, False)
    assert M.view_of("turn_back", 0.3, M.MASQUE_MOVES["turn_back"][1]) == (0.0, True)
    f, back = M.view_of("turn_right", 0.6, M.MASQUE_MOVES["turn_right"][1])
    assert f == 1.0 and not back
    f, _ = M.view_of("turn_left", 0.6, M.MASQUE_MOVES["turn_left"][1])
    assert f == -1.0
    assert M.view_of("ink_slide", 0.3, M.MASQUE_MOVES["ink_slide"][1])[0] == 1.0
    assert M.view_of("dash_to_workspace", 0.3, set())[0] == 1.0       # engine travel is side-on
    spins = {M.view_of("celebrate", t / 20, M.MASQUE_MOVES["celebrate"][1])[1] for t in range(20)}
    assert spins == {True, False}                                    # a spin passes her back


def test_back_view_hides_the_face():
    from hermes_companion.renderer.smooth import FrameRenderer
    r = FrameRenderer("masque", glow=False, squash=False)
    front, back = r.frame("idle_bob", 0.2), r.frame("turn_back", 0.3)
    # porcelain (near-white) pixels belong to the mask; seen from behind there are almost none
    white = lambda im: sum(1 for px in im.getdata() if px[3] > 200 and min(px[:3]) > 225)
    assert white(back) < white(front) * 0.15


def test_every_sheet_move_renders():
    from hermes_companion.renderer.smooth import FrameRenderer
    from hermes_companion.scripts import masque_sheets as S
    r = FrameRenderer("masque", glow=False, squash=False)
    poses = [c[1] for c in S.TURNAROUND + S.SPECIAL] + [c[1] for c in S.MOVEMENT] + \
        [c[1] for c in S.FORMS]
    for pose in poses:
        assert r.frame(pose, 0.35).getbbox() is not None, pose


def test_look_up_and_down_move_the_face():
    from hermes_companion.renderer.smooth import PILCanvas
    imgs = {}
    for vy in (-1.0, 0.0, 1.0):
        c = PILCanvas(*M.FRAME)
        M.draw_mask(c, 160, 118, 38, 50, "cute", vy=vy)
        imgs[vy] = c.img.tobytes()
    assert imgs[-1.0] != imgs[0.0] != imgs[1.0]


def test_hands_are_drawn_over_the_mask_and_the_perch_has_a_window():
    calls = []

    class Rec:
        def delete(self, *a):
            pass

        def __getattr__(self, name):
            return lambda *a, **k: calls.append((name, k.get("fill"), k.get("outline")))
    M.draw_masque(Rec(), "idle_bob", 0.2)
    mask = max(i for i, c in enumerate(calls) if c[1] == M.PORCELAIN)
    glove = [i for i, c in enumerate(calls) if c[1] == M.GLOVE]
    assert glove and min(glove) > mask                  # fingers rest over the mask's edge
    calls.clear()
    M.draw_masque(Rec(), "window_perch", 0.3)
    assert ("create_rectangle", "#2d3a58", "#6a7dab") in calls   # the title bar


def test_mixed_tools_each_hold_their_own_colour(st):
    st.observe(ev("tool.started", "terminal"))
    st.observe(ev("tool.started", "web"))
    st.observe(ev("tool.started", "memory"))
    assert st.tools == ["terminal", "web", "memory"]
    st.observe(ev("tool.finished", "web"))
    assert st.tools == ["terminal", "memory"]


def test_mood_change_swaps_the_mask_and_session_end_rests(st):
    st.observe(ev("tool.started", "terminal"))
    assert st.swapping                                   # calm -> work: a new mask
    st.now[0] += 2
    assert not st.swapping
    st.observe(ev("tool.started", "web"))
    assert not st.swapping                               # still working: same mask
    st.observe(ev("task.complete"))
    assert st.resting and st.tools == []
    st.observe(ev("agent.started"))
    assert not st.resting


def test_session_end_and_swap_change_the_picture():
    from hermes_companion.renderer.smooth import FrameRenderer
    saved = dict(M.STATE.__dict__)
    try:
        r = FrameRenderer("masque", glow=False, squash=False)
        M.STATE.__dict__.update(running=0, cracks=0, category="general", helpers=0, tools=[],
                                swap_until=0.0, rest_until=0.0)
        plain = r.frame("idle_bob", 0.3).tobytes()
        M.STATE.rest_until = 1e12
        assert r.frame("idle_bob", 0.3).tobytes() != plain
        M.STATE.rest_until, M.STATE.swap_until = 0.0, 1e12
        assert r.frame("idle_bob", 0.3).tobytes() != plain
    finally:
        M.STATE.__dict__.update(saved)
