"""Sensei: the fight is the status - every Hermes action has one move."""
from __future__ import annotations

import importlib.util
import pathlib

from hermes_companion.animation import master as M
from hermes_companion.animation.characters import COMPANIONS, draw_companion, traits
from hermes_companion.behavior import behavior_rules as br
from hermes_companion.core.events import EventKind, SemanticEvent
from hermes_companion.renderer.smooth import FrameRenderer, PILCanvas


def _sig(pose, progress=0.45, palette=None):
    canvas = PILCanvas(*M.FRAME)
    draw_companion(canvas, "master", pose, progress, palette)
    return canvas.img.tobytes()


def _ev(kind, category=""):
    return SemanticEvent(EventKind(kind), category=category)


def _engine_poses():
    script = pathlib.Path(M.__file__).resolve().parents[1] / "scripts" / "render_pose_sheet.py"
    spec = importlib.util.spec_from_file_location("render_pose_sheet", script)
    sheet = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(sheet)
    return sheet.engine_poses()


def test_registered_everywhere_people_choose_a_companion():
    from hermes_companion.core import settings
    from hermes_companion.renderer import home
    assert COMPANIONS["master"]["frame"] == M.FRAME
    assert settings.COMPANIONS[-2] == "master"            # Sensei retains his position; Kia Kai is appended
    assert home.ENERGIES["master"] == tuple(M.PALETTES)
    assert traits("master")["greeting"] == M.GREETING


def test_every_engine_pose_is_a_real_move_and_every_move_can_play():
    missing = [p for p in _engine_poses() if not M.move_for(p)]
    assert missing == []
    assert set(M.MOVES) == set(M.MOVE_FOR_POSE.values())


def test_the_fight_tells_you_what_hermes_is_doing():
    def moves(kind):
        return [M.move_for(s["pose"]) for s in br.CHAINS[kind][1]]
    assert "long_backflip" in moves(EventKind.TASK_COMPLETE)
    assert "bicycle_kick" in moves(EventKind.TASK_COMPLETE)
    assert "throw_far" in moves(EventKind.TOOL_FINISHED)
    assert "stop_object" in moves(EventKind.APPROVAL_REQUIRED)
    assert "catch_arrow" in moves(EventKind.APPROVAL_REQUIRED)
    assert "dodge_arrows" in moves(EventKind.TOOL_PROGRESS)
    assert "shadow_clones" in moves(EventKind.SUBAGENT_STARTED)
    assert "hit_react" in moves(EventKind.TOOL_FAILED)
    assert "tree_rest" in moves(EventKind.AGENT_IDLE)
    assert M.move_for("dash_to_workspace") == "wall_run"
    assert M.move_for("web_scan") == "sneak" and M.move_for("memory_vault") == "sneak_strike"


def test_the_backflip_only_means_task_complete():
    assert [p for p, m in M.MOVE_FOR_POSE.items() if m == "long_backflip"] == ["leap"]


def test_moves_are_distinct_and_animate():
    pose_for = {}
    for pose, mv in M.MOVE_FOR_POSE.items():
        pose_for.setdefault(mv, pose)
    looks = {mv: _sig(pose) for mv, pose in pose_for.items()}
    assert len(set(looks.values())) == len(looks)
    assert _sig("leap", 0.1) != _sig("leap", 0.5)


def test_one_ninja_per_running_tool_armed_by_category(monkeypatch):
    st = M.MasterState()
    monkeypatch.setattr(M, "STATE", st)
    st.observe(_ev("tool.started", "terminal"))
    st.observe(_ev("tool.started", "file"))
    st.observe(_ev("tool.started", "memory"))
    ninjas = M.MOVES["jab_cross"](0.3)["ninjas"]
    assert [n["kind"] for n in ninjas] == ["terminal", "file", "memory"]
    assert [M._kind(n["kind"])[0] for n in ninjas] == ["shuriken", "bo_staff", "shadow"]
    st.observe(_ev("tool.finished", "file"))
    assert st.tools == ["terminal", "memory"] and st.defeated == 1


def test_throw_far_actually_sends_the_ninja_flying():
    start = M.MOVES["throw_far"](0.1)["ninjas"][0]
    end = M.MOVES["throw_far"](0.95)["ninjas"][0]
    assert end["state"] == "fly" and end["x"] - start["x"] > 120


def test_wall_run_goes_up_the_wall_and_backflip_goes_high():
    up = M.MOVES["wall_run"](0.35)["master"]
    assert up["rot"] == -90 and up["y"] > 60 and "wall" in M.MOVES["wall_run"](0.35)["fx"]
    assert M.MOVES["long_backflip"](0.5)["master"]["y"] > 80


def test_he_stops_the_object_and_catches_the_arrow():
    held = M.MOVES["stop_object"](0.9)["objects"][0]
    assert held[0] == "boulder" and held[4] is True
    assert M.MOVES["catch_arrow"](0.9)["objects"][0][0] == "arrow_held"
    assert M.MOVES["dodge_arrows"](0.3)["arrows"]


def test_sneaking_targets_an_unaware_ninja_from_behind():
    nj = M.MOVES["sneak"](0.5)["ninjas"][0]
    assert nj["state"] == "unaware" and nj["spin"] < 0       # its back is to us and to him
    assert M.MOVES["sneak_strike"](0.95)["ninjas"][0]["state"] == "down"


def test_rest_is_under_the_blossom_tree():
    sc = M.MOVES["tree_rest"](0.5)
    assert {"tree", "petals"} <= sc["fx"] and sc["master"]["x"] < -80


def test_live_state_and_plaque_follow_real_events(monkeypatch):
    now = [5.0]
    st = M.MasterState(clock=lambda: now[0])
    monkeypatch.setattr(M, "STATE", st)
    st.observe(_ev("tool.started", "terminal"))
    st.observe(_ev("tool.started", "web"))
    assert M.status_text("terminal_work", "work") == ("Running a command", "2 ninjas (kunai rope, shuriken)")
    st.observe(_ev("agent.subagent_spawned"))
    st.observe(_ev("approval.required", "dangerous"))
    assert M.status_text("wait", "approve")[1].startswith("dangerous command")
    st.observe(_ev("approval.approved"))
    st.observe(_ev("tool.finished", "terminal"))
    st.observe(_ev("task.complete"))
    assert st.partying and st.defeated == 1
    assert M.status_text("leap", "joy") == ("Task complete!", "1 down")


def test_kata_are_decoration_not_signatures():
    kata = M.kata_flourishes()
    assert set(kata) <= {"bright", "calm", "focused", "uneasy"}
    signatures = {s["pose"] for _st, steps in br.CHAINS.values() for s in steps}
    assert not signatures & set(M.KATA)


def test_palettes_and_wide_stage():
    assert len({_sig("work", palette=n) for n in M.PALETTES}) == len(M.PALETTES)
    assert FrameRenderer("master", glow=False, squash=False).frame("leap", 0.5).size == M.FRAME


# ── real stances, styles and the new joints ───────────────────────────────

def test_stances_carry_their_real_weight():
    S = M.STANCES
    l0, k0, l1, k1 = S["ma_bu"]["legs"]
    assert (l0, k0) == (l1, k1) and k0 > 45                      # horse: 50/50, deep knees
    _b, back_k, _f, front_k = S["gong_bu"]["legs"]
    assert front_k > 40 and back_k == 0                         # bow: front knee bent, back leg straight
    _b, back_k, _f, front_k = S["kokutsu"]["legs"]
    assert back_k > 40 and front_k == 0                         # back stance: the reverse
    assert S["xu_bu"]["ankles"][1] > 40                         # empty stance: front toe only
    assert S["pu_bu"]["legs"][1] > 120 and S["pu_bu"]["legs"][3] == 0
    assert S["du_li"]["legs"][2] >= 90                          # crane: raised thigh at least level
    assert S["yjkym"]["swivel"][0] > 0.5                        # Wing Chun: toes turned in


def test_every_hand_form_draws_a_different_hand():
    looks = set()
    for form in M.HAND_FORMS:
        cv = PILCanvas(*M.FRAME)
        st = M._pose("ready", hands=(form, form), arms=(90, 0, 90, 0))
        M._draw_fighter(cv, M._palette(None), 150, 180, st, "neutral")
        looks.add(cv.img.tobytes())
    assert len(looks) == len(M.HAND_FORMS) == 8


def test_twist_turns_the_chest_on_the_hips():

    def look(t):
        cv = PILCanvas(*M.FRAME)
        M._draw_fighter(cv, M._palette(None), 150, 180, M._pose("gong_bu", twist=t), "neutral")
        return cv.img.tobytes()
    assert look(0) != look(40) != look(-40)


def test_styles_use_their_signature_hands_and_stances():
    def hands_over(move):
        return {h for i in range(12) for h in (M.MOVES[move](i / 12)["master"].get("hands") or ())}
    assert {"tiger"} <= hands_over("tiger_claw_strike")
    assert {"crane"} <= hands_over("du_li_crane")
    assert {"leopard"} <= hands_over("leopard_fist")
    assert {"snake"} <= hands_over("snake_spear")
    assert {"dragon"} <= hands_over("dragon_claw")
    assert {"knife"} <= hands_over("kokutsu_shuto")
    assert M.move_for("work") == "exchange" and M.move_for("terminal_work") == "thai_roundhouse"
    peak_twist = max(abs(M.MOVES["thai_roundhouse"](i / 20)["master"]["twist"]) for i in range(20))
    assert peak_twist > 30                                     # the hip turns over on the kick


def test_keyframed_techniques_chamber_strike_and_recover():
    a, mid, end = (M.MOVES["teep"](t)["master"] for t in (0.0, 0.5, 0.999))
    assert mid["legs"][2] > 80 and mid["legs"][3] < 20          # knee up, leg extended through
    assert abs(end["legs"][2] - a["legs"][2]) < 5               # back to guard


def test_every_style_chip_names_a_real_move():
    assert set(M.STYLE_OF) <= set(M.MOVES)
    for chip in M.STYLE_OF.values():
        assert 20 + len(chip) * 7.4 < M.FRAME[0] - 12           # always fits the stage


def test_trails_and_dust_add_detail():

    def frame(pose, pr):
        cv = PILCanvas(*M.FRAME)
        M.draw_master(cv, pose, pr)
        return cv.img
    assert "trail" in M.MOVES["thai_roundhouse"](0.45)["fx"]
    assert "dust" in M.MOVES["stop_object"](0.6)["fx"]
    assert frame("terminal_work", 0.45).tobytes() != frame("terminal_work", 0.1).tobytes()


# ── a real battle: the ninjas fight back ──────────────────────────────────

def _acts(move, n=40):
    return [(M.MOVES[move](i / n)["ninjas"][0].get("act"), M.MOVES[move](i / n)) for i in range(n)]


def test_ninjas_strike_and_block_in_a_real_exchange():
    acts = {a for a, _sc in _acts("exchange")}
    assert {"jab", "kick"} <= acts                              # they attack him
    assert acts & set(M.NINJA_BLOCKS)                           # and block some of his strikes
    assert "hit" in acts                                        # but not all of them
    assert any(sc.get("sparks") for _a, sc in _acts("exchange"))  # contact shows where blocks meet strikes
    assert M.move_for("work") == "exchange"


def test_a_failed_tool_is_a_hit_that_gets_through():
    frames = _acts("hit_react")
    assert any(a == "jab" and "hit" in sc["fx"] for a, sc in frames)   # their jab lands on him
    assert any(a == "jab" and "block" in sc["fx"] for a, sc in frames)  # then he blocks the next one
    swept = [sc["master"]["rot"] for a, sc in _acts("knocked_down")]
    assert "sweep" in {a for a, _sc in _acts("knocked_down")} and min(swept) < -70


def test_block_counter_disarms_the_weapon():
    acts = {a for a, _sc in _acts("block_counter")}
    assert {"overhead", "chop", "hit"} <= acts
    late = M.MOVES["block_counter"](0.8)
    assert late["ninjas"][0].get("disarmed") and any(o[0] == "staff" for o in late["objects"])
