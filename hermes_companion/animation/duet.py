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

FRAME = (320, 300)
FLOOR = 228   # stage floor; the status plaque sits below it
CENTER = FRAME[0] / 2

DUET_PALETTES: dict[str, dict[str, str]] = {
    # the look from the reference: sky-blue shirt, white floral dress
    "classic": {"edge": "#241a14", "lead_skin": "#6b4226", "lead_hair": "#1c140f", "beard": "#c9c9c9",
                "shirt": "#7fb8e6", "shirt_hi": "#a9d1f2", "trousers": "#1f2a44",
                "shoes": "#1f2a44", "chain": "#d4a017", "lead_glasses": "#3a3a3a",
                "follow_skin": "#f2c9a5", "follow_hair": "#ead27c", "dress": "#fbfbf7",
                "flowers": "#1f4e9c", "follow_glasses": "#c0392b", "sleeve": "#1f4e9c",
                "follow_shoes": "#1f4e9c", "earring": "#d4a017"},
    "evening": {"edge": "#0a0a14", "lead_skin": "#5a361e", "lead_hair": "#120c08", "beard": "#b8b8b8",
                "shirt": "#1b1f3b", "shirt_hi": "#2c335e", "trousers": "#0d0f1f",
                "shoes": "#0d0f1f", "chain": "#e8bf4f", "lead_glasses": "#d4a017",
                "follow_skin": "#efc3a0", "follow_hair": "#f0d98a", "dress": "#7a1f3d",
                "flowers": "#f4c2d7", "follow_glasses": "#e8bf4f", "sleeve": "#4a0f24",
                "follow_shoes": "#e8bf4f", "earring": "#e8bf4f"},
    "carnival": {"edge": "#2a1608", "lead_skin": "#7a4e2d", "lead_hair": "#1b120c", "beard": "#d6d6d6",
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


def _d(x=0.0, y=0.0, spin=1.0, rot=0.0, arms=_REST_ARMS, legs=_REST_LEGS, *,
       torso=0.0, hip=0.0, head=0.0, wrists=(0.0, 0.0), ankles=(0.0, 0.0),
       swivel=(0.0, 0.0), shoulders=(0.0, 0.0)):
    """One dancer's pose.

    Whole body: x, y (lift), spin (1 front .. -1 back), rot (whole-body tilt).
    Joints: arms (l_sh, l_el, r_sh, r_el), legs (l_hip, l_knee, r_hip, r_knee),
    torso (spine bend over the hips, deg), hip (sideways hip shift, px - Cuban
    motion), head (neck tilt, deg), wrists (l, r flick, deg), ankles (l, r:
    + points the toe, - flexes it), swivel (l, r: + toes in, - toes out - the
    Charleston twist), shoulders (l, r lift, px - shimmies).
    """
    return {"x": x, "y": y, "spin": spin, "rot": rot, "arms": arms, "legs": legs,
            "torso": torso, "hip": hip, "head": head, "wrists": wrists, "ankles": ankles,
            "swivel": swivel, "shoulders": shoulders}


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
    """Cha-cha: rock step and a cha-cha-cha chassé, hips over each straight leg."""
    s = math.sin(p * 6 * math.pi)
    return (_d(-30 + s * 4, hip=5 * s, torso=-4 * s, arms=(70, 50, 100, 20), wrists=(0, 20),
               legs=(20 * s, 25 * max(0, -s), -10 * s, 25 * max(0, s)), ankles=(20 * max(0, s), 20 * max(0, -s))),
            _d(30 - s * 4, hip=-5 * s, torso=4 * s, arms=(100, 20, 70, 50), wrists=(20, 0),
               legs=(-10 * s, 25 * max(0, s), 20 * s, 25 * max(0, -s)), ankles=(20 * max(0, -s), 20 * max(0, s))),
            "both")


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
    """Apart, each dances a shine: Ade a Shorty George, Rae a Suzie Q."""
    ade, _, _ = _fig_shorty_george(p)
    _, rae, _ = _fig_suzie_q(p)
    return ({**ade, "x": -72}, {**rae, "x": 72 + _sw(p, 1) * 8}, "none")


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


# ===========================================================================
# Real dance vocabulary (swing, Lindy, salsa, ballroom, tango, street), built
# on the jointed rig: spine, hips, neck, wrists, ankles, foot swivel, shoulders.
# ===========================================================================
def _sw(p, n=2):
    return math.sin(p * 2 * math.pi * n)


# --- Swing / Lindy hop ------------------------------------------------------
def _fig_swingout(p):
    """Lindy swingout: lead draws the follow in, they rotate, he sends her out."""
    t = _ease(p)
    rot = math.sin(t * math.pi)
    fx = 46 - 70 * math.sin(t * math.pi * 0.5) + 70 * max(0.0, t - 0.6) * 2.4
    return (_d(-28 + 8 * rot, torso=-10 * rot, arms=(70, 40, 60 + 40 * rot, 20), legs=_step(p, 16),
               ankles=(10, 0)),
            _d(fx, spin=math.cos(t * 2 * math.pi), torso=12 * rot, arms=(60 + 40 * rot, 20, 120, 30),
               legs=_step(p + 0.5, 20), ankles=(0, 20)), "inner")


def _fig_tuck_turn(p):
    """East Coast swing tuck turn: a compress, a tuck, then she spins out."""
    t = _ease(p)
    tuck = math.sin(min(t * 2, 1.0) * math.pi * 0.5)
    spin = math.cos(max(0.0, t - 0.5) * 4 * math.pi) if t > 0.5 else 1.0
    return (_d(-26, torso=6 * tuck, arms=(30, 50, 80, 70 - 30 * tuck), wrists=(0, 30 * tuck)),
            _d(22 - 6 * tuck, spin=spin, torso=-8 * tuck, arms=(80, 70, 30, 60), legs=_step(p, 10)), "inner")


def _fig_sugar_push(p):
    """Sugar push: she steps in (compression), both rebound out on a stretch."""
    c = math.sin(p * 2 * math.pi)
    gap = 44 + 10 * c
    return (_d(-gap / 2, torso=-6 * c, arms=(75, 60 - 30 * c, 75, 60 - 30 * c), legs=(8 * c, 10, -6, 0)),
            _d(gap / 2, torso=6 * c, arms=(75, 60 - 30 * c, 75, 60 - 30 * c), legs=(-6, 0, 8 * c, 10)), "both")


def _fig_charleston(p):
    """Side-by-side Charleston: kick forward, kick back, swivelling feet."""
    k = _sw(p, 2)
    sw = abs(_sw(p, 4))
    def one(x, phase):
        kk = math.sin(p * 4 * math.pi + phase)
        return _d(x, y=abs(kk) * 3, torso=-8 * kk, arms=(40 - 30 * kk, 30, 40 + 30 * kk, 30),
                  legs=(45 * max(0, kk), 10, -25 * max(0, -kk), 40 * max(0, -kk)),
                  ankles=(30 * max(0, kk), 0), swivel=(sw, sw), wrists=(25, 25))
    return (one(-30, 0.0), one(30, 0.0), "inner")


def _fig_tandem_charleston(p):
    """Tandem Charleston: she in front, he behind, same kicks, holding hands."""
    k = math.sin(p * 4 * math.pi)
    sw = abs(_sw(p, 4))
    leg = (45 * max(0, k), 10, -25 * max(0, -k), 40 * max(0, -k))
    return (_d(-6, spin=1.0, torso=-6 * k, arms=(60, 40, 60, 40), legs=leg, swivel=(sw, sw)),
            _d(6, spin=1.0, torso=-6 * k, arms=(40, 30, 40, 30), legs=leg, swivel=(sw, sw), ankles=(20 * max(0, k), 0)),
            "both")


def _fig_kick_ball_change(p):
    """Kick-ball-change: kick, step onto the ball of the foot, change weight."""
    q = (p * 3) % 1.0
    kick = math.sin(min(q * 2, 1.0) * math.pi) if q < 0.5 else 0.0
    ball = 30 if 0.5 <= q < 0.75 else 0
    return (_d(-26, y=2 * kick, arms=(40, 70, 75, 40), legs=(50 * kick, 15, 5, 0), ankles=(40 * kick, ball)),
            _d(26, y=2 * kick, arms=(75, 40, 40, 70), legs=(5, 0, 50 * kick, 15), ankles=(ball, 40 * kick)), "both")


def _fig_suzie_q(p):
    """Suzie Q: travelling sideways on swivelling heels, hands pointing the way."""
    sw = _sw(p, 3)
    travel = _sw(p, 1) * 20
    return (_d(-26 + travel, torso=-8, head=-10, arms=(110, 20, 60, 120), wrists=(-30, 0),
               legs=(20 * sw, 20, -10 * sw, 20), swivel=(max(0, sw), max(0, -sw))),
            _d(26 + travel, torso=-8, head=-10, arms=(60, 120, 110, 20), wrists=(0, -30),
               legs=(20 * sw, 20, -10 * sw, 20), swivel=(max(0, -sw), max(0, sw))), "none")


def _fig_shorty_george(p):
    """Shorty George: knees together and low, shuffling forward, hands pointing down."""
    sw = _sw(p, 2)
    return (_d(-28, y=-8, torso=20, arms=(30, 20, 30, 20), wrists=(40, 40),
               legs=(40 + 15 * sw, 70, 40 - 15 * sw, 70), swivel=(0.6, 0.6)),
            _d(28, y=-8, torso=20, arms=(30, 20, 30, 20), wrists=(40, 40),
               legs=(40 - 15 * sw, 70, 40 + 15 * sw, 70), swivel=(0.6, 0.6)), "none")


def _fig_apple_jacks(p):
    """Apple Jacks: rocking heel-toe over bent knees, weight rolling side to side."""
    r = _sw(p, 2)
    return (_d(-28 + r * 4, rot=r * 6, hip=r * 3, arms=(50, 80, 50, 80),
               legs=(25, 40, 25, 40), swivel=(max(0, r), max(0, -r)), ankles=(-20 * max(0, r), -20 * max(0, -r))),
            _d(28 + r * 4, rot=r * 6, hip=r * 3, arms=(50, 80, 50, 80),
               legs=(25, 40, 25, 40), swivel=(max(0, -r), max(0, r)), ankles=(-20 * max(0, -r), -20 * max(0, r))),
            "none")


def _fig_frog_jump(p):
    """Lindy aerial: she leaps forward over his braced arms, knees tucked."""
    arc = math.sin(min(p, 0.999) * math.pi)
    return (_d(-16, y=-6 * arc, torso=25 * arc, arms=(100, 20, 100, 20), legs=(30, 40, 30, 40)),
            _d(4 + 16 * p, y=64 * arc, torso=-10, arms=(130, 30, 130, 30),
               legs=(80 * arc, 110 * arc, 80 * arc, 110 * arc), ankles=(40, 40)), "lift")


# --- Salsa ------------------------------------------------------------------
def _fig_salsa_basic(p):
    """Salsa basic on 1: rock forward and back, hips moving over each step."""
    r = _sw(p, 2)
    return (_d(-24, hip=4 * r, torso=-4 * r, arms=(60, 80, 70, 40), legs=(18 * r, 10, -10 * r, 5)),
            _d(24, hip=-4 * r, torso=4 * r, arms=(70, 40, 60, 80), legs=(-10 * r, 5, 18 * r, 10)), "both")


def _fig_cross_body_lead(p):
    """Cross-body lead: he turns his torso and opens a lane; she walks across it."""
    t = _ease(p)
    return (_d(-26 + 10 * math.sin(t * math.pi), torso=-30 * math.sin(t * math.pi), spin=1 - 1.6 * math.sin(t * math.pi) * 0.5,
               arms=(40, 60, 90, 30), legs=_step(p, 12)),
            _d(30 - 58 * t, spin=math.cos(t * math.pi), arms=(90, 30, 40, 60), legs=_step(p + 0.5, 18)), "inner")


def _fig_inside_turn(p):
    """Inside turn: one and a half turns toward the lead, led by his wrist."""
    t = _ease(p)
    return (_d(-24, torso=-10 * math.sin(t * math.pi), arms=(30, 40, 160, 15), wrists=(0, -40)),
            _d(16, spin=math.cos(t * 3 * math.pi), torso=4, arms=(160, 15, 60, 40), legs=(5, 0, 25, 45),
               ankles=(0, 30)), "lift_hand")


def _fig_copa(p):
    """Copa: she is sent out, checks, turns back in under his arm."""
    t = _ease(p)
    out = math.sin(t * math.pi)
    return (_d(-26, torso=-8 * out, arms=(40, 50, 90 + 50 * (t > 0.6), 30)),
            _d(20 + 30 * out, spin=math.cos(max(0.0, t - 0.5) * 2 * math.pi), torso=12 * out,
               arms=(100, 20, 40, 60), legs=_step(p, 10)), "inner")


def _fig_cuban_motion(p):
    """Cuban motion: hips swing over each straightening knee, chest stays quiet."""
    r = _sw(p, 2)
    return (_d(-26, hip=6 * r, torso=-5 * r, arms=(40, 90, 40, 90), legs=(6 * r, 18 * max(0, -r), -6 * r, 18 * max(0, r))),
            _d(26, hip=7 * r, torso=-6 * r, arms=(40, 90, 40, 90), wrists=(20, 20),
               legs=(6 * r, 18 * max(0, -r), -6 * r, 18 * max(0, r))), "none")


# --- Ballroom ---------------------------------------------------------------
def _fig_promenade_sway(p):
    """Promenade sway: they open to a V and stretch up, heads turned the same way."""
    s = math.sin(min(p, 0.999) * math.pi)
    return (_d(-20, rot=-6 * s, torso=-10 * s, head=-14 * s, arms=(90, 40, 110, 20), legs=(5, 0, 30 * s, 10)),
            _d(20, rot=6 * s, torso=10 * s, head=-14 * s, arms=(110, 20, 90, 40), legs=(30 * s, 10, 5, 0)), "both")


def _fig_oversway(p):
    """Oversway: he softens his knee and sways; she arches back, head closed."""
    s = math.sin(min(p, 0.999) * math.pi)
    return (_d(-14, torso=-14 * s, arms=(70, 60, 100, 30), legs=(30 * s, 40 * s, 5, 0), head=8 * s),
            _d(14, rot=10 * s, torso=40 * s, head=30 * s, arms=(100, 30, 150, 20), legs=(5, 0, 40 * s, 10),
               ankles=(0, 50 * s)), "both")


def _fig_fallaway(p):
    """Fallaway: both step back into a tight V, turning away from each other."""
    s = math.sin(min(p, 0.999) * math.pi)
    return (_d(-22 - 6 * s, spin=1 - 0.5 * s, torso=10 * s, arms=(60, 50, 100, 30), legs=(-20 * s, 20, 5, 0)),
            _d(22 + 6 * s, spin=1 - 0.5 * s, torso=-10 * s, arms=(100, 30, 60, 50), legs=(5, 0, -20 * s, 20)), "inner")


def _fig_hip_twist(p):
    """Rumba hip twist: she swivels on the spot as he guides her hips."""
    r = _sw(p, 2)
    return (_d(-22, torso=-4, arms=(60, 60, 80, 30)),
            _d(20, spin=math.cos(p * 2 * math.pi) * 0.6 + 0.4 * (1 if r > 0 else -1), hip=6 * r,
               arms=(80, 30, 120, 30), wrists=(0, 30), legs=(10, 10, 10, 10), swivel=(max(0, r), max(0, r))), "inner")


# --- Tango ------------------------------------------------------------------
def _fig_tango_corte(p):
    """Corte: a deep lunge and a sharp head snap, then hold."""
    s = math.sin(min(p * 1.6, 1.0) * math.pi * 0.5)
    return (_d(-18, y=-10 * s, torso=-12 * s, head=-20 * s, arms=(70, 60, 100, 20), legs=(45 * s, 60 * s, -20 * s, 0)),
            _d(16, y=-8 * s, torso=20 * s, head=-25 * s, arms=(100, 20, 70, 60), legs=(-20 * s, 0, 40 * s, 30 * s),
               ankles=(40 * s, 0)), "both")


def _fig_ocho(p):
    """Ocho: she pivots on one foot, tracing a figure eight with the free one."""
    r = _sw(p, 1)
    return (_d(-22, torso=-6, arms=(70, 60, 90, 30)),
            _d(20, spin=0.6 * r + 0.4 * math.copysign(1, r), hip=5 * r, arms=(90, 30, 70, 60),
               legs=(10, 0, 30 * abs(r), 10), swivel=(abs(r), 0), ankles=(0, 50)), "both")


def _fig_gancho(p):
    """Gancho: she hooks her leg around his, a quick flick from the knee."""
    hook = math.sin(min(p, 0.999) * math.pi)
    return (_d(-14, torso=-6, arms=(70, 60, 90, 30), legs=(15, 20, 5, 0)),
            _d(12, torso=-10 * hook, arms=(90, 30, 70, 60), legs=(5, 0, -40 * hook, 120 * hook),
               ankles=(0, 60 * hook)), "both")


# --- Street / social ----------------------------------------------------------
def _fig_moonwalk(p):
    """Moonwalk: gliding backwards, one heel up while the flat foot slides."""
    a = _sw(p, 2)
    glide = -_sw(p, 1) * 18
    return (_d(-28 + glide, spin=-0.6, torso=-4, arms=(25, 70, 25, 70),
               ankles=(60 * max(0, a), 60 * max(0, -a)), legs=(10 * max(0, a), 20 * max(0, a), 10 * max(0, -a), 20 * max(0, -a))),
            _d(28 + glide, spin=-0.6, torso=-4, arms=(25, 70, 25, 70),
               ankles=(60 * max(0, -a), 60 * max(0, a)), legs=(10 * max(0, -a), 20 * max(0, -a), 10 * max(0, a), 20 * max(0, a))),
            "none")


def _fig_running_man(p):
    """Running man: a knee comes up as the other foot slides back."""
    a = _sw(p, 2)
    return (_d(-28, y=2 * abs(a), torso=-6, arms=(60 - 40 * a, 90, 60 + 40 * a, 90),
               legs=(70 * max(0, a), 90 * max(0, a), 70 * max(0, -a), 90 * max(0, -a))),
            _d(28, y=2 * abs(a), torso=-6, arms=(60 + 40 * a, 90, 60 - 40 * a, 90),
               legs=(70 * max(0, -a), 90 * max(0, -a), 70 * max(0, a), 90 * max(0, a))), "none")


def _fig_cabbage_patch(p):
    """Cabbage patch: fists circle in front of the chest as the hips rock."""
    c, s2 = math.cos(p * 4 * math.pi), math.sin(p * 4 * math.pi)
    return (_d(-28, hip=4 * s2, torso=-3 * s2, arms=(70 + 20 * c, 100 + 20 * s2, 70 - 20 * c, 100 - 20 * s2),
               legs=(15, 20, 15, 20)),
            _d(28, hip=4 * s2, torso=-3 * s2, arms=(70 - 20 * c, 100 - 20 * s2, 70 + 20 * c, 100 + 20 * s2),
               legs=(15, 20, 15, 20)), "none")


def _fig_robot(p):
    """The robot: stiff, angular, one joint at a time on the beat."""
    q = int(p * 4) % 4
    arms = [(90, 90, 20, 0), (90, 0, 90, 90), (20, 90, 90, 0), (90, 90, 90, 90)][q]
    wr = [(90, 0), (0, -90), (-90, 0), (90, 90)][q]
    hd = [0, 15, 0, -15][q]
    return (_d(-28, head=hd, arms=arms, wrists=wr), _d(28, head=-hd, arms=arms[2:] + arms[:2], wrists=wr[::-1]), "none")


def _fig_shoulder_shimmy(p):
    """Shimmy: shoulders alternate up and down fast, everything else still."""
    s = _sw(p, 8)
    return (_d(-26, shoulders=(4 * s, -4 * s), torso=2 * s, arms=(50, 80, 50, 80)),
            _d(26, shoulders=(-4 * s, 4 * s), torso=-2 * s, arms=(50, 80, 50, 80)), "none")


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

FIGURES.update({
    "swingout": _fig_swingout, "tuck_turn": _fig_tuck_turn, "sugar_push": _fig_sugar_push,
    "charleston": _fig_charleston, "tandem_charleston": _fig_tandem_charleston,
    "kick_ball_change": _fig_kick_ball_change, "frog_jump": _fig_frog_jump,
    "salsa_basic": _fig_salsa_basic, "cross_body_lead": _fig_cross_body_lead,
    "inside_turn": _fig_inside_turn, "copa": _fig_copa, "promenade_sway": _fig_promenade_sway,
    "oversway": _fig_oversway, "tango_corte": _fig_tango_corte, "moonwalk": _fig_moonwalk,
})

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
    "suzie_q": ("bright", _fig_suzie_q), "shorty_george": ("bright", _fig_shorty_george),
    "running_man": ("bright", _fig_running_man), "cabbage_patch": ("bright", _fig_cabbage_patch),
    "shoulder_shimmy": ("bright", _fig_shoulder_shimmy),
    "apple_jacks": ("calm", _fig_apple_jacks), "fallaway": ("calm", _fig_fallaway),
    "ocho": ("calm", _fig_ocho),
    "cuban_motion": ("focused", _fig_cuban_motion), "hip_twist": ("focused", _fig_hip_twist),
    "robot": ("focused", _fig_robot), "gancho": ("focused", _fig_gancho),
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
# Real-dance signatures: each still means exactly one thing.
FIGURE_FOR_POSE.update({
    "work": "sugar_push",                 # steady give-and-take: a tool is working
    "lean_work": "salsa_basic",           # still working: back to the basic
    "dash_to_workspace": "swingout", "sprint_to_workspace": "swingout",   # launching a step
    "memory_vault": "inside_turn", "design_draft": "cross_body_lead",
    "read": "promenade_sway", "close_workstation": "tuck_turn",
    "celebrate": "charleston",            # a step finished
    "excited": "tandem_charleston",       # a helper finished
    "hop": "kick_ball_change",            # you approved: off we go
    "return_home": "moonwalk",            # gliding back home
    "double_jump": "frog_jump",           # task complete, the second big air
    "absorb": "copa", "retry": "salsa_basic", "attention": "tango_corte",
    "recover": "oversway",                # recovering: she leans back, held
    "audio_tune": "side_step",
    "fly_up": "spin_out",                 # helper finished: the lift is kept for task complete
})
FIGURE_FOR_POSE.update({name: name for name in DUET_MOVES})

# Moods for colour (the floor spotlight) and the grammar's mood buckets.
_FIGURE_MOOD = {
    "lift": "joy", "dip": "joy", "spin_out": "joy", "jump_together": "joy",
    "separate": "delegate", "solo": "delegate", "come_together": "delegate",
    "freeze_reach": "approve", "wave_to_you": "approve",
    "stumble": "fail", "reset": "fail", "look_check": "fail",
    "sit_out": "rest", "sway": "rest",
    "flail": "fail", "head_scratch": "fail", "head_shake": "fail",
    "frog_jump": "joy", "charleston": "joy", "tandem_charleston": "joy",
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
class _Draw:
    """Stroke helpers shared by a dancer's body and its jointed sub-frames.

    Every stroke can carry an ``edge``: a darker outline drawn first, so each
    part of the body reads cleanly against any desktop.
    """

    @staticmethod
    def _w(kw):
        """Whole-pixel widths: every canvas (Tk, PIL, test recorders) accepts them."""
        if "width" in kw:
            kw["width"] = max(1, round(kw["width"]))
        return kw

    def line(self, pts, edge=False, **kw):
        flat = [v for xy in pts for v in self.pt(*xy)]
        kw = self._w(kw)
        if edge:
            self.c.create_line(*flat, capstyle="round", joint="round", fill=self.edge,
                               width=kw.get("width", 1) + 2)
        self.c.create_line(*flat, capstyle="round", joint="round", **kw)

    def poly(self, pts, edge=False, **kw):
        flat = [v for xy in pts for v in self.pt(*xy)]
        if edge:
            kw = {**kw, "outline": self.edge, "width": 2}
        self.c.create_polygon(*flat, **self._w(kw))

    def dot(self, x, y, r, edge=False, **kw):
        kw = self._w(kw)
        cx, cy = self.pt(x, y)
        rx = max(1.0, r * abs(self.sx)) if kw.pop("squash", False) else r
        if edge:
            self.c.create_oval(cx - rx - 1.2, cy - r - 1.2, cx + rx + 1.2, cy + r + 1.2,
                               fill=self.edge, outline="")
        self.c.create_oval(cx - rx, cy - r, cx + rx, cy + r, **kw)


class _Body(_Draw):
    """The whole dancer: spin (x-scale), whole-body tilt and placement."""

    def __init__(self, canvas, hx, hy, spin, rot, edge):
        self.c, self.hx, self.hy, self.edge = canvas, hx, hy, edge
        self.sx = spin if abs(spin) > 0.18 else math.copysign(0.18, spin or 1)
        r = math.radians(rot)
        self.cos, self.sin = math.cos(r), math.sin(r)

    def pt(self, x, y):
        x *= self.sx
        return (self.hx + x * self.cos - y * self.sin, self.hy + x * self.sin + y * self.cos)


class _Joint(_Draw):
    """A sub-frame that bends at a pivot: the spine over the hips, the neck."""

    def __init__(self, parent, pivot, angle, shift=(0.0, 0.0), twist=0.0):
        self.parent, self.c, self.edge, self.sx = parent, parent.c, parent.edge, parent.sx
        self.px, self.py = pivot
        self.dx, self.dy = shift
        r = math.radians(angle)
        self.cos, self.sin = math.cos(r), math.sin(r)
        # twist: the frame turns about the vertical axis (shoulders against hips),
        # seen from the front as a narrowing of its width.
        self.tw = max(0.25, abs(math.cos(math.radians(twist))))

    def pt(self, x, y):
        lx, ly = (x - self.px) * self.tw, y - self.py
        return self.parent.pt(self.px + self.dx + lx * self.cos - ly * self.sin,
                              self.py + self.dy + lx * self.sin + ly * self.cos)


def _limb_pts(x, y, ang1, ang2, l1, l2, side):
    a1 = math.radians(ang1)
    ex, ey = x + side * math.sin(a1) * l1, y + math.cos(a1) * l1
    a2 = a1 + math.radians(ang2)
    return (x, y), (ex, ey), (ex + side * math.sin(a2) * l2, ey + math.cos(a2) * l2)


def _mix(a: str, b: str, t: float) -> str:
    """Blend two #rrggbb colours (t=0 -> a, t=1 -> b)."""
    ca = [int(a[i:i + 2], 16) for i in (1, 3, 5)]
    cb = [int(b[i:i + 2], 16) for i in (1, 3, 5)]
    return "#" + "".join(f"{round(x + (y - x) * t):02x}" for x, y in zip(ca, cb))


def _foot(b, ankle_pt, side, ankle_deg, swivel, shoe, strap=None):
    """A foot from the ankle: toe points (+) or flexes (-), swivels in (+) or out (-)."""
    ax, ay = ankle_pt
    a = math.radians(max(-60.0, min(80.0, ankle_deg)))
    out = side * (1.0 - 2.0 * max(0.0, min(1.0, swivel))) if swivel > 0 else side * (1.0 + abs(swivel) * 0.4)
    length = 9.0 * (1.0 - 0.45 * abs(math.sin(a)))       # a pointed foot looks shorter from the front
    toe = (ax + out * length * math.cos(a), ay + 3 + length * math.sin(a))
    heel = (ax - out * 2.5, ay + 3)
    b.line([heel, toe], edge=True, width=6, fill=shoe)
    b.line([(heel[0], heel[1] + 2.5), (toe[0], toe[1] + 2.5)], width=1, fill=_mix(shoe, "#000000", 0.5))  # sole
    b.dot(toe[0] - out * 2, toe[1] - 1.5, 1.2, fill=_mix(shoe, "#ffffff", 0.55), outline="")
    if strap:
        b.line([(ax - 2.5, ay + 1.5), (ax + 2.5, ay + 1.5)], width=1, fill=strap)


def _hand(b, wrist, forearm_from, side, flick, skin, skin_shade):
    """Palm at the wrist plus fingers that follow the forearm, bent by the wrist."""
    hx, hy = wrist
    ex, ey = forearm_from
    ang = math.atan2(hy - ey, hx - ex) + math.radians(side * flick)
    fx, fy = hx + math.cos(ang) * 4.2, hy + math.sin(ang) * 4.2
    b.line([(hx, hy), (fx, fy)], edge=True, width=4, fill=skin)          # fingers
    b.dot(hx, hy, 3.3, edge=True, fill=skin, outline="")                 # palm
    tx, ty = hx + math.cos(ang - side * 1.2) * 3.2, hy + math.sin(ang - side * 1.2) * 3.2
    b.dot(tx, ty, 1.3, fill=skin_shade, outline="")                      # thumb


def _draw_dancer(canvas, who: str, P, hx, hy, st, eyes: str):
    lead = who == "lead"
    skin = P["lead_skin"] if lead else P["follow_skin"]
    edge = P.get("edge") or _mix(skin, "#000000", 0.62)
    body = _Body(canvas, hx, hy, st["spin"], st["rot"], edge)
    back = st["spin"] < 0
    skin_shade = _mix(skin, "#000000", 0.22)
    hip = st.get("hip", 0.0)
    ankles, swivel = st.get("ankles", (0, 0)), st.get("swivel", (0, 0))
    wrists, shoulders = st.get("wrists", (0, 0)), st.get("shoulders", (0, 0))
    hands = {}

    # ---- legs hang from the (shifted) hips; feet from the ankles ---------------
    for i, (side, (hip_a, knee)) in enumerate(((-1, st["legs"][0:2]), (1, st["legs"][2:4]))):
        a, k, f = _limb_pts(hip + side * 6, 0, hip_a, knee, 22, 22, side)
        if lead:
            body.line([a, k, f], edge=True, width=10, fill=P["trousers"])
            body.line([((a[0] + k[0]) / 2, (a[1] + k[1]) / 2), k], width=1,
                      fill=_mix(P["trousers"], "#ffffff", 0.25))           # crease
        else:
            body.line([a, k, f], edge=True, width=7, fill=skin)
            body.line([(k[0] - 1, k[1]), (f[0] - 1, f[1])], width=1.5, fill=skin_shade)
            body.dot(k[0], k[1], 2.2, fill=skin_shade, outline="")             # knee
        _foot(body, f, side, ankles[i], swivel[i], P["shoes"] if lead else P["follow_shoes"],
              None if lead else P["earring"])

    # ---- spine: chest bends over the hips ------------------------------------
    chest = _Joint(body, (hip, 0), st.get("torso", 0.0), (0, 0))
    if lead:
        body.poly([(hip - 11, -8), (hip + 11, -8), (hip + 11, 2), (hip - 11, 2)], edge=True,
                  fill=P["shirt"])                                         # shirt tail at the hips
        chest.poly([(-13, -46), (13, -46), (11, -4), (-11, -4)], edge=True, fill=P["shirt"])
        chest.poly([(-13, -46), (-3, -46), (-9, -38)], fill=P["shirt_hi"], outline="")    # collar
        chest.poly([(13, -46), (3, -46), (9, -38)], fill=P["shirt_hi"], outline="")
        chest.line([(0, -40), (0, -4)], width=1, fill=_mix(P["shirt"], "#000000", 0.25))
        for yy in (-34, -24, -14):
            chest.dot(0, yy, 1.2, fill="#ffffff", outline="")
        chest.poly([(4, -32), (10, -32), (10, -25), (4, -25)], fill=P["shirt_hi"],
                   outline=_mix(P["shirt"], "#000000", 0.3))               # pocket
        chest.line([(-7, -45), (0, -33), (7, -45)], width=2, fill=P["chain"])
        chest.dot(0, -32, 2, fill=P["chain"], outline=_mix(P["chain"], "#000000", 0.4))
        body.line([(hip - 11, 0), (hip + 11, 0)], width=2.5, fill=_mix(P["trousers"], "#000000", 0.3))
        body.dot(hip, 0, 1.6, fill=P["chain"], outline="")
    else:
        body.poly([(hip - 13, -14), (hip + 13, -14), (hip + 20, 12), (hip - 20, 12)], edge=True,
                  fill=P["dress"])                                         # skirt swings with the hips
        for i in range(6):
            body.dot(hip - 16.7 + i * 6.7, 12, 3.3, fill=P["dress"], outline=_mix(P["dress"], "#000000", 0.2))
        for fx, fy in ((-12, 3), (12, 1), (-3, -6)):
            for k in range(5):
                ang = k / 5 * 2 * math.pi
                body.dot(hip + fx + math.cos(ang) * 2.7, fy + math.sin(ang) * 2.7, 2.1, fill=P["flowers"], outline="")
            body.dot(hip + fx, fy, 1.2, fill=P["earring"], outline="")
        chest.poly([(-10, -46), (10, -46), (13, -14), (-13, -14)], edge=True, fill=P["dress"])
        chest.line([(-6, -46), (0, -41), (6, -46)], width=1.5, fill=_mix(P["dress"], "#000000", 0.18))
        chest.line([(-12, -22), (12, -22)], width=3, fill=P["flowers"])         # waist sash
        chest.dot(6, -22, 2.4, fill=P["flowers"], outline="")
        for fx, fy in ((-7, -32), (6, -30), (3, -38)):
            for k in range(5):
                ang = k / 5 * 2 * math.pi
                chest.dot(fx + math.cos(ang) * 2.7, fy + math.sin(ang) * 2.7, 2.1, fill=P["flowers"], outline="")
            chest.dot(fx, fy, 1.2, fill=P["earring"], outline="")

    # ---- arms ride on the spine; shoulders can lift; hands flick at the wrist --
    for i, (side, (shd, elb)) in enumerate(((-1, st["arms"][0:2]), (1, st["arms"][2:4]))):
        sh_y = -42 - shoulders[i]
        a, e, h = _limb_pts(side * 12, sh_y, 180 - shd if shd > 90 else shd, elb, 17, 16, side)
        if shd > 90:   # raised: mirror the vertical component
            a, e, h = (a, (e[0], 2 * sh_y - e[1]), (h[0], 2 * sh_y - h[1]))
        sleeve = P["shirt"] if lead else (P["sleeve"] if side > 0 else skin)
        chest.line([a, e], edge=True, width=7, fill=sleeve)
        chest.line([e, h], edge=True, width=6, fill=skin)
        if lead:
            chest.dot(e[0], e[1], 3.6, fill=P["shirt_hi"], outline=_mix(P["shirt"], "#000000", 0.3))
            if side < 0:
                wx, wy = e[0] + (h[0] - e[0]) * 0.72, e[1] + (h[1] - e[1]) * 0.72
                chest.dot(wx, wy, 2.2, fill=P["chain"], outline=_mix(P["chain"], "#000000", 0.4))
        _hand(chest, h, e, side, wrists[i], skin, skin_shade)
        hands["left" if side < 0 else "right"] = chest.pt(*h)

    # ---- neck + head ------------------------------------------------------------
    head_y = -60
    chest.line([(0, -46), (0, head_y + 10)], edge=True, width=6, fill=skin)
    hb = _Joint(chest, (0, -50), st.get("head", 0.0))
    hair = P["lead_hair"] if lead else P["follow_hair"]
    if lead:                                                    # locs with gold cuffs
        for k in range(-3, 4):
            end = (k * 4.0, head_y + 18 + abs(k))
            hb.line([(k * 3.2, head_y - 10), end], edge=True, width=3, fill=hair)
            if k % 2 == 0:
                hb.dot(end[0] * 0.85, end[1] - 6, 1.4, fill=P["chain"], outline="")
    hb.dot(0, head_y, 12.5, edge=True, fill=skin, outline="", squash=True)
    if back:   # turned away: we see the back of the hair
        hb.dot(0, head_y - 1, 12.6, edge=True, fill=hair, outline="", squash=True)
        if lead:
            for k in range(-3, 4):
                hb.line([(k * 3.4, head_y - 8), (k * 4.2, head_y + 20 + abs(k))], width=3, fill=hair)
        else:
            hb.line([(-6, head_y + 6), (0, head_y + 9), (6, head_y + 6)], width=1.5,
                    fill=_mix(hair, "#000000", 0.25))
        return hands

    if lead:
        hb.dot(0, head_y - 7, 11, fill=hair, outline="", squash=True)
        hb.dot(0, head_y - 2, 11.5, fill=skin, outline="", squash=True)
    else:
        hb.dot(0, head_y - 6, 12, fill=hair, outline="", squash=True)
        hb.dot(0, head_y - 1, 11, fill=skin, outline="", squash=True)
        for k in (-6, -2, 2, 6):
            hb.line([(k, head_y - 11), (k + 1.5, head_y - 7)], width=1.4, fill=_mix(hair, "#000000", 0.18))
    for side in (-1, 1):
        hb.dot(side * 12, head_y, 2.4, fill=skin_shade, outline="", squash=True)

    gx = {"left": -2.5, "right": 2.5}.get(eyes, 0.0)
    gy = {"down": 1.5, "up": -1.5}.get(eyes, 0.0)
    frame = P["lead_glasses"] if lead else P["follow_glasses"]
    brow = _mix(hair, "#000000", 0.2) if not lead else _mix(P["beard"], "#000000", 0.35)
    lift = -1.2 if eyes == "wide" else (0.8 if eyes == "down" else 0.0)
    for side in (-1, 1):
        hb.line([(side * 7.5, head_y - 6 + lift), (side * 2.5, head_y - 7 + lift)], width=1.5, fill=brow)
        hb.dot(side * 5 + gx * 0.3, head_y - 1 + gy * 0.3, 3.9, fill="#ffffff", outline=frame, width=2)
        if eyes == "closed":
            hb.line([(side * 5 - 2, head_y - 1), (side * 5 + 2, head_y - 1)], width=1.2, fill="#2b1a10")
        else:
            r = 1.6 if eyes != "wide" else 2.2
            hb.dot(side * 5 + gx, head_y - 1 + gy, r, fill="#2b1a10", outline="")
            hb.dot(side * 5 + gx - 0.6, head_y - 1.7 + gy, 0.5, fill="#ffffff", outline="")
        if not lead:
            hb.line([(side * 7.6, head_y - 3), (side * 9, head_y - 4.5)], width=1, fill="#2b1a10")
            hb.dot(side * 7.5, head_y + 4, 2, fill="#f4a3a3", outline="")
    hb.line([(-1.5, head_y - 1), (1.5, head_y - 1)], width=1.2, fill=frame)
    hb.line([(0, head_y + 1), (-1, head_y + 4), (0.8, head_y + 4.5)], width=1.2, fill=skin_shade)
    if lead:
        hb.poly([(-10, head_y + 3), (10, head_y + 3), (6, head_y + 14), (-6, head_y + 14)],
                fill=P["beard"], outline=_mix(P["beard"], "#000000", 0.3))
        for k in (-5, -1.5, 2, 5.5):
            hb.line([(k, head_y + 8), (k * 0.85, head_y + 12)], width=1, fill=_mix(P["beard"], "#000000", 0.25))
        hb.line([(-5, head_y + 4.5), (0, head_y + 3.5), (5, head_y + 4.5)], width=2.2, fill=P["beard"])
        hb.line([(-3.5, head_y + 6.5), (0, head_y + 8), (3.5, head_y + 6.5)], width=1.6, fill="#5a2e1a")
    else:
        hb.line([(-3.5, head_y + 5.5), (0, head_y + 7.6), (3.5, head_y + 5.5)], width=2, fill="#b5473d")
        for side in (-1, 1):
            hb.dot(side * 12, head_y + 5, 2.4, fill="", outline=P["earring"], width=2)
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


# ---------------------------------------------------------------------------
# Indicators: plain words anyone can read, built only from the event kind and
# tool category - never from tool arguments, prompts or results.
# ---------------------------------------------------------------------------
POSE_STATUS: dict[str, str] = {
    "crack_knuckles": "Starting a task", "attention": "Getting ready", "jump": "On it",
    "run_to_workspace": "Heading to work", "walk_to_workspace": "Heading to work",
    "dash_to_workspace": "Starting a step", "sprint_to_workspace": "Starting a step",
    "tip_to_workspace": "Starting a step",
    "work": "Working", "lean_work": "Still working", "terminal_work": "Running a command",
    "web_scan": "Searching the web", "read": "Reading", "file_organize": "Working with files",
    "dev_merge": "Working on code", "media_paint": "Making media", "design_draft": "Designing",
    "audio_tune": "Working on audio", "memory_vault": "Using memory",
    "close_workstation": "Step finished", "celebrate": "Step finished", "return_home": "Step done",
    "shock": "A step failed", "fall": "A step failed", "sneak": "A step failed",
    "recover": "Recovering", "inspect": "Checking what broke", "huff": "Shaking it off",
    "sit_back": "A helper failed", "retry": "Trying again", "repair": "Fixing it",
    "wake": "Needs your OK", "panic": "Needs your OK", "run_to_user": "Needs your OK",
    "wave": "Calling you", "wait": "Waiting for your OK", "point": "Needs your OK",
    "nod": "You answered", "hop": "Approved - going", "shrug": "You declined",
    "discard": "Dropped that step",
    "leap": "Task complete!", "double_jump": "Task complete!", "excited": "Helper finished",
    "open_portal": "Sending out a helper", "channel": "Helpers working", "orb_exits": "Helpers working",
    "orb_returns": "A helper is back", "absorb": "Taking the helper's work",
    "fly_up": "Helper finished", "fly_down": "Helper finished",
    "idle_bob": "Quiet", "idle": "Quiet", "sleep": "Resting", "sit": "Resting",
    "look_at_input": "Watching you type", "watch": "Watching you type",
    "look_at_user": "Looking at you", "notice": "Noticed something", "eyebrow_raise": "Noticed something", "think": "Thinking",
    "look_around": "Looking around", "tilt": "Wondering", "head_tilt": "Wondering",
    "stretch": "You're back - stretching", "stretch_lazy": "Taking it easy",
    "yawn": "Getting sleepy", "head_drop": "Resting", "check_watch": "Waiting",
}
_MOOD_WORD = {"work": "Working", "delegate": "Delegating", "fail": "Problem", "approve": "Needs you",
              "joy": "Done", "curious": "Curious", "rest": "Resting", "calm": "Ready"}


def status_text(pose: str, mood: str) -> tuple[str, str]:
    """(headline, detail) for the plaque: what Hermes is doing, in plain words."""
    headline = POSE_STATUS.get(pose) or _MOOD_WORD.get(mood, "Ready")
    st = STATE
    detail = []
    if mood == "work" and st.category not in ("general", "failure", "approval"):
        detail.append(st.category)
    if st.running:
        detail.append(f"{st.running} tool{'s' if st.running != 1 else ''} running")
    if st.helpers:
        detail.append(f"{st.helpers} helper{'s' if st.helpers != 1 else ''} out")
    if mood == "approve" and st.danger:
        headline, detail = "Needs your OK", ["dangerous command"] + detail
    if st.missteps and mood in ("fail", "work"):
        detail.append(f"{st.missteps} misstep{'s' if st.missteps != 1 else ''}")
    if st.thinking and mood not in ("approve", "fail"):
        headline = "Thinking"                           # just got a prompt: reasoning first
    return headline, " \u00b7 ".join(detail)


def _mood_icon(canvas, x, y, mood, color):
    """A small shape per meaning, so the plaque reads even without the words."""
    canvas.create_oval(x - 10, y - 10, x + 10, y + 10, fill=color, outline="#0f172a", width=1)
    ink = "#0f172a"
    if mood == "work":                                   # gear: ring + teeth
        for k in range(6):
            a = k / 6 * 2 * math.pi
            canvas.create_line(x + math.cos(a) * 4, y + math.sin(a) * 4, x + math.cos(a) * 7.5,
                               y + math.sin(a) * 7.5, fill=ink, width=2)
        canvas.create_oval(x - 4, y - 4, x + 4, y + 4, fill=color, outline=ink, width=2)
    elif mood == "approve":                              # raised hand: "!"
        canvas.create_line(x, y - 6, x, y + 2, fill=ink, width=3)
        canvas.create_oval(x - 1.6, y + 4, x + 1.6, y + 7, fill=ink, outline="")
    elif mood == "fail":                                 # cross
        canvas.create_line(x - 5, y - 5, x + 5, y + 5, fill=ink, width=3)
        canvas.create_line(x - 5, y + 5, x + 5, y - 5, fill=ink, width=3)
    elif mood == "joy":                                  # star
        pts = []
        for k in range(10):
            r = 7.5 if k % 2 == 0 else 3.2
            a = -math.pi / 2 + k * math.pi / 5
            pts += [x + math.cos(a) * r, y + math.sin(a) * r]
        canvas.create_polygon(*pts, fill=ink, outline="")
    elif mood == "delegate":                             # two figures
        for dx in (-4, 4):
            canvas.create_oval(x + dx - 2, y - 6, x + dx + 2, y - 2, fill=ink, outline="")
            canvas.create_line(x + dx, y - 2, x + dx, y + 6, fill=ink, width=2)
    elif mood == "rest":                                 # moon
        canvas.create_oval(x - 6, y - 6, x + 6, y + 6, fill=ink, outline="")
        canvas.create_oval(x - 3, y - 8, x + 8, y + 3, fill=color, outline="")
    elif mood == "curious":                              # question mark
        canvas.create_arc(x - 5, y - 8, x + 5, y + 2, start=-60, extent=240, style="arc",
                          outline=ink, width=2)
        canvas.create_line(x, y + 1, x, y + 3, fill=ink, width=2)
        canvas.create_oval(x - 1.5, y + 5, x + 1.5, y + 8, fill=ink, outline="")
    else:                                                # ready: dot
        canvas.create_oval(x - 3, y - 3, x + 3, y + 3, fill=ink, outline="")


def _badge(canvas, x, y, text, color):
    """A labelled counter chip; returns the x after it."""
    w = 20 + len(text) * 7.4          # room for bold text on every renderer
    canvas.create_rectangle(x, y - 9, x + w, y + 9, fill="#0f172a", outline=color, width=2)
    canvas.create_oval(x + 5, y - 3, x + 11, y + 3, fill=color, outline="")
    canvas.create_text(x + 14 + (w - 14) / 2, y, text=text, fill="#f8fafc", font=("Segoe UI", 8, "bold"))
    return x + w + 4


def _draw_indicators(canvas, pose, mood, glow):
    st = STATE
    # top-left: live counters, each named in words; wrap to a second row if needed
    chips = []
    if st.danger:
        chips.append(("dangerous", "#ef4444"))
    if st.running:
        chips.append((f"{st.running} tool{'s' if st.running != 1 else ''}",
                      CATEGORY_COLORS.get(st.category, MOOD_COLORS["work"])))
    if st.helpers:
        chips.append((f"{st.helpers} helper{'s' if st.helpers != 1 else ''}", MOOD_COLORS["delegate"]))
    if st.missteps:
        chips.append((f"{st.missteps} misstep{'s' if st.missteps != 1 else ''}", MOOD_COLORS["fail"]))
    x, y = 6, 12
    for text, color in chips:
        if x + 20 + len(text) * 7.4 > FRAME[0] - 6:
            x, y = 6, y + 22
        x = _badge(canvas, x, y, text, color)
    # bottom: the plaque
    headline, detail = status_text(pose, mood)
    top, bottom = FLOOR + 20, FRAME[1] - 4
    canvas.create_rectangle(24, top, FRAME[0] - 24, bottom, fill="#0f172a", outline=glow, width=2)
    _mood_icon(canvas, 42, (top + bottom) / 2, mood, glow)
    tx = (FRAME[0] + 32) / 2
    if detail:
        canvas.create_text(tx, top + 15, text=headline, fill="#f8fafc", font=("Segoe UI", 11, "bold"))
        canvas.create_text(tx, top + 32, text=detail, fill=glow, font=("Segoe UI", 8, "bold"))
    else:
        canvas.create_text(tx, (top + bottom) / 2, text=headline, fill="#f8fafc", font=("Segoe UI", 12, "bold"))


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
    _draw_indicators(canvas, pose, mood, glow)


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
