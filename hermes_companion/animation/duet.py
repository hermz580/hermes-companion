"""Duet - two partner dancers who show Hermes's work as a dance.

Ade leads: locs, a silver beard, round glasses, a sky-blue shirt and a gold
chain. Rae follows: short golden hair, red round glasses, gold hoops and a
white dress scattered with blue flowers. They dance together, and the dance
*is* the status:

| Hermes is...                 | they dance...                                   |
|------------------------------|-------------------------------------------------|
| starting a task              | a bow, then they take hold                      |
| running a tool               | partner work: side steps, cha-cha, promenades   |
| on the web / browsing        | a travelling promenade                          |
| organising files             | an underarm turn                                |
| merging code                 | switch sides - they cross and trade places      |
| making media                 | a double spin                                   |
| delegating to helpers        | they separate and each dances solo              |
| a helper is back             | they come back together                         |
| needs your approval          | they freeze and both reach toward you           |
| a step failed                | a missed catch - a stumble, then they reset     |
| finished the task            | the lift, then a dip                            |
| quiet                        | a slow sway; asleep = sitting it out            |

Every engine pose maps to exactly one figure (``FIGURE_FOR_POSE``), so the
same Hermes action always gets the same dance. Poses without a figure still
honour ``pose_params`` (gaze, arms, lean, bob, tool prop) so nothing renders
as a neutral fallback.

Same Canvas contract as ``animator.draw_pet``; wider ``FRAME`` for two.
"""
from __future__ import annotations

import math
import time
from dataclasses import dataclass, field

from hermes_companion.animation.animator import pose_params
from hermes_companion.animation.herald import EXCLAIM, MOOD_COLORS, WONDER, _bubble, _prop, mood_of

FRAME = (320, 260)
FLOOR = 228
CENTER = FRAME[0] / 2

DUET_PALETTES: dict[str, dict[str, str]] = {
    # the look from the reference: sky-blue shirt, white floral dress
    "classic": {"lead_skin": "#6b4226", "lead_hair": "#1c140f", "beard": "#c9c9c9",
                "shirt": "#7fb8e6", "shirt_hi": "#a9d1f2", "trousers": "#1f2a44",
                "shoes": "#1f2a44", "chain": "#d4a017", "lead_glasses": "#3a3a3a",
                "follow_skin": "#f2c9a5", "follow_hair": "#ead27c", "dress": "#fbfbf7",
                "flowers": "#1f4e9c", "follow_glasses": "#c0392b", "sleeve": "#1f4e9c",
                "follow_shoes": "#1f4e9c", "earring": "#d4a017"},
    "evening": {"lead_skin": "#5a361e", "lead_hair": "#120c08", "beard": "#b8b8b8",
                "shirt": "#1b1f3b", "shirt_hi": "#2c335e", "trousers": "#0d0f1f",
                "shoes": "#0d0f1f", "chain": "#e8bf4f", "lead_glasses": "#d4a017",
                "follow_skin": "#efc3a0", "follow_hair": "#f0d98a", "dress": "#7a1f3d",
                "flowers": "#f4c2d7", "follow_glasses": "#e8bf4f", "sleeve": "#4a0f24",
                "follow_shoes": "#e8bf4f", "earring": "#e8bf4f"},
    "carnival": {"lead_skin": "#7a4e2d", "lead_hair": "#1b120c", "beard": "#d6d6d6",
                 "shirt": "#f39c12", "shirt_hi": "#f8c471", "trousers": "#1e8449",
                 "shoes": "#145a32", "chain": "#f4d03f", "lead_glasses": "#1b120c",
                 "follow_skin": "#f5cba7", "follow_hair": "#f7dc6f", "dress": "#fdfefe",
                 "flowers": "#8e44ad", "follow_glasses": "#e74c3c", "sleeve": "#8e44ad",
                 "follow_shoes": "#e74c3c", "earring": "#f4d03f"},
}
DUET_DEFAULT_PALETTE = "classic"

# ---------------------------------------------------------------------------
# Figures: the dance vocabulary. Each is a pure function of progress p (0..1)
# returning both dancers' placement and limbs:
#   x: offset from frame centre, y: height above the floor (lift),
#   spin: horizontal scale (1 front, -1 back-turned, ~0 side-on),
#   rot: body tilt in degrees (+ leans right), arms (l_sh, l_el, r_sh, r_el),
#   legs (l_hip, l_knee, r_hip, r_knee); angles in degrees from straight down.
#   hold: which hands are joined ("both", "inner", "lift", "none").
# ---------------------------------------------------------------------------
_REST_ARMS = (14, 12, 14, 12)
_REST_LEGS = (5, 0, 5, 0)


def _d(x=0.0, y=0.0, spin=1.0, rot=0.0, arms=_REST_ARMS, legs=_REST_LEGS):
    return {"x": x, "y": y, "spin": spin, "rot": rot, "arms": arms, "legs": legs}


def _step(p, amp=18.0):
    """Alternating stepping legs."""
    s = math.sin(p * 4 * math.pi)
    return (amp * s, 8 + 8 * s, -amp * s, 8 - 8 * s)


def _ease(t):
    t = min(1.0, max(0.0, t))
    return t * t * (3 - 2 * t)


def _fig_hold(p):
    sway = math.sin(p * 2 * math.pi) * 3
    return (_d(-24 + sway, arms=(40, 70, 75, 40)), _d(24 + sway, arms=(75, 40, 40, 70)), "both")


def _fig_sway(p):
    s = math.sin(p * 2 * math.pi)
    return (_d(-24 + s * 6, rot=s * 5, arms=(30, 60, 70, 40)),
            _d(24 + s * 6, rot=s * 5, arms=(70, 40, 30, 60)), "both")


def _fig_bow(p):
    dip = math.sin(min(p, 0.999) * math.pi)
    return (_d(-34, rot=-25 * dip, arms=(20, 80, 60, 30)),
            _d(34, rot=25 * dip, arms=(60, 30, 20, 80), legs=(5, 0, 25, 40)), "none")


def _fig_side_step(p):
    s = math.sin(p * 4 * math.pi)
    return (_d(-26 + s * 10, arms=(30, 50, 90, 10), legs=_step(p, 14)),
            _d(26 + s * 10, arms=(90, 10, 30, 50), legs=_step(p + 0.25, 14)), "inner")


def _fig_cha_cha(p):
    s = math.sin(p * 6 * math.pi)
    return (_d(-30 + s * 4, rot=s * 4, arms=(70, 50, 100, 20), legs=(20 * s, 25, -10 * s, 10)),
            _d(30 - s * 4, rot=-s * 4, arms=(100, 20, 70, 50), legs=(-10 * s, 10, 20 * s, 25)), "both")


def _fig_promenade(p):
    travel = math.sin(p * 2 * math.pi) * 34
    return (_d(-18 + travel, arms=(30, 40, 110, 10), legs=_step(p, 24)),
            _d(18 + travel, arms=(110, 10, 30, 40), legs=_step(p, 24)), "inner")


def _fig_underarm_turn(p):
    turn = math.cos(p * 2 * math.pi)
    return (_d(-26, arms=(20, 40, 165, 10)),
            _d(18, spin=turn, arms=(165, 10, 40, 50), legs=(6, 0, 30, 50)), "lift_hand")


def _fig_double_spin(p):
    turn = math.cos(p * 4 * math.pi)
    return (_d(-30, spin=turn, arms=(90, 10, 90, 10), legs=(6, 0, 6, 0)),
            _d(30, spin=-turn, arms=(90, 10, 90, 10), legs=(6, 0, 6, 0)), "none")


def _fig_switch_sides(p):
    t = _ease(p)
    lead_x = -30 + 60 * t
    follow_x = 30 - 60 * t
    arc = math.sin(t * math.pi) * 14
    return (_d(lead_x, y=arc * 0.3, spin=math.cos(t * math.pi), arms=(60, 30, 120, 10),
               legs=_step(p, 20)),
            _d(follow_x, y=arc, spin=math.cos(t * math.pi), arms=(120, 10, 60, 30),
               legs=_step(p + 0.5, 20)), "inner")


def _fig_separate(p):
    t = _ease(p)
    return (_d(-28 - 40 * t, arms=(40 + 40 * t, 30, 60 + 50 * t, 10), legs=_step(p, 10 * t)),
            _d(28 + 40 * t, arms=(60 + 50 * t, 10, 40 + 40 * t, 30), legs=_step(p, 10 * t)),
            "reach" if t < 0.6 else "none")


def _fig_solo(p):
    a = math.sin(p * 4 * math.pi)
    b = math.sin(p * 4 * math.pi + 1.6)
    return (_d(-72, y=abs(a) * 4, rot=a * 6, arms=(150 + a * 15, 20, 40 - a * 20, 90),
               legs=(30 * a, 40, 0, 0)),
            _d(72, y=abs(b) * 4, spin=math.cos(p * 2 * math.pi), arms=(60, 90, 150 - b * 15, 20),
               legs=(0, 0, 30 * b, 40)), "none")


def _fig_come_together(p):
    t = _ease(p)
    return (_d(-68 + 42 * t, arms=(60, 20, 90 - 20 * t, 20 + 30 * t), legs=_step(p, 16 * (1 - t))),
            _d(68 - 42 * t, arms=(90 - 20 * t, 20 + 30 * t, 60, 20), legs=_step(p, 16 * (1 - t))),
            "both" if t > 0.8 else "reach")


def _fig_freeze_reach(p):
    pulse = math.sin(p * 2 * math.pi) * 3
    return (_d(-26, rot=-6, arms=(20, 30, 100 + pulse, 0), legs=(10, 0, 20, 10)),
            _d(26, rot=6, arms=(100 + pulse, 0, 20, 30), legs=(20, 10, 10, 0)), "none")


def _fig_wave_to_you(p):
    w = math.sin(p * 6 * math.pi) * 22
    return (_d(-24, arms=(20, 30, 150 + w, 30)), _d(24, arms=(150 - w, 30, 20, 30)), "none")


def _fig_stumble(p):
    t = math.sin(min(p, 0.999) * math.pi)
    return (_d(-22, rot=-8 * t, arms=(80, 10, 80 + 30 * t, 10), legs=(20 * t, 30 * t, 5, 0)),
            _d(36 + 10 * t, rot=22 * t, arms=(120, 20, 40, 60), legs=(5, 0, 40 * t, 50 * t)), "none")


def _fig_reset(p):
    t = _ease(p)
    return (_d(-30 + 6 * t, arms=(30 + 20 * t, 60, 30 + 30 * t, 50)),
            _d(40 - 16 * t, rot=10 * (1 - t), arms=(30 + 30 * t, 50, 30 + 20 * t, 60)),
            "both" if t > 0.7 else "none")


def _fig_lift(p):
    up = math.sin(min(p, 0.999) * math.pi)
    return (_d(-12, rot=-4 * up, arms=(170, 15, 170, 15), legs=(15, 20, 15, 20)),
            _d(10 - 8 * up, y=78 * up, spin=math.cos(p * 2 * math.pi) if up > 0.9 else 1.0,
               arms=(165, 10, 165, 10), legs=(10, 30, 55 * up, 70 * up)), "lift")


def _fig_dip(p):
    d = math.sin(min(p, 0.999) * math.pi)
    return (_d(-18, rot=-10 * d, arms=(60, 40, 95, 20), legs=(25 * d, 30 * d, 5, 0)),
            _d(16, y=-4 * d, rot=55 * d, arms=(70, 30, 150, 20), legs=(5, 0, 45 * d, 20)), "both")


def _fig_jump_together(p):
    h = abs(math.sin(p * 2 * math.pi)) * 22
    return (_d(-24, y=h, arms=(160, 10, 120, 30), legs=(20, 40, 20, 40)),
            _d(24, y=h, arms=(120, 30, 160, 10), legs=(20, 40, 20, 40)), "inner")


def _fig_shrug(p):
    s = abs(math.sin(p * 2 * math.pi))
    return (_d(-30, y=s * 2, arms=(50, 110, 50, 110)), _d(30, y=s * 2, arms=(50, 110, 50, 110)), "none")


def _fig_nod(p):
    n = math.sin(p * 4 * math.pi)
    return (_d(-24, rot=n * 4, arms=(40, 70, 75, 40)), _d(24, rot=n * 4, arms=(75, 40, 40, 70)), "both")


def _fig_spin_out(p):
    turn = math.cos(p * 4 * math.pi)
    open_ = _ease(min(1.0, p * 1.5))
    return (_d(-26, arms=(30, 30, 90 + 40 * open_, 10)),
            _d(14 + 34 * open_, spin=turn, arms=(90 + 40 * open_, 10, 140, 20)), "inner")


def _fig_look_check(p):
    s = math.sin(p * 2 * math.pi)
    return (_d(-28, rot=s * 6, arms=(20, 40, 60, 120)), _d(28, rot=-s * 6, arms=(60, 120, 20, 40)), "none")


def _fig_sit_out(p):
    breathe = math.sin(p * 2 * math.pi) * 1.5
    return (_d(-26, y=-18 + breathe, arms=(30, 60, 50, 40), legs=(85, 90, 85, 90)),
            _d(22, y=-18 + breathe, rot=-12, arms=(50, 40, 30, 60), legs=(85, 90, 85, 90)), "inner")


def _fig_stretch(p):
    up = _ease(math.sin(min(p, 0.999) * math.pi))
    return (_d(-30, arms=(20 + 150 * up, 0, 20 + 150 * up, 0)),
            _d(30, arms=(20 + 150 * up, 0, 20 + 150 * up, 0)), "none")


# --- curious: they notice, listen and look together -------------------------
def _fig_listen_lean(p):
    s = math.sin(p * 2 * math.pi) * 2
    return (_d(-22, rot=8 + s, arms=(40, 70, 75, 40)), _d(26, rot=10 + s, arms=(75, 40, 150, 120)), "inner")


def _fig_glance_back(p):
    return (_d(-26, rot=-6, arms=(40, 70, 60, 40)), _d(26, rot=-8, arms=(60, 40, 40, 70)), "inner")


def _fig_notice_pop(p):
    pop = abs(math.sin(min(p, 0.999) * math.pi)) * 6
    return (_d(-28, y=pop, arms=(120, 60, 120, 60)), _d(28, y=pop, arms=(120, 60, 120, 60)), "none")


def _fig_peek(p):
    lean = math.sin(p * 2 * math.pi)
    return (_d(-6, arms=(20, 30, 20, 30)), _d(10 + 12 * max(0.0, lean), rot=18 * max(0.0, lean),
                                              arms=(60, 90, 30, 60)), "none")


def _fig_head_tilt(p):
    t = math.sin(p * 2 * math.pi) * 8
    return (_d(-26, rot=-10 - t, arms=(20, 40, 60, 120)), _d(26, rot=10 + t, arms=(60, 120, 20, 40)), "none")


def _fig_squint_in(p):
    return (_d(-14, rot=14, arms=(40, 90, 60, 40)), _d(16, rot=-14, arms=(60, 40, 40, 90)), "none")


def _fig_think(p):
    tap = math.sin(p * 8 * math.pi) * 10
    return (_d(-28, arms=(30, 60, 70, 150)), _d(28, arms=(70, 120 + tap, 20, 30), legs=(5, 0, 12 + tap, 10)), "none")


def _fig_look_around(p):
    turn = math.cos(p * 2 * math.pi)
    return (_d(-12, spin=turn, arms=(30, 60, 30, 60)), _d(12, spin=-turn, arms=(30, 60, 30, 60)), "none")


# --- uneasy ----------------------------------------------------------------
def _fig_flail(p):
    w = math.sin(p * 8 * math.pi) * 40
    return (_d(-30, arms=(100 + w, 20, 100 - w, 20), legs=_step(p, 10)),
            _d(34, rot=8, arms=(100 - w, 20, 100 + w, 20), legs=_step(p + 0.5, 10)), "none")


def _fig_head_scratch(p):
    sc = math.sin(p * 10 * math.pi) * 8
    return (_d(-26, arms=(20, 30, 150 + sc, 150)), _d(26, arms=(150 - sc, 150, 20, 30)), "none")


def _fig_head_shake(p):
    sh = math.sin(p * 8 * math.pi) * 9
    return (_d(-26, rot=sh, arms=(20, 40, 20, 40)), _d(26, rot=-sh, arms=(20, 40, 20, 40)), "none")


# --- calm ------------------------------------------------------------------
def _fig_bounce_step(p):
    h = abs(math.sin(p * 4 * math.pi)) * 8
    return (_d(-24, y=h, arms=(50, 80, 75, 40), legs=(10, 20, 10, 20)),
            _d(24, y=h, arms=(75, 40, 50, 80), legs=(10, 20, 10, 20)), "both")


def _fig_check_watch(p):
    tap = math.sin(p * 8 * math.pi) * 14
    return (_d(-26, arms=(20, 30, 70, 130)), _d(26, arms=(30, 90, 30, 90), legs=(5, 0, 14 + tap, 12)), "none")


def _fig_look_down(p):
    return (_d(-24, rot=6, arms=(20, 30, 40, 60)), _d(24, rot=-6, arms=(40, 60, 20, 30)), "inner")


def _fig_stargaze(p):
    return (_d(-24, rot=-6, arms=(20, 30, 160, 10)), _d(24, rot=6, arms=(150, 20, 20, 30)), "none")


def _fig_toss_catch(p):
    return (_d(-36, arms=(30, 40, 90 + 30 * math.sin(p * 2 * math.pi), 30)),
            _d(36, arms=(90 - 30 * math.sin(p * 2 * math.pi), 30, 30, 40)), "none")


# --- joy -------------------------------------------------------------------
def _fig_jive_bounce(p):
    h = abs(math.sin(p * 6 * math.pi)) * 14
    k = math.sin(p * 6 * math.pi) * 30
    return (_d(-26, y=h, arms=(120, 40, 80, 60), legs=(k, 30, 0, 0)),
            _d(26, y=h, arms=(80, 60, 120, 40), legs=(0, 0, -k, 30)), "inner")


def _fig_aerial(p):
    arc = math.sin(min(p, 0.999) * math.pi)
    return (_d(-10, rot=-20 * arc, arms=(120, 40, 120, 40), legs=(20, 30, 20, 30)),
            _d(-10 + 40 * p, y=60 * arc, rot=-180 * p, arms=(150, 20, 150, 20), legs=(60, 30, 60, 30)), "lift")


def _fig_strike_pose(p):
    return (_d(-16, spin=-1.0, rot=-6, arms=(60, 130, 60, 130)),
            _d(16, rot=8, arms=(170, 10, 50, 120), legs=(5, 0, 25, 40)), "none")


def _fig_joy_spin(p):
    turn = math.cos(p * 6 * math.pi)
    return (_d(-24, spin=turn, y=abs(turn) * 4, arms=(150, 20, 150, 20)),
            _d(24, spin=turn, y=abs(turn) * 4, arms=(150, 20, 150, 20)), "none")


# --- rest ------------------------------------------------------------------
def _fig_head_on_shoulder(p):
    br = math.sin(p * 2 * math.pi)
    return (_d(-16, rot=-2, arms=(20, 30, 60, 50)), _d(6, rot=-16 + br, arms=(60, 60, 20, 40)), "inner")


def _fig_lazy_stretch(p):
    up = _ease(math.sin(min(p, 0.999) * math.pi))
    return (_d(-28, rot=-10 * up, arms=(20 + 140 * up, 20, 20 + 140 * up, 20)),
            _d(28, rot=10 * up, arms=(20 + 140 * up, 20, 20 + 140 * up, 20)), "none")


def _fig_yawn(p):
    up = math.sin(min(p, 0.999) * math.pi)
    return (_d(-26, rot=-4 * up, arms=(20, 30, 100 * up + 20, 120)),
            _d(26, rot=4 * up, arms=(100 * up + 20, 120, 20, 30)), "none")


# --- their own decorative moves (flourishes only; never a signature) --------
def _fig_jive_kick(p):
    k = max(0.0, math.sin(p * 4 * math.pi)) * 60
    return (_d(-26, arms=(60, 50, 90, 20), legs=(k, 10, 0, 0)), _d(26, arms=(90, 20, 60, 50), legs=(0, 0, k, 10)), "inner")


def _fig_shimmy(p):
    s = math.sin(p * 12 * math.pi) * 6
    return (_d(-24 + s * 0.3, rot=s, arms=(60, 90, 60, 90)), _d(24 - s * 0.3, rot=-s, arms=(60, 90, 60, 90)), "none")


def _fig_twirl_pair(p):
    t = math.cos(p * 4 * math.pi)
    return (_d(-20, arms=(30, 30, 160, 10)), _d(20, spin=t, arms=(160, 10, 70, 30)), "lift_hand")


def _fig_hand_jive(p):
    s = math.sin(p * 8 * math.pi) * 30
    return (_d(-26, arms=(70 + s, 100, 70 - s, 100)), _d(26, arms=(70 - s, 100, 70 + s, 100)), "none")


def _fig_high_five(p):
    up = math.sin(min(p, 0.999) * math.pi)
    return (_d(-18, y=up * 6, arms=(20, 30, 160 * up + 20, 10)), _d(18, y=up * 6, arms=(160 * up + 20, 10, 20, 30)), "inner")


def _fig_conga_hop(p):
    h = abs(math.sin(p * 4 * math.pi)) * 10
    return (_d(-10 + h, y=h, spin=-1.0, arms=(60, 40, 60, 40), legs=(20, 40, 0, 0)),
            _d(24 + h, y=h, spin=-1.0, arms=(90, 10, 90, 10), legs=(20, 40, 0, 0)), "none")


def _fig_heel_toe(p):
    s = math.sin(p * 4 * math.pi)
    return (_d(-24, arms=(40, 70, 75, 40), legs=(20 * s, 0, 5, 0)), _d(24, arms=(75, 40, 40, 70), legs=(5, 0, -20 * s, 0)), "both")


def _fig_slow_turn(p):
    t = math.cos(p * 2 * math.pi)
    return (_d(-20 * t, spin=t, arms=(40, 70, 75, 40)), _d(20 * t, spin=t, arms=(75, 40, 40, 70)), "both")


def _fig_lean_together(p):
    s = math.sin(p * 2 * math.pi) * 3
    return (_d(-16, rot=8 + s, arms=(20, 30, 60, 40)), _d(16, rot=-8 - s, arms=(60, 40, 20, 30)), "inner")


def _fig_sway_wide(p):
    s = math.sin(p * 2 * math.pi)
    return (_d(-30 + s * 16, rot=s * 10, arms=(30, 60, 100, 20)), _d(30 + s * 16, rot=s * 10, arms=(100, 20, 30, 60)), "inner")


def _fig_back_to_back(p):
    s = math.sin(p * 2 * math.pi) * 4
    return (_d(-12 + s, spin=-1.0, arms=(60, 120, 60, 120)), _d(12 + s, arms=(60, 120, 60, 120)), "none")


def _fig_box_step(p):
    q = int(p * 4) % 4
    dx = (-8, 8, 8, -8)[q]
    return (_d(-24 + dx, arms=(40, 70, 75, 40), legs=_step(p, 18)), _d(24 + dx, arms=(75, 40, 40, 70), legs=_step(p + 0.5, 18)), "both")


def _fig_tap_count(p):
    tap = abs(math.sin(p * 8 * math.pi)) * 18
    return (_d(-26, arms=(30, 90, 60, 60), legs=(tap, 10, 5, 0)), _d(26, arms=(60, 60, 30, 90), legs=(5, 0, tap, 10)), "none")


def _fig_mirror_hands(p):
    s = math.sin(p * 2 * math.pi) * 30
    return (_d(-22, arms=(30, 40, 100 + s, 20)), _d(22, arms=(100 + s, 20, 30, 40)), "none")


def _fig_frame_hold(p):
    return (_d(-22, arms=(90, 60, 100, 20)), _d(22, arms=(100, 20, 90, 60)), "both")


def _fig_fidget(p):
    s = math.sin(p * 10 * math.pi) * 4
    return (_d(-26 + s, arms=(40, 120, 40, 120)), _d(26 - s, arms=(30, 100, 60, 140)), "none")


def _fig_glance_away(p):
    return (_d(-28, rot=-10, spin=0.6, arms=(20, 40, 20, 40)), _d(28, rot=10, spin=0.6, arms=(20, 40, 20, 40)), "none")


def _fig_rub_neck(p):
    r = math.sin(p * 6 * math.pi) * 10
    return (_d(-26, arms=(20, 30, 140 + r, 150)), _d(26, arms=(20, 40, 20, 40)), "none")


def _fig_steady(p):
    s = math.sin(p * 2 * math.pi) * 3
    return (_d(-18, arms=(30, 40, 80, 40)), _d(18, rot=s, arms=(80, 40, 30, 40)), "both")


FIGURES = {
    "hold": _fig_hold, "sway": _fig_sway, "bow": _fig_bow, "side_step": _fig_side_step,
    "cha_cha": _fig_cha_cha, "promenade": _fig_promenade, "underarm_turn": _fig_underarm_turn,
    "double_spin": _fig_double_spin, "switch_sides": _fig_switch_sides, "separate": _fig_separate,
    "solo": _fig_solo, "come_together": _fig_come_together, "freeze_reach": _fig_freeze_reach,
    "wave_to_you": _fig_wave_to_you, "stumble": _fig_stumble, "reset": _fig_reset,
    "lift": _fig_lift, "dip": _fig_dip, "jump_together": _fig_jump_together, "shrug": _fig_shrug,
    "nod": _fig_nod, "spin_out": _fig_spin_out, "look_check": _fig_look_check,
    "sit_out": _fig_sit_out, "stretch": _fig_stretch,
    # curious
    "listen_lean": _fig_listen_lean, "glance_back": _fig_glance_back, "notice_pop": _fig_notice_pop,
    "peek": _fig_peek, "head_tilt": _fig_head_tilt, "squint_in": _fig_squint_in, "think": _fig_think,
    "look_around": _fig_look_around,
    # uneasy
    "flail": _fig_flail, "head_scratch": _fig_head_scratch, "head_shake": _fig_head_shake,
    # calm
    "bounce_step": _fig_bounce_step, "check_watch": _fig_check_watch, "look_down": _fig_look_down,
    "stargaze": _fig_stargaze, "toss_catch": _fig_toss_catch,
    # joy
    "jive_bounce": _fig_jive_bounce, "aerial": _fig_aerial, "strike_pose": _fig_strike_pose,
    "joy_spin": _fig_joy_spin,
    # rest
    "head_on_shoulder": _fig_head_on_shoulder, "lazy_stretch": _fig_lazy_stretch, "yawn": _fig_yawn,
}

# Their own moves: decoration the grammar may add around a signature, sorted
# by mood. They never stand in for a Hermes action.
DUET_MOVES: dict[str, tuple] = {
    "jive_kick": ("bright", _fig_jive_kick), "shimmy": ("bright", _fig_shimmy),
    "twirl_pair": ("bright", _fig_twirl_pair), "hand_jive": ("bright", _fig_hand_jive),
    "high_five": ("bright", _fig_high_five), "conga_hop": ("bright", _fig_conga_hop),
    "heel_toe": ("calm", _fig_heel_toe), "slow_turn": ("calm", _fig_slow_turn),
    "lean_together": ("calm", _fig_lean_together), "sway_wide": ("calm", _fig_sway_wide),
    "back_to_back": ("calm", _fig_back_to_back),
    "box_step": ("focused", _fig_box_step), "tap_count": ("focused", _fig_tap_count),
    "mirror_hands": ("focused", _fig_mirror_hands), "frame_hold": ("focused", _fig_frame_hold),
    "fidget": ("uneasy", _fig_fidget), "glance_away": ("uneasy", _fig_glance_away),
    "rub_neck": ("uneasy", _fig_rub_neck), "steady": ("uneasy", _fig_steady),
}
FIGURES.update({name: fn for name, (_mood, fn) in DUET_MOVES.items()})

# Signature: each engine pose -> one figure, so meaning never varies.
FIGURE_FOR_POSE: dict[str, str] = {
    # starting
    "crack_knuckles": "bow", "attention": "hold", "jump": "jump_together",
    # moving to the work
    "run_to_workspace": "promenade", "walk_to_workspace": "promenade",
    "dash_to_workspace": "promenade", "sprint_to_workspace": "promenade",
    "tip_to_workspace": "promenade",
    # tool work, by kind
    "work": "side_step", "lean_work": "cha_cha", "terminal_work": "cha_cha",
    "web_scan": "promenade", "read": "sway", "file_organize": "underarm_turn",
    "dev_merge": "switch_sides", "media_paint": "double_spin", "design_draft": "double_spin",
    "audio_tune": "cha_cha", "memory_vault": "underarm_turn",
    # a step finished
    "close_workstation": "underarm_turn", "celebrate": "spin_out", "return_home": "promenade",
    # failure
    "shock": "stumble", "fall": "stumble", "recover": "reset", "inspect": "look_check",
    "huff": "sway", "sit_back": "stumble", "sneak": "stumble", "retry": "reset", "repair": "reset",
    # needs you
    "wake": "freeze_reach", "panic": "freeze_reach", "run_to_user": "freeze_reach",
    "wave": "wave_to_you", "wait": "freeze_reach", "point": "freeze_reach",
    # your answer
    "nod": "nod", "hop": "jump_together", "shrug": "shrug", "discard": "separate",
    # done
    "leap": "lift", "double_jump": "lift", "excited": "spin_out",
    # helpers
    "open_portal": "separate", "channel": "solo", "orb_exits": "solo",
    "orb_returns": "come_together", "absorb": "hold", "fly_up": "lift", "fly_down": "dip",
    # quiet
    "idle_bob": "sway", "idle": "sway", "sleep": "sit_out", "sit": "sit_out",
    "stretch": "stretch", "dance": "double_spin", "spin": "double_spin",
    # curious beats
    "look_at_input": "listen_lean", "watch": "listen_lean", "look_at_user": "glance_back",
    "notice": "notice_pop", "eyebrow_raise": "notice_pop", "peeking": "peek",
    "head_tilt": "head_tilt", "tilt": "head_tilt", "squint": "squint_in", "think": "think",
    "look_around": "look_around",
    # uneasy beats
    "arm_flap": "flail", "scratch_head": "head_scratch", "shake_head": "head_shake",
    # calm beats
    "bounce": "bounce_step", "check_watch": "check_watch", "look_down": "look_down",
    "look_up": "stargaze", "play_with_object": "toss_catch",
    # joy beats
    "full_bounce": "jive_bounce", "leap_double_joy": "aerial", "smug": "strike_pose",
    "spin_joy": "joy_spin",
    # rest beats
    "head_drop": "head_on_shoulder", "stretch_lazy": "lazy_stretch", "yawn": "yawn",
}
FIGURE_FOR_POSE.update({name: name for name in DUET_MOVES})

# Moods for colour (the floor spotlight) and the grammar's mood buckets.
_FIGURE_MOOD = {
    "lift": "joy", "dip": "joy", "spin_out": "joy", "jump_together": "joy",
    "separate": "delegate", "solo": "delegate", "come_together": "delegate",
    "freeze_reach": "approve", "wave_to_you": "approve",
    "stumble": "fail", "reset": "fail", "look_check": "fail",
    "sit_out": "rest", "sway": "rest",
    "flail": "fail", "head_scratch": "fail", "head_shake": "fail",
    "jive_bounce": "joy", "aerial": "joy", "strike_pose": "joy", "joy_spin": "joy",
    "head_on_shoulder": "rest", "lazy_stretch": "rest", "yawn": "rest",
    "listen_lean": "curious", "glance_back": "curious", "notice_pop": "curious", "peek": "curious",
    "head_tilt": "curious", "squint_in": "curious", "think": "curious", "look_around": "curious",
}
_FIGURE_MOOD.update({name: {"bright": "joy", "uneasy": "fail", "focused": "work"}.get(m, "calm")
                     for name, (m, _fn) in DUET_MOVES.items()})


def duet_flourishes() -> dict[str, tuple[str, ...]]:
    out: dict[str, list[str]] = {}
    for name, (mood, _fn) in DUET_MOVES.items():
        out.setdefault(mood, []).append(name)
    return {k: tuple(v) for k, v in out.items()}


# Which of their own moves suit each kind of tool work.
CATEGORY_HINTS = {
    "terminal": ("box_step", "tap_count"), "development": ("box_step", "mirror_hands"),
    "web": ("sway_wide", "lean_together"), "browser": ("sway_wide", "slow_turn"),
    "file": ("mirror_hands", "frame_hold"), "docs": ("frame_hold", "heel_toe"),
    "media": ("twirl_pair", "shimmy"), "memory": ("back_to_back", "slow_turn"),
    "delegation": ("back_to_back", "high_five"),
}


def flourish_hints() -> dict[str, tuple[str, ...]]:
    return dict(CATEGORY_HINTS)


CURIOUS_MOVES = ("heel_toe", "lean_together", "slow_turn", "back_to_back")


def figure_for(pose: str) -> str | None:
    return FIGURE_FOR_POSE.get(pose)


def _palette(name: str | None) -> dict[str, str]:
    return DUET_PALETTES.get(name or DUET_DEFAULT_PALETTE, DUET_PALETTES[DUET_DEFAULT_PALETTE])


# ---------------------------------------------------------------------------
# Drawing: each dancer is drawn in local coordinates (hip at 0,0, y up is
# negative) and mapped through spin (x-scale), tilt and placement.
# ---------------------------------------------------------------------------
class _Body:
    def __init__(self, canvas, hx, hy, spin, rot):
        self.c, self.hx, self.hy = canvas, hx, hy
        self.sx = spin if abs(spin) > 0.18 else math.copysign(0.18, spin or 1)
        r = math.radians(rot)
        self.cos, self.sin = math.cos(r), math.sin(r)

    def pt(self, x, y):
        x *= self.sx
        return (self.hx + x * self.cos - y * self.sin, self.hy + x * self.sin + y * self.cos)

    def line(self, pts, **kw):
        flat = [v for xy in pts for v in self.pt(*xy)]
        self.c.create_line(*flat, capstyle="round", joint="round", **kw)

    def poly(self, pts, **kw):
        flat = [v for xy in pts for v in self.pt(*xy)]
        self.c.create_polygon(*flat, **kw)

    def dot(self, x, y, r, **kw):
        cx, cy = self.pt(x, y)
        rx = max(1.0, r * abs(self.sx)) if kw.pop("squash", False) else r
        self.c.create_oval(cx - rx, cy - r, cx + rx, cy + r, **kw)


def _limb_pts(x, y, ang1, ang2, l1, l2, side):
    a1 = math.radians(ang1)
    ex, ey = x + side * math.sin(a1) * l1, y + math.cos(a1) * l1
    a2 = a1 + math.radians(ang2)
    return (x, y), (ex, ey), (ex + side * math.sin(a2) * l2, ey + math.cos(a2) * l2)


def _draw_dancer(canvas, who: str, P, hx, hy, st, eyes: str):
    b = _Body(canvas, hx, hy, st["spin"], st["rot"])
    back = st["spin"] < 0
    lead = who == "lead"
    skin = P["lead_skin"] if lead else P["follow_skin"]
    hands = {}

    # legs
    for side, (hip, knee) in ((-1, st["legs"][0:2]), (1, st["legs"][2:4])):
        a, k, f = _limb_pts(side * 6, 0, hip, knee, 22, 22, side)
        if lead:
            b.line([a, k, f], width=10, fill=P["trousers"])
        else:
            b.line([a, k, f], width=7, fill=skin)
        b.dot(f[0] + side * 3, f[1] + 1, 5, fill=P["shoes"] if lead else P["follow_shoes"], outline="")

    # torso
    if lead:
        b.poly([(-13, -46), (13, -46), (11, 2), (-11, 2)], fill=P["shirt"], outline=P["shirt_hi"], width=1)
        for yy in (-36, -26, -16, -6):                       # buttons
            b.dot(0, yy, 1.2, fill="#ffffff", outline="")
        b.line([(-7, -44), (0, -32), (7, -44)], width=2, fill=P["chain"])       # gold chain
    else:
        b.poly([(-10, -46), (10, -46), (20, 12), (-20, 12)], fill=P["dress"], outline="#d9d9d0", width=1)
        for fx, fy in ((-9, -30), (8, -14), (-12, 4), (12, 2), (2, -38)):       # flowers
            for k in range(5):
                ang = k / 5 * 2 * math.pi
                b.dot(fx + math.cos(ang) * 2.6, fy + math.sin(ang) * 2.6, 2.1, fill=P["flowers"], outline="")
            b.dot(fx, fy, 1.1, fill=P["dress"], outline="")

    # arms (lead's shirt sleeves; Rae's right sleeve matches the flowers)
    sh_y = -42
    for side, (shd, elb) in ((-1, st["arms"][0:2]), (1, st["arms"][2:4])):
        a, e, h = _limb_pts(side * 12, sh_y, 180 - shd if shd > 90 else shd, elb, 17, 16, side)
        if shd > 90:   # raised: mirror the vertical component
            a, e, h = (a, (e[0], 2 * sh_y - e[1]), (h[0], 2 * sh_y - h[1]))
        sleeve = P["shirt"] if lead else (P["sleeve"] if side > 0 else skin)
        b.line([a, e], width=7, fill=sleeve)
        b.line([e, h], width=6, fill=skin)
        b.dot(h[0], h[1], 3.2, fill=skin, outline="")
        hands["left" if side < 0 else "right"] = b.pt(*h)

    # head
    head_y = -60
    b.line([(0, -46), (0, head_y + 10)], width=6, fill=skin)
    if lead:   # locs fall behind the head
        for k in range(-3, 4):
            b.line([(k * 3.2, head_y - 10), (k * 4.0, head_y + 18 + abs(k))], width=3, fill=P["lead_hair"])
    b.dot(0, head_y, 12.5, fill=skin, outline="", squash=True)
    if lead:
        b.dot(0, head_y - 7, 11, fill=P["lead_hair"], outline="", squash=True)   # crown
        b.dot(0, head_y - 2, 11.5, fill=skin, outline="", squash=True)
    else:
        b.dot(0, head_y - 6, 12, fill=P["follow_hair"], outline="", squash=True)  # short crop
        b.dot(0, head_y - 1, 11, fill=skin, outline="", squash=True)
    if back:   # turned away: we see the back of the hair
        hair = P["lead_hair"] if lead else P["follow_hair"]
        b.dot(0, head_y - 1, 12.6, fill=hair, outline="", squash=True)
        if lead:
            for k in range(-3, 4):
                b.line([(k * 3.4, head_y - 8), (k * 4.2, head_y + 20 + abs(k))], width=3, fill=hair)
    else:
        gx = {"left": -2.5, "right": 2.5}.get(eyes, 0.0)
        gy = {"down": 1.5, "up": -1.5}.get(eyes, 0.0)
        frame = P["lead_glasses"] if lead else P["follow_glasses"]
        for side in (-1, 1):
            b.dot(side * 5 + gx * 0.3, head_y - 1 + gy * 0.3, 3.8, fill="", outline=frame, width=2)
            if eyes == "closed":
                b.line([(side * 5 - 2, head_y - 1), (side * 5 + 2, head_y - 1)], width=1, fill="#2b1a10")
            else:
                r = 1.6 if eyes != "wide" else 2.2
                b.dot(side * 5 + gx, head_y - 1 + gy, r, fill="#2b1a10", outline="")
        b.line([(-1.5, head_y - 1), (1.5, head_y - 1)], width=1, fill=frame)
        if lead:   # silver beard + smile
            b.poly([(-9, head_y + 3), (9, head_y + 3), (5, head_y + 13), (-5, head_y + 13)],
                   fill=P["beard"], outline="")
            b.line([(-4, head_y + 5), (0, head_y + 7), (4, head_y + 5)], width=2, fill="#5a2e1a")
        else:
            b.line([(-4, head_y + 5), (0, head_y + 7.5), (4, head_y + 5)], width=2, fill="#a2453a")
            b.dot(-11, head_y + 3, 2.2, fill="", outline=P["earring"], width=2)
            b.dot(11, head_y + 3, 2.2, fill="", outline=P["earring"], width=2)
    return hands


# ---------------------------------------------------------------------------
# Live stage: what Hermes is doing right now, beyond the current move.
# Fed by the live renderer (``observe``) from signed, content-free events.
# ---------------------------------------------------------------------------
CATEGORY_COLORS = {
    "terminal": "#2dd4bf", "development": "#14b8a6", "web": "#60a5fa", "browser": "#38bdf8",
    "file": "#f59e0b", "docs": "#f59e0b", "media": "#f472b6", "memory": "#a78bfa",
    "planning": "#84cc16", "delegation": "#a78bfa", "desktop": "#94a3b8",
}


@dataclass
class DuetState:
    category: str = "general"
    running: int = 0          # tools in flight -> more energy, beat lights on the floor
    helpers: int = 0          # subagents in flight -> backup dancers
    missteps: int = 0         # failures not yet recovered (3 successes heal one)
    streak: int = 0
    danger: bool = False      # a destructive command waits for approval -> red floor
    think_until: float = 0.0
    party_until: float = 0.0  # task complete -> confetti
    clock: object = field(default=time.monotonic, repr=False)

    def observe(self, ev) -> None:
        kind = getattr(ev.kind, "value", str(ev.kind))
        cat = ev.category or "general"
        now = self.clock()
        if kind == "agent.started":
            self.running = self.helpers = self.missteps = self.streak = 0
            self.party_until = 0.0
        elif kind == "user.prompt_submitted":
            self.think_until = now + 3.0
        elif kind == "tool.started":
            self.running = min(self.running + 1, 5)
            self.category = cat
        elif kind == "tool.progress":
            self.category = cat
        elif kind == "tool.finished":
            self.running = max(0, self.running - 1)
            self.streak += 1
            if self.streak >= 3 and self.missteps:
                self.missteps -= 1
                self.streak = 0
        elif kind == "tool.failed":
            self.running = max(0, self.running - 1)
            self.missteps = min(self.missteps + 1, 3)
            self.streak = 0
        elif kind == "approval.required":
            self.danger = cat == "dangerous"
        elif kind in ("approval.approved", "approval.rejected"):
            self.danger = False
        elif kind == "agent.subagent_spawned":
            self.helpers = min(self.helpers + 1, 4)
        elif kind in ("agent.subagent_finished", "agent.subagent_failed"):
            self.helpers = max(0, self.helpers - 1)
            if kind.endswith("failed"):
                self.missteps = min(self.missteps + 1, 3)
        elif kind in ("task.complete", "agent.idle"):
            self.running = self.helpers = 0
            self.danger = False
            self.category = "general"
            if kind == "task.complete":
                self.party_until = now + 6.0

    @property
    def thinking(self) -> bool:
        return self.clock() < self.think_until

    @property
    def partying(self) -> bool:
        return self.clock() < self.party_until

    def key(self) -> tuple:
        return (self.category, self.running, self.helpers, self.missteps, self.danger,
                self.thinking, self.partying)


STATE = DuetState()


def observe(ev) -> None:
    STATE.observe(ev)


def state_key() -> tuple:
    return STATE.key()


def _backup_dancer(canvas, x, y, p, color, phase):
    """A small silhouette couple in the back: one helper Hermes sent out."""
    for k, dx in enumerate((-6, 6)):
        a = math.sin(p * 4 * math.pi + phase + k)
        hx, hy = x + dx, y - abs(a) * 2
        canvas.create_line(hx, hy, hx - 4, hy + 12, fill=color, width=2)
        canvas.create_line(hx, hy, hx + 4, hy + 12, fill=color, width=2)
        canvas.create_line(hx, hy, hx, hy - 12, fill=color, width=3)
        canvas.create_line(hx, hy - 10, hx + (8 if k else -8) * a, hy - 18, fill=color, width=2)
        canvas.create_oval(hx - 3, hy - 19, hx + 3, hy - 13, fill=color, outline="")


def _draw_stage(canvas, p, mood, P):
    """Stage effects from live state: helpers, missteps, thinking, party, energy."""
    st = STATE
    for i in range(st.helpers):                         # backup dancers, one per helper
        side = -1 if i % 2 == 0 else 1
        _backup_dancer(canvas, CENTER + side * (104 + 22 * (i // 2)), FLOOR - 34, p,
                       "#a78bfa", i * 1.3)
    for i in range(st.running):                         # beat lights: one per tool in flight
        x = CENTER - 12 * (st.running - 1) / 2 + i * 12
        lit = (int(p * 8) + i) % 2 == 0
        canvas.create_oval(x - 3, FLOOR + 4, x + 3, FLOOR + 10,
                           fill=CATEGORY_COLORS.get(st.category, "#2dd4bf") if lit else "#475569",
                           outline="")
    for i in range(st.missteps * 3):                    # loose petals drift down
        x = CENTER - 40 + (i * 37) % 90
        y = 70 + ((p * 120 + i * 29) % 130)
        canvas.create_oval(x - 2.5, y - 1.5, x + 2.5, y + 1.5, fill=P["flowers"], outline="")
    if st.thinking:                                     # thinking: dots over both heads
        for k, hx in enumerate((CENTER - 26, CENTER + 26)):
            for j in range(3):
                on = (int(p * 6) + j + k) % 3 == 0
                canvas.create_oval(hx - 9 + j * 8, 60, hx - 5 + j * 8, 64,
                                   fill="#475569" if on else "#cbd5e1", outline="")
    if st.partying:                                     # confetti after a finished task
        for i in range(18):
            x = 20 + (i * 53) % (FRAME[0] - 40)
            y = 10 + ((p * 160 + i * 23) % 180)
            color = ("#facc15", "#f472b6", "#60a5fa", "#34d399")[i % 4]
            canvas.create_rectangle(x, y, x + 4, y + 2, fill=color, outline="")


def draw_duet(canvas, pose: str, progress: float = 0.0, palette: str | None = None) -> None:
    P = _palette(palette)
    canvas.delete("all")
    p = progress % 1.0
    figure = FIGURE_FOR_POSE.get(pose)
    prm = pose_params(pose, progress)
    if figure is not None:
        lead, follow, hold = FIGURES[figure](p)
        mood = _FIGURE_MOOD.get(figure) or mood_of(pose)
    else:
        # Unmapped pose: a neutral hold that still shows gaze, lean, bob and arms.
        lead, follow, hold = _fig_hold(p)
        arms = {"up": (160, 10, 160, 10), "wave": (14, 12, 150 + math.sin(p * 12) * 18, 30),
                "bent": (40, 100, 40, 100), "cross": (50, 120, 50, 120), "hold": (40, 70, 40, 70),
                "work": (45, 80, 50, 75), "stretch": (90, 0, 90, 0), "throw": (20, 20, 140, 10),
                }.get(prm["arms"])
        if arms:
            lead = {**lead, "arms": arms}
            follow = {**follow, "arms": arms[2:] + arms[:2]}
            hold = "none"
        tilt = prm["lean"] * 120
        lift = -prm["bob"] + {"jump": 18, "tall": 4, "sit": -14, "fall": -10}.get(prm["body"], 0)
        lead = {**lead, "rot": lead["rot"] + tilt, "y": lead["y"] + lift}
        follow = {**follow, "rot": follow["rot"] + tilt, "y": follow["y"] + lift}
        mood = mood_of(pose)
    glow = MOOD_COLORS.get(mood, MOOD_COLORS["calm"])
    if STATE.danger and mood == "approve":
        glow = "#ef4444"                                # a destructive command waits on you
    elif mood == "work" and STATE.category in CATEGORY_COLORS:
        glow = CATEGORY_COLORS[STATE.category]          # the kind of work tints the floor
    eyes = prm["eyes"]
    if mood == "work" and STATE.running > 1:            # more tools in flight, more energy
        lift = abs(math.sin(p * 4 * math.pi)) * 2 * (STATE.running - 1)
        lead = {**lead, "y": lead["y"] + lift}
        follow = {**follow, "y": follow["y"] + lift}

    # floor spotlight in the mood colour + dance-floor sparkle
    canvas.create_oval(CENTER - 120, FLOOR - 12, CENTER + 120, FLOOR + 12, fill=glow, outline="")
    canvas.create_oval(CENTER - 96, FLOOR - 7, CENTER + 96, FLOOR + 7, fill="#fffdf5", outline="")
    for i in range(7):
        sx = CENTER - 90 + i * 30 + 6 * math.sin(p * 6.28 + i)
        canvas.create_oval(sx - 1.5, FLOOR - 1.5, sx + 1.5, FLOOR + 1.5, fill=glow, outline="")

    # music notes while they dance (not while frozen or failing)
    if mood in ("work", "joy", "delegate", "calm", "rest"):
        for k, (nx, ny) in enumerate(((-28, 30), (2, 18), (30, 34))):
            rise = (p * 30 + k * 11) % 30
            x0, y0 = CENTER + nx, ny + 20 - rise
            canvas.create_oval(x0 - 4, y0 - 3, x0 + 2, y0 + 3, fill="#f4c20d", outline="")
            canvas.create_line(x0 + 2, y0, x0 + 2, y0 - 14, fill="#f4c20d", width=2)
            if k != 1:
                canvas.create_line(x0 + 2, y0 - 14, x0 + 8, y0 - 10, fill="#f4c20d", width=2)

    _draw_stage(canvas, p, mood, P)
    hip = FLOOR - 46
    lead_h = _dancer_hip(lead, hip)
    follow_h = _dancer_hip(follow, hip)
    # whoever is lifted or further back draws first
    order = [("lead", lead, lead_h), ("follow", follow, follow_h)]
    if follow["y"] > 30:
        order.reverse()
    hands = {}
    for who, st, (hx, hy) in order:
        hands[who] = _draw_dancer(canvas, who, P, hx, hy, st, eyes)

    _draw_hold(canvas, hold, hands, P)
    if STATE.missteps:
        hx, hy = _dancer_hip(lead, hip)
        canvas.create_polygon(hx + 14, hy - 74, hx + 11, hy - 67, hx + 17, hy - 67,
                              fill="#60a5fa", outline="")
        canvas.create_oval(hx + 11, hy - 70, hx + 17, hy - 64, fill="#60a5fa", outline="")
    if pose in EXCLAIM:
        _bubble(canvas, CENTER, 22, "!", glow)
    elif pose in WONDER:
        _bubble(canvas, CENTER, 22, "?", glow)
    _prop(canvas, prm["extra"], CENTER, 30, p, glow)


def _dancer_hip(st, hip_y):
    return CENTER + st["x"], hip_y - st["y"]


def _draw_hold(canvas, hold, hands, P):
    """Joined hands: each partner's arm reaches to meet, with a spark at the touch."""
    lead, follow = hands.get("lead", {}), hands.get("follow", {})
    pairs = {"both": (("right", "left"), ("left", "right")), "inner": (("right", "left"),),
             "lift_hand": (("right", "left"),), "reach": (("right", "left"),),
             "lift": (("left", "left"), ("right", "right"))}.get(hold, ())
    for a, b in pairs:
        if a in lead and b in follow:
            (x1, y1), (x2, y2) = lead[a], follow[b]
            if math.hypot(x2 - x1, y2 - y1) < 70:
                mx, my = (x1 + x2) / 2, (y1 + y2) / 2
                if hold == "reach":   # still reaching: fingertips, not yet touching
                    canvas.create_line(x1, y1, mx - 4, my, fill=P["lead_skin"], width=3, capstyle="round")
                    canvas.create_line(x2, y2, mx + 4, my, fill=P["follow_skin"], width=3, capstyle="round")
                    continue
                canvas.create_line(x1, y1, mx, my, fill=P["lead_skin"], width=5, capstyle="round")
                canvas.create_line(x2, y2, mx, my, fill=P["follow_skin"], width=5, capstyle="round")
                canvas.create_oval(mx - 2.5, my - 2.5, mx + 2.5, my + 2.5, fill=P["chain"], outline="")


VOICE = {
    "starting": "Take your partner!", "reviewing": "Reading the floor...",
    "needs-you": "We need your OK!", "issue": "Missed a step - we'll try it again.",
    "complete": "Ta-da! That's the lift.", "paused": "Holding the pose for you.",
}
GREETING = "Ade and Rae, ready to dance."
