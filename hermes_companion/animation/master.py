"""Sensei - a master fighter whose fight shows what Hermes is doing.

Every tool Hermes runs is a ninja coming at him, and the ninja's weapon
names the kind of work: shuriken (terminal), kunai and rope (web), bo staff
(files), twin blades (code), smoke bombs (media), a shadow ninja (memory).
He fights them, throws them far when a tool finishes, dodges arrows while a
long tool keeps going, stops a thrown object mid-air when Hermes needs your
OK, sneaks up on them while Hermes reads or searches, runs up and along the
wall to start a step, sends shadow clones out with the helpers, and rests
under a blossom tree when everything is quiet. A finished task is a long
backflip and a bicycle kick.

| Hermes is...                 | Sensei...                                         |
|------------------------------|---------------------------------------------------|
| starting a task              | bows, then drops into a horse stance              |
| launching a step             | runs up the wall / along its side                 |
| running a tool               | fights that tool's ninja: jab-cross, roundhouse   |
| a long tool keeps going      | arrows fly in; he dodges every one                |
| reading, searching, memory   | sneaks up on a ninja and takes it from behind     |
| a step finished              | a palm strike, then throws the ninja far away     |
| a step failed                | takes a hit, goes down, kips back up              |
| needs your OK                | catches an arrow / stops a thrown boulder, waits  |
| you approved / declined      | flips up and goes / tosses it aside               |
| delegating to helpers        | shadow clones step out and fight beside him       |
| finished the task            | a long backflip, then a bicycle kick              |
| quiet / asleep               | rests under the blossom tree, petals falling      |

Every engine pose maps to exactly one move (``MOVE_FOR_POSE``) so the same
action always looks the same. The jointed rig (spine, hips, neck, wrists,
ankles, foot swivel) is shared with the Duet companion.
"""
from __future__ import annotations

import math
import time
from dataclasses import dataclass, field

from hermes_companion.animation.animator import pose_params
from hermes_companion.animation.duet import (
    _Body, _Joint, _badge, _d, _ease, _foot, _limb_pts, _mix, _mood_icon, _step,
)
from hermes_companion.animation.herald import EXCLAIM, MOOD_COLORS, WONDER, _bubble, mood_of

FRAME = (360, 300)
FLOOR = 228
MX = 150                     # where Sensei stands

PALETTES: dict[str, dict[str, str]] = {
    "midnight": {"edge": "#0b0d14", "skin": "#8a5a3c", "hair": "#cfcfcf", "beard": "#e2e2e2",
                 "gi": "#1f2a44", "gi_hi": "#2f3d63", "trim": "#d4a017", "belt": "#111111",
                 "band": "#c0392b", "pants": "#1a2238", "sky": "#1c2340", "moon": "#f5e6b8"},
    "jade": {"edge": "#0a140f", "skin": "#c68b59", "hair": "#d8d8d8", "beard": "#ececec",
             "gi": "#1e5e44", "gi_hi": "#2a7a59", "trim": "#e8d9a8", "belt": "#111111",
             "band": "#e8d9a8", "pants": "#174a36", "sky": "#14281f", "moon": "#f2f0d0"},
    "dawn": {"edge": "#1a0f0a", "skin": "#5c3a21", "hair": "#bdbdbd", "beard": "#dcdcdc",
             "gi": "#f4efe6", "gi_hi": "#ffffff", "trim": "#b22222", "belt": "#111111",
             "band": "#b22222", "pants": "#e9e2d6", "sky": "#f6d7b0", "moon": "#fff3d6"},
}
DEFAULT_PALETTE = "midnight"

# Ninja kinds follow the tool category Hermes is using.
NINJA_KINDS = {
    "terminal": ("shuriken", "#2dd4bf"), "development": ("twin_blades", "#22d3ee"),
    "web": ("kunai_rope", "#60a5fa"), "browser": ("kunai_rope", "#38bdf8"),
    "file": ("bo_staff", "#f59e0b"), "docs": ("bo_staff", "#f59e0b"),
    "media": ("smoke_bomb", "#f472b6"), "memory": ("shadow", "#a78bfa"),
    "planning": ("bo_staff", "#84cc16"), "desktop": ("shuriken", "#94a3b8"),
    "general": ("plain", "#94a3b8"),
}


def _kind(category: str) -> tuple[str, str]:
    return NINJA_KINDS.get(category, NINJA_KINDS["general"])


# ---------------------------------------------------------------------------
# Live state: the fight follows real, signed Hermes events.
# ---------------------------------------------------------------------------
@dataclass
class MasterState:
    tools: list = field(default_factory=list)   # categories of tools in flight = ninjas
    category: str = "general"
    helpers: int = 0
    missteps: int = 0
    streak: int = 0
    defeated: int = 0         # ninjas thrown this task (finished tools)
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
            self.tools, self.helpers, self.missteps, self.streak, self.defeated = [], 0, 0, 0, 0
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
                self.defeated += 1
                self.streak += 1
                if self.streak >= 3 and self.missteps:
                    self.missteps -= 1
                    self.streak = 0
            else:
                self.missteps = min(self.missteps + 1, 3)
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
                self.missteps = min(self.missteps + 1, 3)
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
        return (tuple(self.tools), self.category, self.helpers, self.missteps, min(self.defeated, 9),
                self.danger, self.thinking, self.partying)


STATE = MasterState()


def observe(ev) -> None:
    STATE.observe(ev)


def state_key() -> tuple:
    return STATE.key()


# ---------------------------------------------------------------------------
# Scenes. A move is a function of progress p returning a Scene: Sensei's pose
# (the shared jointed rig), the ninjas, flying props and stage effects.
# ---------------------------------------------------------------------------
def _n(x, state="attack", y=0.0, rot=0.0, spin=1.0, arms=(60, 40, 90, 20), legs=(10, 10, 10, 10),
       torso=0.0, kind=None):
    """A ninja, placed relative to Sensei. "unaware" ninjas show their backs."""
    if state == "unaware":
        spin = -1.0
    return {**_d(x, y=y, spin=spin, rot=rot, arms=arms, legs=legs, torso=torso),
            "state": state, "kind": kind}


def _scene(master, ninjas=(), arrows=(), objects=(), fx=()):
    return {"master": master, "ninjas": list(ninjas), "arrows": list(arrows),
            "objects": list(objects), "fx": set(fx)}


def _sw(p, n=1.0):
    return math.sin(p * 2 * math.pi * n)


def _kinds_in_play(minimum=1):
    """One ninja per tool in flight (at least ``minimum``), typed by category."""
    cats = list(STATE.tools) or [STATE.category] * minimum
    while len(cats) < minimum:
        cats.append(cats[-1])
    return cats[:4]


def _attackers(p, base_x=74.0, stagger=None):
    """Ninjas lined up to his right, bobbing in; the first may be hit."""
    out = []
    for i, cat in enumerate(_kinds_in_play()):
        bob = _sw(p + i * 0.3, 2) * 4
        state = stagger if (i == 0 and stagger) else "attack"
        jab = max(0.0, _sw(p + i * 0.37, 2)) if state == "attack" else 0.0   # they throw, not just stand
        out.append(_n(base_x + i * 34 + bob - 6 * jab, state, kind=cat,
                      arms=(70 + 25 * jab, 125 - 125 * jab, 55, 135), legs=_step(p + i * 0.2, 10),
                      torso=-6 * jab))
    return out


# --- start / stance ----------------------------------------------------------
def _m_bow_ready(p):
    b = math.sin(min(p * 2, 1.0) * math.pi)
    stance = _ease(max(0.0, p - 0.5) * 2)
    return _scene(_d(0, torso=35 * b, arms=(20, 100, 20, 100), legs=(5 + 25 * stance, 30 * stance, 5 + 25 * stance, 30 * stance),
                     y=-6 * stance))


def _m_horse_stance(p):
    breathe = _sw(p) * 2
    return _scene(_d(0, y=-10 + breathe, arms=(60, 100, 60, 100), legs=(40, 50, 40, 50), swivel=(-0.5, -0.5)),
                  _attackers(p, 120))


def _m_leap_ready(p):
    h = math.sin(min(p, 0.999) * math.pi) * 30
    return _scene(_d(0, y=h, arms=(150, 20, 150, 20), legs=(40, 80, 40, 80), ankles=(30, 30)))


# --- travel: wall run / run in ----------------------------------------------
def _m_wall_run(p):
    """Up the wall and along its side, then a flip off."""
    t = _ease(p)
    if t < 0.5:   # running up the wall: body horizontal, feet on the wall
        u = t * 2
        m = _d(130, y=20 + 120 * u, rot=-90, arms=(60 + 40 * _sw(p, 4), 30, 60 - 40 * _sw(p, 4), 30),
               legs=_step(p, 30), torso=-10)
    else:         # along its side at the top, then away
        u = (t - 0.5) * 2
        m = _d(130 - 140 * u, y=140 - 120 * u, rot=-90 + 90 * u, spin=1.0,
               arms=(120, 20, 120, 20), legs=(40, 60, 40, 60))
    return _scene(m, fx={"wall", "speed"})


def _m_run_in(p):
    return _scene(_d(-40 + 40 * _ease(p), torso=12, arms=(60 + 40 * _sw(p, 3), 90, 60 - 40 * _sw(p, 3), 90),
                     legs=_step(p * 1.5, 30), ankles=(20, 20)), fx={"speed"})


def _m_walk_back(p):
    return _scene(_d(40 - 40 * _ease(p), spin=-1.0, arms=(20, 30, 20, 30), legs=_step(p, 14)))


# --- strikes ----------------------------------------------------------------
def _m_jab_cross(p):
    j = max(0.0, _sw(p, 3))
    c = max(0.0, -_sw(p, 3))
    return _scene(_d(0, torso=8 * (j - c), hip=3 * (j - c), arms=(90 * c + 30, 100 - 90 * c, 90 * j + 30, 100 - 90 * j),
                     legs=(30, 20, -10, 10), ankles=(0, 20)),
                  _attackers(p, 68, "stagger" if j > 0.8 else None), fx={"impact"} if j > 0.8 or c > 0.8 else ())


def _m_roundhouse(p):
    k = math.sin(min(p, 0.999) * math.pi)
    return _scene(_d(0, torso=-25 * k, rot=-8 * k, arms=(40, 90, 120, 40), legs=(5, 0, 100 * k, 20 * (1 - k)),
                     ankles=(0, 60 * k), swivel=(-0.6 * k, 0)),
                  _attackers(p, 78, "stagger" if k > 0.85 else None), fx={"impact"} if k > 0.85 else ())


def _m_block_counter(p):
    blk = p < 0.5
    k = math.sin(max(0.0, p - 0.5) * 2 * math.pi) if not blk else 0.0
    return _scene(_d(0, torso=-6 if blk else 10 * k, arms=(150, 120, 150, 120) if blk else (60, 90, 30 + 60 * k, 100 - 90 * k),
                     legs=(25, 25, 0, 10)), _attackers(p, 62), fx={"block"} if blk else ({"impact"} if k > 0.8 else ()))


def _m_palm_strike(p):
    s = math.sin(min(p, 0.999) * math.pi)
    return _scene(_d(0, torso=10 * s, hip=4 * s, arms=(30, 100, 90 * s + 20, 10), wrists=(0, -70 * s),
                     legs=(35, 30, -15, 5)), _attackers(p, 64 + 20 * s, "stagger" if s > 0.7 else None),
                  fx={"impact"} if s > 0.7 else ())


def _m_throw_far(p):
    """He grabs the ninja and throws it far: one tool done."""
    t = _ease(p)
    grab = t < 0.4
    m = _d(0, torso=-20 if grab else 30 * math.sin(min((t - 0.4) / 0.6, 1) * math.pi),
           rot=-6 if grab else 8, arms=(100, 40, 120, 30) if grab else (40, 60, 160, 10), legs=(35, 30, -10, 5))
    first = _kinds_in_play()[0]
    if grab:
        flyer = _n(38, "stagger", y=10 * t, kind=first, rot=-20)
    else:
        u = (t - 0.4) / 0.6
        flyer = _n(38 + 190 * u, "fly", y=10 + 110 * math.sin(u * math.pi * 0.9), rot=-20 - 540 * u, kind=first)
    rest = _attackers(p, 120)[1:]
    return _scene(m, [flyer] + rest, fx={"throw"})


def _m_staff_disarm(p):
    """Files: he takes the bo staff and turns it on its owner."""
    t = _ease(p)
    return _scene(_d(0, torso=8 * _sw(p, 2), arms=(100, 40, 110 + 30 * _sw(p, 3), 20), wrists=(40, 40),
                     legs=(25, 20, 10, 10)), _attackers(p, 66, "stagger" if t > 0.6 else None),
                  objects=[("staff", 40, -60 + 10 * _sw(p, 3), 60 * _sw(p, 3))])


def _m_twin_sweep(p):
    """Code: a low leg sweep takes two ninjas at once."""
    s = math.sin(min(p, 0.999) * math.pi)
    m = _d(0, y=-26 * s, torso=30 * s, arms=(110, 30, 90, 40), legs=(80 * s, 120 * s, 100 * s, 10), ankles=(0, 40 * s))
    ninjas = [_n(60 + i * 30, "fly" if s > 0.6 else "attack", y=30 * s * (s > 0.6), rot=-80 * s * (s > 0.6), kind=c)
              for i, c in enumerate(_kinds_in_play(2))]
    return _scene(m, ninjas, fx={"impact"} if s > 0.6 else ())


def _m_spin_kick(p):
    t = math.cos(p * 2 * math.pi)
    k = math.sin(min(p, 0.999) * math.pi)
    return _scene(_d(0, y=10 * k, spin=t, arms=(100, 20, 100, 20), legs=(10, 20, 95 * k, 10), ankles=(0, 50)),
                  _attackers(p, 80, "stagger" if k > 0.85 else None), fx={"speed"})


def _m_flying_kick(p):
    a = math.sin(min(p, 0.999) * math.pi)
    return _scene(_d(-10 + 60 * p, y=60 * a, rot=-15, torso=-10, arms=(160, 20, 40, 60), legs=(90, 0, 40, 100), ankles=(40, 40)),
                  _attackers(p, 96, "fly" if p > 0.75 else None), fx={"speed", "impact"} if p > 0.75 else {"speed"})


def _m_elbow_combo(p):
    e = max(0.0, _sw(p, 2))
    return _scene(_d(0, torso=12 * e, arms=(40, 150, 100 * e + 20, 150), legs=(30, 25, 0, 10)),
                  _attackers(p, 56, "stagger" if e > 0.8 else None), fx={"impact"} if e > 0.8 else ())


def _m_dodge_arrows(p):
    """A long tool keeps going: arrows keep coming and he dodges every one."""
    lean = _sw(p, 1.5)
    m = _d(0, y=-6 * abs(lean), torso=-45 * max(0.0, lean) + 25 * max(0.0, -lean), head=-10 * lean,
           arms=(100, 30, 100, 30), legs=(30, 40, 20, 30), ankles=(0, 20))
    arrows = [((p * 1.4 + k * 0.33) % 1.0 * 360 - 20, -55 + 26 * k, 180) for k in range(3)]
    return _scene(m, arrows=arrows, fx={"arrows"})


# --- sneaking (reading, searching, memory) -----------------------------------
def _m_sneak(p):
    t = _ease(p)
    return _scene(_d(-60 + 80 * t, y=-18, torso=40, head=-15, arms=(40, 90, 80, 120), wrists=(30, 30),
                     legs=(60 + 15 * _sw(p, 2), 90, 60 - 15 * _sw(p, 2), 90), ankles=(40, 40)),
                  [_n(90, "unaware", spin=-1.0, kind=_kinds_in_play()[0], arms=(20, 30, 20, 30), legs=(5, 0, 5, 0))],
                  fx={"stealth"})


def _m_sneak_scan(p):
    look = _sw(p, 1)
    return _scene(_d(-30, y=-22, torso=35, head=25 * look, arms=(60, 120, 40, 60), legs=(70, 100, 50, 80)),
                  [_n(100, "unaware", kind=_kinds_in_play()[0], arms=(20, 30, 20, 30), legs=(5, 0, 5, 0))],
                  fx={"stealth"})


def _m_sneak_strike(p):
    """From behind: a quiet takedown."""
    t = _ease(p)
    hit = t > 0.6
    return _scene(_d(40 * t, y=-12 * (1 - t), torso=30 * (1 - t), arms=(80, 60, 130 if hit else 60, 20),
                     legs=(40 * (1 - t), 60 * (1 - t), 30, 20)),
                  [_n(70, "down" if hit else "unaware", rot=90 if hit else 0, y=-30 if hit else 0,
                      kind=_kinds_in_play()[0])], fx={"stealth"} | ({"impact"} if hit else set()))


# --- trouble (failure) -----------------------------------------------------
def _m_hit_react(p):
    h = math.sin(min(p, 0.999) * math.pi)
    return _scene(_d(-8 * h, torso=-30 * h, head=-20 * h, arms=(70, 40, 120, 30), legs=(10, 20, 30, 10)),
                  _attackers(p, 50), fx={"hit"})


def _m_knocked_down(p):
    d = _ease(p)
    return _scene(_d(-10, y=-40 * d, rot=-80 * d, arms=(90, 30, 120, 30), legs=(30 * d, 40, 60 * d, 20)),
                  _attackers(p, 64), fx={"hit"})


def _m_roll_away(p):
    return _scene(_d(-50 * p, y=-30, spin=math.cos(p * 4 * math.pi), rot=-360 * p, arms=(60, 120, 60, 120),
                     legs=(90, 120, 90, 120)), _attackers(p, 80))


def _m_kip_up(p):
    u = _ease(p)
    return _scene(_d(0, y=-40 * (1 - u) + 16 * math.sin(u * math.pi), rot=-80 * (1 - u), arms=(150, 20, 150, 20),
                     legs=(60 * (1 - u), 90 * (1 - u), 60 * (1 - u), 90 * (1 - u))), _attackers(p, 90))


def _m_wipe_lip(p):
    return _scene(_d(0, head=-10, arms=(20, 30, 90, 150), wrists=(0, 40), legs=(20, 15, 5, 0)), _attackers(p, 96))


def _m_breathe(p):
    b = _sw(p) * 3
    return _scene(_d(0, y=b, arms=(40 + 10 * b, 100, 40 + 10 * b, 100), legs=(20, 20, 20, 20)), _attackers(p, 110))


def _m_ready_again(p):
    s = _ease(p)
    return _scene(_d(0, y=-8 * s, arms=(70, 110, 90, 60), legs=(30, 30, 10, 20)), _attackers(p, 84))


# --- needs you (approval) ----------------------------------------------------
def _m_catch_arrow(p):
    """An arrow comes; he snatches it out of the air and holds it up for you."""
    t = _ease(p)
    caught = t > 0.45
    ax = 200 - 150 * min(1.0, t / 0.45)
    return _scene(_d(0, torso=-6, head=-10, arms=(30, 60, 150 if caught else 100, 30), wrists=(0, 30),
                     legs=(25, 20, 5, 0)), arrows=[] if caught else [(ax, -58, 180)],
                  objects=[("arrow_held", 16, -98, 0)] if caught else [], fx={"freeze"} if caught else {"arrows"})


def _m_stop_object(p):
    """A boulder is thrown at him; he stops it with one palm and waits for you."""
    t = _ease(p)
    held = t > 0.4
    bx = 220 - 170 * min(1.0, t / 0.4)
    return _scene(_d(0, torso=-8, rot=-4, arms=(30, 60, 90, 0), wrists=(0, -80), legs=(40, 30, -10, 5), ankles=(0, 30)),
                  [_n(150, "attack", kind=_kinds_in_play()[0], arms=(150, 20, 150, 20))],
                  objects=[("boulder", 50 if held else bx, -60, 0, held)], fx={"freeze"} if held else ())


def _m_beckon_you(p):
    w = max(0.0, _sw(p, 3))
    return _scene(_d(0, spin=0.5, head=-25, arms=(20, 30, 110, 60 + 60 * w), wrists=(0, -50 * w), legs=(15, 10, 5, 0)))


# --- your answer -------------------------------------------------------------
def _m_bow_small(p):
    b = math.sin(min(p, 0.999) * math.pi)
    return _scene(_d(0, torso=20 * b, arms=(20, 110, 20, 110), legs=(5, 0, 5, 0)))


def _m_flip_up(p):
    a = math.sin(min(p, 0.999) * math.pi)
    return _scene(_d(0, y=40 * a, rot=-360 * p, arms=(150, 20, 150, 20), legs=(60 * a, 100 * a, 60 * a, 100 * a)),
                  fx={"speed"})


def _m_shrug(p):
    s = abs(_sw(p))
    return _scene(_d(0, y=2 * s, shoulders=(4 * s, 4 * s), arms=(50, 110, 50, 110), legs=(10, 0, 10, 0)))


def _m_toss_aside(p):
    t = _ease(p)
    return _scene(_d(0, torso=-10 * t, arms=(30, 40, 60 + 90 * t, 10), legs=(10, 10, 10, 10)),
                  objects=[("boulder", 40 + 180 * t, -60 + 60 * t * t, 0, False)])


# --- done ------------------------------------------------------------------
def _m_long_backflip(p):
    """Task complete: a long, high backflip across the stage."""
    a = math.sin(min(p, 0.999) * math.pi)
    return _scene(_d(60 - 120 * p, y=95 * a, rot=360 * p, arms=(160, 20, 160, 20),
                     legs=(30 + 50 * a, 80 * a, 30 + 50 * a, 80 * a), ankles=(40, 40)), fx={"speed", "victory"})


def _m_bicycle_kick(p):
    """Then the bicycle kick: airborne, legs cycling, one last ninja flies."""
    a = math.sin(min(p, 0.999) * math.pi)
    c = _sw(p, 3)
    return _scene(_d(0, y=70 * a, rot=-120 * a, arms=(150, 30, 110, 40),
                     legs=(60 + 50 * c, 30, 60 - 50 * c, 30), ankles=(40, 40)),
                  [_n(70 + 120 * p, "fly", y=40 + 60 * a, rot=-300 * p, kind=_kinds_in_play()[0])],
                  fx={"impact", "victory"} if a > 0.8 else {"victory"})


def _m_victory(p):
    return _scene(_d(0, y=4 * abs(_sw(p, 2)), arms=(170, 10, 30, 100), legs=(20, 10, 5, 0)), fx={"victory"})


def _m_double_backflip(p):
    a = math.sin(min(p, 0.999) * math.pi)
    return _scene(_d(0, y=80 * a, rot=720 * p, arms=(160, 20, 160, 20), legs=(70 * a, 110 * a, 70 * a, 110 * a)),
                  fx={"victory", "speed"})


def _m_tornado_kick(p):
    t = math.cos(p * 4 * math.pi)
    a = math.sin(min(p, 0.999) * math.pi)
    return _scene(_d(0, y=40 * a, spin=t, rot=20 * a, arms=(120, 20, 120, 20), legs=(20, 40, 110 * a, 0)),
                  fx={"speed", "victory"})


def _m_victory_bounce(p):
    return _scene(_d(0, y=abs(_sw(p, 3)) * 12, arms=(150, 20, 150, 20), legs=(20, 30, 20, 30)), fx={"victory"})


def _m_arms_crossed(p):
    return _scene(_d(0, head=-8, arms=(60, 130, 60, 130), legs=(20, 0, 20, 0)), fx={"victory"})


# --- helpers: shadow clones --------------------------------------------------
def _m_shadow_clones(p):
    t = _ease(p)
    return _scene(_d(0, arms=(90, 100, 90, 100), wrists=(60, 60), legs=(30, 30, 30, 30)), fx={"clones_out"})


def _m_clones_fight(p):
    return _scene(_d(0, arms=(70, 100, 90, 60), legs=(30, 25, 10, 15)), _attackers(p, 100), fx={"clones"})


def _m_clones_return(p):
    return _scene(_d(0, arms=(90, 100, 90, 100), wrists=(60, 60), legs=(20, 20, 20, 20)), fx={"clones_in"})


def _m_land_crouch(p):
    u = _ease(p)
    return _scene(_d(0, y=30 * (1 - u) - 14 * math.sin(u * math.pi), arms=(110, 20, 60, 40),
                     legs=(60 * (1 - u * 0.5), 90, 40, 70)), fx={"impact"} if u > 0.8 else ())


# --- quiet: under the blossom tree --------------------------------------------
def _m_tree_rest(p):
    b = _sw(p) * 1.5
    return _scene(_d(-110, y=-30 + b, torso=-10, head=8, arms=(40, 80, 40, 80), legs=(85, 90, 85, 100)),
                  fx={"tree", "petals"})


def _m_tree_sleep(p):
    b = _sw(p) * 1
    return _scene(_d(-110, y=-30 + b, torso=-18, head=25, arms=(20, 60, 20, 60), legs=(85, 90, 80, 90)),
                  fx={"tree", "petals", "zzz"})


def _m_doze(p):
    return _scene(_d(-110, y=-30, torso=-14, head=18 + 4 * _sw(p), arms=(30, 70, 30, 70), legs=(85, 90, 85, 90)),
                  fx={"tree", "petals"})


def _m_yawn(p):
    up = math.sin(min(p, 0.999) * math.pi)
    return _scene(_d(-110, y=-30, torso=-10, arms=(30 + 120 * up, 30, 30, 70), legs=(85, 90, 85, 90)),
                  fx={"tree", "petals"})


def _m_lazy_stretch(p):
    up = math.sin(min(p, 0.999) * math.pi)
    return _scene(_d(-110, y=-30, torso=-15 * up, arms=(20 + 150 * up, 10, 20 + 150 * up, 10), legs=(85, 90, 85, 90)),
                  fx={"tree", "petals"})


def _m_kata_stretch(p):
    up = math.sin(min(p, 0.999) * math.pi)
    return _scene(_d(0, arms=(20 + 150 * up, 0, 20 + 150 * up, 0), legs=(5, 0, 5, 0)))


# --- awareness (curious beats) ---------------------------------------------
def _m_scan(p, side=1.0):
    return _scene(_d(0, head=18 * side + 5 * _sw(p), arms=(60, 100, 60, 100), legs=(25, 20, 25, 20)))


def _m_scan_left(p):
    return _m_scan(p, 1.0)


def _m_glance_you(p):
    return _scene(_d(0, spin=0.6, head=-20, arms=(40, 90, 40, 90), legs=(20, 10, 20, 10)))


def _m_alert(p):
    pop = math.sin(min(p, 0.999) * math.pi) * 4
    return _scene(_d(0, y=pop, arms=(120, 80, 120, 80), legs=(30, 30, 30, 30)), _attackers(p, 140))


def _m_peek_cover(p):
    return _scene(_d(-110, y=-10, torso=20, head=-10, arms=(90, 40, 30, 60), legs=(40, 60, 30, 40)),
                  _attackers(p, 120), fx={"tree", "stealth"})


def _m_head_tilt(p):
    return _scene(_d(0, head=18 + 4 * _sw(p), arms=(30, 60, 30, 60), legs=(15, 0, 15, 0)))


def _m_squint(p):
    return _scene(_d(0, torso=12, head=-8, arms=(80, 140, 30, 60), legs=(15, 10, 15, 10)), _attackers(p, 150))


def _m_stroke_beard(p):
    s = _sw(p, 3) * 6
    return _scene(_d(0, head=6, arms=(30, 60, 70, 140 + s), legs=(10, 0, 10, 0)))


def _m_scan_around(p):
    return _scene(_d(0, spin=math.cos(p * 2 * math.pi), head=10 * _sw(p), arms=(60, 100, 60, 100), legs=(25, 20, 25, 20)))


def _m_flail(p):
    w = _sw(p, 4) * 40
    return _scene(_d(0, arms=(100 + w, 20, 100 - w, 20), legs=_step(p, 10)), _attackers(p, 70))


def _m_scratch(p):
    return _scene(_d(0, head=10, arms=(20, 30, 150 + 6 * _sw(p, 5), 150), legs=(10, 0, 10, 0)))


def _m_shake(p):
    return _scene(_d(0, head=10 * _sw(p, 4), arms=(30, 60, 30, 60), legs=(10, 0, 10, 0)))


def _m_bounce(p):
    return _scene(_d(0, y=abs(_sw(p, 2)) * 8, arms=(70, 110, 70, 110), legs=(15, 20, 15, 20), ankles=(30, 30)))


def _m_wait(p):
    tap = abs(_sw(p, 4)) * 14
    return _scene(_d(0, arms=(60, 130, 60, 130), legs=(5, 0, 14 + tap, 10)))


def _m_look_down(p):
    return _scene(_d(0, head=20, torso=8, arms=(20, 30, 20, 30), legs=(5, 0, 5, 0)))


def _m_look_up(p):
    return _scene(_d(0, head=-20, torso=-6, arms=(20, 30, 20, 30), legs=(5, 0, 5, 0)), fx={"moon"})


def _m_juggle(p):
    return _scene(_d(0, arms=(60 + 30 * _sw(p, 2), 60, 60 - 30 * _sw(p, 2), 60), legs=(10, 0, 10, 0)),
                  objects=[("shuriken", -10 + 20 * _sw(p + k / 3, 1), -110 + 20 * abs(_sw(p + k / 3, 1)), 360 * p, False)
                           for k in range(3)])


# --- his own kata moves (decoration only; never a signature) -----------------
def _k_crane(p):
    return _scene(_d(0, arms=(150, 30, 150, 30), wrists=(70, 70), legs=(5, 0, 70, 120), ankles=(0, 50)))


def _k_tiger_claw(p):
    s = _sw(p, 2)
    return _scene(_d(0, torso=10 * s, arms=(90, 60, 90, 60), wrists=(80, 80), legs=(35, 30, 10, 10)))


def _k_snake_strike(p):
    s = max(0.0, _sw(p, 3))
    return _scene(_d(0, torso=15 * s, arms=(40, 120, 70 + 30 * s, 20), wrists=(0, -40), legs=(30, 30, 0, 10)))


def _k_low_sweep(p):
    s = _sw(p, 1)
    return _scene(_d(0, y=-30, spin=s, torso=35, arms=(110, 30, 110, 30), legs=(90, 130, 100, 10)))


def _k_axe_kick(p):
    k = math.sin(min(p, 0.999) * math.pi)
    return _scene(_d(0, torso=-10 * k, arms=(40, 80, 40, 80), legs=(5, 0, 160 * k, 10), ankles=(0, 60 * k)))


def _k_meditate(p):
    return _scene(_d(0, y=-30 + _sw(p) * 1.5, arms=(40, 120, 40, 120), wrists=(60, 60), legs=(85, 110, 85, 110)))


def _k_staff_twirl(p):
    return _scene(_d(0, arms=(100, 40, 100, 40), legs=(20, 15, 20, 15)), objects=[("staff", 0, -70, 720 * p, False)])


def _k_shadow_box(p):
    j = _sw(p, 4)
    return _scene(_d(0, hip=3 * j, arms=(30 + 60 * max(0, j), 100, 30 + 60 * max(0, -j), 100), legs=_step(p, 12)))


def _k_iron_horse(p):
    return _scene(_d(0, y=-16, arms=(90, 0, 90, 0), wrists=(-80, -80), legs=(50, 60, 50, 60), swivel=(-0.6, -0.6)))


def _k_one_finger(p):
    s = _sw(p) * 3
    return _scene(_d(0, y=s, arms=(170, 0, 20, 30), wrists=(0, 0), legs=(5, 0, 5, 0)))


MOVES = {
    "bow_ready": _m_bow_ready, "horse_stance": _m_horse_stance, "leap_ready": _m_leap_ready,
    "wall_run": _m_wall_run, "run_in": _m_run_in, "walk_back": _m_walk_back,
    "jab_cross": _m_jab_cross, "roundhouse": _m_roundhouse, "block_counter": _m_block_counter,
    "palm_strike": _m_palm_strike, "throw_far": _m_throw_far, "staff_disarm": _m_staff_disarm,
    "twin_sweep": _m_twin_sweep, "spin_kick": _m_spin_kick, "flying_kick": _m_flying_kick,
    "elbow_combo": _m_elbow_combo, "dodge_arrows": _m_dodge_arrows,
    "sneak": _m_sneak, "sneak_scan": _m_sneak_scan, "sneak_strike": _m_sneak_strike,
    "hit_react": _m_hit_react, "knocked_down": _m_knocked_down, "roll_away": _m_roll_away,
    "kip_up": _m_kip_up, "wipe_lip": _m_wipe_lip, "breathe": _m_breathe, "ready_again": _m_ready_again,
    "catch_arrow": _m_catch_arrow, "stop_object": _m_stop_object, "beckon_you": _m_beckon_you,
    "bow_small": _m_bow_small, "flip_up": _m_flip_up, "shrug": _m_shrug, "toss_aside": _m_toss_aside,
    "long_backflip": _m_long_backflip, "bicycle_kick": _m_bicycle_kick, "victory": _m_victory,
    "double_backflip": _m_double_backflip, "tornado_kick": _m_tornado_kick,
    "victory_bounce": _m_victory_bounce, "arms_crossed": _m_arms_crossed,
    "shadow_clones": _m_shadow_clones, "clones_fight": _m_clones_fight, "clones_return": _m_clones_return,
    "land_crouch": _m_land_crouch,
    "tree_rest": _m_tree_rest, "tree_sleep": _m_tree_sleep, "doze": _m_doze, "yawn": _m_yawn,
    "lazy_stretch": _m_lazy_stretch, "kata_stretch": _m_kata_stretch,
    "scan_left": _m_scan_left, "glance_you": _m_glance_you, "alert": _m_alert, "peek_cover": _m_peek_cover,
    "head_tilt": _m_head_tilt, "squint": _m_squint, "stroke_beard": _m_stroke_beard,
    "scan_around": _m_scan_around, "flail": _m_flail, "scratch": _m_scratch, "shake": _m_shake,
    "bounce": _m_bounce, "wait": _m_wait, "look_down": _m_look_down, "look_up": _m_look_up,
    "juggle": _m_juggle,
}

# His own kata: decoration around a signature, sorted by mood.
KATA: dict[str, tuple] = {
    "crane_stance": ("calm", _k_crane), "meditate": ("calm", _k_meditate),
    "iron_horse": ("calm", _k_iron_horse), "one_finger": ("calm", _k_one_finger),
    "tiger_claw": ("focused", _k_tiger_claw), "snake_strike": ("focused", _k_snake_strike),
    "shadow_box": ("focused", _k_shadow_box), "staff_twirl": ("focused", _k_staff_twirl),
    "axe_kick": ("bright", _k_axe_kick), "low_sweep": ("bright", _k_low_sweep),
}
MOVES.update({name: fn for name, (_m, fn) in KATA.items()})

# Signature: every engine pose -> one move, so meaning never varies.
MOVE_FOR_POSE: dict[str, str] = {
    "crack_knuckles": "bow_ready", "attention": "horse_stance", "jump": "leap_ready",
    "run_to_workspace": "run_in", "walk_to_workspace": "run_in",
    "dash_to_workspace": "wall_run", "sprint_to_workspace": "wall_run", "tip_to_workspace": "wall_run",
    "work": "jab_cross", "lean_work": "dodge_arrows", "terminal_work": "roundhouse",
    "web_scan": "sneak", "read": "sneak_scan", "file_organize": "staff_disarm",
    "dev_merge": "twin_sweep", "media_paint": "spin_kick", "design_draft": "flying_kick",
    "audio_tune": "elbow_combo", "memory_vault": "sneak_strike",
    "close_workstation": "palm_strike", "celebrate": "throw_far", "return_home": "walk_back",
    "shock": "hit_react", "fall": "knocked_down", "sneak": "roll_away", "recover": "kip_up",
    "inspect": "wipe_lip", "huff": "breathe", "sit_back": "hit_react", "retry": "ready_again",
    "repair": "block_counter",
    "wake": "catch_arrow", "panic": "catch_arrow", "run_to_user": "stop_object", "wave": "beckon_you",
    "wait": "stop_object", "point": "stop_object",
    "nod": "bow_small", "hop": "flip_up", "shrug": "shrug", "discard": "toss_aside",
    "leap": "long_backflip", "double_jump": "bicycle_kick", "excited": "victory",
    "open_portal": "shadow_clones", "channel": "clones_fight", "orb_exits": "clones_fight",
    "orb_returns": "clones_return", "absorb": "clones_return", "fly_up": "flying_kick",
    "fly_down": "land_crouch",
    "idle_bob": "tree_rest", "idle": "tree_rest", "sleep": "tree_sleep", "sit": "tree_sleep",
    "stretch": "kata_stretch", "dance": "spin_kick", "spin": "tornado_kick",
    "look_at_input": "scan_left", "watch": "scan_left", "look_at_user": "glance_you",
    "notice": "alert", "eyebrow_raise": "alert", "peeking": "peek_cover", "head_tilt": "head_tilt",
    "tilt": "head_tilt", "squint": "squint", "think": "stroke_beard", "look_around": "scan_around",
    "arm_flap": "flail", "scratch_head": "scratch", "shake_head": "shake",
    "bounce": "bounce", "check_watch": "wait", "look_down": "look_down", "look_up": "look_up",
    "play_with_object": "juggle",
    "full_bounce": "victory_bounce", "leap_double_joy": "double_backflip", "smug": "arms_crossed",
    "spin_joy": "tornado_kick",
    "head_drop": "doze", "stretch_lazy": "lazy_stretch", "yawn": "yawn",
}
MOVE_FOR_POSE.update({name: name for name in KATA})

_MOVE_MOOD = {
    "long_backflip": "joy", "bicycle_kick": "joy", "victory": "joy", "double_backflip": "joy",
    "tornado_kick": "joy", "victory_bounce": "joy", "arms_crossed": "joy", "throw_far": "joy",
    "catch_arrow": "approve", "stop_object": "approve", "beckon_you": "approve",
    "hit_react": "fail", "knocked_down": "fail", "roll_away": "fail", "kip_up": "fail",
    "wipe_lip": "fail", "flail": "fail", "scratch": "fail", "shake": "fail",
    "shadow_clones": "delegate", "clones_fight": "delegate", "clones_return": "delegate",
    "tree_rest": "rest", "tree_sleep": "rest", "doze": "rest", "yawn": "rest", "lazy_stretch": "rest",
    "sneak": "work", "sneak_scan": "work", "sneak_strike": "work", "dodge_arrows": "work",
}
_MOVE_MOOD.update({name: {"bright": "joy", "focused": "work"}.get(m, "calm") for name, (m, _f) in KATA.items()})


def move_for(pose: str) -> str | None:
    return MOVE_FOR_POSE.get(pose)


def kata_flourishes() -> dict[str, tuple[str, ...]]:
    out: dict[str, list[str]] = {}
    for name, (mood, _fn) in KATA.items():
        out.setdefault(mood, []).append(name)
    return {k: tuple(v) for k, v in out.items()}


CATEGORY_HINTS = {
    "terminal": ("shadow_box", "snake_strike"), "development": ("tiger_claw", "shadow_box"),
    "web": ("crane_stance", "one_finger"), "file": ("staff_twirl",), "docs": ("staff_twirl",),
    "memory": ("meditate", "iron_horse"), "media": ("axe_kick", "low_sweep"),
}


def flourish_hints() -> dict[str, tuple[str, ...]]:
    return dict(CATEGORY_HINTS)


CURIOUS_MOVES = ("crane_stance", "one_finger", "iron_horse")
VOICE = {
    "starting": "Come, then.", "reviewing": "I see you there...",
    "needs-you": "Your word, before I strike.", "issue": "A lucky hit. Again.",
    "complete": "It is done.", "paused": "I will wait.",
}
GREETING = "Sensei is ready."


def _palette(name):
    return PALETTES.get(name or DEFAULT_PALETTE, PALETTES[DEFAULT_PALETTE])


# ---------------------------------------------------------------------------
# Drawing
# ---------------------------------------------------------------------------
HIP_Y = FLOOR - 46


HAND_FORMS = ("fist", "palm", "knife", "tiger", "crane", "leopard", "snake", "dragon")


def _hand_form(b, wrist, elbow, side, flick, form, skin, shade):
    """A real hand shape at the wrist, laid along the forearm.

    fist (knuckles + thumb across), palm (open, fingers up), knife (shuto
    edge), tiger (curled claws), crane (fingertips pinched to a beak),
    leopard (half fist, second knuckles forward), snake (spear-hand, fingers
    together) and dragon (spread, hooked fingers).
    """
    hx, hy = wrist
    ex, ey = elbow
    ang = math.atan2(hy - ey, hx - ex) + math.radians(side * flick)
    ux, uy = math.cos(ang), math.sin(ang)
    vx, vy = -uy * side, ux * side

    def at(a, c):
        return (hx + ux * a + vx * c, hy + uy * a + vy * c)

    dark = _mix(skin, "#000000", 0.45)
    if form == "palm":
        b.dot(*at(1.5, 0), 3.6, edge=True, fill=skin, outline="")
        for c in (-2.4, -0.8, 0.8, 2.4):
            b.line([at(3.5, c), at(8.5 - abs(c) * 0.5, c * 1.25)], edge=True, width=1.8, fill=skin)
        b.line([at(1.0, -3.2), at(3.5, -5.6)], edge=True, width=1.8, fill=skin)          # thumb out
        b.line([at(0.5, -1.5), at(2.5, 1.5)], width=1, fill=shade)                      # palm crease
    elif form == "knife":
        b.poly([at(-0.5, -2.6), at(8.5, -2.0), at(9.2, 0.6), at(-0.5, 2.6)], edge=True, fill=skin)
        b.line([at(0, 2.6), at(9.0, 0.8)], width=1.4, fill=shade)                       # striking edge
        b.line([at(1.5, -2.6), at(4.5, -1.0)], width=1.4, fill=dark)                    # thumb tucked
    elif form == "tiger":
        b.dot(*at(1.5, 0), 3.8, edge=True, fill=skin, outline="")
        for c in (-2.6, -0.9, 0.9, 2.6):
            b.line([at(3.0, c), at(6.4, c * 1.35), at(6.0, c * 1.35 + 2.2)], edge=True, width=1.7, fill=skin)
        b.line([at(0.5, -3.4), at(3.2, -5.4), at(4.2, -3.8)], edge=True, width=1.7, fill=skin)
    elif form == "crane":
        b.poly([at(-0.5, -2.8), at(-0.5, 2.8), at(7.5, 0.3)], edge=True, fill=skin)
        b.line([at(1.5, -1.6), at(6.5, 0.2)], width=1, fill=shade)
        b.dot(*at(7.4, 0.3), 1.0, fill=dark, outline="")                                # the beak
    elif form == "leopard":
        b.poly([at(-0.5, -3.2), at(4.0, -3.2), at(6.0, -1.8), at(6.0, 1.8), at(4.0, 3.2), at(-0.5, 3.2)],
               edge=True, fill=skin)
        for c in (-1.6, 0, 1.6):
            b.line([at(4.2, c - 0.6), at(6.0, c)], width=1, fill=dark)                  # flat second knuckles
        b.line([at(1.0, -3.2), at(3.0, -0.8)], width=1.4, fill=shade)
    elif form == "snake":
        b.poly([at(-0.5, -2.4), at(8.5, -1.0), at(11.0, 0), at(8.5, 1.0), at(-0.5, 2.4)], edge=True, fill=skin)
        for c in (-0.6, 0.6):
            b.line([at(3.0, c), at(9.0, c * 0.6)], width=1, fill=shade)                 # fingers pressed together
    elif form == "dragon":
        b.dot(*at(1.5, 0), 3.6, edge=True, fill=skin, outline="")
        for k, c in enumerate((-3.6, -1.4, 0.6, 2.6)):
            b.line([at(3.0, c * 0.8), at(7.2, c * 1.6), at(8.2, c * 1.6 + 1.6)], edge=True, width=1.6, fill=skin)
        b.line([at(0.5, -3.4), at(2.2, -6.4), at(3.6, -6.0)], edge=True, width=1.6, fill=skin)
    else:  # fist
        b.poly([at(-0.5, -3.4), at(5.0, -3.4), at(6.2, -2.0), at(6.2, 2.0), at(5.0, 3.4), at(-0.5, 3.4)],
               edge=True, fill=skin)
        for c in (-2.0, -0.6, 0.8, 2.2):
            b.dot(*at(5.4, c), 0.8, fill=dark, outline="")                              # knuckles
        b.line([at(1.0, -3.4), at(3.6, -1.0), at(3.8, 1.0)], width=1.6, fill=shade)     # thumb across


def _draw_fighter(canvas, P, hx, hy, st, eyes, *, ninja=None, clone=None):
    """Sensei (ninja=None) or a ninja (ninja=(kind, colour)) on the shared rig."""
    if ninja:
        kind, colour = ninja
        suit = "#4c1d95" if kind == "shadow" else "#1b1c24"
        skin, edge = "#c79a7a", "#05060a"
    elif clone:
        suit, skin, edge, colour = clone, _mix(clone, "#ffffff", 0.25), _mix(clone, "#000000", 0.5), clone
    else:
        suit, skin, edge, colour = P["gi"], P["skin"], P["edge"], P["band"]
    body = _Body(canvas, hx, hy, st["spin"], st["rot"], edge)
    back = st["spin"] < 0
    shade = _mix(skin, "#000000", 0.22)
    pants = suit if (ninja or clone) else P["pants"]
    hip = st.get("hip", 0.0)
    ankles, swivel = st.get("ankles", (0, 0)), st.get("swivel", (0, 0))
    wrists, shoulders = st.get("wrists", (0, 0)), st.get("shoulders", (0, 0))
    hands = {}
    for i, (side, (hip_a, knee)) in enumerate(((-1, st["legs"][0:2]), (1, st["legs"][2:4]))):
        a, k, f = _limb_pts(hip + side * 6, 0, hip_a, knee, 22, 22, side)
        body.line([a, k, f], edge=True, width=11 if not ninja else 9, fill=pants)
        if not clone:                                        # cloth crease down the thigh, knee fold
            body.line([((a[0] * 2 + k[0]) / 3 + 2, (a[1] * 2 + k[1]) / 3), (k[0] + 1.5, k[1] - 1)],
                      width=1, fill=_mix(pants, "#000000", 0.28))
            body.dot(k[0], k[1], 2.2, fill=_mix(pants, "#000000", 0.18), outline="")
        if ninja:                                            # wrapped shins
            for t in (0.55, 0.75):
                body.line([(k[0] + (f[0] - k[0]) * t - 3, k[1] + (f[1] - k[1]) * t),
                           (k[0] + (f[0] - k[0]) * t + 3, k[1] + (f[1] - k[1]) * t)], width=1, fill="#3a3b48")
        _foot(body, f, side, ankles[i], swivel[i], "#2a2a33" if ninja else (skin if not clone else suit))
    twist = st.get("twist", 0.0)
    chest = _Joint(body, (hip, 0), st.get("torso", 0.0), twist=twist)
    chest.poly([(-14, -46), (14, -46), (12, 2), (-12, 2)], edge=True, fill=suit)
    if not clone:                                            # far side in shade; turning shows more of it
        far = 1 if twist >= 0 else -1
        depth = 4 + min(8.0, abs(twist) / 6)
        chest.poly([(far * (14 - depth), -46), (far * 14, -46), (far * 12, 2), (far * (12 - depth), 2)],
                   fill=_mix(suit, "#000000", 0.25), outline="")
        for fy in (-36, -26):                                # cloth folds from the armpit
            chest.line([(-far * 12, fy), (-far * 4, fy + 6)], width=1, fill=_mix(suit, "#000000", 0.3))
    if not ninja and not clone:                              # gi lapels + trim
        chest.poly([(-14, -46), (-4, -46), (6, -18), (-4, -14)], fill=P["gi_hi"], outline="")
        chest.line([(-6, -46), (5, -18)], width=2, fill=P["trim"])
        chest.line([(6, -46), (-2, -30)], width=2, fill=P["trim"])
    chest.line([(-12, -8), (12, -8)], width=4, fill=colour if ninja else (P["belt"] if not clone else edge))  # belt / sash
    flow, wave = st.get("_flow", 0.0), st.get("_wave", 0.0)
    sash = colour if ninja else (P["belt"] if not clone else edge)
    chest.dot(5, -8, 3, fill=sash, outline=_mix(sash, "#000000", 0.4))                  # the knot
    for k in (0, 1):                                         # two tails that stream with speed
        tx = 6 - 10 * flow - k * 3
        ty = 6 + 4 * (1 - flow) + math.sin(wave + k) * 2 * flow
        chest.line([(5, -7), (5 + (tx - 5) * 0.5, -1 + k), (tx, ty + k * 2)], width=3, fill=sash)
    for i, (side, (shd, elb)) in enumerate(((-1, st["arms"][0:2]), (1, st["arms"][2:4]))):
        sh_y = -42 - shoulders[i]
        a, e, h = _limb_pts(side * 13, sh_y, 180 - shd if shd > 90 else shd, elb, 17, 16, side)
        if shd > 90:
            a, e, h = (a, (e[0], 2 * sh_y - e[1]), (h[0], 2 * sh_y - h[1]))
        chest.line([a, e], edge=True, width=8, fill=suit)
        chest.line([e, h], edge=True, width=6, fill=suit if ninja else skin)
        if not ninja and not clone:
            chest.dot(e[0], e[1], 4, fill=P["gi_hi"], outline=P["trim"])           # sleeve cuff
        form = (st.get("hands") or ("fist", "fist"))[i]
        _hand_form(chest, h, e, side, wrists[i], form, skin if not ninja else "#2a2a33",
                   shade if not ninja else "#111118")
        hands["left" if side < 0 else "right"] = chest.pt(*h)
    head_y = -60
    chest.line([(0, -46), (0, head_y + 10)], edge=True, width=6, fill=skin if not ninja else suit)
    hb = _Joint(chest, (0, -50), st.get("head", 0.0))
    if ninja:                                                # hood with an eye slit
        hb.dot(0, head_y, 12, edge=True, fill=suit, outline="", squash=True)
        if not back:
            hb.poly([(-9, head_y - 4), (9, head_y - 4), (9, head_y + 2), (-9, head_y + 2)], fill=skin, outline="")
            for sd in (-1, 1):
                hb.line([(sd * 6, head_y - 1), (sd * 2, head_y - 2)], width=2, fill="#111111")
        hb.line([(-12, head_y - 7), (12, head_y - 7)], width=3, fill=colour)        # headband
        hb.line([(12, head_y - 7), (20 + 6 * flow, head_y - 4 + math.sin(wave) * 2 * flow),
                 (24 + 12 * flow, head_y + 4 - 8 * flow)], width=2, fill=colour)
        return hands
    hb.dot(0, head_y, 12.5, edge=True, fill=skin, outline="", squash=True)
    hair = P["hair"] if not clone else edge
    hb.dot(0, head_y - 14, 5, edge=True, fill=hair, outline="")                     # topknot
    hb.dot(0, head_y - 6, 12, fill=hair, outline="", squash=True)
    hb.dot(0, head_y - 1, 11, fill=skin, outline="", squash=True)
    band = P["band"] if not clone else colour
    hb.line([(-12, head_y - 6), (12, head_y - 6)], width=3, fill=band)             # headband + tails
    for k in (0, 1):                                         # tails trail further the faster he moves
        hb.line([(-12, head_y - 6 + k), (-20 - 6 * flow, head_y - 3 + math.sin(wave + k) * 3 * flow),
                 (-28 - 14 * flow - k * 4, head_y + 4 - 9 * flow + k * 3)], width=2, fill=band)
    if back or clone:
        if back:
            hb.dot(0, head_y - 1, 12.6, fill=hair, outline="", squash=True)
        return hands
    gx = {"left": -2.5, "right": 2.5}.get(eyes, 0.0)
    for sd in (-1, 1):
        hb.line([(sd * 8, head_y - 3), (sd * 2.5, head_y - 4.5)], width=2, fill=_mix(hair, "#000000", 0.3))  # brows
        if eyes == "closed":
            hb.line([(sd * 5 - 2, head_y), (sd * 5 + 2, head_y)], width=1, fill="#1a1010")
        else:
            hb.dot(sd * 5 + gx, head_y, 1.7 if eyes != "wide" else 2.3, fill="#1a1010", outline="")
    hb.line([(0, head_y + 1), (-1, head_y + 4), (0.8, head_y + 4.5)], width=1, fill=shade)
    hb.poly([(-9, head_y + 4), (9, head_y + 4), (4, head_y + 20), (0, head_y + 24), (-4, head_y + 20)],
            fill=P["beard"], outline=_mix(P["beard"], "#000000", 0.3))             # long beard
    hb.line([(-5, head_y + 5), (0, head_y + 4), (5, head_y + 5)], width=2, fill=P["beard"])
    hb.line([(-3, head_y + 7.5), (3, head_y + 7.5)], width=1, fill="#5a2e1a")
    return hands


def _weapon(canvas, kind, hand, colour, p):
    if not hand:
        return
    x, y = hand
    if kind == "shuriken":
        _shuriken(canvas, x + 6, y - 4, 6, p * 720, "#cbd5e1")
    elif kind == "kunai_rope":
        canvas.create_line(x, y, x + 12, y - 6, fill="#cbd5e1", width=3)
        canvas.create_line(x, y, x - 10, y + 10, x - 4, y + 22, fill="#a16207", width=1, smooth=True)
    elif kind == "bo_staff":
        canvas.create_line(x - 22, y + 18, x + 22, y - 18, fill="#a16207", width=4, capstyle="round")
    elif kind == "twin_blades":
        for dy in (-3, 3):
            canvas.create_line(x, y + dy, x + 18, y + dy - 10, fill="#e2e8f0", width=2)
    elif kind == "smoke_bomb":
        canvas.create_oval(x + 2, y - 6, x + 10, y + 2, fill="#334155", outline="#0f172a")
        for k in range(3):
            canvas.create_oval(x + 6 + k * 5, y - 14 - k * 4, x + 14 + k * 6, y - 6 - k * 4, fill="#e2e8f0", outline="")


def _shuriken(canvas, x, y, r, ang, colour):
    pts = []
    for k in range(8):
        rr = r if k % 2 == 0 else r * 0.35
        a = math.radians(ang) + k * math.pi / 4
        pts += [x + math.cos(a) * rr, y + math.sin(a) * rr]
    canvas.create_polygon(*pts, fill=colour, outline="#0f172a")
    canvas.create_oval(x - 1.5, y - 1.5, x + 1.5, y + 1.5, fill="#0f172a", outline="")


def _arrow(canvas, x, y, ang):
    a = math.radians(ang)
    dx, dy = math.cos(a) * 22, math.sin(a) * 22
    canvas.create_line(x, y, x + dx, y + dy, fill="#a16207", width=2)
    canvas.create_polygon(x, y, x + math.cos(a + 2.6) * 6, y + math.sin(a + 2.6) * 6,
                          x + math.cos(a - 2.6) * 6, y + math.sin(a - 2.6) * 6, fill="#cbd5e1", outline="")
    for k in (-1, 1):
        canvas.create_line(x + dx, y + dy, x + dx + math.cos(a + k * 0.5) * 6, y + dy + math.sin(a + k * 0.5) * 6,
                           fill="#f8fafc", width=2)


def _tree(canvas, x, big, p):
    """The blossom tree he rests under."""
    s = 1.25 if big else 0.9
    base = FLOOR + 2
    canvas.create_polygon(x - 7 * s, base, x + 7 * s, base, x + 4 * s, base - 70 * s, x - 3 * s, base - 70 * s,
                          fill="#5b3a29", outline="#2b1a10")
    canvas.create_line(x, base - 50 * s, x + 26 * s, base - 82 * s, fill="#5b3a29", width=round(5 * s))
    canvas.create_line(x, base - 60 * s, x - 24 * s, base - 88 * s, fill="#5b3a29", width=round(4 * s))
    for k, (dx, dy, r) in enumerate(((0, -96, 26), (-26, -86, 20), (26, -84, 22), (-10, -110, 18), (16, -108, 18))):
        canvas.create_oval(x + (dx - r) * s, base + (dy - r) * s, x + (dx + r) * s, base + (dy + r) * s,
                           fill=("#f9a8d4", "#fbcfe8", "#f472b6")[k % 3], outline="")
    for k in range(9):
        bx = x + (k * 37 % 80 - 40) * s
        by = base - 120 * s + (k * 23 % 60) * s
        canvas.create_oval(bx - 2, by - 2, bx + 2, by + 2, fill="#ffffff", outline="")


def _petals(canvas, x, p):
    for k in range(10):
        px = x - 30 + (k * 29 + p * 90) % 120
        py = FLOOR - 140 + ((p * 110 + k * 31) % 140)
        canvas.create_oval(px - 3, py - 1.5, px + 3, py + 1.5, fill="#f9a8d4", outline="")


def _burst(canvas, x, y, colour):
    for k in range(8):
        a = k * math.pi / 4
        canvas.create_line(x + math.cos(a) * 5, y + math.sin(a) * 5, x + math.cos(a) * 13,
                           y + math.sin(a) * 13, fill=colour, width=2)


POSE_STATUS = {
    "crack_knuckles": "Starting a task", "attention": "Ready", "jump": "On it",
    "run_to_workspace": "Heading in", "walk_to_workspace": "Heading in",
    "dash_to_workspace": "Starting a step", "sprint_to_workspace": "Starting a step",
    "tip_to_workspace": "Starting a step",
    "work": "Working", "lean_work": "Still working", "terminal_work": "Running a command",
    "web_scan": "Searching the web", "read": "Reading", "file_organize": "Working with files",
    "dev_merge": "Working on code", "media_paint": "Making media", "design_draft": "Designing",
    "audio_tune": "Working on audio", "memory_vault": "Using memory",
    "close_workstation": "Step finished", "celebrate": "Step finished", "return_home": "Step done",
    "shock": "A step failed", "fall": "A step failed", "sneak": "A step failed",
    "recover": "Recovering", "inspect": "Checking what broke", "huff": "Catching breath",
    "sit_back": "A helper failed", "retry": "Trying again", "repair": "Fixing it",
    "wake": "Needs your OK", "panic": "Needs your OK", "run_to_user": "Needs your OK",
    "wave": "Calling you", "wait": "Waiting for your OK", "point": "Needs your OK",
    "nod": "You answered", "hop": "Approved - going", "shrug": "You declined", "discard": "Dropped that step",
    "leap": "Task complete!", "double_jump": "Task complete!", "excited": "Helper finished",
    "open_portal": "Sending out helpers", "channel": "Helpers working", "orb_exits": "Helpers working",
    "orb_returns": "A helper is back", "absorb": "Taking the helper's work",
    "fly_up": "Helper finished", "fly_down": "Helper finished",
    "idle_bob": "Quiet", "idle": "Quiet", "sleep": "Resting", "sit": "Resting",
    "look_at_input": "Watching you type", "watch": "Watching you type", "look_at_user": "Looking at you",
    "notice": "Noticed something", "eyebrow_raise": "Noticed something", "think": "Thinking",
    "look_around": "Looking around", "tilt": "Wondering", "head_tilt": "Wondering",
    "stretch": "You're back", "stretch_lazy": "Taking it easy", "yawn": "Getting sleepy",
    "head_drop": "Resting", "check_watch": "Waiting",
}
_MOOD_WORD = {"work": "Working", "delegate": "Delegating", "fail": "Problem", "approve": "Needs you",
              "joy": "Done", "curious": "Curious", "rest": "Resting", "calm": "Ready"}


def status_text(pose: str, mood: str) -> tuple[str, str]:
    """(headline, detail): what Hermes is doing, from event kinds, categories and counts only."""
    st = STATE
    headline = POSE_STATUS.get(pose) or _MOOD_WORD.get(mood, "Ready")
    detail = []
    if st.running and mood in ("work", "fail", "calm", "curious"):
        weapons = sorted({_kind(c)[0].replace("_", " ") for c in st.tools})
        detail.append(f"{st.running} ninja{'s' if st.running != 1 else ''} ({', '.join(weapons)})")
    if st.helpers:
        detail.append(f"{st.helpers} clone{'s' if st.helpers != 1 else ''} out")
    if mood == "approve" and st.danger:
        headline, detail = "Needs your OK", ["dangerous command"] + detail
    if st.missteps and mood in ("fail", "work"):
        detail.append(f"{st.missteps} hit{'s' if st.missteps != 1 else ''} taken")
    if mood == "joy" and st.defeated:
        detail.append(f"{st.defeated} down")
    if st.thinking and mood not in ("approve", "fail"):
        headline = "Thinking"
    return headline, " \u00b7 ".join(detail)


def _indicators(canvas, pose, mood, glow):
    st = STATE
    chips = []
    if st.danger:
        chips.append(("dangerous", "#ef4444"))
    if st.running:
        chips.append((f"{st.running} ninja{'s' if st.running != 1 else ''}", _kind(st.tools[-1])[1]))
    if st.helpers:
        chips.append((f"{st.helpers} clone{'s' if st.helpers != 1 else ''}", MOOD_COLORS["delegate"]))
    if st.missteps:
        chips.append((f"{st.missteps} hit{'s' if st.missteps != 1 else ''}", MOOD_COLORS["fail"]))
    if st.defeated:
        chips.append((f"{st.defeated} down", MOOD_COLORS["joy"]))
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


def draw_master(canvas, pose: str, progress: float = 0.0, palette: str | None = None) -> None:
    P = _palette(palette)
    canvas.delete("all")
    p = progress % 1.0
    move = MOVE_FOR_POSE.get(pose)
    prm = pose_params(pose, progress)
    if move is not None:
        sc = MOVES[move](p)
        mood = _MOVE_MOOD.get(move) or mood_of(pose)
    else:  # unknown pose: a ready stance that still honours gaze, lean and bob
        sc = _m_horse_stance(p)
        m = sc["master"]
        sc["master"] = {**m, "rot": m["rot"] + prm["lean"] * 120, "y": m["y"] - prm["bob"]}
        mood = mood_of(pose)
    glow = MOOD_COLORS.get(mood, MOOD_COLORS["calm"])
    if STATE.danger and mood == "approve":
        glow = "#ef4444"
    elif mood == "work" and STATE.tools:
        glow = _kind(STATE.tools[-1])[1]
    fx = sc["fx"]
    # how fast he is moving right now: belt and headband tails stream with it
    m = sc["master"]
    if move is not None:
        prev = MOVES[move](max(0.0, p - 0.03))["master"]
        speed = (math.hypot(m["x"] - prev["x"], m["y"] - prev["y"]) + abs(m["rot"] - prev["rot"]) / 8
                 + abs(m.get("twist", 0.0) - prev.get("twist", 0.0)) / 6)
        m["_flow"] = min(1.0, speed / 6)
    m["_wave"] = p * 2 * math.pi * 3

    # sky + moon, mat, tree
    canvas.create_oval(FRAME[0] - 70, 26, FRAME[0] - 40, 56, fill=P["moon"], outline="")
    _tree(canvas, 46, "tree" in fx, p)
    if "petals" in fx or "tree" in fx:
        _petals(canvas, 60, p)
    if "wall" in fx:
        wx = MX + 150
        canvas.create_rectangle(wx, 40, FRAME[0] - 4, FLOOR, fill="#57534e", outline="#292524", width=2)
        for row in range(0, int(FLOOR - 40), 16):
            for col in range(0, 60, 22):
                ox = 11 if (row // 16) % 2 else 0
                canvas.create_rectangle(wx + col + ox, 40 + row, wx + col + ox + 22, 56 + row,
                                        fill="", outline="#78716c")
    canvas.create_oval(MX - 150, FLOOR - 10, MX + 190, FLOOR + 10, fill=glow, outline="")
    canvas.create_oval(MX - 128, FLOOR - 6, MX + 168, FLOOR + 6, fill="#e7e5e4", outline="")
    for k in range(9):                                       # mat seams
        sx = MX - 110 + k * 32
        canvas.create_line(sx, FLOOR - 4, sx + 4, FLOOR + 4, fill="#d6d3d1", width=1)
    # ground shadows: smaller and lighter the higher a fighter is off the floor
    for who in [m] + [nj for nj in sc["ninjas"] if nj["state"] != "down"]:
        lift = max(0.0, who["y"])
        w = 26 * max(0.35, 1 - lift / 140)
        cx = MX + who["x"]
        canvas.create_oval(cx - w, FLOOR - 3, cx + w, FLOOR + 3,
                           fill="#a8a29e" if lift < 50 else "#c4bfba", outline="")

    # shadow clones (helpers)
    if fx & {"clones", "clones_out", "clones_in"}:
        n = max(1, STATE.helpers)
        for k in range(n):
            reach = (_ease(p) if "clones_out" in fx else (1 - _ease(p)) if "clones_in" in fx else 1.0)
            ox = -(50 + 40 * k) * reach
            _draw_fighter(canvas, P, MX + sc["master"]["x"] + ox, HIP_Y - sc["master"]["y"], sc["master"],
                          "neutral", clone="#7c3aed")

    # ninjas
    ninja_hands = []
    for nj in sc["ninjas"]:
        kind, colour = _kind(nj["kind"] or "general")
        st = dict(nj)
        if nj["state"] == "down":
            st = {**st, "rot": 90, "y": -36}
        hx, hy = MX + nj["x"], HIP_Y - st["y"]
        hands = _draw_fighter(canvas, P, hx, hy, st, "neutral", ninja=(kind, colour))
        if nj["state"] not in ("down", "fly") and not nj.get("disarmed"):
            lead = nj.get("act") in ("overhead", "chop")         # swinging it at him
            _weapon(canvas, kind, hands.get("left" if lead else "right"), colour, p)
        if nj["state"] == "fly":
            for k in range(4):
                canvas.create_line(hx - 20 - k * 8, hy - 30 + k * 6, hx - 6 - k * 8, hy - 30 + k * 6,
                                   fill="#94a3b8", width=2)
        if nj["state"] == "stagger":
            for k in range(3):
                a = p * 6.28 + k * 2.1
                canvas.create_text(hx + math.cos(a) * 12, hy - 80 + math.sin(a) * 4, text="*",
                                   fill="#facc15", font=("Segoe UI", 10, "bold"))
        ninja_hands.append((hx, hy))

    # Sensei
    mhx, mhy = MX + m["x"], HIP_Y - m["y"]
    if "trail" in fx and move is not None:                   # afterimages of where he just was
        for k, dt in ((2, 0.09), (1, 0.045)):
            g = MOVES[move](max(0.0, p - dt))["master"]
            _draw_fighter(canvas, P, MX + g["x"], HIP_Y - g["y"], g, "neutral",
                          clone=_mix(glow, "#ffffff", 0.35 + 0.2 * k))
    if "dust" in fx:                                         # puffs kicked up at the feet
        for k in range(6):
            side = -1 if k % 2 else 1
            r = 3 + (k % 3) * 2 + 4 * p
            dx = side * (14 + k * 5 + 10 * p)
            canvas.create_oval(mhx + dx - r, FLOOR - 4 - r - k, mhx + dx + r, FLOOR - 4 + r - k,
                               fill=("#d6d3d1", "#e7e5e4", "#a8a29e")[k % 3], outline="")
    if "speed" in fx:
        for k in range(4):
            canvas.create_line(mhx - 40 - k * 6, mhy - 50 + k * 10, mhx - 18 - k * 6, mhy - 50 + k * 10,
                               fill="#94a3b8", width=2)
    hands = _draw_fighter(canvas, P, mhx, mhy, m, prm["eyes"])

    # arrows + objects
    for ax, ay, ang in sc["arrows"]:
        _arrow(canvas, ax, HIP_Y + ay, ang)
    for obj in sc["objects"]:
        kind, ox, oy, ang = obj[:4]
        held = obj[4] if len(obj) > 4 else False
        x, y = MX + ox, HIP_Y + oy
        if kind == "boulder":
            canvas.create_oval(x - 16, y - 14, x + 16, y + 14, fill="#78716c", outline="#292524", width=2)
            canvas.create_line(x - 8, y - 4, x + 2, y + 2, fill="#44403c", width=2)
        elif kind == "shuriken":
            _shuriken(canvas, x, y, 7, ang, "#e2e8f0")
        elif kind == "staff":
            a = math.radians(ang)
            canvas.create_line(x - math.cos(a) * 30, y - math.sin(a) * 30, x + math.cos(a) * 30,
                               y + math.sin(a) * 30, fill="#a16207", width=4, capstyle="round")
        elif kind == "arrow_held":
            _arrow(canvas, x - 10, y, 0)
        if held:
            canvas.create_oval(x - 24, y - 22, x + 24, y + 22, fill="", outline="#fbbf24", width=2)
    for sx, sy in sc.get("sparks", ()):                       # contact: a block or a check meets a strike
        x, y = MX + sx, HIP_Y + sy
        _burst(canvas, x, y, "#f8fafc")
        canvas.create_oval(x - 3, y - 3, x + 3, y + 3, fill="#fde68a", outline="")
    if "freeze" in fx:
        canvas.create_oval(mhx - 60, mhy - 120, mhx + 90, mhy + 10, fill="", outline=glow, width=2)
    if "impact" in fx and ninja_hands:
        hx, hy = ninja_hands[0]
        _burst(canvas, hx - 10, hy - 50, "#facc15")
    if "block" in fx:
        canvas.create_arc(mhx - 10, mhy - 90, mhx + 40, mhy - 30, start=-60, extent=120, style="arc",
                          outline="#60a5fa", width=3)
    if "hit" in fx:
        _burst(canvas, mhx, mhy - 70, "#fb7185")
    if "stealth" in fx:
        for k in range(4):
            canvas.create_oval(mhx - 40 - k * 16, FLOOR - 2, mhx - 34 - k * 16, FLOOR + 1, fill="#475569", outline="")
    if "zzz" in fx:
        for k in range(3):
            canvas.create_text(mhx + 18 + k * 9, mhy - 96 - k * 10 - (p * 8) % 8, text="z",
                               fill="#c4b5fd", font=("Segoe UI", 9 + k * 2, "bold"))
    if "victory" in fx or STATE.partying:
        for k in range(14):
            x = 20 + (k * 53) % (FRAME[0] - 40)
            y = 10 + ((p * 160 + k * 23) % 170)
            canvas.create_rectangle(x, y, x + 4, y + 2, fill=("#facc15", "#f472b6", "#60a5fa", "#34d399")[k % 4],
                                    outline="")
    if STATE.thinking:
        for j in range(3):
            on = (int(p * 6) + j) % 3 == 0
            canvas.create_oval(mhx - 8 + j * 8, mhy - 110, mhx - 4 + j * 8, mhy - 106,
                               fill="#475569" if on else "#cbd5e1", outline="")
    if pose in EXCLAIM:
        _bubble(canvas, mhx, 26, "!", glow)
    elif pose in WONDER:
        _bubble(canvas, mhx, 26, "?", glow)
    _indicators(canvas, pose, mood, glow)


# ===========================================================================
# Real stances and styles, keyframed.
#
# Stances follow their weight: ma bu / kiba dachi 50/50; gong bu / zenkutsu
# ~70% front; kokutsu ~70% back; xu bu / neko ashi almost all on the back leg
# with the front toe touching; pu bu sits on one bent leg with the other
# straight out; xie bu crosses and sits back; du li stands on one leg with the
# raised thigh at least level. Techniques are keyframed (chamber -> strike ->
# follow-through -> recover) with easing between keys, not a single sine.
# ===========================================================================
_LERP_KEYS = ("x", "y", "spin", "rot", "torso", "hip", "head", "twist")
_TUPLE_KEYS = ("arms", "legs", "wrists", "ankles", "swivel", "shoulders")


def _mix_pose(a: dict, b: dict, t: float) -> dict:
    out = dict(a)
    for k in _LERP_KEYS:
        out[k] = a.get(k, 0.0) + (b.get(k, 0.0) - a.get(k, 0.0)) * t
    for k in _TUPLE_KEYS:
        av, bv = a.get(k), b.get(k)
        if av is not None and bv is not None:
            out[k] = tuple(x + (y - x) * t for x, y in zip(av, bv))
    out["hands"] = a.get("hands") if t < 0.5 else b.get("hands", a.get("hands"))
    for k in ("state", "act"):
        if k in a or k in b:
            out[k] = a.get(k) if t < 0.5 else b.get(k, a.get(k))
    return out


def _kf(p: float, keys: list) -> dict:
    """Interpolate keyframes [(t, pose), ...] at progress p with smooth easing."""
    p = min(max(p, 0.0), 0.9999)
    for (t0, a), (t1, b) in zip(keys, keys[1:]):
        if t0 <= p <= t1:
            return _mix_pose(a, b, _ease((p - t0) / (t1 - t0 or 1)))
    return dict(keys[-1][1])


def _pose(stance: str = "ready", **kw) -> dict:
    """A full pose built on a named stance, overridden by any joint in kw."""
    base = dict(STANCES[stance])
    base.update(kw)
    hands = base.pop("hands", ("fist", "fist"))
    twist = base.pop("twist", 0.0)
    d = _d(**{k: v for k, v in base.items()})
    d["hands"], d["twist"] = hands, twist
    return d


STANCES: dict[str, dict] = {
    # stance -> joint values (front leg = right, toward the ninjas)
    "ready":      {"legs": (14, 10, 14, 10), "arms": (60, 100, 60, 100)},
    "ma_bu":      {"legs": (48, 62, 48, 62), "y": -16, "swivel": (-0.6, -0.6), "arms": (60, 110, 60, 110)},
    "gong_bu":    {"legs": (38, 0, 46, 52), "hip": 6, "y": -10, "torso": 6, "ankles": (0, 0)},
    "kokutsu":    {"legs": (40, 50, 32, 0), "hip": -6, "y": -8, "torso": -6},
    "xu_bu":      {"legs": (24, 48, 18, 14), "hip": -7, "y": -8, "ankles": (0, 60)},
    "pu_bu":      {"legs": (82, 140, 84, 0), "hip": -10, "y": -36, "torso": 18},
    "xie_bu":     {"legs": (28, 96, -18, 70), "hip": -4, "y": -26, "swivel": (0.4, 0.8), "torso": -4},
    "du_li":      {"legs": (4, 0, 92, 112), "y": 2, "ankles": (0, 50)},
    "yjkym":      {"legs": (20, 30, 20, 30), "y": -6, "swivel": (0.9, 0.9), "arms": (40, 100, 80, 40),
                   "hands": ("palm", "fist")},
    "thai_guard": {"legs": (20, 18, 12, 10), "y": -2, "ankles": (20, 20), "arms": (55, 140, 55, 140),
                   "hands": ("fist", "fist")},
    "ginga_l":    {"legs": (60, 80, 20, 10), "hip": -8, "y": -18, "torso": 18, "arms": (130, 30, 40, 90)},
    "ginga_r":    {"legs": (20, 10, 60, 80), "hip": 8, "y": -18, "torso": -18, "arms": (40, 90, 130, 30)},
}


# --- stance moves ------------------------------------------------------------
def _t_ma_bu(p):
    b = _sw(p) * 2
    return _scene(_pose("ma_bu", y=-16 + b, arms=(70, 120, 70, 120)), fx={"dust"} if p < 0.1 else ())


def _t_xu_bu(p):
    return _scene(_kf(p, [(0, _pose("ready")), (0.4, _pose("xu_bu", arms=(90, 60, 50, 120), hands=("palm", "palm"))),
                          (1, _pose("xu_bu", arms=(100, 50, 40, 120), hands=("palm", "palm")))]), _attackers(p, 110))


def _t_xie_bu(p):
    return _scene(_kf(p, [(0, _pose("ready")), (0.5, _pose("xie_bu", arms=(110, 40, 40, 120), hands=("knife", "fist"))),
                          (1, _pose("xie_bu", arms=(120, 30, 30, 120), hands=("knife", "fist")))]))


def _t_kokutsu_shuto(p):
    """Back stance with a knife-hand block (kokutsu dachi, shuto uke)."""
    return _scene(_kf(p, [(0, _pose("ready")),
                          (0.35, _pose("kokutsu", arms=(40, 140, 120, 140), hands=("knife", "knife"), twist=30)),
                          (0.6, _pose("kokutsu", arms=(70, 120, 80, 60), hands=("knife", "knife"), wrists=(0, -30))),
                          (1, _pose("kokutsu", arms=(70, 120, 80, 60), hands=("knife", "knife")))]), _attackers(p, 90))


def _t_neko_block(p):
    return _scene(_kf(p, [(0, _pose("ready")), (0.5, _pose("xu_bu", arms=(30, 120, 140, 60), hands=("palm", "fist"))),
                          (1, _pose("xu_bu", arms=(30, 120, 130, 70), hands=("palm", "fist")))]),
                  _attackers(p, 70), fx={"block"} if p > 0.4 else ())


def _t_zenkutsu_gyaku(p):
    """Front stance, reverse punch: the hip drives, the rear fist corkscrews out."""
    return _scene(_kf(p, [(0, _pose("gong_bu", arms=(30, 140, 70, 40), twist=0)),
                          (0.3, _pose("gong_bu", arms=(30, 140, 70, 40), twist=-30, hip=2)),
                          (0.5, _pose("gong_bu", arms=(90, 0, 30, 140), twist=30, hip=8, torso=10)),
                          (0.75, _pose("gong_bu", arms=(90, 0, 30, 140), twist=30, hip=8, torso=10)),
                          (1, _pose("gong_bu", arms=(30, 140, 70, 40)))]),
                  _attackers(p, 66, "stagger" if 0.45 < p < 0.8 else None),
                  fx={"impact", "trail"} if 0.45 < p < 0.6 else ())


def _t_pu_bu_sweep(p):
    """Code: drop into pu bu and sweep two ninjas off their feet."""
    sweep = 0.35 < p < 0.75
    m = _kf(p, [(0, _pose("ready")), (0.3, _pose("pu_bu", arms=(120, 30, 100, 30))),
                (0.6, _pose("pu_bu", spin=-0.6, arms=(120, 30, 100, 30), legs=(82, 140, 100, 0))),
                (1, _pose("ma_bu"))])
    ninjas = [_n(64 + i * 30, "fly" if sweep else "attack", y=34 if sweep else 0, rot=-90 if sweep else 0, kind=c)
              for i, c in enumerate(_kinds_in_play(2))]
    return _scene(m, ninjas, fx={"impact", "dust"} if sweep else {"dust"} if p > 0.25 else ())


def _t_du_li_crane(p):
    """Du li: the crane on one leg, wings spread, beaks ready."""
    return _scene(_kf(p, [(0, _pose("ready")), (0.4, _pose("du_li", arms=(150, 40, 150, 40), hands=("crane", "crane"),
                                                            wrists=(60, 60))),
                          (0.7, _pose("du_li", arms=(170, 20, 120, 60), hands=("crane", "crane"), wrists=(70, 40))),
                          (1, _pose("du_li", arms=(150, 40, 150, 40), hands=("crane", "crane"), wrists=(60, 60)))]))


# --- Shaolin five animals ----------------------------------------------------
def _t_tiger_claw(p):
    """Tiger: a pressing double claw from a bow stance."""
    return _scene(_kf(p, [(0, _pose("ready", hands=("tiger", "tiger"))),
                          (0.3, _pose("ma_bu", arms=(40, 150, 40, 150), hands=("tiger", "tiger"), twist=-20)),
                          (0.55, _pose("gong_bu", arms=(100, 20, 80, 40), hands=("tiger", "tiger"), wrists=(-60, -60),
                                       torso=14, twist=10)),
                          (1, _pose("gong_bu", arms=(90, 30, 70, 60), hands=("tiger", "tiger")))]),
                  _attackers(p, 66, "stagger" if p > 0.5 else None), fx={"impact", "trail"} if 0.5 < p < 0.65 else ())


def _t_crane_wings(p):
    return _t_du_li_crane(p)


def _t_leopard_fist(p):
    """Leopard: fast, straight strikes with the half-closed leopard fist."""
    k = (p * 3) % 1.0
    m = _kf(k, [(0, _pose("gong_bu", arms=(40, 140, 40, 140), hands=("leopard", "leopard"))),
                (0.35, _pose("gong_bu", arms=(40, 140, 95, 0), hands=("leopard", "leopard"), twist=25)),
                (0.7, _pose("gong_bu", arms=(95, 0, 40, 140), hands=("leopard", "leopard"), twist=-25)),
                (1, _pose("gong_bu", arms=(40, 140, 40, 140), hands=("leopard", "leopard")))])
    return _scene(m, _attackers(p, 64, "stagger" if k > 0.3 else None), fx={"trail"})


def _t_snake_spear(p):
    """Snake: fingers together like a spear, striking soft and sudden."""
    s = max(0.0, _sw(p, 2))
    return _scene(_pose("xu_bu", arms=(50, 130, 70 + 30 * s, 60 - 60 * s), hands=("palm", "snake"),
                        wrists=(0, -20 * s), torso=6 * s), _attackers(p, 70), fx={"trail"} if s > 0.8 else ())


def _t_dragon_claw(p):
    return _scene(_kf(p, [(0, _pose("ready", hands=("dragon", "dragon"))),
                          (0.4, _pose("xie_bu", arms=(160, 30, 60, 110), hands=("dragon", "dragon"))),
                          (0.7, _pose("gong_bu", arms=(70, 60, 110, 20), hands=("dragon", "dragon"), twist=30, torso=10)),
                          (1, _pose("gong_bu", arms=(70, 60, 110, 20), hands=("dragon", "dragon")))]),
                  _attackers(p, 68, "stagger" if p > 0.7 else None))


# --- Wing Chun -----------------------------------------------------------------
def _t_chain_punch(p):
    """Chain punch: vertical fists rolling down the centreline from yjkym."""
    k = (p * 4) % 1.0
    lead_out = k < 0.5
    e = math.sin((k % 0.5) * 2 * math.pi)
    a = (40, 120, 90 * e + 10, 100 - 100 * e) if lead_out else (90 * e + 10, 100 - 100 * e, 40, 120)
    return _scene(_pose("yjkym", arms=a, hands=("fist", "fist"), wrists=(0, 0)),
                  _attackers(p, 60, "stagger" if e > 0.85 else None), fx={"trail"} if e > 0.6 else ())


def _t_tan_bong(p):
    """Tan sau (palm-up deflection) into bong sau (wing arm)."""
    return _scene(_kf(p, [(0, _pose("yjkym")),
                          (0.4, _pose("yjkym", arms=(80, 70, 40, 120), hands=("palm", "fist"), wrists=(40, 0))),
                          (0.7, _pose("yjkym", arms=(110, 100, 40, 120), hands=("palm", "fist"), wrists=(-20, 0))),
                          (1, _pose("yjkym"))]), _attackers(p, 64), fx={"block"} if p > 0.35 else ())


# --- Muay Thai --------------------------------------------------------------
def _t_teep(p):
    """Teep: lift the knee, push the ball of the foot through the body."""
    m = _kf(p, [(0, _pose("thai_guard")),
                (0.3, _pose("thai_guard", legs=(10, 10, 95, 120), torso=-6)),
                (0.5, _pose("thai_guard", legs=(10, 10, 90, 0), torso=-16, ankles=(20, -20))),
                (0.7, _pose("thai_guard", legs=(10, 10, 95, 120), torso=-6)),
                (1, _pose("thai_guard"))])
    return _scene(m, _attackers(p, 92 + (30 if 0.45 < p < 0.8 else 0), "stagger" if 0.45 < p < 0.8 else None),
                  fx={"impact"} if 0.45 < p < 0.55 else ())


def _t_thai_elbow(p):
    """A step in and a horizontal elbow, then the upward elbow."""
    m = _kf(p, [(0, _pose("thai_guard")),
                (0.25, _pose("thai_guard", arms=(55, 140, 95, 165), twist=-30)),
                (0.45, _pose("thai_guard", arms=(55, 140, 95, 165), twist=35, torso=8, hip=4)),
                (0.65, _pose("thai_guard", arms=(160, 165, 55, 140), twist=-10, torso=-6)),
                (1, _pose("thai_guard"))])
    return _scene(m, _attackers(p, 54, "stagger" if 0.4 < p < 0.75 else None),
                  fx={"impact", "trail"} if 0.4 < p < 0.5 or 0.6 < p < 0.7 else ())


def _t_thai_knee(p):
    m = _kf(p, [(0, _pose("thai_guard")), (0.35, _pose("thai_guard", arms=(120, 120, 120, 120), hands=("palm", "palm"))),
                (0.55, _pose("thai_guard", arms=(110, 130, 110, 130), hands=("palm", "palm"), legs=(10, 10, 110, 130),
                             torso=-10, ankles=(30, 60))),
                (1, _pose("thai_guard"))])
    return _scene(m, _attackers(p, 50, "stagger" if 0.5 < p < 0.8 else None), fx={"impact"} if 0.5 < p < 0.6 else ())


def _t_thai_roundhouse(p):
    """Rear roundhouse: pivot on the ball of the standing foot, hip over, the
    shin swings through, arm swings down for balance, then return to guard."""
    m = _kf(p, [(0, _pose("thai_guard")),
                (0.2, _pose("thai_guard", swivel=(-0.8, 0), twist=-25, legs=(14, 8, 30, 40))),
                (0.45, _pose("thai_guard", swivel=(-1.0, 0), twist=40, torso=-24, rot=-8,
                             legs=(10, 6, 108, 12), arms=(60, 130, 20, 20), ankles=(40, 50))),
                (0.6, _pose("thai_guard", swivel=(-1.0, 0), twist=55, torso=-20, rot=-6,
                            legs=(10, 6, 96, 30), arms=(60, 130, 10, 20), ankles=(40, 40))),
                (1, _pose("thai_guard"))])
    return _scene(m, _attackers(p, 80, "stagger" if 0.42 < p < 0.75 else None),
                  fx={"impact", "trail"} if 0.42 < p < 0.55 else {"trail"} if 0.3 < p < 0.6 else ())


# --- Taekwondo --------------------------------------------------------------
def _t_tornado_kick(p):
    """Tornado (360) roundhouse: spin, jump, kick at the top."""
    a = math.sin(min(p, 0.999) * math.pi)
    turn = math.cos(p * 2 * math.pi)
    m = _kf(p, [(0, _pose("ready")), (0.25, _pose("ready", spin=-1.0, y=10, legs=(30, 60, 30, 60))),
                (0.5, _pose("ready", spin=0.2, y=40, rot=-20, legs=(40, 90, 100, 10), arms=(100, 40, 60, 90),
                            ankles=(40, 50))),
                (0.75, _pose("ready", spin=1.0, y=20, legs=(40, 80, 60, 60))), (1, _pose("thai_guard"))])
    m["spin"] = turn if p < 0.75 else m["spin"]
    return _scene(m, _attackers(p, 84, "fly" if 0.45 < p < 0.8 else None), fx={"trail", "speed"} if a > 0.3 else ())


def _t_spinning_hook(p):
    m = _kf(p, [(0, _pose("thai_guard")), (0.3, _pose("thai_guard", spin=-1.0, twist=40)),
                (0.55, _pose("thai_guard", spin=-0.4, torso=-30, rot=-10, legs=(10, 6, 110, 80), ankles=(0, 30))),
                (0.75, _pose("thai_guard", spin=0.6, torso=-20, legs=(10, 6, 80, 120))), (1, _pose("thai_guard"))])
    return _scene(m, _attackers(p, 82, "stagger" if 0.5 < p < 0.8 else None), fx={"trail"} if 0.4 < p < 0.75 else ())


# --- Capoeira -----------------------------------------------------------------
def _t_ginga(p):
    """Ginga: the swaying triangle step, arms guarding the face."""
    t = (p * 2) % 1.0
    m = _kf(t, [(0, _pose("ginga_l")), (0.5, _pose("ginga_r")), (1, _pose("ginga_l"))])
    return _scene(m, _attackers(p, 96))


def _t_au(p):
    """Aú: the capoeira cartwheel, hands to the floor, legs over."""
    m = _kf(p, [(0, _pose("ginga_l")),
                (0.3, _pose("ready", rot=-90, y=30, arms=(170, 0, 170, 0), legs=(60, 0, 60, 0), hands=("palm", "palm"))),
                (0.55, _pose("ready", rot=-180, y=56, arms=(170, 0, 170, 0), legs=(70, 0, 70, 0), hands=("palm", "palm"))),
                (0.8, _pose("ready", rot=-270, y=30, arms=(170, 0, 170, 0), legs=(60, 0, 60, 0), hands=("palm", "palm"))),
                (1, _pose("ginga_r", rot=-360))])
    m["x"] = -40 + 80 * p
    return _scene(m, fx={"speed", "victory"})


def _t_meia_lua(p):
    """Meia lua de compasso: hands down, the heel arcs round like a compass."""
    m = _kf(p, [(0, _pose("ginga_l")),
                (0.3, _pose("ginga_l", torso=60, arms=(20, 0, 20, 0), hands=("palm", "palm"))),
                (0.55, _pose("ginga_l", torso=70, spin=-0.5, legs=(60, 70, 120, 10), arms=(20, 0, 20, 0),
                             hands=("palm", "palm"), ankles=(0, -30))),
                (0.8, _pose("ginga_l", torso=50, spin=0.5, legs=(60, 70, 90, 30))), (1, _pose("ginga_r"))])
    return _scene(m, _attackers(p, 88, "stagger" if 0.5 < p < 0.8 else None), fx={"trail"} if 0.4 < p < 0.8 else ())


# --- the headline moves, rebuilt as real technique ---------------------------
def _t_hip_throw(p):
    """O-goshi hip throw: grip, step in, load the ninja on the hip, rotate,
    release - and he flies far. One tool done."""
    first = _kinds_in_play()[0]
    m = _kf(p, [(0, _pose("thai_guard")),
                (0.2, _pose("gong_bu", arms=(100, 40, 120, 40), hands=("palm", "palm"))),
                (0.4, _pose("ma_bu", twist=-60, torso=20, arms=(120, 60, 100, 80), hands=("fist", "fist"))),
                (0.6, _pose("ma_bu", twist=40, torso=35, rot=6, arms=(150, 30, 60, 100))),
                (1, _pose("gong_bu", arms=(160, 10, 40, 80), hands=("palm", "fist")))])
    if p < 0.4:
        flyer = _n(40 - 10 * p / 0.4, "stagger", kind=first, rot=-10)
    elif p < 0.6:
        u = (p - 0.4) / 0.2
        flyer = _n(30 - 20 * u, "fly", y=20 + 50 * u, rot=-20 - 160 * u, kind=first)
    else:
        u = (p - 0.6) / 0.4
        flyer = _n(10 + 220 * u, "fly", y=70 + 60 * math.sin(u * math.pi * 0.8), rot=-180 - 540 * u, kind=first)
    return _scene(m, [flyer] + _attackers(p, 130)[1:], fx={"throw", "trail"} if p > 0.55 else {"throw"})


def _t_long_backflip(p):
    """Set, jump, tuck, open, spot the landing: a long, high backflip."""
    m = _kf(p, [(0, _pose("ready", arms=(20, 20, 20, 20))),
                (0.12, _pose("ma_bu", y=-20, arms=(10, 10, 10, 10), torso=20)),           # set
                (0.25, _pose("ready", y=40, arms=(175, 0, 175, 0), legs=(5, 0, 5, 0), ankles=(60, 60))),  # jump
                (0.45, _pose("ready", y=95, rot=160, arms=(80, 60, 80, 60), legs=(100, 140, 100, 140))),  # tuck
                (0.65, _pose("ready", y=80, rot=300, arms=(160, 10, 160, 10), legs=(20, 30, 20, 30))),   # open
                (0.85, _pose("ma_bu", y=-10, rot=360, arms=(120, 20, 120, 20))),                          # land
                (1, _pose("ready", rot=360, arms=(150, 20, 150, 20)))])
    m["x"] = 60 - 130 * _ease(min(1.0, p / 0.85))
    return _scene(m, fx={"speed", "victory", "trail"} | ({"dust"} if p > 0.82 else set()))


def _t_bicycle_kick(p):
    """Scissor kick: launch, the first leg feints, the second whips through."""
    first = _kinds_in_play()[0]
    m = _kf(p, [(0, _pose("ready")),
                (0.2, _pose("ma_bu", y=-14, arms=(60, 60, 60, 60))),
                (0.4, _pose("ready", y=70, rot=-110, legs=(100, 20, 20, 60), arms=(150, 30, 110, 40))),
                (0.55, _pose("ready", y=82, rot=-140, legs=(20, 60, 120, 0), arms=(160, 20, 100, 40), ankles=(50, 50))),
                (0.8, _pose("ready", y=20, rot=-200, legs=(60, 60, 60, 60), arms=(170, 10, 170, 10))),
                (1, _pose("ma_bu", rot=-360))])
    hit = 0.5 < p
    flyer = _n(70 + (180 * (p - 0.5) / 0.5 if hit else 0), "fly" if hit else "attack",
               y=(40 + 70 * math.sin((p - 0.5) / 0.5 * math.pi * 0.8)) if hit else 0,
               rot=-400 * (p - 0.5) if hit else 0, kind=first)
    return _scene(m, [flyer], fx={"victory", "trail"} | ({"impact"} if 0.5 < p < 0.6 else set()))


def _t_dodge_arrows(p):
    """Arrows keep coming: he sways back (limbo), sidesteps in ginga, ducks."""
    m = _kf(p, [(0, _pose("ginga_l")),
                (0.25, _pose("ma_bu", torso=-55, head=-20, arms=(110, 20, 110, 20), legs=(40, 70, 40, 70))),
                (0.5, _pose("ginga_r")),
                (0.75, _pose("pu_bu", torso=30, arms=(120, 30, 100, 30))),
                (1, _pose("ginga_l"))])
    arrows = [((p * 1.6 + k * 0.33) % 1.0 * 380 - 20, -70 + 22 * k, 180) for k in range(3)]
    return _scene(m, arrows=arrows, fx={"arrows", "trail"})


def _t_stop_object(p):
    """A boulder is hurled; he roots into ma bu and stops it with one palm."""
    held = p > 0.4
    bx = 230 - 180 * min(1.0, p / 0.4)
    m = _kf(p, [(0, _pose("thai_guard")), (0.38, _pose("ma_bu", arms=(40, 120, 70, 60), hands=("fist", "palm"))),
                (0.45, _pose("ma_bu", arms=(40, 120, 95, 0), hands=("fist", "palm"), wrists=(0, -80), hip=-3)),
                (1, _pose("ma_bu", arms=(40, 120, 95, 0), hands=("fist", "palm"), wrists=(0, -80)))])
    return _scene(m, [_n(160, "attack", kind=_kinds_in_play()[0], arms=(150, 20, 150, 20))],
                  objects=[("boulder", 52 if held else bx, -62, 0, held)],
                  fx={"freeze", "dust"} if held else ())


def _t_catch_arrow(p):
    caught = p > 0.45
    ax = 210 - 160 * min(1.0, p / 0.45)
    m = _kf(p, [(0, _pose("kokutsu", hands=("palm", "palm"))),
                (0.42, _pose("kokutsu", arms=(30, 60, 100, 30), hands=("palm", "palm"))),
                (0.5, _pose("kokutsu", arms=(30, 60, 150, 30), hands=("palm", "fist"), head=-10)),
                (1, _pose("xu_bu", arms=(30, 60, 160, 20), hands=("palm", "fist"), head=-14))])
    return _scene(m, arrows=[] if caught else [(ax, -60, 180)],
                  objects=[("arrow_held", 18, -100, 0)] if caught else [],
                  fx={"freeze"} if caught else {"arrows"})


# Register the new techniques and upgrade the headline moves.
MOVES.update({
    "ma_bu": _t_ma_bu, "xu_bu": _t_xu_bu, "xie_bu": _t_xie_bu, "kokutsu_shuto": _t_kokutsu_shuto,
    "neko_block": _t_neko_block, "zenkutsu_gyaku": _t_zenkutsu_gyaku, "pu_bu_sweep": _t_pu_bu_sweep,
    "du_li_crane": _t_du_li_crane, "tiger_claw_strike": _t_tiger_claw, "leopard_fist": _t_leopard_fist,
    "snake_spear": _t_snake_spear, "dragon_claw": _t_dragon_claw, "chain_punch": _t_chain_punch,
    "tan_bong": _t_tan_bong, "teep": _t_teep, "thai_elbow": _t_thai_elbow, "thai_knee": _t_thai_knee,
    "thai_roundhouse": _t_thai_roundhouse, "tornado_kick": _t_tornado_kick,
    "spinning_hook": _t_spinning_hook, "ginga": _t_ginga, "au": _t_au, "meia_lua": _t_meia_lua,
    # rebuilt headline moves (same meaning, real technique)
    "throw_far": _t_hip_throw, "long_backflip": _t_long_backflip, "bicycle_kick": _t_bicycle_kick,
    "dodge_arrows": _t_dodge_arrows, "stop_object": _t_stop_object, "catch_arrow": _t_catch_arrow,
})

# Real techniques as signatures where the meaning fits.
MOVE_FOR_POSE.update({
    "work": "chain_punch",               # steady centreline work: a tool is running
    "terminal_work": "thai_roundhouse",  # a command: the big pivoting kick
    "audio_tune": "thai_elbow", "media_paint": "tornado_kick", "dev_merge": "pu_bu_sweep",
    "close_workstation": "tiger_claw_strike", "retry": "zenkutsu_gyaku", "huff": "du_li_crane",
    "walk_to_workspace": "ginga", "tip_to_workspace": "xu_bu", "dance": "ginga",
    "panic": "tan_bong", "eyebrow_raise": "neko_block", "watch": "kokutsu_shuto",
    "idle": "ma_bu", "sit": "xie_bu", "spin": "spinning_hook", "spin_joy": "au",
    "fly_up": "teep", "sit_back": "xie_bu", "squint": "snake_spear", "tilt": "dragon_claw",
    "look_up": "leopard_fist", "bounce": "thai_knee", "leap_double_joy": "meia_lua",
})

# Displaced moves stay as kata decoration (never a signature), sorted by mood.
_DISPLACED = {"jab_cross": "focused", "roundhouse": "focused", "elbow_combo": "focused",
              "twin_sweep": "bright", "spin_kick": "bright", "palm_strike": "focused",
              "ready_again": "calm", "breathe": "calm", "scan_left": "calm", "alert": "calm",
              "tree_sleep": "calm", "head_tilt": "calm", "stroke_beard": "calm",
              "double_backflip": "bright", "tornado_kick": "bright"}
for _name, _mood in _DISPLACED.items():
    # a kata self-maps by name, so it must never shadow a real engine pose
    if _name not in MOVE_FOR_POSE.values() and _name in MOVES and _name not in MOVE_FOR_POSE:
        KATA[_name] = (_mood, MOVES[_name])
for _name, _mood in {"tiger_claw_strike": "focused", "leopard_fist": "focused", "snake_spear": "calm",
                     "dragon_claw": "bright", "crane_wings": "calm", "kokutsu_shuto": "focused",
                     "meia_lua": "bright", "au": "bright"}.items():
    if _name == "crane_wings":
        MOVES[_name] = _t_crane_wings
    if _name not in MOVE_FOR_POSE.values():
        KATA[_name] = (_mood, MOVES[_name])
# the old pose-named moves keep playing as kata under their own names
for _old, _new, _mood in (("squint", "eagle_eye", "calm"), ("bounce", "light_feet", "bright"),
                          ("look_up", "sky_watch", "calm")):
    MOVES[_new] = MOVES.pop(_old)
    KATA[_new] = (_mood, MOVES[_new])
MOVE_FOR_POSE.update({name: name for name in KATA})
_MOVE_MOOD.update({
    "au": "joy", "meia_lua": "joy", "tornado_kick": "work", "spinning_hook": "joy",
    "tan_bong": "approve", "du_li_crane": "calm", "xie_bu": "rest", "ma_bu": "rest",
})
_MOVE_MOOD.update({name: {"bright": "joy", "focused": "work"}.get(m, "calm")
                   for name, (m, _f) in KATA.items() if name not in _MOVE_MOOD})


# What style each technique comes from, shown as a chip so people can read the fight.
STYLE_OF = {
    "ma_bu": "Horse stance", "xu_bu": "Empty stance", "xie_bu": "Cross stance",
    "kokutsu_shuto": "Karate shuto", "neko_block": "Cat stance", "zenkutsu_gyaku": "Gyaku-zuki",
    "pu_bu_sweep": "Pu bu sweep", "du_li_crane": "Crane", "crane_wings": "Crane",
    "tiger_claw_strike": "Tiger claw", "leopard_fist": "Leopard fist", "snake_spear": "Snake hand",
    "dragon_claw": "Dragon claw", "chain_punch": "Wing Chun", "tan_bong": "Tan / bong sau",
    "teep": "Muay Thai teep", "thai_elbow": "Muay Thai elbow", "thai_knee": "Muay Thai knee",
    "thai_roundhouse": "Muay Thai kick", "tornado_kick": "TKD tornado", "spinning_hook": "Spin hook",
    "ginga": "Capoeira ginga", "au": "Capoeira au", "meia_lua": "Meia lua",
    "throw_far": "O-goshi throw", "long_backflip": "Backflip", "bicycle_kick": "Bicycle kick",
    "dodge_arrows": "Evade", "stop_object": "Iron palm", "catch_arrow": "Arrow catch",
}


# ===========================================================================
# Real exchanges: the ninjas fight back.
#
# A bout is keyframed for both fighters at once. Ninjas jab, kick, sweep and
# swing weapons; they block and parry some of his strikes and take others.
# He parries (tan sau), checks kicks with his shin, rises to block overhead
# chops (age uke) - and when a tool fails, a ninja's strike gets through.
# The ninja's lead side (left limbs) faces him; his right side faces them.
# ===========================================================================
NINJA_ACTS: dict[str, dict] = {
    "guard":      {"arms": (70, 125, 55, 135), "legs": (22, 18, 12, 8)},
    "jab":        {"arms": (95, 0, 55, 135), "legs": (28, 10, 10, 8), "torso": -8},
    "kick":       {"arms": (55, 135, 40, 70), "legs": (100, 12, 8, 6), "torso": 22},
    "sweep":      {"arms": (100, 40, 120, 40), "legs": (84, 4, 70, 120), "torso": -12, "y": -30},
    "high_block": {"arms": (140, 95, 55, 135), "legs": (20, 22, 14, 8), "torso": 6, "hands": ("knife", "fist")},
    "low_block":  {"arms": (30, 20, 55, 135), "legs": (24, 20, 14, 8), "torso": -4, "hands": ("knife", "fist")},
    "parry":      {"arms": (75, 60, 55, 135), "legs": (22, 18, 12, 8), "wrists": (40, 0), "hands": ("palm", "fist")},
    "overhead":   {"arms": (168, 20, 60, 130), "legs": (26, 14, 10, 8), "torso": 8},
    "chop":       {"arms": (100, 10, 60, 130), "legs": (32, 10, 8, 6), "torso": -14},
    "hit":        {"arms": (40, 30, 130, 50), "legs": (10, 6, 30, 30), "torso": 26, "head": 22, "state": "stagger"},
}
NINJA_BLOCKS = ("high_block", "low_block", "parry")


def _nj(act: str, x: float, kind=None, **kw) -> dict:
    a = {**NINJA_ACTS[act], **kw}
    st = a.pop("state", "attack")
    hands = a.pop("hands", ("fist", "fist"))
    d = _n(x, st, y=a.pop("y", 0.0), arms=a.pop("arms"), legs=a.pop("legs"), torso=a.pop("torso", 0.0), kind=kind)
    d.update(a)
    d["hands"], d["act"], d["twist"] = hands, act, 0.0
    return d


def _bout(p, beats, extra_ninjas=True):
    """beats: [(t, master_pose, ninja_act, ninja_x, info)]; info may carry fx
    (held from that beat to the next) and a spark (x, y) shown at contact."""
    kind = _kinds_in_play()[0]
    m = _kf(p, [(t, mp) for t, mp, _a, _x, _i in beats])
    nj = _kf(p, [(t, _nj(a, x, kind)) for t, _mp, a, x, _i in beats])
    fx, sparks = set(), []
    for (t, _mp, _a, _x, info), nxt in zip(beats, beats[1:] + [(1.01,) + beats[-1][1:]]):
        if t <= p < nxt[0]:
            fx |= set(info.get("fx", ()))
        if "spark" in info and abs(p - t) < 0.07:
            sparks.append(info["spark"])
    ninjas = [nj] + (_attackers(p, 130)[1:] if extra_ninjas else [])
    sc = _scene(m, ninjas, fx=fx)
    sc["sparks"] = sparks
    return sc


def _b_exchange(p):
    """Work: a real exchange. He parries a jab (tan sau); his reverse punch
    is blocked high; he checks the ninja's kick with his shin; his roundhouse
    lands; both reset."""
    G = _pose("thai_guard")
    return _bout(p, [
        (0.00, G, "guard", 76, {}),
        (0.14, _pose("yjkym", arms=(40, 120, 82, 70), hands=("fist", "palm"), wrists=(0, 40)), "jab", 64,
         {"fx": {"block"}, "spark": (34, -56)}),
        (0.30, _pose("gong_bu", arms=(30, 140, 92, 0), twist=30, torso=8), "high_block", 70,
         {"spark": (44, -66)}),
        (0.46, _pose("thai_guard", legs=(14, 8, 72, 124), ankles=(20, 40)), "kick", 62,
         {"spark": (30, -34)}),
        (0.62, _pose("thai_guard", twist=45, torso=-20, rot=-6, legs=(10, 6, 100, 14), arms=(60, 130, 15, 20),
                     swivel=(-1.0, 0)), "hit", 88, {"fx": {"impact", "trail"}}),
        (0.82, G, "guard", 82, {}),
        (1.00, G, "guard", 76, {}),
    ])


def _b_trade_blows(p):
    """A tool failed: he blocks the feint low, the ninja's jab gets through,
    he staggers back, then shuts the next jab down with a high block."""
    G = _pose("thai_guard")
    return _bout(p, [
        (0.00, G, "guard", 72, {}),
        (0.16, _pose("thai_guard", arms=(55, 140, 30, 30), hands=("fist", "knife")), "low_block", 62,
         {"spark": (30, -24)}),
        (0.32, _pose("thai_guard", x=-12, torso=-26, head=-22, arms=(100, 40, 70, 60)), "jab", 58,
         {"fx": {"hit"}}),
        (0.52, _pose("kokutsu", x=-18, torso=-10, arms=(60, 120, 70, 120)), "guard", 64, {}),
        (0.72, _pose("kokutsu", x=-10, arms=(40, 120, 155, 80), hands=("fist", "knife")), "jab", 56,
         {"fx": {"block"}, "spark": (28, -66)}),
        (1.00, G, "guard", 72, {}),
    ])


def _b_swept(p):
    """Fall: the ninja drops into a low spinning sweep and takes his legs."""
    G = _pose("thai_guard")
    down = _pose("ready", y=-40, rot=-82, arms=(90, 30, 120, 30), legs=(30, 40, 60, 20), x=-6)
    return _bout(p, [
        (0.00, G, "guard", 74, {}),
        (0.22, G, "sweep", 54, {"fx": {"dust"}}),
        (0.40, _pose("ready", y=-16, rot=-46, legs=(60, 20, 90, 10), arms=(150, 30, 120, 40)), "sweep", 52,
         {"fx": {"dust", "hit"}, "spark": (8, -6)}),
        (0.70, down, "guard", 70, {"fx": {"dust"}}),
        (1.00, down, "guard", 78, {}),
    ])


def _b_block_counter(p):
    """Repair: the ninja swings his weapon overhead; Sensei rises into age
    uke, steps in with a palm strike, and the weapon flies out of his hand."""
    G = _pose("thai_guard")
    sc = _bout(p, [
        (0.00, G, "guard", 72, {}),
        (0.20, _pose("kokutsu", arms=(40, 120, 60, 110)), "overhead", 66, {}),
        (0.36, _pose("kokutsu", arms=(40, 120, 160, 70), hands=("fist", "knife")), "chop", 60,
         {"fx": {"block"}, "spark": (34, -74)}),
        (0.56, _pose("gong_bu", arms=(30, 140, 92, 0), hands=("fist", "palm"), wrists=(0, -70), twist=25),
         "hit", 84, {"fx": {"impact", "trail"}}),
        (0.80, G, "guard", 90, {}),
        (1.00, G, "guard", 78, {}),
    ])
    if p > 0.52:                                             # disarmed: the weapon spins away
        u = min(1.0, (p - 0.52) / 0.48)
        sc["ninjas"][0]["disarmed"] = True
        sc["objects"].append(("staff", 70 + 90 * u, -110 - 50 * math.sin(u * math.pi) + 100 * u * u, 720 * u))
    return sc


MOVES.update({"exchange": _b_exchange, "hit_react": _b_trade_blows, "knocked_down": _b_swept,
              "block_counter": _b_block_counter})
MOVE_FOR_POSE["work"] = "exchange"
KATA["chain_punch"] = ("focused", MOVES["chain_punch"])
MOVE_FOR_POSE["chain_punch"] = "chain_punch"
_MOVE_MOOD.update({"exchange": "work", "chain_punch": "work"})
STYLE_OF.update({"exchange": "Sparring", "hit_react": "Hit lands", "knocked_down": "Leg sweep",
                 "block_counter": "Age-uke counter"})
