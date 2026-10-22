"""Kai: every Hermes state is its own kind of motion, and the tests measure it."""
from __future__ import annotations

import importlib.util
import pathlib

from hermes_companion.animation import kai as K
from hermes_companion.animation.characters import COMPANIONS, draw_companion, traits
from hermes_companion.behavior import behavior_rules as br
from hermes_companion.core.events import EventKind, SemanticEvent
from hermes_companion.renderer.smooth import PILCanvas


def _sig(pose, progress=0.45, palette=None):
    canvas = PILCanvas(*K.FRAME)
    draw_companion(canvas, "kai", pose, progress, palette)
    return canvas.img.tobytes()


def _ev(kind, category=""):
    return SemanticEvent(EventKind(kind), category=category)


def _engine_poses():
    script = pathlib.Path(K.__file__).resolve().parents[1] / "scripts" / "render_pose_sheet.py"
    spec = importlib.util.spec_from_file_location("render_pose_sheet", script)
    sheet = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(sheet)
    return sheet.engine_poses()


def _track(move, key, steps=41):
    """One number of the move over its whole duration."""
    out = []
    for i in range(steps):
        sc = K.MOVES[move](i / (steps - 1) * 0.999)
        out.append(key(sc))
    return out


def test_registered_everywhere_people_choose_a_companion():
    from hermes_companion.core import settings
    from hermes_companion.renderer import home, tray
    assert COMPANIONS["kai"]["frame"] == K.FRAME
    assert settings.COMPANIONS[-1] == "kai"               # appended: existing cards keep their place
    assert settings.display_name("kai") == "Kai"
    assert home.ENERGIES["kai"] == tuple(K.PALETTES) == tray.ENERGIES["kai"]
    assert traits("kai")["greeting"] == K.GREETING


def test_every_engine_pose_is_a_real_move_and_every_move_can_play():
    assert [p for p in _engine_poses() if not K.move_for(p)] == []
    assert set(K.MOVES) == set(K.MOVE_FOR_POSE.values())


def test_each_hermes_state_has_its_own_kind_of_motion():
    kinds = [kind for _move, kind in K.SIGNATURES.values()]
    moves = [move for move, _kind in K.SIGNATURES.values()]
    assert len(set(kinds)) == len(kinds) and len(set(moves)) == len(moves)
    chains = {k: [K.move_for(s["pose"]) for s in steps] for k, (_st, steps) in br.CHAINS.items()}
    assert "drop_in" in chains[EventKind.AGENT_STARTED]
    assert "ollie_up" in chains[EventKind.TOOL_STARTED] and "manual" in chains[EventKind.TOOL_STARTED]
    assert "pump" in chains[EventKind.TOOL_PROGRESS]
    assert "kickflip" in chains[EventKind.TOOL_FINISHED]
    assert "slam" in chains[EventKind.TOOL_FAILED]
    assert {"foot_brake", "board_lean"} <= set(chains[EventKind.APPROVAL_REQUIRED])
    assert "big_air" in chains[EventKind.TASK_COMPLETE]
    assert "call_crew" in chains[EventKind.SUBAGENT_STARTED]
    assert "sit_on_board" in chains[EventKind.AGENT_IDLE]


def test_the_motions_are_what_they_claim():
    lift = lambda sc: sc["kai"]["y"]                                     # noqa: E731
    # descend: drop in starts at the coping and ends on the street
    drop = _track("drop_in", lift)
    assert drop[0] > 60 and drop[-1] < 15
    # soar: big air goes higher than any other move does
    peak = max(_track("big_air", lift))
    others = max(max(_track(m, lift)) for m in K.MOVES if m not in ("big_air", "drop_in", "tail_stall",
                                                                    "rock_to_fakie", "pump"))
    assert peak > others + 20
    # balance: the manual keeps the nose up the whole time
    assert min(_track("manual", lambda sc: sc["board"]["rot"])) > 8
    # oscillate: the pump goes wall to wall
    xs = _track("pump", lambda sc: sc["kai"]["x"])
    assert max(xs) > 80 and min(xs) < -80
    # board flips: a full turn about its long axis
    assert max(_track("kickflip", lambda sc: sc["board"]["flip"])) >= 0.99
    # fall: the slam ends with him lying down, the board gone without him
    end = K.MOVES["slam"](0.99)
    assert end["kai"]["rot"] < -80 and end["board"]["mode"] == "free" and end["board"]["x"] > 120
    # stillness: waiting, his hips do not move at all
    hips = _track("board_lean", lambda sc: (sc["kai"]["x"], sc["kai"]["y"], sc["kai"]["rot"]))
    assert len(set(hips)) == 1 and K.MOVES["board_lean"](0.5)["board"]["mode"] == "upright"
    # others arrive: the crew skates in
    assert K.MOVES["call_crew"](0.9)["crew"][0] == "in"
    # rest low: sitting on the board, lower than standing
    assert K.MOVES["sit_on_board"](0.5)["kai"]["y"] < -20


def test_big_air_only_means_task_complete():
    assert [p for p, m in K.MOVE_FOR_POSE.items() if m == "big_air"] == ["leap"]
    assert [p for p, m in K.MOVE_FOR_POSE.items() if m == "slam"] == ["fall"]


def test_moves_are_distinct_and_animate():
    pose_for = {}
    for pose, mv in K.MOVE_FOR_POSE.items():
        pose_for.setdefault(mv, pose)
    looks = {mv: _sig(pose) for mv, pose in pose_for.items()}
    assert len(set(looks.values())) == len(looks)
    assert _sig("celebrate", 0.1) != _sig("celebrate", 0.5)


def test_feet_stay_on_the_board_when_riding():
    for move in ("manual", "grind", "carve", "push_off", "ready_stance", "roll_back"):
        sc = K.MOVES[move](0.4)
        kai, board = sc["kai"], sc["board"]
        assert board["mode"] == "ride"
        soles = K.HIP_Y - kai["y"] + K._feet_drop(kai["legs"])
        deck = K.FLOOR - K.DECK - board["y"]
        assert abs(soles - deck) <= 1.5, move


def test_ramp_moves_ride_the_ramp_surface():
    for x in (0, 40, 90, 120):
        lift, _slope = K.ramp_surface(x)
        sc_kai, sc_board = K._on_ramp(x)
        assert sc_board["y"] == lift
    assert K.ramp_surface(0) == (0.0, 0.0)
    assert abs(K.ramp_surface(K.COPING_X)[0] - K.RAMP_H) < 1


def test_one_chalk_mark_per_running_tool_and_scrapes_heal(monkeypatch):
    st = K.KaiState()
    monkeypatch.setattr(K, "STATE", st)
    st.observe(_ev("tool.started", "terminal"))
    st.observe(_ev("tool.started", "web"))
    assert st.tools == ["terminal", "web"]
    st.observe(_ev("tool.failed", "web"))
    assert st.scrapes == 1 and st.tools == ["terminal"]
    for _ in range(3):
        st.observe(_ev("tool.started", "file"))
        st.observe(_ev("tool.finished", "file"))
    assert st.scrapes == 0 and st.landed == 3


def test_live_state_and_plaque_follow_real_events(monkeypatch):
    now = [5.0]
    st = K.KaiState(clock=lambda: now[0])
    monkeypatch.setattr(K, "STATE", st)
    st.observe(_ev("tool.started", "terminal"))
    st.observe(_ev("tool.started", "web"))
    assert K.status_text("terminal_work", "work") == ("Running a command", "2 in the line")
    st.observe(_ev("agent.subagent_spawned"))
    st.observe(_ev("approval.required", "dangerous"))
    assert K.status_text("wait", "approve")[1].startswith("dangerous command")
    st.observe(_ev("approval.approved"))
    st.observe(_ev("tool.finished", "terminal"))
    st.observe(_ev("task.complete"))
    assert st.partying and st.landed == 1
    assert K.status_text("leap", "joy") == ("Task complete!", "1 landed")


def test_tricks_are_decoration_not_signatures():
    tricks = K.trick_flourishes()
    assert set(tricks) <= {"bright", "calm", "focused", "uneasy"}
    signatures = {s["pose"] for _st, steps in br.CHAINS.values() for s in steps}
    assert not signatures & set(K.TRICKS)


def test_every_palette_and_unknown_pose_draws():
    for palette in K.PALETTES:
        assert _sig("work", 0.3, palette)
    assert _sig("not_a_real_pose", 0.3)
