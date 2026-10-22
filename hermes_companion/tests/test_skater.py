"""Kia Kai: live Hermes skate lines, shared joint rig and UI integration."""
from __future__ import annotations

import importlib.util
import pathlib

from hermes_companion.animation import skater as K
from hermes_companion.animation.characters import COMPANIONS, draw_companion, traits
from hermes_companion.behavior import behavior_rules as br
from hermes_companion.core import settings as S
from hermes_companion.core.events import EventKind, SemanticEvent
from hermes_companion.renderer import home, tray
from hermes_companion.renderer.smooth import PILCanvas, FrameRenderer


def _ev(kind, category=""):
    return SemanticEvent(EventKind(kind), category=category)


def _frame(pose, progress=0.45, palette=None):
    c = PILCanvas(*K.FRAME)
    draw_companion(c, "skater", pose, progress, palette)
    return c.img.tobytes()


def _engine_poses():
    script = pathlib.Path(K.__file__).resolve().parents[1] / "scripts" / "render_pose_sheet.py"
    spec = importlib.util.spec_from_file_location("render_pose_sheet", script)
    sheet = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(sheet)
    return sheet.engine_poses()


def test_registration_in_registry_settings_home_tray_and_traits():
    assert "skater" in COMPANIONS and S.COMPANIONS[-1] == "skater"
    assert COMPANIONS["skater"]["frame"] == K.FRAME
    assert S.display_name("skater") == "Kia Kai"
    assert home.COMPANION_INFO["skater"][0] == "Kia Kai"
    assert tray.ENERGIES["skater"] == tuple(K.PALETTES)
    assert traits("skater")["greeting"] == K.GREETING
    assert S.play_command(dict(S.DEFAULTS, companion="skater"))[3:5] == ["--companion", "skater"]


def test_every_engine_pose_has_a_signature_and_a_visible_frame():
    missing = [p for p in _engine_poses() if K.move_for(p) is None]
    assert missing == []
    for name in ("work", "terminal_work", "lean_work", "dev_merge", "web_scan",
                 "shock", "fall", "wait", "leap", "idle_bob"):
        assert _frame(name) != _frame("__unknown_skater_probe__")
    assert _frame("work", 0.1) != _frame("work", 0.5)


def test_semantic_signatures_match_the_same_lifecycle_meanings_as_sensei():
    def moves(kind):
        return [K.move_for(x["pose"]) for x in br.CHAINS[kind][1]]
    assert "victory" in moves(EventKind.TASK_COMPLETE)
    assert "brake" in moves(EventKind.APPROVAL_REQUIRED)
    assert "crew_out" in moves(EventKind.SUBAGENT_STARTED)
    assert "bail" in moves(EventKind.TOOL_FAILED)
    assert "rest" in moves(EventKind.AGENT_IDLE)
    assert K.move_for("lean_work") == "manual"
    assert K.move_for("dev_merge") == "grind"
    assert K.move_for("dash_to_workspace") == "wallride"


def test_tricks_move_board_and_body_in_distinct_ways():
    low, peak = K.MOVES["ollie"](0.0), K.MOVES["ollie"](0.5)
    assert peak["deck"][1] - low["deck"][1] > 50
    assert peak["body"]["y"] - low["body"]["y"] > 50
    assert K.MOVES["kickflip"](0.5)["deck"][3] > 2.0
    assert "rail" in K.MOVES["grind"](0.5)["fx"]
    assert "wall" in K.MOVES["wallride"](0.5)["fx"]
    assert "confetti" in K.MOVES["victory"](0.5)["fx"]


def test_real_signed_semantic_events_feed_the_skatepark_without_content(monkeypatch):
    now = [100.0]
    st = K.SkaterState(clock=lambda: now[0])
    monkeypatch.setattr(K, "STATE", st)
    st.observe(_ev("agent.started"))
    st.observe(_ev("tool.started", "terminal"))
    st.observe(_ev("tool.started", "media"))
    assert st.running == 2 and "line(s)" in K.status_text("work", "work")[1]
    st.observe(_ev("agent.subagent_spawned"))
    assert st.helpers == 1
    st.observe(_ev("tool.failed", "terminal"))
    assert st.bails == 1 and st.running == 1
    st.observe(_ev("approval.required", "dangerous"))
    assert K.status_text("wait", "approve") == ("Needs your OK", "dangerous command · 1 crew out · 1 bail(s)")
    st.observe(_ev("approval.approved"))
    assert not st.danger
    st.observe(_ev("tool.finished", "media"))
    assert st.landed == 1
    st.observe(_ev("task.complete"))
    assert st.celebrating and st.running == 0 and st.helpers == 0
    assert K.status_text("leap", "joy")[0] == "Task complete!"


def test_palette_changes_and_shared_rig_is_fully_articulated():
    assert len({_frame("work", palette=name) for name in K.PALETTES}) == 3
    assert FrameRenderer("skater", glow=False, squash=False).frame("leap", 0.5).size == K.FRAME
    st = K.MOVES["carve"](0.25)["body"]
    assert len(st["arms"]) == len(st["legs"]) == 4
    assert len(st["wrists"]) == len(st["ankles"]) == len(st["swivel"]) == 2
    assert "twist" in st and "torso" in st and "head" in st
    assert _frame("web_scan") != _frame("dev_merge")


def test_deterministic_render_and_visibility_of_all_role_signals():
    assert _frame("leap") == _frame("leap")
    pictures = [_frame(x) for x in ("shock", "wait", "open_portal", "leap", "idle_bob")]
    assert len(set(pictures)) == len(pictures)
    assert K.CATEGORY_MARKS["terminal"][0] != K.CATEGORY_MARKS["web"][0]


def test_flourishes_are_not_reserved_engine_signatures():
    assert not set(K.FLOURISHES) & set(_engine_poses())
    assert all(n in K.FLOURISHES for names in K.skate_flourishes().values() for n in names)
    assert set(K.CATEGORY_HINTS["media"]) <= set(K.FLOURISHES)
