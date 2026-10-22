"""Kia Kai — an articulated skateboarder whose skate session shows Hermes status.

The same Duet/Sensei joint primitives drive shoulders, elbows, knees, hips,
neck, torso twist, wrists and ankles. Signed semantic events, not content,
drive tools, bails, helper crew, approval holds and completion celebrations.
"""
from __future__ import annotations

import math
import time
from dataclasses import dataclass, field

from hermes_companion.animation.animator import pose_params
from hermes_companion.animation.duet import (
    _Body, _Joint, _d, _ease, _foot, _hand, _limb_pts, _mix, _mood_icon, _badge,
)
from hermes_companion.animation.herald import (
    EXCLAIM, MOOD_COLORS, WONDER, _bubble, mood_of,
)
from hermes_companion.animation import master

FRAME = (360, 300)
FLOOR = 228
CX = 164
HIP_Y = FLOOR - 49

PALETTES = {
    "street": {"edge": "#10151b", "skin": "#835036", "hair": "#18151a",
               "hood": "#ec8a3b", "hood_hi": "#ffd19a", "pants": "#253d4b",
               "shoes": "#f8f1dd", "deck": "#18b6a1", "accent": "#e8bf52",
               "sky": "#182a39", "concrete": "#74838a"},
    "midnight": {"edge": "#0b0d18", "skin": "#69412e", "hair": "#18121b",
                 "hood": "#6043ad", "hood_hi": "#b7a9ed", "pants": "#191d37",
                 "shoes": "#e3ddf7", "deck": "#bc79f2", "accent": "#f9c74f",
                 "sky": "#141629", "concrete": "#4f536d"},
    "sunrise": {"edge": "#26141b", "skin": "#a66b47", "hair": "#26141b",
                "hood": "#c0494f", "hood_hi": "#ffb4a5", "pants": "#384e61",
                "shoes": "#fff1d6", "deck": "#ffba4a", "accent": "#20a799",
                "sky": "#e2a089", "concrete": "#978889"},
}
DEFAULT_PALETTE = "street"
# Work type gets a small, content-free symbol on the deck.
CATEGORY_MARKS = {
    "terminal": (">_", "#2dd4bf"), "development": ("{}", "#22d3ee"),
    "web": ("@", "#60a5fa"), "browser": ("@", "#38bdf8"),
    "file": ("F", "#f59e0b"), "docs": ("F", "#f59e0b"),
    "media": ("*", "#f472b6"), "memory": ("M", "#a78bfa"),
    "planning": ("+", "#84cc16"), "desktop": ("#", "#94a3b8"),
    "general": ("K", "#94a3b8"),
}


@dataclass
class SkaterState:
    tools: list[str] = field(default_factory=list)
    category: str = "general"
    helpers: int = 0
    bails: int = 0
    streak: int = 0
    landed: int = 0
    danger: bool = False
    think_until: float = 0.0
    victory_until: float = 0.0
    clock: object = field(default=time.monotonic, repr=False)

    @property
    def running(self) -> int:
        return len(self.tools)

    @property
    def thinking(self) -> bool:
        return self.clock() < self.think_until

    @property
    def celebrating(self) -> bool:
        return self.clock() < self.victory_until

    def observe(self, ev) -> None:
        kind = getattr(ev.kind, "value", str(ev.kind))
        cat = ev.category or "general"
        now = self.clock()
        if kind == "agent.started":
            self.tools, self.helpers = [], 0
            self.bails = self.streak = self.landed = 0
            self.danger = False
            self.victory_until = 0.0
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
                if self.streak >= 3 and self.bails:
                    self.bails -= 1
                    self.streak = 0
            else:
                self.bails = min(3, self.bails + 1)
                self.streak = 0
        elif kind == "approval.required":
            self.danger = cat == "dangerous"
        elif kind in ("approval.approved", "approval.rejected"):
            self.danger = False
        elif kind == "agent.subagent_spawned":
            self.helpers = min(3, self.helpers + 1)
        elif kind in ("agent.subagent_finished", "agent.subagent_failed"):
            self.helpers = max(0, self.helpers - 1)
            if kind.endswith("failed"):
                self.bails = min(3, self.bails + 1)
        elif kind in ("task.complete", "agent.idle"):
            self.tools, self.helpers, self.danger = [], 0, False
            self.category = "general"
            if kind == "task.complete":
                self.victory_until = now + 6.0

    def key(self):
        return (tuple(self.tools), self.category, self.helpers, self.bails,
                min(self.landed, 99), self.danger, self.thinking, self.celebrating)


STATE = SkaterState()


def observe(ev) -> None:
    STATE.observe(ev)


def state_key() -> tuple:
    return STATE.key()


def _pose(x=0.0, y=0.0, rot=0.0, spin=1.0, torso=-8.0, head=0.0,
          arms=(50, 40, 90, 35), legs=(22, 40, 25, 40),
          wrists=(0, 0), ankles=(0, 0), swivel=(0, 0), hip=0.0, twist=0.0):
    st = _d(x, y=y, rot=rot, spin=spin, torso=torso, head=head, arms=arms,
            legs=legs, wrists=wrists, ankles=ankles, swivel=swivel, hip=hip)
    st["twist"] = twist
    return st


def _scene(body, *, deck_x=0.0, deck_y=0.0, deck_tilt=0.0, deck_flip=0.0, fx=()):
    return {"body": body, "deck": (deck_x, deck_y, deck_tilt, deck_flip),
            "fx": frozenset(fx)}


def _s(p, n=1):
    return math.sin(p * math.tau * n)


def _a(p):
    return math.sin(min(0.9999, max(0.0, p)) * math.pi)


# One deterministic, keyframed visual per action. Trick names describe
# the symbolic animation, not a real-world physics simulation.
def _cruise(p):
    s = _s(p, 2)
    return _scene(_pose(x=8 * _s(p), torso=-8 + 5 * s, rot=3 * s,
                        legs=(24, 38 + 7 * s, 20, 42 - 7 * s),
                        arms=(55 + 8 * s, 35, 85 - 8 * s, 40)),
                  deck_x=8 * _s(p), deck_tilt=3 * s)


def _push(p):
    s = _s(p, 2)
    return _scene(_pose(x=-34 + 66 * _ease(p), torso=-15, hip=-4,
                        arms=(25 + 24 * s, 60, 110 - 24 * s, 25),
                        legs=(10, 20, 35 + 28 * max(0, s), 40 + 26 * max(0, s))),
                  deck_x=-34 + 66 * _ease(p), fx=("speed",))


def _carve(p):
    s = _s(p)
    return _scene(_pose(x=30 * s, rot=15 * s, torso=-18 * s, twist=20 * s,
                        arms=(110, 22, 125, 25), legs=(28, 47, 30, 42),
                        swivel=(s * 0.5, -s * 0.5)), deck_x=30 * s,
                  deck_tilt=15 * s, fx=("speed",))


def _ollie(p):
    h = 58 * _a(p)
    return _scene(_pose(y=h, torso=-16 * _a(p), head=-8 * _a(p),
                        arms=(140, 25, 120, 25),
                        legs=(35 + 48 * _a(p), 60, 24 + 48 * _a(p), 65),
                        ankles=(25, 45)), deck_y=h + 3, deck_tilt=8 * _s(p),
                  fx=("air",) if h > 10 else ())


def _kickflip(p):
    sc = _ollie(p)
    return _scene(sc["body"], deck_y=sc["deck"][1] + 8,
                  deck_flip=math.tau * _ease(p), fx=("air", "flip"))


def _shuvit(p):
    sc = _ollie(p)
    sc["body"]["spin"] = math.cos(math.tau * p)
    return _scene(sc["body"], deck_y=sc["deck"][1],
                  deck_tilt=16 * _s(p), deck_flip=math.pi * _s(p),
                  fx=("air", "spin"))


def _manual(p):
    return _scene(_pose(x=12 * _s(p), rot=-10, torso=18,
                        arms=(150, 30, 150, 30), legs=(32, 52, 12, 18),
                        ankles=(40, 0)), deck_x=12 * _s(p), deck_tilt=-19,
                  fx=("balance",))


def _grind(p):
    x = -76 + 150 * _ease(p)
    return _scene(_pose(x=x, y=18, torso=-10, arms=(110, 30, 125, 30),
                        legs=(45, 62, 38, 60), twist=14 * _s(p)),
                  deck_x=x, deck_y=18, deck_tilt=5 * _s(p),
                  fx=("rail", "sparks"))


def _wallride(p):
    x = 45 + 55 * _a(p)
    return _scene(_pose(x=x, y=40 + 58 * _a(p), rot=-30,
                        arms=(150, 15, 110, 25),
                        legs=(48, 55, 70, 20), twist=25),
                  deck_x=x, deck_y=37 + 55 * _a(p), deck_tilt=-58,
                  fx=("wall", "speed"))


def _scan(p):
    return _scene(_pose(x=4 * _s(p), torso=24, head=24 * _s(p),
                        arms=(40, 100, 60, 90), legs=(43, 55, 30, 43)))


def _bail(p):
    t = _ease(p)
    return _scene(_pose(x=-12 - 20 * t, y=-18 * t,
                        rot=-78 * t, torso=24 * t,
                        arms=(150, 15, 120, 30), legs=(52, 22, 88, 25)),
                  deck_x=30 + 65 * t, deck_tilt=30 * t,
                  fx=("bail", "sparks"))


def _recover(p):
    t = _ease(p)
    return _scene(_pose(x=-14 + 14 * t, y=-12 * (1 - t),
                        rot=-55 * (1 - t), torso=28 * (1 - t),
                        arms=(100, 85, 60, 40), legs=(68, 100 - 60 * t, 36, 42)))


def _brake(p):
    return _scene(_pose(rot=-4, torso=18, head=-10,
                        arms=(30, 60, 145, 22), legs=(46, 70, 10, 16),
                        ankles=(10, 25)), deck_tilt=-9, fx=("hold",))


def _wave(p):
    return _scene(_pose(arms=(55, 40, 160, 30 + 20 * _s(p, 3)),
                        head=12 * _s(p), torso=-6), fx=("attention",))


def _reject(p):
    return _scene(_pose(spin=math.cos(math.pi * p), head=-15,
                        arms=(110, 20, 110, 20)), deck_tilt=8 * _s(p))


def _crew_out(p):
    return _scene(_pose(y=20 * _a(p), arms=(145, 30, 145, 30)),
                  deck_y=20 * _a(p), fx=("crew", "out"))


def _crew_in(p):
    return _scene(_pose(x=18 * (1 - _ease(p)), arms=(100, 20, 120, 20)),
                  deck_x=18 * (1 - _ease(p)), fx=("crew", "in"))


def _victory(p):
    h = 92 * _a(p)
    return _scene(_pose(y=h, spin=math.cos(math.tau * p),
                        rot=20 * _s(p), twist=40 * _s(p),
                        arms=(160, 20, 155, 20), legs=(80, 85, 85, 85)),
                  deck_y=h + 6, deck_flip=math.tau * _ease(p),
                  fx=("air", "confetti"))


def _rest(p):
    return _scene(_pose(x=-24, y=-32, rot=0, torso=30,
                        arms=(20, 90, 30, 90), legs=(75, 100, 60, 92),
                        head=8 * _s(p)), deck_x=48, fx=("ledge",))


def _sleep(p):
    sc = _rest(p)
    sc["body"]["head"] = 28
    sc["fx"] = frozenset(("ledge", "zzz"))
    return sc


def _dance(p):
    s = _s(p, 3)
    return _scene(_pose(hip=6 * s,
                        arms=(70 + 30 * s, 80, 70 - 30 * s, 80),
                        legs=(23 + 18 * s, 40, 23 - 18 * s, 40)),
                  deck_tilt=6 * s)


MOVES = {
    "cruise": _cruise, "push": _push, "carve": _carve,
    "ollie": _ollie, "kickflip": _kickflip, "shuvit": _shuvit,
    "manual": _manual, "grind": _grind, "wallride": _wallride,
    "scan": _scan, "bail": _bail, "recover": _recover,
    "brake": _brake, "wave": _wave, "reject": _reject,
    "crew_out": _crew_out, "crew_in": _crew_in, "victory": _victory,
    "rest": _rest, "sleep": _sleep, "dance": _dance,
}

# Inherit Sensei's canonical engine *pose vocabulary*, not his fighting
# semantics or visual state. The overrides ensure all lifecycle transitions
# are read as skating; an unknown engine pose still follows pose_params.
MOVE_FOR_POSE = {pose: "cruise" for pose in master.MOVE_FOR_POSE}
for names, move in (
    (("crack_knuckles", "attention", "jump"), "ollie"),
    (("run_to_workspace", "walk_to_workspace", "return_home", "fly_down"), "push"),
    (("dash_to_workspace", "sprint_to_workspace", "tip_to_workspace"), "wallride"),
    (("work", "terminal_work", "audio_tune"), "push"),
    (("lean_work", "file_organize", "close_workstation"), "manual"),
    (("web_scan", "read", "memory_vault", "look_around"), "scan"),
    (("dev_merge", "design_draft"), "grind"),
    (("media_paint", "dance"), "shuvit"),
    (("celebrate", "hop", "fly_up"), "kickflip"),
    (("shock", "fall", "sneak", "sit_back"), "bail"),
    (("recover", "inspect", "huff", "retry", "repair"), "recover"),
    (("wake", "panic", "run_to_user", "wait", "point"), "brake"),
    (("wave", "notice", "eyebrow_raise", "look_at_user"), "wave"),
    (("nod",), "ollie"),
    (("shrug", "discard"), "reject"),
    (("open_portal", "channel", "orb_exits"), "crew_out"),
    (("orb_returns", "absorb"), "crew_in"),
    (("leap", "double_jump", "excited", "spin_joy", "leap_double_joy"), "victory"),
    (("idle_bob", "idle", "sit", "head_drop", "stretch_lazy"), "rest"),
    (("sleep", "yawn"), "sleep"),
    (("look_at_input", "watch", "think", "head_tilt", "tilt", "peeking", "squint"), "scan"),
    (("spin", "bounce", "full_bounce", "play_with_object"), "shuvit"),
):
    for name in names:
        MOVE_FOR_POSE[name] = move

# Optional flourishes are not signatures; never override a lifecycle pose.
FLOURISHES = {
    "nose_manual": ("focused", _manual), "curb_grind": ("focused", _grind),
    "heel_flip": ("bright", _kickflip), "bank_carve": ("calm", _carve),
}
CURIOUS_MOVES = ("bank_carve", "nose_manual")
CATEGORY_HINTS = {
    "terminal": ("nose_manual",), "development": ("curb_grind",),
    "web": ("bank_carve",), "file": ("nose_manual",),
    "media": ("heel_flip",), "memory": ("bank_carve",),
}
VOICE = {
    "starting": "Board's down. Let's roll.",
    "reviewing": "Reading the line.",
    "needs-you": "Your call. I'm holding.",
    "issue": "Bailed. Getting back up.",
    "complete": "Clean landing. We did that!",
    "paused": "At the curb, when you're ready.",
}
GREETING = "Kia Kai is ready to roll."


def move_for(pose: str) -> str | None:
    return MOVE_FOR_POSE.get(pose)


def skate_flourishes() -> dict[str, tuple[str, ...]]:
    out: dict[str, list[str]] = {}
    for name, (mood, _fn) in FLOURISHES.items():
        out.setdefault(mood, []).append(name)
    return {k: tuple(v) for k, v in out.items()}


def flourish_hints() -> dict[str, tuple[str, ...]]:
    return dict(CATEGORY_HINTS)


def _draw_board(canvas, P, x, y, angle=0.0, flip=0.0, symbol="K"):
    """Separate articulated prop: flip exposes the underside, wheels remain visible."""
    ca, sa = math.cos(math.radians(angle)), math.sin(math.radians(angle))
    thickness = max(1.6, abs(math.cos(flip)) * 5.5)
    def xy(a, b):
        return x + a * ca - b * sa, y + a * sa + b * ca
    pts = [xy(-32, -thickness), xy(32, -thickness), xy(37, 0),
           xy(32, thickness), xy(-32, thickness), xy(-37, 0)]
    canvas.create_polygon(*[v for point in pts for v in point],
                          fill=P["deck"] if math.cos(flip) >= 0 else P["accent"],
                          outline=P["edge"], width=2)
    for dx in (-24, 24):
        wx, wy = xy(dx, thickness + 4)
        canvas.create_oval(wx - 4.5, wy - 4.5, wx + 4.5, wy + 4.5,
                           fill=P["edge"], outline=P["shoes"], width=1)
        canvas.create_oval(wx - 1.4, wy - 1.4, wx + 1.4, wy + 1.4,
                           fill=P["accent"], outline="")
    if thickness > 3:
        sx, sy = xy(0, 0)
        canvas.create_text(sx, sy, text=symbol, fill=P["edge"],
                           font=("Segoe UI", 9, "bold"))


def _draw_kai(canvas, P, hx, hy, st, eyes):
    """Shared articulated body pipeline used by Sensei and Ade & Rae."""
    skin, edge = P["skin"], P["edge"]
    shade = _mix(skin, "#000000", 0.26)
    body = _Body(canvas, hx, hy, st["spin"], st["rot"], edge)
    hip = st.get("hip", 0.0)
    ankles, swivel = st["ankles"], st["swivel"]
    for i, (side, (upper, knee)) in enumerate(
            ((-1, st["legs"][:2]), (1, st["legs"][2:]))):
        a, k, f = _limb_pts(hip + side * 7, 0, upper, knee, 22, 22, side)
        body.line([a, k, f], edge=True, width=10, fill=P["pants"])
        body.dot(k[0], k[1], 2.1, fill=P["hood_hi"], outline="")
        _foot(body, f, side, ankles[i], swivel[i], P["shoes"],
              strap=P["accent"])

    chest = _Joint(body, (hip, 0), st["torso"], twist=st["twist"])
    chest.poly([(-15, -48), (15, -48), (12, 0), (-12, 0)],
               edge=True, fill=P["hood"])
    chest.poly([(-15, -48), (-5, -48), (-11, -34)],
               fill=P["hood_hi"], outline="")
    chest.line([(0, -39), (0, -8)], width=2, fill=P["hood_hi"])
    chest.line([(-13, -10), (13, -10)], width=3, fill=P["accent"])
    # Small lightning emblem; recognisable without any words.
    chest.poly([(-2, -34), (5, -34), (0, -25), (5, -25), (-4, -15), (-1, -26)],
               fill=P["accent"], outline="")
    for i, (side, (shd, elbow)) in enumerate(
            ((-1, st["arms"][:2]), (1, st["arms"][2:]))):
        sy = -43
        a, e, h = _limb_pts(side * 13, sy,
                            180 - shd if shd > 90 else shd, elbow, 17, 16, side)
        if shd > 90:
            e, h = (e[0], 2 * sy - e[1]), (h[0], 2 * sy - h[1])
        chest.line([a, e], edge=True, width=8, fill=P["hood"])
        chest.line([e, h], edge=True, width=6, fill=skin)
        chest.dot(e[0], e[1], 3, fill=P["hood_hi"], outline="")
        _hand(chest, h, e, side, st["wrists"][i], skin, shade)
    head_y = -62
    chest.line([(0, -48), (0, -49)], width=6, fill=skin)
    head = _Joint(chest, (0, -51), st["head"])
    # Locs with gold cuffs peek out beneath a sideways beanie.
    for j in range(-3, 4):
        head.line([(j * 3, head_y - 10), (j * 4.1, head_y + 13 + abs(j))],
                  width=3, fill=P["hair"])
        if j % 2 == 0:
            head.dot(j * 4, head_y + 7, 1.5, fill=P["accent"], outline="")
    head.dot(0, head_y, 12, edge=True, fill=skin, outline="", squash=True)
    head.poly([(-13, head_y - 5), (12, head_y - 7),
               (14, head_y - 14), (-12, head_y - 18)],
              edge=True, fill=P["pants"])
    head.line([(-12, head_y - 8), (14, head_y - 10)],
              width=3, fill=P["accent"])
    if st["spin"] < 0:
        head.dot(0, head_y - 1, 11, fill=P["hair"], outline="", squash=True)
    else:
        gx = {"left": -2, "right": 2}.get(eyes, 0)
        for side in (-1, 1):
            head.line([(side * 8, head_y - 4), (side * 3, head_y - 5)],
                      width=1.7, fill=P["hair"])
            if eyes == "closed":
                head.line([(side * 5 - 2, head_y), (side * 5 + 2, head_y)],
                          fill=edge, width=1)
            else:
                head.dot(side * 5 + gx, head_y, 1.7,
                         fill=edge, outline="")
        head.line([(-2, head_y + 6), (0, head_y + 8), (3, head_y + 6)],
                  width=1.6, fill=shade)
        head.dot(-12, head_y + 5, 1.4, fill=P["accent"], outline="")


POSE_STATUS = {
    "crack_knuckles": "Starting a task", "attention": "Ready to roll",
    "terminal_work": "Running a command", "web_scan": "Searching the web",
    "read": "Reading", "file_organize": "Working with files",
    "dev_merge": "Working on code", "media_paint": "Making media",
    "design_draft": "Designing", "memory_vault": "Using memory",
    "work": "Working", "lean_work": "Still working",
    "close_workstation": "Step finished", "celebrate": "Step finished",
    "shock": "A step failed", "fall": "A step failed",
    "recover": "Getting back up", "repair": "Fixing it",
    "wait": "Waiting for your OK", "wake": "Needs your OK",
    "panic": "Needs your OK", "hop": "Approved",
    "shrug": "Declined", "leap": "Task complete!",
    "double_jump": "Task complete!", "open_portal": "Sending helpers",
    "channel": "Helpers working", "orb_returns": "Helpers returning",
    "idle_bob": "Quiet", "idle": "Quiet", "sleep": "Resting",
}
MOOD_FOR_MOVE = {
    "bail": "fail", "recover": "fail", "brake": "approve",
    "reject": "approve", "wave": "curious", "scan": "curious",
    "crew_out": "delegate", "crew_in": "delegate",
    "kickflip": "joy", "victory": "joy",
    "rest": "rest", "sleep": "rest", "ollie": "work",
}


def status_text(pose: str, mood: str) -> tuple[str, str]:
    headline = POSE_STATUS.get(pose) or {
        "work": "Working", "delegate": "Delegating", "fail": "A problem",
        "approve": "Needs you", "joy": "Done", "rest": "Resting",
    }.get(mood, "Ready")
    detail = []
    if STATE.running and mood in ("work", "curious", "calm", "fail"):
        marks = ", ".join(sorted({CATEGORY_MARKS.get(c, CATEGORY_MARKS["general"])[0]
                                   for c in STATE.tools}))
        detail.append(f"{STATE.running} line(s) in progress · {marks}")
    if STATE.helpers:
        detail.append(f"{STATE.helpers} crew out")
    if STATE.bails:
        detail.append(f"{STATE.bails} bail(s)")
    if STATE.danger and mood == "approve":
        headline = "Needs your OK"
        detail.insert(0, "dangerous command")
    if STATE.landed and mood == "joy":
        detail.append(f"{STATE.landed} tricks landed")
    if STATE.thinking and mood not in ("approve", "fail"):
        headline = "Thinking"
    return headline, " · ".join(detail)


def draw_skater(canvas, pose: str, progress: float = 0.0,
                palette: str | None = None) -> None:
    P = PALETTES.get(palette or DEFAULT_PALETTE, PALETTES[DEFAULT_PALETTE])
    canvas.delete("all")
    p = progress % 1.0
    move = move_for(pose)
    if pose in FLOURISHES:
        move_fn = FLOURISHES[pose][1]
    else:
        move_fn = MOVES.get(move, _cruise)
    sc = move_fn(p)
    st = sc["body"]
    prm = pose_params(pose, progress)
    if move is None and pose not in FLOURISHES:
        st["rot"] += prm["lean"] * 90
        st["y"] -= prm["bob"]
    mood = MOOD_FOR_MOVE.get(move) or mood_of(pose)
    if pose in ("leap", "double_jump", "excited"):
        mood = "joy"
    if pose in ("wait", "panic", "wake", "run_to_user"):
        mood = "approve"
    if pose in ("shock", "fall", "sneak"):
        mood = "fail"
    glow = MOOD_COLORS.get(mood, MOOD_COLORS["calm"])
    if STATE.danger and mood == "approve":
        glow = "#ef4444"
    elif STATE.running and mood == "work":
        glow = CATEGORY_MARKS.get(STATE.tools[-1], CATEGORY_MARKS["general"])[1]

    # No confidential event content is ever placed on canvas.
    canvas.create_oval(270, 23, 311, 64, fill=P["accent"], outline="")
    for k in range(4):
        canvas.create_line(k * 95, 221, k * 95 + 75, 221,
                           fill=P["concrete"], width=2)
    canvas.create_line(0, FLOOR + 9, FRAME[0], FLOOR + 9,
                       fill=P["concrete"], width=3)
    if "wall" in sc["fx"]:
        canvas.create_rectangle(278, 60, 347, FLOOR,
                                outline=P["concrete"], width=3)
        for k in range(8):
            y = 70 + k * 18
            canvas.create_line(279, y, 345, y, fill=P["concrete"])
    if "rail" in sc["fx"]:
        canvas.create_line(28, FLOOR - 26, 318, FLOOR - 26,
                           fill=P["accent"], width=4)
        for xx in (38, 302):
            canvas.create_line(xx, FLOOR - 26, xx, FLOOR + 7,
                               fill=P["concrete"], width=3)
    if "ledge" in sc["fx"]:
        canvas.create_rectangle(91, FLOOR - 13, 166, FLOOR + 8,
                                fill=P["concrete"], outline=P["edge"])

    dx, dy, tilt, flip = sc["deck"]
    bx = CX + dx
    by = FLOOR - 3 - dy
    # Ground shadow contracts in the air.
    shadow_w = max(10, 36 - dy * 0.2)
    canvas.create_oval(bx - shadow_w, FLOOR + 1, bx + shadow_w,
                       FLOOR + 7, fill=_mix(P["concrete"], P["edge"], 0.25), outline="")
    symbol = CATEGORY_MARKS.get(STATE.category, CATEGORY_MARKS["general"])[0]
    if "crew" in sc["fx"]:
        for i in range(STATE.helpers):
            x = CX - 76 - 38 * i
            y = FLOOR - 4
            _draw_board(canvas, P, x, y, symbol="+")
            canvas.create_oval(x - 9, y - 67, x + 9, y - 48,
                               outline=glow, width=2)
            canvas.create_line(x, y - 48, x, y - 13, fill=glow, width=5)
            canvas.create_line(x, y - 36, x - 10, y - 22, fill=glow, width=3)
            canvas.create_line(x, y - 36, x + 10, y - 22, fill=glow, width=3)
    _draw_board(canvas, P, bx, by, tilt, flip, symbol=symbol)
    _draw_kai(canvas, P, CX + st["x"], HIP_Y - st["y"], st, prm["eyes"])

    if "sparks" in sc["fx"]:
        for k in range(7):
            sx = bx - 15 + (k * 7 + p * 30) % 40
            sy = by + 4 - (k * 3 + p * 20) % 16
            canvas.create_line(sx, sy, sx + 6, sy - 5,
                               fill=P["accent"], width=2)
    if "speed" in sc["fx"]:
        for i in range(4):
            canvas.create_line(bx - 70 - i * 6, by - 17 + i * 6,
                               bx - 45 - i * 6, by - 17 + i * 6,
                               fill=P["accent"], width=2)
    if "hold" in sc["fx"]:
        canvas.create_oval(CX - 59, FLOOR - 138, CX + 68, FLOOR + 10,
                           outline=glow, width=2)
    if "bail" in sc["fx"]:
        canvas.create_text(CX - 35, 62, text="BAIL!", fill="#fb7185",
                           font=("Segoe UI", 15, "bold"))
    if "zzz" in sc["fx"]:
        canvas.create_text(CX + 22, 76, text="Z z z", fill=P["accent"],
                           font=("Segoe UI", 11, "bold"))
    if "confetti" in sc["fx"] or STATE.celebrating:
        for i in range(18):
            x = 12 + (i * 39) % (FRAME[0] - 24)
            y = 10 + (p * 150 + i * 23) % 170
            canvas.create_rectangle(x, y, x + 4, y + 4,
                                    fill=(P["accent"], P["deck"], P["hood_hi"])[i % 3],
                                    outline="")
    if STATE.thinking:
        for i in range(3):
            canvas.create_oval(CX + i * 9 - 9, 55, CX + i * 9 - 5, 59,
                               fill=glow if (int(p * 6) + i) % 3 == 0 else P["concrete"],
                               outline="")
    if pose in EXCLAIM:
        _bubble(canvas, CX, 20, "!", glow)
    elif pose in WONDER:
        _bubble(canvas, CX, 20, "?", glow)

    # Visible, content-free counters and a readable status plaque.
    chips = []
    if STATE.danger:
        chips.append(("CAUTION", "#ef4444"))
    if STATE.running:
        chips.append((f"{STATE.running} tools", glow))
    if STATE.helpers:
        chips.append((f"{STATE.helpers} crew", "#a78bfa"))
    if STATE.bails:
        chips.append((f"{STATE.bails} bails", "#fb7185"))
    if STATE.landed:
        chips.append((f"{STATE.landed} landed", P["accent"]))
    x = 6
    for label, col in chips[:4]:
        x = _badge(canvas, x, 12, label, col)
    headline, detail = status_text(pose, mood)
    canvas.create_rectangle(18, FLOOR + 21, FRAME[0] - 18, FRAME[1] - 5,
                            fill=P["edge"], outline=glow, width=2)
    _mood_icon(canvas, 35, 268, mood, glow)
    tx = (FRAME[0] + 24) / 2
    canvas.create_text(tx, 258 if detail else 267, text=headline,
                       fill="#ffffff", font=("Segoe UI", 11, "bold"))
    if detail:
        canvas.create_text(tx, 282, text=detail[:60], fill=glow,
                           font=("Segoe UI", 8, "bold"))
