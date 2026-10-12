"""Duet: the dance is the status - every Hermes action has one partner move."""
from __future__ import annotations

from hermes_companion.animation import duet as D
from hermes_companion.animation.characters import COMPANIONS, draw_companion, traits
from hermes_companion.behavior import behavior_rules as br
from hermes_companion.core.events import EventKind
from hermes_companion.renderer.smooth import FrameRenderer, PILCanvas


def _signature(pose, progress=0.42, palette=None):
    canvas = PILCanvas(*D.FRAME)
    draw_companion(canvas, "duet", pose, progress, palette)
    return canvas.img.tobytes()


def _first_pose_for(figure):
    return next(p for p, f in D.FIGURE_FOR_POSE.items() if f == figure)


def _chain_poses(kind):
    return [step["pose"] for step in br.CHAINS[kind][1]]


def test_duet_is_registered_everywhere_people_choose_a_companion():
    from hermes_companion.core import settings
    from hermes_companion.renderer import home

    assert "duet" in COMPANIONS and COMPANIONS["duet"]["frame"] == D.FRAME
    assert "duet" in settings.COMPANIONS
    assert "duet" in home.COMPANION_INFO and home.ENERGIES["duet"] == tuple(D.DUET_PALETTES)
    assert traits("duet")["greeting"] == D.GREETING


def test_every_figure_is_a_distinct_dance():
    looks = {figure: _signature(_first_pose_for(figure))
             for figure in D.FIGURES if figure in D.FIGURE_FOR_POSE.values()}
    assert len(set(looks.values())) == len(looks), "two figures draw the same picture"
    assert len(D.FIGURES) >= 20


def test_the_dance_tells_you_what_hermes_is_doing():
    """The big moves are pinned to the events they mean."""
    expect = {
        EventKind.TASK_COMPLETE: "lift",
        EventKind.SUBAGENT_STARTED: "separate",
        EventKind.SUBAGENT_FINISHED: "come_together",
        EventKind.APPROVAL_REQUIRED: "freeze_reach",
        EventKind.TOOL_FAILED: "stumble",
        EventKind.AGENT_STARTED: "bow",
    }
    for kind, figure in expect.items():
        figures = [D.figure_for(p) for p in _chain_poses(kind)]
        assert figure in figures, (kind, figures)
    assert D.figure_for("dev_merge") == "switch_sides"
    assert D.figure_for("media_paint") == "double_spin"
    assert D.figure_for("file_organize") == "underarm_turn"


def test_every_pose_the_engine_can_emit_has_a_real_dance():
    """Chains, category chains, emotional arcs and idle beats: all danced."""
    import importlib.util
    import pathlib
    script = pathlib.Path(D.__file__).resolve().parents[1] / "scripts" / "render_pose_sheet.py"
    spec = importlib.util.spec_from_file_location("render_pose_sheet", script)
    sheet = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(sheet)
    missing = [p for p in sheet.engine_poses() if not D.figure_for(p)]
    assert missing == [], f"poses with no dance figure: {missing}"


def test_own_moves_are_decoration_sorted_by_mood_and_never_signatures():
    flourishes = D.duet_flourishes()
    assert set(flourishes) == {"bright", "calm", "focused", "uneasy"}
    assert sum(len(v) for v in flourishes.values()) == len(D.DUET_MOVES) >= 16
    signature_poses = {s["pose"] for _st, steps in br.CHAINS.values() for s in steps}
    assert not signature_poses & set(D.DUET_MOVES)
    for hint in D.CATEGORY_HINTS.values():
        assert set(hint) <= set(D.DUET_MOVES)


def test_same_action_same_dance_and_moves_progress():
    pose = _first_pose_for("lift")
    assert _signature(pose, 0.3) == _signature(pose, 0.3)
    assert _signature(pose, 0.1) != _signature(pose, 0.5)


def test_lift_actually_lifts_and_separate_actually_separates():
    lead, follow, hold = D.FIGURES["lift"](0.5)
    assert follow["y"] > 60 and hold == "lift"
    lead0, follow0, _ = D.FIGURES["separate"](0.0)
    lead1, follow1, _ = D.FIGURES["separate"](1.0)
    assert (follow1["x"] - lead1["x"]) > (follow0["x"] - lead0["x"]) + 60
    a, b, _ = D.FIGURES["switch_sides"](0.0)
    c, d, _ = D.FIGURES["switch_sides"](1.0)
    assert a["x"] < b["x"] and c["x"] > d["x"]                 # they traded places


def test_spins_turn_the_dancers_around():
    _, follow, _ = D.FIGURES["underarm_turn"](0.5)
    assert follow["spin"] < 0                                  # back to us mid-turn
    lead, _, _ = D.FIGURES["double_spin"](0.125)
    assert abs(lead["spin"]) < 0.2                             # side-on mid-spin
    lead, _, _ = D.FIGURES["double_spin"](0.25)
    assert lead["spin"] < -0.9                                 # back to us


def test_every_palette_renders_and_differs():
    looks = {name: _signature("work", palette=name) for name in D.DUET_PALETTES}
    assert len(set(looks.values())) == len(looks)


def test_smooth_renderer_uses_the_wide_stage():
    frame = FrameRenderer("duet", glow=False, squash=False).frame("leap", 0.5)
    assert frame.size == D.FRAME


def _ev(kind, category=""):
    from hermes_companion.core.events import SemanticEvent
    return SemanticEvent(EventKind(kind), category=category)


def test_live_stage_follows_real_hermes_events():
    now = [10.0]
    st = D.DuetState(clock=lambda: now[0])
    st.observe(_ev("tool.started", "terminal"))
    st.observe(_ev("tool.started", "web"))
    assert st.running == 2 and st.category == "web"
    st.observe(_ev("agent.subagent_spawned"))
    st.observe(_ev("agent.subagent_spawned"))
    assert st.helpers == 2                                   # two backup dancers
    st.observe(_ev("tool.failed", "web"))
    assert st.missteps == 1 and st.running == 1
    for _ in range(3):
        st.observe(_ev("tool.finished", "terminal"))
    assert st.missteps == 0                                  # three clean steps heal one
    st.observe(_ev("approval.required", "dangerous"))
    assert st.danger
    st.observe(_ev("approval.approved"))
    assert not st.danger
    st.observe(_ev("task.complete"))
    assert st.partying and st.helpers == 0
    now[0] += 7
    assert not st.partying


def test_live_stage_changes_the_picture(monkeypatch):
    calm = _signature("work")
    busy = D.DuetState()
    busy.running, busy.helpers, busy.missteps, busy.category = 3, 2, 1, "terminal"
    monkeypatch.setattr(D, "STATE", busy)
    assert _signature("work") != calm
    key = D.state_key()
    assert key[1:4] == (3, 2, 1)


def test_plaque_says_what_hermes_is_doing_in_plain_words(monkeypatch):
    st = D.DuetState()
    monkeypatch.setattr(D, "STATE", st)
    assert D.status_text("terminal_work", "work") == ("Running a command", "")
    st.running, st.category = 2, "terminal"
    assert D.status_text("terminal_work", "work") == ("Running a command", "terminal · 2 tools running")
    st.running, st.category, st.danger = 0, "general", True
    assert D.status_text("wait", "approve") == ("Needs your OK", "dangerous command")
    st.danger, st.helpers = False, 1
    assert D.status_text("channel", "delegate") == ("Helpers working", "1 helper out")
    assert D.status_text("leap", "joy")[0] == "Task complete!"
    assert D.status_text("__unknown__", "rest")[0] == "Resting"     # falls back to a mood word
    st.think_until = float("inf")
    assert D.status_text("jump", "joy")[0] == "Thinking"
    assert D.status_text("wait", "approve")[0] == "Waiting for your OK"   # your OK still wins


def test_every_signature_pose_has_a_plain_status_line():
    for kind, (_state, steps) in br.CHAINS.items():
        for step in steps:
            headline, _ = D.status_text(step["pose"], "calm")
            assert headline and headline != "Ready", (kind.value, step["pose"])


def test_indicators_never_carry_content():
    """Only kinds, categories and counts - no free text from tools reaches the plaque."""
    st = D.DuetState()
    st.observe(_ev("tool.started", "terminal"))
    words = " ".join(D.POSE_STATUS.values()) + " " + " ".join(D.CATEGORY_COLORS)
    assert "rm -rf" not in words and "/" not in words


def test_badges_wrap_inside_the_stage(monkeypatch):
    shapes = []

    class Rec:
        def __getattr__(self, name):
            def record(*coords, **kw):
                shapes.append((name, coords))
            return record

    st = D.DuetState()
    st.running, st.helpers, st.missteps, st.danger = 3, 4, 3, True
    monkeypatch.setattr(D, "STATE", st)
    D._draw_indicators(Rec(), "wait", "approve", "#ef4444")
    rects = [c for n, c in shapes if n == "create_rectangle"]
    assert len(rects) == 5                              # four badges + the plaque
    assert all(0 <= c[0] and c[2] <= D.FRAME[0] for c in rects)
