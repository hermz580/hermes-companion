"""Kai - a street skater whose session shows what Hermes is doing.

Designed movement-first: every Hermes state gets its own *kind* of motion,
not just a different pose, so you can read the state from the way he moves
even at a glance and even from the corner of your eye.

| Hermes is...                 | Kai...                                   | motion          |
|------------------------------|------------------------------------------|-----------------|
| starting a task              | drops in off the ramp, then pushes off   | descend, travel |
| launching a step             | ollies up onto the ledge                 | pop up          |
| running a tool               | holds a manual (balanced on two wheels)  | balance         |
|   ... a command (terminal)   | grinds the rail, sparks in the work colour| slide           |
|   ... on the web             | carves big S-turns                       | sweep           |
|   ... reading                | nose manual, eyes down                   | balance (front) |
|   ... files                  | pop shove-it: the board spins flat       | board rotates   |
|   ... code                   | boardslide across the rail               | slide sideways  |
| a long tool keeps going      | pumps the halfpipe, wall to wall         | oscillate       |
| a step finished              | kickflip, caught and landed              | board flips     |
| a step failed                | board shoots out, he slams, chases it    | fall            |
| needs your OK                | foot-brakes to a dead stop, kicks the    | sudden stop,    |
|                              | board up and leans on it, waiting        | then stillness  |
| you approved / declined      | runs and jumps back on / kick-turns away | restart / turn  |
| delegating to helpers        | whistles in his crew; they skate behind  | others appear   |
| finished the task            | big air off the kicker with a grab       | rise highest    |
| quiet / asleep               | sits on his board, then lies back        | rest low        |

The board is the second character: in a kickflip it flips, in a shove-it it
spins, when he slams it rolls away, and when he waits it stands on its tail
beside him. Live signals stay content-free: one chalk mark per tool running
(coloured by the kind of work), one crew skater per helper, a scrape per
failure (healed by a streak), and a "landed" count per finished tool.

Every engine pose maps to exactly one move (``MOVE_FOR_POSE``) so the same
action always looks the same. The jointed rig is shared with Duet and Sensei.
"""
from __future__ import annotations

import math
import time
from dataclasses import dataclass, field

from hermes_companion.animation.animator import pose_params
from hermes_companion.animation.duet import (
    _Body, _Joint, _badge, _d, _ease, _foot, _hand, _limb_pts, _mix, _mood_icon, _step,
)
from hermes_companion.animation.herald import EXCLAIM, MOOD_COLORS, WONDER, _bubble, mood_of
from hermes_companion.animation.master import POSE_STATUS

FRAME = (360, 300)
FLOOR = 228
MX = 170                     # where Kai rolls
HIP_Y = FLOOR - 46           # hips when standing on the ground
DECK = 12                    # deck top above the floor when the board is down
LEG = 22                     # thigh = shin

# Kia Kai's look: beanie with a gold band, gold-cuffed locs, a lightning-bolt
# hoodie and a teal "K" deck.
PALETTES: dict[str, dict[str, str]] = {
    "street": {"skin": "#835036", "hoodie": "#ec8a3b", "hoodie_hi": "#ffd19a", "pants": "#253d4b",
               "cap": "#253d4b", "shoes": "#f8f1dd", "accent": "#e8bf52", "deck": "#18b6a1",
               "deck_art": "#e8bf52", "wheels": "#f8f1dd", "sky": "#fde68a", "city": "#cbd5e1",
               "ground": "#74838a", "hair": "#18151a", "edge": "#10151b"},
    "midnight": {"skin": "#69412e", "hoodie": "#6043ad", "hoodie_hi": "#b7a9ed", "pants": "#191d37",
                 "cap": "#191d37", "shoes": "#e3ddf7", "accent": "#f9c74f", "deck": "#bc79f2",
                 "deck_art": "#f9c74f", "wheels": "#e3ddf7", "sky": "#312e81", "city": "#4f536d",
                 "ground": "#4f536d", "hair": "#18121b", "edge": "#0b0d18"},
    "sunrise": {"skin": "#a66b47", "hoodie": "#c0494f", "hoodie_hi": "#ffb4a5", "pants": "#384e61",
                "cap": "#384e61", "shoes": "#fff1d6", "accent": "#20a799", "deck": "#ffba4a",
                "deck_art": "#20a799", "wheels": "#fff1d6", "sky": "#e2a089", "city": "#c4a59a",
                "ground": "#978889", "hair": "#26141b", "edge": "#26141b"},
}
DEFAULT_PALETTE = "street"

# The kind of work tints the sparks, the chalk marks and the glow.
WORK_COLORS = {
    "terminal": "#2dd4bf", "development": "#22d3ee", "web": "#60a5fa", "browser": "#38bdf8",
    "file": "#f59e0b", "docs": "#f59e0b", "media": "#f472b6", "memory": "#a78bfa",
    "planning": "#84cc16", "desktop": "#94a3b8", "general": "#94a3b8",
}


def _color(category: str) -> str:
    return WORK_COLORS.get(category, WORK_COLORS["general"])


# ---------------------------------------------------------------------------
# Live state, from signed, content-free Hermes events.
# ---------------------------------------------------------------------------
@dataclass
class KaiState:
    tools: list = field(default_factory=list)   # categories of tools in flight = chalk marks
    category: str = "general"
    helpers: int = 0          # crew skating behind him
    scrapes: int = 0          # failures not yet healed (3 clean landings heal one)
    streak: int = 0
    landed: int = 0           # finished tools this task
    danger: bool = False
    think_until: float = 0.0
    party_until: float = 0.0
    clock: object = field(default=time.monotonic, repr=False)

    @property
    def running(self) -> int:
        return len(self.tools)

    def observe(self, ev) -> None:
        kind = getattr(ev.kind, "value", str(ev.kind))
        cat = ev.category or "general"
        now = self.clock()
        if kind == "agent.started":
            self.tools, self.helpers, self.scrapes, self.streak, self.landed = [], 0, 0, 0, 0
            self.party_until = 0.0
        elif kind == "user.prompt_submitted":
            self.think_until = now + 3.0
        elif kind == "tool.started":
            self.tools = (self.tools + [cat])[-4:]
            self.category = cat
        elif kind == "tool.progress":
            self.category = cat
        elif kind in ("tool.finished", "tool.failed"):
            if cat in self.tools:
                self.tools.remove(cat)
            elif self.tools:
                self.tools.pop(0)
            if kind == "tool.finished":
                self.landed += 1
                self.streak += 1
                if self.streak >= 3 and self.scrapes:
                    self.scrapes -= 1
                    self.streak = 0
            else:
                self.scrapes = min(self.scrapes + 1, 3)
                self.streak = 0
        elif kind == "approval.required":
            self.danger = cat == "dangerous"
        elif kind in ("approval.approved", "approval.rejected"):
            self.danger = False
        elif kind == "agent.subagent_spawned":
            self.helpers = min(self.helpers + 1, 3)
        elif kind in ("agent.subagent_finished", "agent.subagent_failed"):
            self.helpers = max(0, self.helpers - 1)
            if kind.endswith("failed"):
                self.scrapes = min(self.scrapes + 1, 3)
        elif kind in ("task.complete", "agent.idle"):
            self.tools, self.helpers, self.danger = [], 0, False
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
        return (tuple(self.tools), self.category, self.helpers, self.scrapes, min(self.landed, 9),
                self.danger, self.thinking, self.partying)


STATE = KaiState()


def observe(ev) -> None:
    STATE.observe(ev)


def state_key() -> tuple:
    return STATE.key()


# ---------------------------------------------------------------------------
# Moves. A move is a function of progress p returning a Scene: Kai's pose on
# the shared rig, the board, and stage effects.
#
# The board: x/y place it (y = wheels off the floor), rot tilts it (+ nose
# up), flip turns it about its long axis (1.0 = one kickflip), shove spins it
# flat (0.5 = a shove-it), and mode says who holds it:
#   ride    - under his feet (placed from his legs)
#   free    - on its own (rolling away, popping up, in the air)
#   hand    - in his right hand
#   upright - standing on its tail beside him
#   sit     - on the floor, he sits on it
# ---------------------------------------------------------------------------
STANCE = (24, -4, 24, -4)            # feet on the bolts, knees soft
CROUCH = (40, -40, 40, -40)          # loading a pop
TUCK = (62, -90, 62, -90)            # knees up in the air
BALANCE = (75, 20, 75, 20)           # arms out wide
LOW_ARMS = (18, 14, 18, 14)


RAMP_AT, RAMP_R, RAMP_H = 64.0, 72.0, 86.0     # transition starts at MX+64 and curves up to the coping


def ramp_surface(x: float) -> tuple[float, float]:
    """Height of the ramp under x (relative to MX) and its slope angle in degrees.

    A quarter pipe either side (halfpipe) or just on the right: concave,
    flat at the bottom and steep at the coping.
    """
    d = abs(x) - RAMP_AT
    if d <= 0:
        return 0.0, 0.0
    s = min(0.999, d / RAMP_R)
    a = math.asin(s)
    lift = RAMP_H * (1 - math.cos(a)) / (1 - math.cos(math.asin(0.999)))
    return lift, math.degrees(a) * (1 if x > 0 else -1)


COPING_X = RAMP_AT + RAMP_R * 0.999


def _on_ramp(x, legs=STANCE, **kw):
    """Riding the ramp surface at x: lifted to it and tilted with it."""
    lift, slope = ramp_surface(x)
    slope = max(-58.0, min(58.0, slope))          # leans with the wall, never lies flat on it
    return _ride(x, lift, rot=-slope, legs=legs, **kw)


def _board(x=0.0, y=0.0, rot=0.0, flip=0.0, shove=0.0, mode="ride", spin_wheels=False):
    return {"x": x, "y": y, "rot": rot, "flip": flip, "shove": shove, "mode": mode,
            "spin_wheels": spin_wheels}


def _scene(kai, board=None, fx=(), crew=None):
    return {"kai": kai, "board": board, "fx": set(fx), "crew": crew}


def _feet_drop(legs) -> float:
    """How far below the hips the soles are for these leg angles."""
    lows = []
    for hip_a, knee in (legs[0:2], legs[2:4]):
        _a, _k, f = _limb_pts(0, 0, hip_a, knee, LEG, LEG, 1)
        lows.append(f[1])
    return max(lows) + 3


def _ride(x=0.0, lift=0.0, rot=0.0, legs=STANCE, board_rot=0.0, flip=0.0, shove=0.0,
          spin_wheels=True, **kw):
    """Kai standing on the board: his hips sit so his soles touch the deck."""
    y = _feet_drop(legs) - (FLOOR - HIP_Y - DECK) + lift
    kw.setdefault("arms", LOW_ARMS)
    kai = _d(x, y=y, rot=rot, legs=legs, **kw)
    return kai, _board(x, lift, board_rot, flip, shove, "ride", spin_wheels)


def _sw(p, n=1.0):
    return math.sin(p * 2 * math.pi * n)


def _arc(p):
    """0 -> 1 -> 0 over the move: a jump's height curve."""
    return math.sin(min(max(p, 0.0), 0.999) * math.pi)


def _pop(p, height, start=0.2, end=0.8):
    """Crouch, pop, hang, land: (lift, crouch 0..1) at progress p."""
    if p < start:
        return 0.0, _ease(p / start)
    if p > end:
        return 0.0, 1 - _ease((p - end) / (1 - end))
    u = (p - start) / (end - start)
    return height * _arc(u), 0.0


def _legs_mix(a, b, t):
    return tuple(x + (y - x) * t for x, y in zip(a, b))


# --- start a task: drop in, push off -----------------------------------------
def _m_drop_in(p):
    """On the deck at the coping, tail hooked, he leans over and rides down the transition."""
    if p < 0.3:                                              # standing on the deck, leaning in
        u = _ease(p / 0.3)
        kai, board = _ride(COPING_X + 6, RAMP_H, rot=-20 * u, legs=STANCE, arms=(70, 30, 40, 60),
                           torso=12 * u)
        board["rot"] = 30 * (1 - u)                          # nose up over the edge, then down
        return _scene(kai, board, fx={"ramp"})
    u = _ease((p - 0.3) / 0.7)
    x = COPING_X * (1 - u)
    kai, board = _on_ramp(x, legs=_legs_mix(STANCE, CROUCH, 0.6 * _arc(u)), arms=(70, 30, 40, 60), torso=10)
    return _scene(kai, board, fx={"ramp", "speed"})


def _m_push_off(p):
    """Back foot pushes the street, front foot rides: travelling, steady beat."""
    push = max(0.0, _sw(p, 2))
    legs = (18, -4, 30 + 30 * push, 10 - 30 * push)
    kai, board = _ride(-50 + 50 * _ease(p), 0, legs=STANCE, arms=(30 - 20 * push, 30, 20 + 30 * push, 40),
                       torso=8)
    kai["legs"] = legs
    kai["ankles"] = (0, 30 * push)
    return _scene(kai, board, fx={"speed"})


# --- launch a step / prompt: ollies -------------------------------------------
def _m_ollie_up(p):
    """Crouch, snap the tail, float up onto the ledge."""
    lift, crouch = _pop(p, 58)
    forward = 70 * _ease(p)
    landed = 30 * _ease(max(0.0, (p - 0.55) / 0.45))
    legs = _legs_mix(_legs_mix(STANCE, CROUCH, crouch), TUCK, min(1.0, lift / 40))
    kai, board = _ride(forward, max(lift, landed), legs=legs, arms=(95, 20, 60, 40))
    board["rot"] = -22 if 0.15 < p < 0.3 else (8 if lift > 20 else 0)
    return _scene(kai, board, fx={"ledge"})


def _m_ollie_hop(p):
    """A quick pop in place: 'got it'."""
    lift, crouch = _pop(p, 30, 0.25, 0.75)
    legs = _legs_mix(_legs_mix(STANCE, CROUCH, crouch), TUCK, min(1.0, lift / 30))
    kai, board = _ride(0, lift, legs=legs, arms=(55, 30, 55, 30))
    board["rot"] = -18 if 0.2 < p < 0.32 else 0
    return _scene(kai, board)


def _m_ready_stance(p):
    kai, board = _ride(0, 0, legs=_legs_mix(STANCE, CROUCH, 0.5 + 0.1 * _sw(p)), arms=(40, 60, 40, 60),
                       torso=12, head=4)
    return _scene(kai, board)


# --- running a tool: balance, slide, sweep -----------------------------------
def _m_manual(p):
    """Back wheels only, nose up, arms out: the long balance of work in progress."""
    wobble = _sw(p, 2) * 3
    kai, board = _ride(-20 + 40 * p, 4, rot=-6 + wobble, legs=(26, -10, 18, 4), arms=BALANCE,
                       torso=-8 - wobble)
    board["rot"] = 14 + wobble
    return _scene(kai, board, fx={"marks"})


def _m_nose_manual(p):
    """Front wheels only, leaning over the nose, eyes down: reading."""
    wobble = _sw(p, 1.5) * 2
    kai, board = _ride(20 - 30 * p, 4, rot=6 + wobble, legs=(14, 6, 28, -14), arms=(55, 50, 55, 50),
                       torso=16, head=10)
    board["rot"] = -13 - wobble
    return _scene(kai, board, fx={"marks"})


def _m_grind(p):
    """50-50 along the rail, sparks the colour of the work."""
    kai, board = _ride(-80 + 160 * p, 34, legs=_legs_mix(STANCE, CROUCH, 0.4), arms=BALANCE,
                       torso=6 + 2 * _sw(p, 3))
    return _scene(kai, board, fx={"rail", "sparks", "marks"})


def _m_boardslide(p):
    """Board across the rail, sliding sideways: two things meeting, like a merge."""
    kai, board = _ride(-70 + 140 * p, 34, legs=(30, -16, 30, -16), arms=BALANCE, spin=0.55,
                       hip=3 * _sw(p, 2))
    board["shove"] = 0.22
    return _scene(kai, board, fx={"rail", "sparks", "marks"})


def _m_carve(p):
    """Big S-turns, leaning into each one: covering ground, like searching the web."""
    s = _sw(p)
    kai, board = _ride(80 * s, 0, rot=-16 * math.cos(p * 2 * math.pi), arms=(60 - 30 * s, 30, 60 + 30 * s, 30),
                       torso=6, head=-8 * s)
    board["shove"] = 0.04 * math.cos(p * 2 * math.pi)
    return _scene(kai, board, fx={"marks"})


def _m_shove_it(p):
    """Pop shove-it: the board spins flat under him - sorting things into place."""
    lift, crouch = _pop(p, 24, 0.2, 0.8)
    legs = _legs_mix(_legs_mix(STANCE, CROUCH, crouch), (40, -60, 40, -60), min(1.0, lift / 20))
    kai, board = _ride(0, lift, legs=legs, arms=(60, 30, 60, 30))
    board["shove"] = 0.5 * _ease((p - 0.2) / 0.6)
    board["mode"] = "free" if 0.25 < p < 0.75 else "ride"
    board["y"] = lift * 0.7
    return _scene(kai, board, fx={"marks"})


def _m_spin_180(p):
    """Frontside 180: he and the board turn together."""
    lift, _c = _pop(p, 20, 0.15, 0.85)
    kai, board = _ride(0, lift, arms=(90, 20, 30, 60))
    kai["spin"] = math.cos(p * math.pi)
    board["shove"] = 0.5 * _ease(p)
    return _scene(kai, board, fx={"marks"})


def _m_tic_tac(p):
    """Nose swings left, right, left: inching forward, drafting."""
    swing = _sw(p, 2)
    kai, board = _ride(-30 + 60 * p, 0, legs=(22, -2, 28, -10), arms=(50 + 20 * swing, 40, 50 - 20 * swing, 40),
                       hip=4 * swing)
    board["rot"] = 7 * max(0.0, swing)
    board["shove"] = 0.05 * swing
    return _scene(kai, board, fx={"marks"})


def _m_rock_to_fakie(p):
    """Up the ramp, rock the front truck over the coping, roll back down."""
    u = _arc(p)
    if u < 0.82:
        kai, board = _on_ramp(COPING_X * 0.88 * u / 0.82, legs=_legs_mix(STANCE, CROUCH, 0.5 * (1 - u)),
                              arms=(60, 30, 80, 20))
    else:                                                    # on the lip: front truck over the coping
        rock = 1 if _sw(p, 6) > 0 else 0.4
        kai, board = _ride(COPING_X - 6, RAMP_H - 6, rot=-24, legs=(30, -16, 18, 2), arms=(60, 30, 80, 20),
                           torso=8)
        board["rot"] = -16 * rock
    return _scene(kai, board, fx={"ramp", "marks"})


def _m_tail_stall(p):
    """Perched on the coping on his tail, still, looking up: remembering."""
    kai, board = _ride(COPING_X + 4, RAMP_H, rot=-8, legs=(20, -2, 26, -12), arms=(30, 60, 20, 30), head=-10,
                       torso=-4)
    board["rot"] = -40
    return _scene(kai, board, fx={"ramp", "marks"})


def _m_pump(p):
    """Wall to wall in the halfpipe, pumping each transition: still going."""
    s = _sw(p)
    bottom = 1 - s * s
    kai, board = _on_ramp(COPING_X * 0.92 * s, legs=_legs_mix(STANCE, CROUCH, bottom), arms=(50, 40, 50, 40))
    return _scene(kai, board, fx={"halfpipe", "marks"})


def _m_kickflip(p):
    """Crouch, pop, flick: the board flips a full turn, he catches it, lands."""
    lift, crouch = _pop(p, 48, 0.2, 0.82)
    legs = _legs_mix(_legs_mix(STANCE, CROUCH, crouch), TUCK, min(1.0, lift / 36))
    kai, board = _ride(0, lift, legs=legs, arms=(85, 20, 70, 30))
    flipping = 0.26 < p < 0.7
    board["flip"] = _ease((p - 0.26) / 0.44) if flipping else (1.0 if p >= 0.7 else 0.0)
    if flipping:
        board["mode"] = "free"
        board["y"] = lift - 6
        kai["ankles"] = (0, 40)          # the front foot flicks it
    return _scene(kai, board, fx={"marks"})


def _m_land_bolts(p):
    """Wheels down on the bolts, knees soak it up."""
    t = _ease(p)
    sink = _arc(min(1.0, p * 1.6))
    kai, board = _ride(0, 18 * (1 - t), legs=_legs_mix(STANCE, CROUCH, sink), arms=(60 - 40 * t, 30, 60 - 40 * t, 30))
    return _scene(kai, board, fx={"dust"} if p > 0.4 else ())


def _m_roll_back(p):
    """Rolls back to his spot, fakie, easy."""
    kai, board = _ride(50 - 50 * _ease(p), 0, arms=LOW_ARMS, head=4 * _sw(p))
    return _scene(kai, board, fx={"speed"} if p < 0.6 else ())


# --- task complete: big air ----------------------------------------------------
def _m_big_air(p):
    """Off the kicker, the highest he ever goes, grabbing the board: the task is done."""
    if p < 0.3:                                              # roll at the kicker
        u = p / 0.3
        kai, board = _ride(-110 + 50 * u, 22 * u * u, rot=-24 * u, legs=_legs_mix(STANCE, CROUCH, u))
        return _scene(kai, board, fx={"kicker", "speed"})
    u = (p - 0.3) / 0.7
    lift = 80 * _arc(u)
    kai, board = _ride(-60 + 130 * u, lift, rot=-20 + 20 * u, legs=TUCK if u < 0.8 else STANCE,
                       arms=(150, 10, 30, 140) if u < 0.8 else (90, 20, 90, 20))
    kai["wrists"] = (0, 40)
    return _scene(kai, board, fx={"kicker", "grab"} if u < 0.8 else {"kicker", "dust"})


def _m_tre_flip(p):
    """360 flip: the board flips and spins at once; arms up on the landing."""
    lift, crouch = _pop(p, 52, 0.2, 0.78)
    legs = _legs_mix(_legs_mix(STANCE, CROUCH, crouch), TUCK, min(1.0, lift / 36))
    up = max(0.0, (p - 0.78) / 0.22)
    kai, board = _ride(0, lift, legs=legs, arms=(85 + 70 * up, 20, 70 + 85 * up, 30))
    if 0.24 < p < 0.72:
        u = _ease((p - 0.24) / 0.48)
        board.update(flip=u, shove=0.5 * u, mode="free", y=lift - 6)
    return _scene(kai, board)


# --- a step failed: slip, slam, chase, get up ------------------------------------
def _m_slip_out(p):
    """The board shoots out forward; his feet go up, arms windmill."""
    t = _ease(p)
    kai = _d(0, y=12 * (1 - t), rot=-34 * t, arms=(140 + 40 * _sw(p, 3), 30, 150 - 40 * _sw(p, 3), 40),
             legs=(40, -20, 60, -40), torso=-14 * t, head=-12 * t)
    return _scene(kai, _board(30 + 110 * t, 0, 0, spin_wheels=True, mode="free"), fx={"stars"} if p > 0.6 else ())


def _m_slam(p):
    """Down on his back; the board rolls off without him."""
    t = _ease(min(1.0, p * 1.4))
    kai = _d(-10, y=-30 * t, rot=-88 * t, arms=(150, 20, 120, 40), legs=(50, -60, 30, -30), torso=-6, head=-14)
    return _scene(kai, _board(130 + 20 * _ease(p), 0, 0, mode="free", spin_wheels=p < 0.8),
                  fx={"stars", "dust"} if p < 0.7 else {"stars"})


def _m_chase_board(p):
    """On foot, jogging after the board."""
    t = _ease(p)
    kai = _d(-20 + 110 * t, y=2 * abs(_sw(p, 2)), arms=(40 + 40 * _sw(p, 2), 80, 40 - 40 * _sw(p, 2), 80),
             legs=_step(p * 1.5, 26), torso=12)
    return _scene(kai, _board(140 - 10 * t, 0, 0, mode="free", spin_wheels=p < 0.7), fx={"speed"})


def _m_pop_up(p):
    """Back on his feet, dusting off his knees."""
    t = _ease(p)
    dust = max(0.0, _sw(p, 3)) * (1 if p > 0.5 else 0)
    kai = _d(0, y=-22 * (1 - t), rot=-30 * (1 - t), arms=(40 + 30 * dust, 110, 30, 60),
             legs=_legs_mix((60, -80, 60, -80), (8, 0, 8, 0), t), torso=24 * dust)
    return _scene(kai, _board(54, 0, 0, mode="free"), fx={"dust"} if dust else ())


def _m_check_board(p):
    """Board up in his hands, spinning a wheel to see what went wrong."""
    kai = _d(0, arms=(70, 60, 50, 80), legs=(8, 0, 8, 0), head=10, torso=6)
    return _scene(kai, _board(0, 0, 80, mode="hand", spin_wheels=True), fx={"wheel_check"})


def _m_fix_truck(p):
    """Kneels and tightens a truck with his skate tool: fixing it."""
    turn = _sw(p, 3)
    kai = _d(-16, y=-22, arms=(70, 80, 90 + 20 * turn, 60), legs=(70, -100, 20, -80), torso=26, head=14)
    return _scene(kai, _board(26, 0, 0, flip=0.5, mode="free"), fx={"tool"})


def _m_line_up(p):
    """Sets the board down, steps on, eyes on the line: trying again."""
    t = _ease(p)
    kai, board = _ride(-30 * (1 - t), 0, arms=(30, 40, 30, 40), head=-6, torso=8 * (1 - t))
    if p < 0.4:
        kai = _d(-30, arms=(30, 60, 60, 30), legs=(10, 0, 10, 0), torso=20)
        board = _board(10, 10 * (1 - p / 0.4), 0, mode="free")
    return _scene(kai, board)


def _m_shake_out(p):
    """Shakes out his arms and a leg: catching his breath."""
    s = _sw(p, 4)
    kai = _d(0, arms=(30 + 20 * s, 20, 30 - 20 * s, 20), legs=(6, 0, 20 + 14 * s, -20), shoulders=(3 * s, -3 * s),
             head=6 * s)
    return _scene(kai, _board(48, 0, 0, mode="free"))


# --- needs your OK: hard stop, board up, wait ------------------------------------
def _m_foot_brake(p):
    """Back foot drags the ground: a sudden, hard stop."""
    t = 1 - (1 - p) ** 3                                     # fast, then nothing
    kai, board = _ride(70 - 70 * t, 0, rot=-10 * (1 - p), arms=(60, 30, 80, 20), torso=-8)
    kai["legs"] = (16, -2, 52, -10)
    kai["ankles"] = (0, -40)
    return _scene(kai, board, fx={"brake"} if p < 0.85 else ())


def _m_kick_up(p):
    """Steps on the tail; the board pops up into his hand."""
    t = _ease(p)
    if p < 0.5:
        u = p / 0.5
        kai = _d(0, arms=LOW_ARMS, legs=(8, 0, 20, -10), ankles=(0, -20))
        return _scene(kai, _board(20, 30 * u * u, 70 * u, mode="free"))
    kai = _d(0, arms=(30, 70, 50 + 30 * t, 80), legs=(8, 0, 8, 0))
    return _scene(kai, _board(0, 0, 80, mode="hand"))


def _m_walk_over(p):
    """Walks toward you, board under his arm."""
    kai = _d(40 - 40 * _ease(p), y=2 * abs(_sw(p, 2)), arms=(30 + 20 * _sw(p, 2), 30, 40, 100),
             legs=_step(p, 16))
    return _scene(kai, _board(0, 0, 5, mode="hand"))


def _m_hail_you(p):
    """Board up high in one hand, waving you over with the other."""
    wave = _sw(p, 3)
    kai = _d(0, arms=(150 + 15 * wave, 20 + 25 * wave, 165, 10), legs=(10, 0, 10, 0), head=-4)
    return _scene(kai, _board(0, 0, 10, mode="hand"))


def _m_board_lean(p):
    """Board stood on its tail, his elbow on the nose, foot tapping: waiting for you."""
    tap = max(0.0, _sw(p, 3))
    kai = _d(-8, rot=4, arms=(20, 20, 70, 110), legs=(6, 0, 18, -8), ankles=(0, -18 * tap), head=3)
    return _scene(kai, _board(34, 0, 88, mode="upright"))


def _m_point_you(p):
    kai = _d(0, arms=(90, 0, 30, 100), legs=(10, 0, 10, 0), head=4 * _sw(p))
    return _scene(kai, _board(34, 0, 88, mode="upright"))


# --- you answered -----------------------------------------------------------------
def _m_nod_ok(p):
    kai = _d(0, arms=LOW_ARMS, legs=(10, 0, 10, 0), head=10 * max(0.0, _sw(p, 2)))
    return _scene(kai, _board(34, 0, 88, mode="upright"))


def _m_run_jump_on(p):
    """Two running steps, throws the board down, jumps on and rolls away: approved."""
    if p < 0.45:
        u = p / 0.45
        kai = _d(-60 + 40 * u, arms=(40 + 40 * _sw(u, 2), 70, 40, 100), legs=_step(u, 24), torso=10)
        return _scene(kai, _board(0, 0, 5, mode="hand"))
    u = (p - 0.45) / 0.55
    lift = 26 * _arc(min(1.0, u * 2))
    kai, board = _ride(-20 + 70 * u, lift, legs=_legs_mix(STANCE, TUCK, lift / 26), arms=(80, 20, 80, 20))
    board["y"] = 0.0 if lift < 4 else lift - 8
    board["mode"] = "ride" if lift < 4 else "free"
    return _scene(kai, board, fx={"speed"})


def _m_shrug(p):
    s = _arc(p)
    kai = _d(0, arms=(50, 100 * s, 50, 100 * s), legs=(10, 0, 10, 0), shoulders=(6 * s, 6 * s), head=6 * s)
    return _scene(kai, _board(34, 0, 88, mode="upright"))


def _m_kick_turn_away(p):
    """Nose up, swing the board 180, roll the other way: declined."""
    t = _ease(min(1.0, p * 1.6))
    kai, board = _ride(-70 * max(0.0, (p - 0.6) / 0.4), 0, arms=(70, 30, 40, 60), legs=(30, -14, 16, 4))
    kai["spin"] = math.cos(t * math.pi)
    board["rot"] = 24 * _arc(min(1.0, p * 1.6))
    board["shove"] = 0.5 * t
    return _scene(kai, board)


# --- helpers: the crew ----------------------------------------------------------------
def _m_call_crew(p):
    """Two fingers in his mouth, a whistle: his crew rolls in."""
    kai = _d(0, arms=(30, 20, 160, 150), legs=(10, 0, 10, 0), head=-6)
    return _scene(kai, _board(-34, 0, 88, mode="upright"), fx={"whistle"}, crew=("in", _ease(p)))


def _m_crew_session(p):
    """The crew skates behind him; he holds a manual to their beat."""
    sc = _m_manual(p)
    sc["crew"] = ("skate", 1.0)
    return sc


def _m_crew_out(p):
    """The crew rolls off to do their part."""
    kai, board = _ride(0, 0, arms=(30, 20, 150, 30), head=-6)
    return _scene(kai, board, crew=("out", _ease(p)))


def _m_crew_back(p):
    kai, board = _ride(0, 0, arms=(60, 30, 40, 40))
    return _scene(kai, board, crew=("back", _ease(p)))


def _m_fist_bump(p):
    """A crew mate rolls up; fist bump: taking their work."""
    reach = _arc(p)
    kai = _d(0, arms=(20, 20, 90 - 10 * reach, 10), legs=(10, 0, 10, 0), head=-4)
    return _scene(kai, _board(-34, 0, 88, mode="upright"), fx={"bump"} if reach > 0.8 else (),
                  crew=("bump", reach))


def _m_boneless(p):
    """Front foot plants, hand grabs, jump up with the board: a helper's done."""
    lift = 40 * _arc(p)
    kai = _d(0, y=lift, arms=(30, 40, 60, 120), legs=(30, -40, 60, -90) if lift > 6 else (10, 0, 40, -30))
    return _scene(kai, _board(10, max(0.0, lift - 22), 0, mode="free"))


def _m_land_soft(p):
    t = _ease(p)
    kai, board = _ride(0, 36 * (1 - t), legs=_legs_mix(TUCK, STANCE, t), arms=(70, 20, 70, 20))
    return _scene(kai, board, fx={"dust"} if p > 0.7 else ())


def _m_board_slap(p):
    """Bangs his tail on the street: a skater's applause."""
    slap = max(0.0, _sw(p, 3))
    kai = _d(-14, arms=(60, 60, 60, 60), legs=(8, 0, 22, -16), head=4 * slap)
    return _scene(kai, _board(20, 0, -24 * slap, mode="free"), fx={"clack"} if slap > 0.85 else ())


def _m_slump(p):
    """Sat on his board, elbows on knees, head down: a helper failed."""
    kai = _d(0, y=-26, arms=(40, 120, 40, 120), legs=(70, -110, 70, -110), torso=24, head=18)
    return _scene(kai, _board(0, 0, 0, mode="sit"))


# --- quiet / rest -----------------------------------------------------------------------
def _m_sit_on_board(p):
    """Sat on his board, rolling a little, nodding to his headphones."""
    roll = _sw(p) * 6
    kai = _d(roll, y=-26, arms=(30, 80, 30, 80), legs=(60, -100, 66, -96), torso=6, head=6 * _sw(p, 2))
    return _scene(kai, _board(roll, 0, 0, mode="sit", spin_wheels=abs(roll) > 2), fx={"headphones", "notes"})


def _m_lie_back(p):
    """Lying back, hood up, knees up, board under his feet: asleep."""
    breathe = _sw(p) * 1.5
    kai = _d(-10, y=-34, rot=-90, arms=(150, 30, 150, 30), legs=(60, -90, 60, -90), torso=breathe, head=-4)
    return _scene(kai, _board(28, 0, 0, mode="free"), fx={"zzz", "hood"})


def _m_doze(p):
    kai = _d(0, y=-26, arms=(30, 80, 30, 80), legs=(60, -100, 66, -96), torso=10, head=24 * _ease(p))
    return _scene(kai, _board(0, 0, 0, mode="sit"), fx={"headphones"})


def _m_yawn(p):
    s = _arc(p)
    kai = _d(0, y=-26, arms=(30 + 120 * s, 60, 30 + 120 * s, 60), legs=(60, -100, 66, -96), head=-10 * s)
    return _scene(kai, _board(0, 0, 0, mode="sit"))


def _m_lazy_stretch(p):
    s = _arc(p)
    kai = _d(0, y=6 * s, arms=(30 + 140 * s, 20, 30 + 140 * s, 20), legs=(8, 0, 8, 0), torso=-6 * s)
    return _scene(kai, _board(40, 0, 0, mode="free"))


def _m_fingerboard(p):
    """Sat on his board, doing tiny tricks on a fingerboard: playing."""
    kai = _d(0, y=-26, arms=(50, 110, 60, 100), legs=(60, -100, 66, -96), torso=16, head=12)
    return _scene(kai, _board(0, 0, 0, mode="sit"), fx={"fingerboard"})


# --- noticing you / curious ---------------------------------------------------------------
def _m_watch_you(p):
    """One foot on the tail, nose up, watching you type."""
    kai = _d(0, arms=LOW_ARMS, legs=(8, 0, 22, -10), head=-4)
    return _scene(kai, _board(26, 0, 28, mode="free"))


def _m_look_at_you(p):
    kai = _d(0, arms=(20, 14, 50, 90), legs=(8, 0, 8, 0), head=3 * _sw(p))
    return _scene(kai, _board(-34, 0, 88, mode="upright"))


def _m_head_snap(p):
    t = _ease(min(1.0, p * 3))
    kai, board = _ride(0, 0, arms=(40, 60, 40, 60), head=-12 * t, torso=-4 * t)
    return _scene(kai, board)


def _m_look_around(p):
    kai, board = _ride(0, 0, arms=LOW_ARMS, head=14 * _sw(p))
    kai["spin"] = 0.7 + 0.3 * math.cos(p * 2 * math.pi)
    return _scene(kai, board)


def _m_peek(p):
    """Peeks out from behind his upright board."""
    out = _arc(p)
    kai = _d(-30 + 26 * out, arms=(20, 90, 80, 40), legs=(8, 0, 8, 0), torso=-10 * out, head=-14 * out)
    return _scene(kai, _board(0, 0, 88, mode="upright"))


def _m_head_tilt(p):
    kai = _d(0, arms=(20, 14, 20, 14), legs=(8, 0, 8, 0), head=16 * _arc(p))
    return _scene(kai, _board(34, 0, 88, mode="upright"))


def _m_squint(p):
    kai = _d(0, arms=(20, 14, 150, 160), legs=(8, 0, 8, 0), head=-6, torso=6)
    return _scene(kai, _board(34, 0, 88, mode="upright"))


def _m_think(p):
    kai = _d(0, arms=(60, 120, 40, 150), legs=(8, 0, 8, 0), head=8 + 3 * _sw(p))
    return _scene(kai, _board(34, 0, 88, mode="upright"))


def _m_wobble(p):
    """Arms windmilling on the board, almost losing it."""
    s = _sw(p, 3)
    kai, board = _ride(0, 0, rot=10 * s, arms=(120 + 40 * s, 20, 120 - 40 * s, 20), torso=-8 * s)
    board["rot"] = 6 * s
    return _scene(kai, board)


def _m_scratch(p):
    kai = _d(0, arms=(20, 14, 160, 140 + 10 * _sw(p, 4)), legs=(8, 0, 8, 0), head=6)
    return _scene(kai, _board(34, 0, 88, mode="upright"))


def _m_head_shake(p):
    kai = _d(0, arms=LOW_ARMS, legs=(8, 0, 8, 0), head=12 * _sw(p, 3))
    return _scene(kai, _board(34, 0, 88, mode="upright"))


def _m_bounce_knees(p):
    b = abs(_sw(p, 2))
    kai, board = _ride(0, 0, legs=_legs_mix(STANCE, CROUCH, b * 0.7), arms=(40, 60, 40, 60), head=4 * b)
    return _scene(kai, board)


def _m_check_phone(p):
    kai = _d(0, arms=(20, 14, 50, 120), legs=(8, 0, 8, 0), head=14)
    return _scene(kai, _board(34, 0, 88, mode="upright"), fx={"phone"})


def _m_look_down(p):
    kai, board = _ride(0, 0, arms=LOW_ARMS, head=16, torso=8)
    return _scene(kai, board)


def _m_look_up(p):
    kai, board = _ride(0, 0, arms=(20, 14, 20, 14), head=-16, torso=-6)
    return _scene(kai, board)


def _m_arms_crossed(p):
    kai = _d(-6, arms=(60, 130, 60, 130), legs=(8, 0, 18, -8), head=-4 + 2 * _sw(p))
    return _scene(kai, _board(34, 0, 88, mode="upright"))


def _m_dance_board(p):
    """Shuffles his feet along the deck to the beat."""
    s = _sw(p, 2)
    kai, board = _ride(0, 0, legs=(24 + 12 * s, -4, 24 - 12 * s, -4), arms=(40 + 30 * s, 60, 40 - 30 * s, 60),
                       hip=5 * s, shoulders=(3 * s, -3 * s), head=6 * s)
    return _scene(kai, board, fx={"notes"})


def _m_double_ollie(p):
    """Two pops in a row, the second higher."""
    first = p < 0.45
    lift, crouch = _pop(p / 0.45 if first else (p - 0.45) / 0.55, 26 if first else 44, 0.2, 0.8)
    legs = _legs_mix(_legs_mix(STANCE, CROUCH, crouch), TUCK, min(1.0, lift / 30))
    kai, board = _ride(0, lift, legs=legs, arms=(120, 20, 120, 20))
    return _scene(kai, board)


# --- out on the desktop: travel, drops and riding window edges -------------------------------
# These draw only Kai and his board ("bare"): the real desktop is the street,
# window title bars are his rails, and the taskbar is the ground he lands on.
def _m_skate_roll(p):
    """Rolling across the desktop, a push every so often."""
    push = max(0.0, _sw(p, 1.5)) ** 2
    kai, board = _ride(0, 0, arms=(30 + 20 * push, 30, 20 + 30 * push, 40), torso=8 + 4 * push)
    kai["legs"] = (20, -4, 26 + 34 * push, 8 - 34 * push)
    return _scene(kai, board, fx={"bare", "speed"})


def _m_ollie_gap(p):
    """An ollie over a gap while travelling; the window carries the height."""
    _lift, crouch = _pop(p, 0, 0.15, 0.85)
    air = 0.15 < p < 0.85
    legs = TUCK if air else _legs_mix(STANCE, CROUCH, crouch)
    kai, board = _ride(0, 0, legs=legs, arms=(95, 20, 70, 30) if air else (50, 40, 50, 40))
    board["rot"] = -20 if 0.1 < p < 0.2 else (6 if air else 0)
    return _scene(kai, board, fx={"bare"})


def _m_kicker_air(p):
    """Sets down a little kicker, rolls up it and launches across the screen."""
    if p < 0.18:                                             # on the kicker
        u = p / 0.18
        kai, board = _ride(-30 + 30 * u, 22 * u, rot=-24 * u, legs=_legs_mix(STANCE, CROUCH, u))
        return _scene(kai, board, fx={"bare", "kicker_here", "speed"})
    if p > 0.86:                                             # landing
        u = (p - 0.86) / 0.14
        kai, board = _ride(0, 0, legs=_legs_mix(CROUCH, STANCE, u), arms=(60, 30, 60, 30))
        return _scene(kai, board, fx={"bare", "dust"})
    kai, board = _ride(0, 0, rot=-10 * _sw(p), legs=TUCK, arms=(150, 10, 30, 140))
    kai["wrists"] = (0, 40)
    return _scene(kai, board, fx={"bare", "grab"})


def _m_bomb_drop(p):
    """Off the edge with the board under his feet, all the way down to the taskbar."""
    if p < 0.86:
        wobble = _sw(p, 3) * 4
        kai, board = _ride(0, 0, rot=wobble, legs=_legs_mix(STANCE, TUCK, 0.5), arms=(150, 20, 140, 30))
        board["rot"] = -6
        return _scene(kai, board, fx={"bare", "perch", "falling"})
    u = (p - 0.86) / 0.14
    kai, board = _ride(0, 0, legs=_legs_mix(CROUCH, STANCE, u), arms=(60, 30, 60, 30))
    return _scene(kai, board, fx={"bare", "perch", "dust"})


def _m_edge_grind(p):
    """Grinding the top edge of the window like a rail, sparks off the trucks."""
    kai, board = _ride(0, 0, legs=_legs_mix(STANCE, CROUCH, 0.45), arms=BALANCE, torso=6 + 2 * _sw(p, 3))
    return _scene(kai, board, fx={"bare", "perch", "sparks"})


def _m_edge_sit(p):
    """Sat on the edge of the window, legs hanging over, board beside him."""
    swing = _sw(p, 1.5)
    kai = _d(0, y=-DECK - 30, arms=(28, 10, 28, 10), legs=(58, -70 + 14 * swing, 58, -70 - 14 * swing),
             torso=-4, head=4 * _sw(p))                      # knees over the edge, shins swinging
    return _scene(kai, _board(40, 0, 0, mode="free"), fx={"bare", "perch", "headphones"})


# --- his own tricks: decoration around a signature -------------------------------------------
def _t_heelflip(p):
    sc = _m_kickflip(p)
    if sc["board"]["mode"] == "free":
        sc["board"]["flip"] = -sc["board"]["flip"]       # flips the other way
        sc["kai"]["ankles"] = (40, 0)                    # the heel flicks it
    return sc


def _t_varial(p):
    sc = _m_shove_it(p)
    sc["board"]["flip"] = sc["board"]["shove"] * 2
    return sc


def _t_walk_the_dog(p):
    """Front foot turns the nose back and forth, calm as anything."""
    s = _sw(p, 2)
    kai, board = _ride(0, 0, legs=(20, -2, 28, -8), arms=(30, 40, 30, 40), head=4 * s)
    board["shove"] = 0.08 * s
    return _scene(kai, board)


def _t_slow_carve(p):
    sc = _m_carve(p)
    sc["kai"]["x"] *= 0.4
    sc["board"]["x"] *= 0.4
    return sc


def _t_nollie(p):
    sc = _m_ollie_hop(p)
    sc["board"]["rot"] = -sc["board"]["rot"]            # pops off the nose
    return sc


def _t_fakie_manual(p):
    sc = _m_manual(p)
    sc["kai"]["spin"] = -1.0
    return sc


def _t_wobble_save(p):
    sc = _m_wobble(p)
    sc["kai"]["arms"] = (150, 10, 40, 80)
    return sc


MOVES = {
    "drop_in": _m_drop_in, "push_off": _m_push_off, "ollie_up": _m_ollie_up, "ollie_hop": _m_ollie_hop,
    "ready_stance": _m_ready_stance,
    "manual": _m_manual, "nose_manual": _m_nose_manual, "grind": _m_grind, "boardslide": _m_boardslide,
    "carve": _m_carve, "shove_it": _m_shove_it, "spin_180": _m_spin_180, "tic_tac": _m_tic_tac,
    "rock_to_fakie": _m_rock_to_fakie, "tail_stall": _m_tail_stall, "pump": _m_pump,
    "kickflip": _m_kickflip, "land_bolts": _m_land_bolts, "roll_back": _m_roll_back,
    "big_air": _m_big_air, "tre_flip": _m_tre_flip,
    "slip_out": _m_slip_out, "slam": _m_slam, "chase_board": _m_chase_board, "pop_up": _m_pop_up,
    "check_board": _m_check_board, "fix_truck": _m_fix_truck, "line_up": _m_line_up,
    "shake_out": _m_shake_out,
    "foot_brake": _m_foot_brake, "kick_up": _m_kick_up, "walk_over": _m_walk_over, "hail_you": _m_hail_you,
    "board_lean": _m_board_lean, "point_you": _m_point_you,
    "nod_ok": _m_nod_ok, "run_jump_on": _m_run_jump_on, "shrug": _m_shrug, "kick_turn_away": _m_kick_turn_away,
    "call_crew": _m_call_crew, "crew_session": _m_crew_session, "crew_out": _m_crew_out,
    "crew_back": _m_crew_back, "fist_bump": _m_fist_bump, "boneless": _m_boneless, "land_soft": _m_land_soft,
    "board_slap": _m_board_slap, "slump": _m_slump,
    "sit_on_board": _m_sit_on_board, "lie_back": _m_lie_back, "doze": _m_doze, "yawn": _m_yawn,
    "lazy_stretch": _m_lazy_stretch, "fingerboard": _m_fingerboard,
    "watch_you": _m_watch_you, "look_at_you": _m_look_at_you, "head_snap": _m_head_snap,
    "look_around": _m_look_around, "peek": _m_peek, "head_tilt": _m_head_tilt, "squint": _m_squint,
    "think": _m_think, "wobble": _m_wobble, "scratch": _m_scratch, "head_shake": _m_head_shake,
    "bounce_knees": _m_bounce_knees, "check_phone": _m_check_phone, "look_down": _m_look_down,
    "look_up": _m_look_up, "arms_crossed": _m_arms_crossed, "dance_board": _m_dance_board,
    "double_ollie": _m_double_ollie,
    "skate_roll": _m_skate_roll, "ollie_gap": _m_ollie_gap, "kicker_air": _m_kicker_air,
    "bomb_drop": _m_bomb_drop, "edge_grind": _m_edge_grind, "edge_sit": _m_edge_sit,
}
DESKTOP_MOVES = ("skate_roll", "ollie_gap", "kicker_air", "bomb_drop", "edge_grind", "edge_sit")

# His own tricks: decoration around a signature, sorted by mood.
TRICKS: dict[str, tuple] = {
    "heelflip": ("bright", _t_heelflip), "varial": ("bright", _t_varial),
    "walk_the_dog": ("calm", _t_walk_the_dog), "slow_carve": ("calm", _t_slow_carve),
    "nollie": ("focused", _t_nollie), "fakie_manual": ("focused", _t_fakie_manual),
    "wobble_save": ("uneasy", _t_wobble_save),
}
MOVES.update({name: fn for name, (_m, fn) in TRICKS.items()})

# Signature: every engine pose -> one move, so meaning never varies.
MOVE_FOR_POSE: dict[str, str] = {
    "crack_knuckles": "drop_in", "run_to_workspace": "push_off", "walk_to_workspace": "push_off",
    "attention": "ready_stance", "jump": "ollie_hop",
    "dash_to_workspace": "ollie_up", "sprint_to_workspace": "ollie_up", "tip_to_workspace": "ollie_up",
    "work": "manual", "lean_work": "pump", "terminal_work": "grind", "web_scan": "carve",
    "read": "nose_manual", "file_organize": "shove_it", "dev_merge": "boardslide",
    "media_paint": "spin_180", "design_draft": "tic_tac", "audio_tune": "rock_to_fakie",
    "memory_vault": "tail_stall",
    "close_workstation": "land_bolts", "celebrate": "kickflip", "return_home": "roll_back",
    "shock": "slip_out", "fall": "slam", "sneak": "chase_board", "recover": "pop_up",
    "inspect": "check_board", "huff": "shake_out", "retry": "line_up", "repair": "fix_truck",
    "sit_back": "slump",
    "wake": "foot_brake", "panic": "kick_up", "run_to_user": "walk_over", "wave": "hail_you",
    "wait": "board_lean", "point": "point_you",
    "nod": "nod_ok", "hop": "run_jump_on", "shrug": "shrug", "discard": "kick_turn_away",
    "leap": "big_air", "double_jump": "tre_flip", "excited": "board_slap",
    "open_portal": "call_crew", "channel": "crew_session", "orb_exits": "crew_out",
    "orb_returns": "crew_back", "absorb": "fist_bump", "fly_up": "boneless", "fly_down": "land_soft",
    "idle_bob": "sit_on_board", "idle": "sit_on_board", "sleep": "lie_back", "sit": "sit_on_board",
    "head_drop": "doze", "yawn": "yawn", "stretch": "lazy_stretch", "stretch_lazy": "lazy_stretch",
    "play_with_object": "fingerboard",
    "look_at_input": "watch_you", "watch": "watch_you", "look_at_user": "look_at_you",
    "notice": "head_snap", "eyebrow_raise": "head_snap", "look_around": "look_around",
    "peeking": "peek", "head_tilt": "head_tilt", "tilt": "head_tilt", "squint": "squint",
    "think": "think", "arm_flap": "wobble", "scratch_head": "scratch", "shake_head": "head_shake",
    "bounce": "bounce_knees", "full_bounce": "bounce_knees", "check_watch": "check_phone",
    "look_down": "look_down", "look_up": "look_up", "smug": "arms_crossed",
    "dance": "dance_board", "spin": "spin_180", "spin_joy": "spin_180",
    "leap_double_joy": "double_ollie",
}
MOVE_FOR_POSE.update({name: name for name in TRICKS})
MOVE_FOR_POSE.update({name: name for name in DESKTOP_MOVES})

# What kind of motion each Hermes state's signature move is. No two states
# share one, so the state reads from the movement itself (tested).
SIGNATURES = {
    "starting": ("drop_in", "descend"),
    "launching a step": ("ollie_up", "pop"),
    "working": ("manual", "balance"),
    "long work": ("pump", "oscillate"),
    "step finished": ("kickflip", "board flips"),
    "step failed": ("slam", "fall"),
    "needs you": ("board_lean", "stillness"),
    "task complete": ("big_air", "soar"),
    "helpers": ("call_crew", "others arrive"),
    "quiet": ("sit_on_board", "rest low"),
}

_MOVE_MOOD = {
    "big_air": "joy", "tre_flip": "joy", "kickflip": "joy", "land_bolts": "joy", "board_slap": "joy",
    "double_ollie": "joy",
    "foot_brake": "approve", "kick_up": "approve", "walk_over": "approve", "hail_you": "approve",
    "board_lean": "approve", "point_you": "approve",
    "slip_out": "fail", "slam": "fail", "chase_board": "fail", "pop_up": "fail", "check_board": "fail",
    "shake_out": "fail", "slump": "fail", "wobble": "fail", "scratch": "fail", "head_shake": "fail",
    "call_crew": "delegate", "crew_session": "delegate", "crew_out": "delegate", "crew_back": "delegate",
    "fist_bump": "delegate",
    "sit_on_board": "rest", "lie_back": "rest", "doze": "rest", "yawn": "rest", "lazy_stretch": "rest",
    "manual": "work", "nose_manual": "work", "grind": "work", "boardslide": "work", "carve": "work",
    "shove_it": "work", "spin_180": "work", "tic_tac": "work", "rock_to_fakie": "work",
    "tail_stall": "work", "pump": "work", "fix_truck": "work", "line_up": "work",
}
_MOVE_MOOD.update({"bomb_drop": "calm", "edge_grind": "calm", "edge_sit": "rest", "kicker_air": "calm",
                   "skate_roll": "calm", "ollie_gap": "calm"})
_MOVE_MOOD.update({name: {"bright": "joy", "focused": "work", "uneasy": "fail"}.get(m, "calm")
                   for name, (m, _f) in TRICKS.items()})


TOWARD_USER = ("run_to_user", "to_user", "panic")
ROAM = 1.6                    # travel further than a plain walk: real crossings of the screen


def travel(step: dict, rng) -> dict:
    """Swap a moving step for Kai's way of getting there: rolling, ollies, a kicker launch.

    Distance, direction and timing keep what the Hermes event asked for (only
    further), so the chain still goes where it was sent.
    """
    move = step.get("move")
    if not move or not move.get("dx"):
        return step
    dx, kind, pose = move["dx"], move.get("type", ""), step.get("pose", "")
    if any(k in pose for k in TOWARD_USER):
        name = "skate_roll"
    elif kind in ("hop", "leap", "pounce", "fly", "bounce", "pop"):
        name = "ollie_gap"
    elif abs(dx) >= 300 and rng.random() < 0.5:
        name = "kicker_air"
    else:
        name = "skate_roll"
    return dict(step, pose=name, move=dict(move, dx=int(dx * ROAM)))


def move_for(pose: str) -> str | None:
    return MOVE_FOR_POSE.get(pose)


def trick_flourishes() -> dict[str, tuple[str, ...]]:
    out: dict[str, list[str]] = {}
    for name, (mood, _fn) in TRICKS.items():
        out.setdefault(mood, []).append(name)
    return {k: tuple(v) for k, v in out.items()}


CATEGORY_HINTS = {
    "terminal": ("nollie", "fakie_manual"), "development": ("varial", "nollie"),
    "web": ("slow_carve", "walk_the_dog"), "file": ("varial",), "docs": ("walk_the_dog",),
    "memory": ("walk_the_dog",), "media": ("heelflip", "varial"),
}


def flourish_hints() -> dict[str, tuple[str, ...]]:
    return dict(CATEGORY_HINTS)


CURIOUS_MOVES = ("walk_the_dog", "slow_carve", "fakie_manual")
VOICE = {
    "starting": "Dropping in.", "reviewing": "I see you...",
    "needs-you": "Your call - I'll wait.", "issue": "Slammed it. Again.",
    "complete": "Landed it!", "paused": "Just chilling.",
}
GREETING = "Kai's here. Let's roll."


def _palette(name):
    return PALETTES.get(name or DEFAULT_PALETTE, PALETTES[DEFAULT_PALETTE])


# ---------------------------------------------------------------------------
# Drawing
# ---------------------------------------------------------------------------
def _draw_board(canvas, P, cx, cy, ang, flip, shove, p, spin_wheels):
    """Side-on deck with kicktails. flip shows the graphic or the grip; shove shortens it."""
    half = 36 * max(0.16, abs(math.cos(shove * 2 * math.pi)))
    f = flip * 2 * math.pi
    thick = 2.5 + 8 * abs(math.sin(f))
    up = math.cos(f) >= 0                                    # wheels below when upright
    a = math.radians(ang)
    ca, sa = math.cos(a), math.sin(a)

    def pt(u, v):
        return cx + u * ca - v * sa, cy + u * sa + v * ca

    kick = 5 * max(0.2, abs(math.cos(f)))
    top = [(-half, -kick), (-half * 0.78, 0), (half * 0.78, 0), (half, -kick)]
    bottom = [(half, -kick + thick), (half * 0.78, thick), (-half * 0.78, thick), (-half, -kick + thick)]
    face = P["deck_art"] if math.sin(f) > 0.25 else P["deck"]
    flat = [c for uv in top + bottom for c in pt(*uv)]
    canvas.create_polygon(*flat, fill=face, outline=P["edge"], width=2)
    if thick < 6 and half > 20:                              # his mark on the side of the deck
        kx, ky = pt(0, thick / 2)
        canvas.create_text(kx, ky - 1, text="K", fill=P["edge"], font=("Segoe UI", 7, "bold"))
    if thick > 6:                                            # the graphic: a stripe across the deck
        canvas.create_line(*pt(-half * 0.4, thick / 2), *pt(half * 0.4, thick / 2),
                           fill=P["deck"] if face != P["deck"] else P["deck_art"], width=2)
    side = 1 if up else -1
    for u in (-half * 0.6, half * 0.6):
        tx, ty = pt(u, thick + 2 if up else -2)
        wx, wy = pt(u, thick + 5 if up else -5)
        canvas.create_line(*pt(u, thick if up else 0), tx, ty, fill="#94a3b8", width=3)   # truck
        canvas.create_oval(wx - 4, wy - 4, wx + 4, wy + 4, fill=P["wheels"], outline="#0f172a", width=1)
        if spin_wheels:
            r = p * 12 + u
            canvas.create_line(wx, wy, wx + 3 * math.cos(r), wy + 3 * math.sin(r) * side, fill="#64748b", width=1)
    return pt(0, thick + 5)


def _draw_kai(canvas, P, hx, hy, st, eyes, fx):
    """Kai on the shared rig: baggy cargo pants, chunky sneakers, hoodie, cap backwards."""
    skin, edge = P["skin"], P["edge"]
    shade = _mix(skin, "#000000", 0.22)
    body = _Body(canvas, hx, hy, st["spin"], st["rot"], edge)
    back = st["spin"] < 0
    hip = st.get("hip", 0.0)
    ankles, swivel = st.get("ankles", (0, 0)), st.get("swivel", (0, 0))
    wrists, shoulders = st.get("wrists", (0, 0)), st.get("shoulders", (0, 0))
    hands = {}

    # legs: baggy cargos, a scrape patch per unhealed failure
    for i, (side, (hip_a, knee)) in enumerate(((-1, st["legs"][0:2]), (1, st["legs"][2:4]))):
        a, k, f = _limb_pts(hip + side * 6, 0, hip_a, knee, LEG, LEG, side)
        body.line([a, k, f], edge=True, width=11, fill=P["pants"])
        body.poly([(k[0] - 4, k[1] - 9), (k[0] + 4, k[1] - 9), (k[0] + 4, k[1] - 3), (k[0] - 4, k[1] - 3)],
                  fill=_mix(P["pants"], "#ffffff", 0.18), outline="")                 # cargo pocket
        if i < STATE.scrapes or (i == 0 and STATE.scrapes >= 3):
            body.line([(k[0] - 3, k[1]), (k[0] + 3, k[1])], width=3, fill="#fef3c7")    # plaster
            body.line([(k[0], k[1] - 2.5), (k[0], k[1] + 2.5)], width=1, fill="#f87171")
        body.dot(k[0], k[1], 2.1, fill=P["hoodie_hi"], outline="")                     # knee
        _foot(body, f, side, ankles[i], swivel[i], P["shoes"], P["accent"])
        body.dot(f[0], f[1] + 2, 3.2, fill=P["shoes"], outline=_mix(P["shoes"], "#000000", 0.45))  # chunky toe

    chest = _Joint(body, (hip, 0), st.get("torso", 0.0), (0, 0))
    # hoodie: hem at the hips, kangaroo pocket, drawstrings
    chest.poly([(-15, -48), (15, -48), (16, 4), (-16, 4)], edge=True, fill=P["hoodie"])
    chest.poly([(-10, -16), (10, -16), (12, -2), (-12, -2)], fill=_mix(P["hoodie"], "#000000", 0.12), outline="")
    chest.line([(-16, 2), (16, 2)], width=3, fill=_mix(P["hoodie"], "#000000", 0.25))
    if not back:
        for sx in (-4, 4):
            chest.line([(sx, -46), (sx * 1.2, -32)], width=1.4, fill=P["hoodie_hi"])
            chest.dot(sx * 1.2, -31, 1.4, fill=P["accent"], outline="")
    hood_up = "hood" in fx
    if not hood_up:
        chest.poly([(-11, -50), (11, -50), (8, -42), (-8, -42)], fill=_mix(P["hoodie"], "#000000", 0.2),
                   outline="")                                                         # hood down
    # the lightning bolt: his mark, readable without words
    chest.poly([(-2, -36), (5, -36), (0, -27), (5, -27), (-4, -16), (-1, -28)], fill=P["accent"], outline="")
    if "headphones" in fx:                                    # music when he's chilling
        chest.line([(-9, -47), (0, -42), (9, -47)], width=2, fill=P["edge"])
        for sx in (-9, 9):
            chest.dot(sx, -46, 3.2, fill=P["accent"], outline=P["edge"], width=1)

    # arms
    for i, (side, (shd, elb)) in enumerate(((-1, st["arms"][0:2]), (1, st["arms"][2:4]))):
        sh_y = -44 - shoulders[i]
        a, e, h = _limb_pts(side * 14, sh_y, 180 - shd if shd > 90 else shd, elb, 17, 16, side)
        if shd > 90:
            a, e, h = (a, (e[0], 2 * sh_y - e[1]), (h[0], 2 * sh_y - h[1]))
        chest.line([a, e], edge=True, width=8, fill=P["hoodie"])
        chest.line([e, h], edge=True, width=7, fill=P["hoodie"])
        cuff = (e[0] + (h[0] - e[0]) * 0.8, e[1] + (h[1] - e[1]) * 0.8)
        chest.line([cuff, h], width=7, fill=P["accent"] if side < 0 else P["hoodie_hi"])   # wristband / cuff
        _hand(chest, h, e, side, wrists[i], skin, shade)
        hands["left" if side < 0 else "right"] = chest.pt(*h)

    # neck + head
    head_y = -62
    chest.line([(0, -48), (0, head_y + 10)], edge=True, width=6, fill=skin)
    hb = _Joint(chest, (0, -52), st.get("head", 0.0))
    if not hood_up:                                           # locs with gold cuffs
        for j in range(-3, 4):
            hb.line([(j * 3, head_y - 10), (j * 4.1, head_y + 13 + abs(j))], edge=True, width=3,
                    fill=P["hair"])
            if j % 2 == 0:
                hb.dot(j * 4, head_y + 7, 1.6, fill=P["accent"], outline="")
    hb.dot(0, head_y, 12.5, edge=True, fill=skin, outline="", squash=True)
    if hood_up:
        hb.dot(0, head_y - 2, 14, edge=True, fill=P["hoodie"], outline="", squash=True)
        hb.dot(0, head_y + 1, 10, fill=skin, outline="", squash=True)
    else:                                                     # beanie, worn sideways, gold band
        hb.poly([(-13, head_y - 5), (12, head_y - 7), (14, head_y - 14), (-12, head_y - 18)], edge=True,
                fill=P["cap"])
        hb.line([(-12, head_y - 8), (14, head_y - 10)], width=3, fill=P["accent"])
    if back:
        hb.dot(0, head_y - 1, 11, fill=P["hair"], outline="", squash=True)
        return hands
    for side in (-1, 1):
        hb.dot(side * 12, head_y, 2.4, fill=shade, outline="", squash=True)
    gx = {"left": -2.5, "right": 2.5}.get(eyes, 0.0)
    gy = {"down": 1.5, "up": -1.5}.get(eyes, 0.0)
    for side in (-1, 1):
        hb.line([(side * 7.5, head_y - 5), (side * 2.5, head_y - 6)], width=1.6, fill=P["hair"])
        if eyes == "closed" or "zzz" in fx:
            hb.line([(side * 5 - 2, head_y), (side * 5 + 2, head_y)], width=1.3, fill="#1c1917")
        else:
            hb.dot(side * 5 + gx * 0.3, head_y + gy * 0.3, 3.2, fill="#ffffff", outline="")
            hb.dot(side * 5 + gx, head_y + gy, 1.7 if eyes != "wide" else 2.3, fill="#1c1917", outline="")
    hb.line([(0, head_y + 1), (-1, head_y + 4), (0.8, head_y + 4.5)], width=1.2, fill=shade)
    hb.line([(-4, head_y + 6.5), (0, head_y + 8.5), (4, head_y + 6.5)], width=1.8, fill="#7c2d12")   # grin
    return hands


def _crew_skater(canvas, x, y, p, colour, phase):
    """A small silhouette skater in the back: one helper Hermes sent out."""
    hop = max(0.0, math.sin(p * 4 * math.pi + phase)) * 8
    y -= hop
    canvas.create_line(x - 12, y + 2, x + 12, y + 2, fill=colour, width=3)              # board
    for wx in (x - 8, x + 8):
        canvas.create_oval(wx - 2, y + 3, wx + 2, y + 7, fill=colour, outline="")
    canvas.create_line(x - 5, y, x - 2, y - 12, fill=colour, width=2)
    canvas.create_line(x + 5, y, x + 2, y - 12, fill=colour, width=2)
    canvas.create_line(x, y - 12, x, y - 26, fill=colour, width=4)
    canvas.create_line(x - 9, y - 22, x + 9, y - 22, fill=colour, width=2)
    canvas.create_oval(x - 4, y - 34, x + 4, y - 26, fill=colour, outline="")


def _stage(canvas, P, fx, p, glow, kai_x):
    W = FRAME[0]
    canvas.create_oval(W - 70, 22, W - 40, 52, fill=P["sky"], outline="")               # sun / moon
    for bx, bw, bh in ((14, 34, 70), (52, 26, 96), (82, 40, 58), (230, 30, 84), (264, 44, 64)):
        canvas.create_line(bx, FLOOR - 40, bx, FLOOR - 40 - bh, bx + bw, FLOOR - 40 - bh, bx + bw, FLOOR - 40,
                           fill=P["city"], width=2)                                       # skyline, outline only
        for wy in range(int(FLOOR - 30 - bh), FLOOR - 50, 16):
            canvas.create_line(bx + 7, wy, bx + 11, wy, fill=P["city"], width=2)          # a lit window or two
    canvas.create_rectangle(0, FLOOR, W, FLOOR + 12, fill=P["ground"], outline="")       # the street
    canvas.create_oval(MX + kai_x - 90, FLOOR - 8, MX + kai_x + 90, FLOOR + 8, fill=glow, outline="")
    for k in range(6):                                                                     # cracks in the concrete
        cx = 20 + k * 58
        canvas.create_line(cx, FLOOR + 3, cx + 8, FLOOR + 8, fill=_mix(P["ground"], "#000000", 0.25), width=1)
    for side in ((1,) if "ramp" in fx else ()) + ((1, -1) if "halfpipe" in fx else ()):
        xs = [RAMP_AT + RAMP_R * k / 12 for k in range(13)]
        surface = [(MX + side * min(x, COPING_X), FLOOR - ramp_surface(side * min(x, COPING_X))[0]) for x in xs]
        back = MX + side * (COPING_X + 26)
        pts = surface + [(back, FLOOR - RAMP_H), (back, FLOOR)]
        canvas.create_polygon(*[c for xy in pts for c in xy], fill="#a8a29e", outline="#57534e", width=2)
        canvas.create_line(MX + side * COPING_X, FLOOR - RAMP_H, back, FLOOR - RAMP_H, fill="#e7e5e4", width=4)
    if "rail" in fx:
        ry = FLOOR - 34 - DECK + 2
        canvas.create_line(MX - 110, ry, MX + 110, ry, fill="#cbd5e1", width=4)
        for rx in (MX - 96, MX, MX + 96):
            canvas.create_line(rx, ry, rx, FLOOR, fill="#64748b", width=3)
    if "ledge" in fx:
        canvas.create_rectangle(MX + 40, FLOOR - 30, MX + 150, FLOOR, fill="#78716c", outline="#44403c", width=2)
    if "kicker" in fx:
        canvas.create_polygon(MX - 100, FLOOR, MX - 52, FLOOR, MX - 52, FLOOR - 24, fill="#a16207",
                              outline="#422006", width=2)
    if "marks" in fx and STATE.tools:                                                      # chalk: one per tool
        for i, cat in enumerate(STATE.tools):
            mx = MX - 120 + i * 26
            canvas.create_line(mx, FLOOR + 6, mx + 16, FLOOR + 6, fill=_color(cat), width=3)
            canvas.create_line(mx + 10, FLOOR + 2, mx + 16, FLOOR + 6, mx + 10, FLOOR + 10, fill=_color(cat),
                               width=2)
    if STATE.danger:                                                                       # a cone: careful
        canvas.create_polygon(MX - 120, FLOOR, MX - 104, FLOOR, MX - 112, FLOOR - 26, fill="#ef4444",
                              outline="#7f1d1d", width=2)
        canvas.create_line(MX - 117, FLOOR - 10, MX - 107, FLOOR - 10, fill="#f8fafc", width=3)


def _effects(canvas, P, fx, p, kai_hip, board_pt, glow, hands):
    hx, hy = kai_hip
    work = _color(STATE.category)
    if "speed" in fx:
        for k in range(4):
            canvas.create_line(hx - 50 - k * 6, hy - 40 + k * 12, hx - 26 - k * 6, hy - 40 + k * 12,
                               fill="#94a3b8", width=2)
    if "sparks" in fx and board_pt:
        bx, by = board_pt
        for k in range(7):
            a = math.pi + 0.5 + k * 0.25 + p * 3
            r = 8 + (k * 7 + p * 40) % 18
            canvas.create_line(bx - 20, by, bx - 20 + math.cos(a) * r, by + math.sin(a) * r * 0.6,
                               fill=work if k % 2 else "#fde047", width=2)
    if "brake" in fx:
        for k in range(6):
            r = 3 + k
            canvas.create_oval(hx + 30 + k * 6 - r, FLOOR - 4 - r - k, hx + 30 + k * 6 + r, FLOOR - 4 + r - k,
                               fill=("#d6d3d1", "#e7e5e4", "#a8a29e")[k % 3], outline="")
    if "dust" in fx:
        for k in range(6):
            side = -1 if k % 2 else 1
            r = 3 + (k % 3) * 2 + 4 * p
            canvas.create_oval(hx + side * (16 + k * 4) - r, FLOOR - 4 - r, hx + side * (16 + k * 4) + r,
                               FLOOR - 4 + r, fill=("#d6d3d1", "#e7e5e4", "#a8a29e")[k % 3], outline="")
    if "stars" in fx:
        for k in range(3):
            a = p * 6.28 + k * 2.1
            canvas.create_text(hx + math.cos(a) * 16, hy - 70 + math.sin(a) * 5, text="*", fill="#facc15",
                               font=("Segoe UI", 12, "bold"))
    if "clack" in fx and board_pt:
        canvas.create_text(board_pt[0] + 26, board_pt[1] - 16, text="CLACK", fill=glow, font=("Segoe UI", 9, "bold"))
    if "whistle" in fx:
        for k in range(3):
            r = 6 + k * 6 + (p * 18) % 6
            canvas.create_arc(hx + 10 - r, hy - 80 - r, hx + 10 + r, hy - 80 + r, start=-30, extent=60,
                              style="arc", outline=glow, width=2)
    if "bump" in fx and "right" in hands:
        x, y = hands["right"]
        for k in range(6):
            a = k / 6 * 2 * math.pi
            canvas.create_line(x + math.cos(a) * 6, y + math.sin(a) * 6, x + math.cos(a) * 12,
                               y + math.sin(a) * 12, fill=glow, width=2)
    if "notes" in fx:
        for k, (nx, ny) in enumerate(((-30, 30), (24, 18))):
            rise = (p * 30 + k * 13) % 30
            x0, y0 = hx + nx, hy - 70 + ny - rise
            canvas.create_oval(x0 - 4, y0 - 3, x0 + 2, y0 + 3, fill=P["accent"], outline="")
            canvas.create_line(x0 + 2, y0, x0 + 2, y0 - 12, fill=P["accent"], width=2)
    if "zzz" in fx:
        for k in range(3):
            canvas.create_text(hx + 30 + k * 10, hy - 40 - k * 12 - (p * 10) % 10, text="z",
                               fill="#c4b5fd", font=("Segoe UI", 9 + 2 * k, "bold"))
    if "wheel_check" in fx and "right" in hands:
        x, y = hands["right"]
        canvas.create_arc(x - 14, y - 40, x + 6, y - 20, start=p * 720, extent=270, style="arc",
                          outline="#94a3b8", width=2)
    if "tool" in fx and "right" in hands:
        x, y = hands["right"]
        canvas.create_line(x, y, x + 10, y + 8, fill="#94a3b8", width=4)                  # skate tool
    if "phone" in fx and "right" in hands:
        x, y = hands["right"]
        canvas.create_rectangle(x - 4, y - 14, x + 4, y, fill="#0f172a", outline="#94a3b8", width=1)
        canvas.create_rectangle(x - 3, y - 12, x + 3, y - 3, fill=P["accent"], outline="")
    if "fingerboard" in fx and "right" in hands:
        x, y = hands["right"]
        u = _arc((p * 2) % 1.0)
        canvas.create_line(x - 7, y - 4 - 6 * u, x + 7, y - 4 - 6 * u, fill=P["deck_art"], width=3)
    if "grab" in fx:
        canvas.create_text(hx + 58, hy - 40, text="INDY!", fill=glow, font=("Segoe UI", 10, "bold"))


def _draw_crew(canvas, crew, p, glow):
    if not crew:
        return
    phase, amount = crew
    n = max(1, STATE.helpers)
    colour = _mix(MOOD_COLORS["delegate"], "#1e1b4b", 0.25)
    for k in range(n):
        home = MX - 110 + k * 46
        if phase == "in":
            x = -40 + (home + 40) * amount
        elif phase == "out":
            x = home - (home + 60) * amount
        elif phase == "back":
            x = -40 + (home + 40) * amount
        elif phase == "bump":
            x = MX - 70 + 40 * amount if k == 0 else home
        else:
            x = home + 18 * math.sin(p * 2 * math.pi + k)
        _crew_skater(canvas, x, FLOOR - 50, p, colour, k * 1.3)


STYLE_OF = {name: name.replace("_", " ") for name in
            ("kickflip", "tre_flip", "big_air", "grind", "boardslide", "manual", "nose_manual", "shove_it",
             "pump", "carve", "drop_in", "ollie_up", "slam", "foot_brake", "tail_stall", "rock_to_fakie",
             "tic_tac", "spin_180")}
STYLE_OF.update({"tre_flip": "360 flip", "spin_180": "frontside 180", "big_air": "indy air",
                 "drop_in": "drop in", "rock_to_fakie": "rock to fakie"})


TRAVEL_STATUS = {"skate_roll": "On the move", "ollie_gap": "On the move", "kicker_air": "On the move",
                 "bomb_drop": "Dropping in"}


def status_text(pose: str, mood: str) -> tuple[str, str]:
    """(headline, detail): what Hermes is doing, from event kinds, categories and counts only."""
    st = STATE
    headline = POSE_STATUS.get(pose) or TRAVEL_STATUS.get(pose) or {"work": "Working", "delegate": "Delegating", "fail": "Problem",
                                         "approve": "Needs you", "joy": "Done", "rest": "Resting"}.get(mood, "Ready")
    detail = []
    if st.running and mood in ("work", "fail", "calm", "curious"):
        detail.append(f"{st.running} in the line")
    if st.helpers:
        detail.append(f"{st.helpers} crew out")
    if mood == "approve" and st.danger:
        headline, detail = "Needs your OK", ["dangerous command"] + detail
    if st.scrapes and mood in ("fail", "work"):
        detail.append(f"{st.scrapes} scrape{'s' if st.scrapes != 1 else ''}")
    if mood == "joy" and st.landed:
        detail.append(f"{st.landed} landed")
    if st.thinking and mood not in ("approve", "fail"):
        headline = "Thinking"
    return headline, " · ".join(detail)


def _indicators(canvas, pose, mood, glow):
    st = STATE
    chips = []
    if st.danger:
        chips.append(("dangerous", "#ef4444"))
    if st.running:
        chips.append((f"{st.running} in the line", _color(st.tools[-1])))
    if st.helpers:
        chips.append((f"{st.helpers} crew", MOOD_COLORS["delegate"]))
    if st.scrapes:
        chips.append((f"{st.scrapes} scrape{'s' if st.scrapes != 1 else ''}", MOOD_COLORS["fail"]))
    if st.landed:
        chips.append((f"{st.landed} landed", MOOD_COLORS["joy"]))
    style = STYLE_OF.get(MOVE_FOR_POSE.get(pose, ""))
    if style:
        chips.append((style, "#94a3b8"))
    x, y = 6, 12
    for text, colour in chips:
        if x + 20 + len(text) * 7.4 > FRAME[0] - 6:
            x, y = 6, y + 22
        x = _badge(canvas, x, y, text, colour)
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


def scene_for(pose: str, progress: float = 0.0) -> tuple[dict, str]:
    """The scene and mood a pose draws: used by the drawing and by the tests."""
    p = progress % 1.0
    move = MOVE_FOR_POSE.get(pose)
    if move is not None:
        return MOVES[move](p), _MOVE_MOOD.get(move) or mood_of(pose)
    prm = pose_params(pose, progress)           # unknown pose: ready stance honouring lean and bob
    sc = _m_ready_stance(p)
    sc["kai"] = {**sc["kai"], "rot": sc["kai"]["rot"] + prm["lean"] * 120, "y": sc["kai"]["y"] - prm["bob"]}
    return sc, mood_of(pose)


def draw_kai(canvas, pose: str, progress: float = 0.0, palette: str | None = None) -> None:
    P = _palette(palette)
    canvas.delete("all")
    p = progress % 1.0
    sc, mood = scene_for(pose, progress)
    prm = pose_params(pose, progress)
    glow = MOOD_COLORS.get(mood, MOOD_COLORS["calm"])
    if STATE.danger and mood == "approve":
        glow = "#ef4444"
    elif mood == "work" and STATE.tools:
        glow = _color(STATE.tools[-1])
    kai, board, fx = sc["kai"], sc["board"], sc["fx"]

    bare = "bare" in fx                    # out on the real desktop: no street scenery
    if not bare:
        _stage(canvas, P, fx, p, glow, kai["x"])
        _draw_crew(canvas, sc["crew"], p, glow)
    hx, hy = MX + kai["x"], HIP_Y - kai["y"]
    if not bare:
        lift = max(0.0, kai["y"])                               # ground shadow shrinks as he rises
        w = 28 * max(0.35, 1 - lift / 150)
        canvas.create_oval(hx - w, FLOOR - 3, hx + w, FLOOR + 3, fill=_mix(P["ground"], "#000000", 0.3),
                           outline="")
    if "kicker_here" in fx:                                     # the little ramp he sets down
        canvas.create_polygon(MX - 36, FLOOR, MX + 16, FLOOR, MX + 16, FLOOR - 24, fill="#a16207",
                              outline=P["edge"], width=2)

    board_pt = None
    hands_first = board is not None and board["mode"] in ("hand", "sit")
    if board is not None and not hands_first:
        if board["mode"] == "ride":
            body = _Body(canvas, hx, hy, 1.0, kai["rot"], "#000000")
            cx, cy = body.pt(0, _feet_drop(kai["legs"]) + 3)
            board_pt = _draw_board(canvas, P, cx, cy + 1, kai["rot"] - board["rot"], board["flip"],
                                   board["shove"], p, board["spin_wheels"])
        elif board["mode"] == "upright":
            board_pt = _draw_board(canvas, P, MX + board["x"], FLOOR - 36, -board["rot"], 0, 0, p, False)
        else:
            board_pt = _draw_board(canvas, P, MX + board["x"], FLOOR - DECK + 2 - board["y"], -board["rot"],
                                   board["flip"], board["shove"], p, board["spin_wheels"])
    if board is not None and board["mode"] == "sit":
        board_pt = _draw_board(canvas, P, hx + 4, FLOOR - DECK + 2, 0, 0, 0, p, board["spin_wheels"])
    hands = _draw_kai(canvas, P, hx, hy, kai, prm["eyes"], fx)
    if board is not None and board["mode"] == "hand":
        x, y = hands.get("right", (hx + 20, hy - 30))
        board_pt = _draw_board(canvas, P, x + 6, y - 4, -board["rot"], 0, 0, p, board["spin_wheels"])
    _effects(canvas, P, fx, p, (hx, hy), board_pt, glow, hands)
    if STATE.partying and mood == "joy":
        for k in range(14):
            cx = (k * 47 + p * 160) % FRAME[0]
            cy = 30 + ((k * 31 + p * 120) % 150)
            canvas.create_rectangle(cx, cy, cx + 4, cy + 7,
                                    fill=("#facc15", "#22d3ee", "#f472b6", "#a3e635")[k % 4], outline="")
    if "falling" in fx:                                         # wind past him on the way down
        for k in range(4):
            x = hx - 30 + k * 20
            canvas.create_line(x, hy - 110 - (p * 60 + k * 17) % 40, x, hy - 80 - (p * 60 + k * 17) % 40,
                               fill="#94a3b8", width=2)
    if pose in EXCLAIM:
        _bubble(canvas, hx, 40, "!", glow)
    elif pose in WONDER or STATE.thinking:
        _bubble(canvas, hx, 40, "?", glow)
    if "perch" not in fx:                                       # on a window Hermes is quiet: no plaque
        _indicators(canvas, pose, mood, glow)
