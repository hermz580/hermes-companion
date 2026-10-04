"""Nyamekra - the All-Doing Crow. One being, one form, infinite capability.

An Afrocentric anthropomorphic crow drawn from the user's character sheet:
black feathers with violet sheen, a gold crown with a sun-orb, a celestial
halo of orbital rings that is always present, galaxy eyes, stacked gold neck
rings, a golden ankh, kente-like woven gold patterns in the feathered robe,
gold bangles and talons, and the world-orb held in one hand.

Nyamekra never changes form. Its range comes from *composition*: every
gesture can channel any of the ten Symbols of Essence (ankh, adinkra heart,
crow, sun, moon, spiral, baobab, pyramid, orbital rings, infinity), on top of
wing and crow-body moves and every shared engine pose. Through the move
grammar those combine with entrances, gaits, tempos and exits into millions
of distinct performances - see ``performance_space()``.

Truth rules match the other companions: Nyamekra's own moves are body
language used only as mood-matched flourishes, mood colour comes from the
shared Herald palette, and curiosity/tool cues are the same "!", "?" and
props, so a Hermes action always reads the same.
"""
from __future__ import annotations

import math

from hermes_companion.animation.animator import PUPIL, pose_params
from hermes_companion.animation.herald import (
    EXCLAIM, MOOD_COLORS, WONDER, _bubble, _prop, mood_of,
)
from hermes_companion.animation.nia import _limb

# One form, one look. (Kept as a dict so the registry contract is the same.)
_BODY: dict[str, str] = {
        "feather": "#0d0b10", "feather_hi": "#2a2238", "sheen": "#4b2e83",
        "gold": "#e8b84a", "gold_hi": "#ffe39a", "gold_dk": "#9a6b16",
        "robe": "#120f17", "violet": "#5b3aa6", "beak": "#4a4248", "beak_hi": "#8a7f86",
        "talon": "#15121a",
}

# Elemental & energy styles: the being never changes, only the energy it
# carries. name -> (particle colour, accent colour, particle kind)
ENERGY: dict[str, tuple[str, str, str]] = {
    "cosmic": ("#c4b5fd", "#ffe39a", "star"),
    "earth": ("#a16207", "#d6b98c", "pebble"),
    "fire": ("#f97316", "#fde047", "ember"),
    "water": ("#38bdf8", "#e0f2fe", "bubble"),
    "air": ("#e2e8f0", "#94a3b8", "swirl"),
    "shadow": ("#3b3448", "#7c6f9a", "wisp"),
    "light": ("#fefce8", "#fde68a", "ray"),
    "neon": ("#f0abfc", "#22d3ee", "spark"),
    "natural": ("#4ade80", "#bef264", "leaf"),
    "robotic": ("#67e8f9", "#94a3b8", "circuit"),
}
# Every palette is the same body; the name only selects the energy style.
NYAMEKRA_PALETTES: dict[str, dict[str, str]] = {name: dict(_BODY) for name in ENERGY}
NYAMEKRA_DEFAULT_PALETTE = "cosmic"

# Expressions from the character sheet; chosen from what the pose means.
# name -> (brow tilt, eye scale, upper lid 0..1, beak open, eye sparkle)
EXPRESSIONS: dict[str, tuple[float, float, float, float, bool]] = {
    "calm": (0, 1.0, 0.45, 0, False), "focused": (2, 0.85, 0.35, 0, False),
    "curious": (-3, 1.15, 0.0, 1, True), "joyful": (-2, 1.0, 0.25, 4, True),
    "fierce": (4, 0.9, 0.3, 3, False), "wise": (0, 0.95, 0.55, 0, True),
    "playful": (-2, 1.1, 0.1, 3, True), "sad": (-4, 0.95, 0.5, 0, False),
    "protective": (3, 1.05, 0.15, 1, False),
}
_EXPRESSION_OF_MOOD = {"calm": "calm", "work": "focused", "curious": "curious",
                       "joy": "joyful", "fail": "sad", "approve": "protective",
                       "delegate": "wise", "rest": "calm"}

# "Different tasks, different looks, same Nyamekra": role gear appears only
# while Hermes is doing that kind of work, so the look itself says what is
# happening. The body never changes.
ROLE_OF: dict[str, str] = {
    "terminal_work": "tech", "dev_merge": "tech", "lean_work": "tech", "work": "tech",
    "web_scan": "traveler", "read": "teacher", "file_organize": "teacher",
    "media_paint": "creative", "design_draft": "creative", "audio_tune": "creative",
    "memory_vault": "majestic", "open_portal": "celestial", "orb_exits": "celestial",
    "orb_returns": "celestial", "absorb": "celestial", "repair": "healer",
    "retry": "healer", "recover": "healer", "attention": "tactical",
    "run_to_user": "tactical", "panic": "tactical", "wait": "tactical",
}
# Key tools, shown as the chest emblem for each role.
ROLE_TOOL = {"tech": "automation", "traveler": "travel", "teacher": "knowledge",
             "creative": "creation", "healer": "healing", "tactical": "protection",
             "celestial": "omnipresence", "majestic": "time"}

SYMBOLS = ("ankh", "adinkra", "crow", "sun", "moon", "spiral", "baobab",
           "pyramid", "orbit", "infinity")
SYMBOL_MOOD = {"ankh": "bright", "sun": "bright", "infinity": "bright", "crow": "bright",
               "moon": "calm", "spiral": "calm", "orbit": "calm",
               "baobab": "focused", "pyramid": "focused", "adinkra": "focused"}

# gesture -> (arms l_sh, l_el, r_sh, r_el; wing 0 closed .. 1 spread; bounce)
GESTURES = {
    "raise":   ((20, 20, 160, 10), 0.6, 2),
    "offer":   ((15, 30, 70, 40), 0.2, 1),
    "sweep":   ((70, 10, 80, 10), 0.9, 2),
    "summon":  ((150, 20, 150, 20), 1.0, 3),
    "cradle":  ((45, 90, 45, 90), 0.1, 1),
    "bless":   ((20, 30, 110, 60), 0.4, 1),
    "point":   ((15, 20, 95, 0), 0.3, 1),
    "orbit":   ((60, 70, 120, 50), 0.7, 2),
}

# body moves: name -> (mood, arms, wing, bounce, sway, fx)
BODY_MOVES = {
    "wing_spread":    ("bright", (85, 0, 85, 0), 1.0, 2, 0, {"wings"}),
    "wing_beat":      ("bright", (70, 10, 70, 10), 1.0, 5, 0, {"beat"}),
    "glide":          ("calm", (90, 0, 90, 0), 0.9, 1, 6, {"glide"}),
    "halo_spin":      ("bright", (30, 30, 30, 30), 0.3, 2, 0, {"halo_fast"}),
    "orb_juggle":     ("bright", (40, 60, 120, 30), 0.3, 3, 0, {"juggle"}),
    "eye_glow":       ("focused", (15, 20, 15, 20), 0.1, 0, 0, {"eye"}),
    "head_cock":      ("calm", (15, 20, 15, 20), 0.1, 1, 0, {"cock"}),
    "caw":            ("bright", (30, 20, 30, 20), 0.5, 3, 0, {"caw"}),
    "preen":          ("calm", (60, 120, 15, 20), 0.2, 0, 0, {"preen"}),
    "hop_step":       ("bright", (30, 20, 30, 20), 0.4, 6, 3, {"hop"}),
    "wing_wrap":      ("uneasy", (40, 140, 40, 140), 0.0, 0, 0, {"wrap"}),
    "feather_ruffle": ("uneasy", (20, 20, 20, 20), 0.3, 2, 2, {"ruffle"}),
    "meditate":       ("calm", (40, 100, 40, 100), 0.2, 0, 0, {"float"}),
    "survey_realms":  ("focused", (15, 20, 100, 30), 0.3, 0, 4, {"scan"}),
    "steady_breath":  ("uneasy", (25, 40, 25, 40), 0.1, 0, 0, {"breath"}),
    # from the turnaround sheet's scenes
    "commanding_presence": ("focused", (40, 60, 85, 10), 0.5, 1, 0, {"scepter"}),
    "cosmic_control":  ("bright", (30, 30, 130, 30), 0.6, 2, 0, {"cosmos"}),
    "storyteller_read": ("calm", (50, 80, 50, 80), 0.2, 0, 0, {"seat", "book"}),
    "glyph_weave":     ("focused", (40, 60, 110, 40), 0.3, 1, 0, {"glyphs"}),
    "turn_back":       ("calm", (12, 10, 12, 10), 0.2, 0, 0, {"back"}),
    # dynamic poses from the sheet
    "flight":          ("bright", (80, 10, 80, 10), 1.0, 8, 4, {"flight", "beat"}),
    "landing":         ("calm", (60, 20, 60, 20), 0.8, 0, 0, {"land"}),
    "casting":         ("focused", (40, 50, 95, 5), 0.4, 1, 0, {"cast"}),
    "perch_crouch":    ("calm", (35, 90, 35, 90), 0.1, 0, 0, {"crouch"}),
    "sprint_dash":     ("bright", (20, 100, 60, 40), 0.6, 2, 6, {"sprint"}),
    "defense_shield":  ("uneasy", (70, 60, 90, 20), 0.5, 0, 0, {"shield"}),
    "interact":        ("focused", (30, 50, 75, 50), 0.2, 0, 0, {"interact"}),
}

# Poses that travel left: Nyamekra turns to face the way it is going.
FACE_LEFT = frozenset({"run_to_user", "return_home", "panic", "orb_returns"})


class _Mirror:
    """Canvas proxy that draws everything mirrored across the frame centre."""

    def __init__(self, canvas, width: int = 200) -> None:
        self._c, self._w = canvas, width

    def _xs(self, coords):
        flat = list(coords[0]) if len(coords) == 1 and isinstance(coords[0], (list, tuple)) \
            else list(coords)
        return [self._w - v if i % 2 == 0 else v for i, v in enumerate(flat)]

    def delete(self, *a):
        return self._c.delete(*a)

    def create_line(self, *coords, **kw):
        return self._c.create_line(*self._xs(coords), **kw)

    def create_polygon(self, *coords, **kw):
        return self._c.create_polygon(*self._xs(coords), **kw)

    def _box(self, method, x1, y1, x2, y2, **kw):
        return getattr(self._c, method)(self._w - x2, y1, self._w - x1, y2, **kw)

    def create_oval(self, x1, y1, x2, y2, **kw):
        return self._box("create_oval", x1, y1, x2, y2, **kw)

    def create_rectangle(self, x1, y1, x2, y2, **kw):
        return self._box("create_rectangle", x1, y1, x2, y2, **kw)

    def create_arc(self, x1, y1, x2, y2, **kw):
        if "start" in kw or "extent" in kw:
            start, extent = kw.get("start", 0.0), kw.get("extent", 90.0)
            kw = dict(kw, start=180.0 - start - extent, extent=extent)
        return self._box("create_arc", x1, y1, x2, y2, **kw)

    def create_text(self, x, y, **kw):
        return self._c.create_text(self._w - x, y, **kw)


def _build_moves() -> dict[str, tuple]:
    moves: dict[str, tuple] = {}
    for g, (arms, wing, bounce) in GESTURES.items():
        for s in SYMBOLS:
            moves[f"{g}_{s}"] = (SYMBOL_MOOD[s], arms, wing, bounce, 0, {"symbol:" + s})
    moves.update(BODY_MOVES)
    return moves


NYAMEKRA_MOVES: dict[str, tuple] = _build_moves()


def nyamekra_flourishes() -> dict[str, tuple[str, ...]]:
    out: dict[str, list[str]] = {}
    for name, spec in NYAMEKRA_MOVES.items():
        out.setdefault(spec[0], []).append(name)
    return {k: tuple(v) for k, v in out.items()}


def performance_space() -> int:
    """Distinct decorated performances of a one-move Hermes chain."""
    from hermes_companion.behavior.move_grammar import (
        EASINGS, FLOURISH_MS, FLOURISH_POSES, GAITS, TEMPOS,
    )
    extra = nyamekra_flourishes()
    per_mood = min(len(FLOURISH_POSES[m]) + len(extra.get(m, ())) for m in FLOURISH_POSES)
    entries = 1 + per_mood + per_mood * (per_mood - 1)
    exits = 1 + per_mood
    return entries * exits * len(GAITS) * len(EASINGS) * len(TEMPOS) * len(FLOURISH_MS)


_ARMS = {
    "down": (12, 10, 12, 10), "up": (165, 10, 165, 10), "cross": (50, 120, 50, 120),
    "hold": (40, 70, 40, 70), "wave": (12, 10, 150, 30), "bent": (30, 90, 30, 90),
    "stretch": (90, 0, 90, 0), "throw": (20, 20, 140, 10), "work": (45, 80, 50, 75),
}
_WING_FOR_BODY = {"jump": 0.9, "fall": 0.7, "walk": 0.3, "lean_forward": 0.5, "tall": 0.4}


# ---- symbols of essence ---------------------------------------------------
def _symbol(canvas, name, x, y, s, color, p):
    w = max(2, int(round(s * 0.18)))
    if name == "ankh":
        canvas.create_oval(x - s * 0.35, y - s, x + s * 0.35, y - s * 0.3, outline=color, width=w)
        canvas.create_line(x, y - s * 0.3, x, y + s, fill=color, width=w)
        canvas.create_line(x - s * 0.6, y - s * 0.15, x + s * 0.6, y - s * 0.15, fill=color, width=w)
    elif name == "adinkra":                                  # Akoma heart
        canvas.create_polygon(x, y + s * 0.9, x - s, y - s * 0.1, x - s * 0.55, y - s * 0.8,
                              x, y - s * 0.35, x + s * 0.55, y - s * 0.8, x + s, y - s * 0.1,
                              outline=color, fill="", smooth=True)
    elif name == "crow":
        canvas.create_polygon(x - s, y, x - s * 0.2, y - s * 0.4, x + s * 0.5, y - s * 0.3,
                              x + s, y - s * 0.5, x + s * 0.6, y, x - s * 0.1, y + s * 0.3,
                              fill=color, outline="")
    elif name == "sun":
        canvas.create_oval(x - s * 0.45, y - s * 0.45, x + s * 0.45, y + s * 0.45, fill=color, outline="")
        for i in range(10):
            a = i * 0.628 + p * 2
            canvas.create_line(x + math.cos(a) * s * 0.6, y + math.sin(a) * s * 0.6,
                               x + math.cos(a) * s, y + math.sin(a) * s, fill=color, width=w)
    elif name == "moon":
        canvas.create_arc(x - s, y - s, x + s, y + s, start=60, extent=240, style="arc",
                          outline=color, width=int(w * 1.8))
    elif name == "spiral":
        pts = []
        for i in range(28):
            t = i / 27
            a = t * 4.2 * math.pi + p * 3
            pts += [x + math.cos(a) * s * t, y + math.sin(a) * s * t]
        canvas.create_line(*pts, fill=color, width=w, smooth=True)
    elif name == "baobab":
        canvas.create_polygon(x - s * 0.25, y + s, x + s * 0.25, y + s, x + s * 0.18, y - s * 0.2,
                              x - s * 0.18, y - s * 0.2, fill=color, outline="")
        for k in (-1, 0, 1):
            canvas.create_line(x, y - s * 0.2, x + k * s * 0.8, y - s * 0.75, fill=color, width=w)
        canvas.create_oval(x - s, y - s, x + s, y - s * 0.55, outline=color, width=w)
    elif name == "pyramid":
        canvas.create_polygon(x - s, y + s * 0.7, x + s, y + s * 0.7, x, y - s,
                              outline=color, fill="", width=w)
        for k in (0.2, -0.2):
            canvas.create_line(x - s * (0.6 + k), y + s * 0.7 * (1 - k), x + s * (0.6 + k),
                               y + s * 0.7 * (1 - k), fill=color, width=1)
    elif name == "orbit":
        canvas.create_oval(x - s * 0.3, y - s * 0.3, x + s * 0.3, y + s * 0.3, fill=color, outline="")
        canvas.create_oval(x - s, y - s * 0.35, x + s, y + s * 0.35, outline=color, width=w)
        a = p * 6.28
        canvas.create_oval(x + math.cos(a) * s - 2, y + math.sin(a) * s * 0.35 - 2,
                           x + math.cos(a) * s + 2, y + math.sin(a) * s * 0.35 + 2,
                           fill=color, outline="")
    elif name == "infinity":
        pts = []
        for i in range(33):
            t = i / 32 * 2 * math.pi
            d = 1 + math.sin(t) ** 2
            pts += [x + s * math.cos(t) / d, y + s * math.sin(t) * math.cos(t) / d]
        canvas.create_line(*pts, fill=color, width=w, smooth=True)


def _glow_dot(canvas, x, y, r, color, core):
    canvas.create_oval(x - r * 1.8, y - r * 1.8, x + r * 1.8, y + r * 1.8, outline=color, width=1)
    canvas.create_oval(x - r, y - r, x + r, y + r, fill=core, outline=color)


def _feather(canvas, x, y, ang, length, width, fill, edge, tip):
    """One tapered feather from (x, y) pointing at `ang` (radians)."""
    dx, dy = math.cos(ang), math.sin(ang)
    nx, ny = -dy, dx
    tx, ty = x + dx * length, y + dy * length
    canvas.create_polygon(x + nx * width * 0.3, y + ny * width * 0.3,
                          x + dx * length * 0.45 + nx * width, y + dy * length * 0.45 + ny * width,
                          tx, ty,
                          x + dx * length * 0.45 - nx * width, y + dy * length * 0.45 - ny * width,
                          x - nx * width * 0.3, y - ny * width * 0.3,
                          fill=fill, outline=edge, smooth=True)
    canvas.create_line(x, y, tx - dx * 3, ty - dy * 3, fill=edge, width=1)
    if tip:
        canvas.create_line(tx - dx * 6, ty - dy * 6, tx, ty, fill=tip, width=2)


def _wing(canvas, root_x, root_y, side, spread, P, p, beat):
    """A crow wing as a fan of individual feathers; spread 0 folded .. 1 open."""
    flap = math.sin(p * 2 * math.pi * 2) * (0.35 if beat else 0.06)
    # folded: feathers hang down along the body; open: they fan up and out
    base = math.pi / 2 - side * (0.15 + spread * 1.35 + flap * spread)
    for layer, (fill, length, width, tip) in enumerate((
            (P["feather"], 58, 6.5, P["gold"]),          # primaries
            (P["feather_hi"], 44, 6.0, None),            # secondaries
            (P["sheen"], 28, 5.5, None))):               # coverts
        n = 7 - layer
        for i in range(n):
            t = i / max(1, n - 1)
            ang = base + side * (t - 0.5) * (0.25 + spread * 0.9)
            ln = length * (0.75 + 0.35 * t) * (0.7 + 0.3 * spread)
            _feather(canvas, root_x, root_y, ang, ln, width, fill, P["gold_dk"] if layer == 0 else fill, tip)


def expression_of(pose: str, mood: str, own: bool) -> str:
    if pose in ("defense_shield", "attention", "panic"):
        return "fierce"
    if pose in ("storyteller_read", "meditate", "glyph_weave", "memory_vault") or \
            pose.endswith("_baobab") or pose.endswith("_spiral"):
        return "wise"
    if own and mood == "joy":
        return "playful"
    return _EXPRESSION_OF_MOOD.get(mood, "calm")


_TOOL_ICON = {"automation": "gear", "travel": "arrow", "knowledge": "book",
              "creation": "star", "healing": "cross", "protection": "shield",
              "omnipresence": "infinity", "time": "clock"}


def _tool_icon(canvas, tool, x, y, color):
    kind = _TOOL_ICON[tool]
    if kind == "gear":
        for i in range(8):
            a = i * 0.785
            canvas.create_line(x + math.cos(a) * 3, y + math.sin(a) * 3,
                               x + math.cos(a) * 5.5, y + math.sin(a) * 5.5, fill=color, width=2)
        canvas.create_oval(x - 3, y - 3, x + 3, y + 3, outline=color, width=1)
    elif kind == "arrow":
        canvas.create_line(x - 5, y + 4, x + 5, y - 4, fill=color, width=2)
        canvas.create_polygon(x + 5, y - 4, x, y - 4, x + 5, y + 1, fill=color, outline="")
    elif kind == "book":
        canvas.create_polygon(x - 6, y - 4, x, y - 2, x + 6, y - 4, x + 6, y + 4, x, y + 6,
                              x - 6, y + 4, fill="", outline=color)
        canvas.create_line(x, y - 2, x, y + 6, fill=color)
    elif kind == "star":
        pts = []
        for i in range(10):
            a = -math.pi / 2 + i * math.pi / 5
            r = 6 if i % 2 == 0 else 2.5
            pts += [x + math.cos(a) * r, y + math.sin(a) * r]
        canvas.create_polygon(*pts, fill=color, outline="")
    elif kind == "cross":
        canvas.create_rectangle(x - 1.5, y - 5, x + 1.5, y + 5, fill=color, outline="")
        canvas.create_rectangle(x - 5, y - 1.5, x + 5, y + 1.5, fill=color, outline="")
    elif kind == "shield":
        canvas.create_polygon(x - 5, y - 5, x + 5, y - 5, x + 5, y, x, y + 6, x - 5, y,
                              fill="", outline=color, width=2)
    elif kind == "infinity":
        _symbol(canvas, "infinity", x, y, 6, color, 0.0)
    elif kind == "clock":
        canvas.create_oval(x - 5, y - 5, x + 5, y + 5, outline=color, width=1)
        canvas.create_line(x, y, x, y - 4, fill=color, width=1)
        canvas.create_line(x, y, x + 3, y + 1, fill=color, width=1)


def _energy(canvas, style, cx, cy, p):
    col, accent, kind = ENERGY[style]
    for i in range(10):
        a = i * 0.628 + p * 2.0
        r = 48 + 10 * math.sin(p * 6.28 + i)
        x, y = cx + math.cos(a) * r, cy - 30 + math.sin(a) * r * 0.9
        c = col if i % 2 else accent
        if kind in ("star", "spark"):
            canvas.create_line(x - 2.5, y, x + 2.5, y, fill=c, width=1)
            canvas.create_line(x, y - 2.5, x, y + 2.5, fill=c, width=1)
        elif kind == "ember":
            y -= (p * 30 + i * 5) % 30
            canvas.create_oval(x - 1.8, y - 2.6, x + 1.8, y + 2.6, fill=c, outline="")
        elif kind == "bubble":
            y -= (p * 24 + i * 6) % 24
            canvas.create_oval(x - 2.5, y - 2.5, x + 2.5, y + 2.5, fill="", outline=c)
        elif kind == "swirl":
            canvas.create_arc(x - 5, y - 3, x + 5, y + 3, start=i * 36, extent=200,
                              style="arc", outline=c, width=1)
        elif kind == "wisp":
            canvas.create_line(x, y, x + 3, y - 4, x - 1, y - 8, fill=c, width=2, smooth=True)
        elif kind == "ray":
            canvas.create_line(cx + math.cos(a) * 36, cy - 30 + math.sin(a) * 33, x, y, fill=c, width=1)
        elif kind == "leaf":
            canvas.create_polygon(x - 3, y, x, y - 3, x + 3, y, x, y + 3, fill=c, outline="", smooth=True)
        elif kind == "pebble":
            canvas.create_oval(x - 2, y - 1.5, x + 2, y + 1.5, fill=c, outline="")
        elif kind == "circuit":
            canvas.create_line(x - 4, y, x, y, x, y - 4, fill=c, width=1)
            canvas.create_oval(x - 1, y - 5, x + 1, y - 3, fill=c, outline="")


def _role_gear(canvas, role, cx, top, hcx, hcy, hands, P, p):
    if role == "tech":                                            # headset + HUD ring
        canvas.create_arc(hcx - 20, hcy - 22, hcx + 20, hcy + 10, start=20, extent=140,
                          style="arc", outline="#22d3ee", width=2)
        canvas.create_oval(hcx - 23, hcy - 4, hcx - 15, hcy + 6, fill="#0f172a", outline="#22d3ee")
        canvas.create_line(hcx - 19, hcy + 6, hcx - 8, hcy + 12, fill="#22d3ee", width=1)
    elif role == "traveler":                                      # pack strap + satchel
        canvas.create_line(cx - 18, top + 2, cx + 20, top + 46, fill="#7c4a1e", width=4)
        canvas.create_rectangle(cx + 16, top + 40, cx + 30, top + 52, fill="#7c4a1e", outline=P["gold_dk"])
    elif role == "teacher":                                       # spectacles + scarf
        canvas.create_oval(hcx + 1, hcy - 11, hcx + 11, hcy + 1, outline=P["gold_hi"], width=1)
        canvas.create_line(cx - 16, top + 1, cx + 16, top + 1, fill="#1e3a8a", width=5)
        canvas.create_line(cx + 10, top + 1, cx + 14, top + 22, fill="#1e3a8a", width=5)
    elif role == "creative":                                      # tilted beret + paint dots
        canvas.create_oval(hcx - 18, hcy - 26, hcx + 10, hcy - 14, fill="#9f1239", outline="")
        canvas.create_oval(hcx - 4, hcy - 30, hcx, hcy - 26, fill="#9f1239", outline="")
        for i, col in enumerate(("#f472b6", "#fbbf24", "#60a5fa", "#a3e635")):
            canvas.create_oval(cx - 14 + i * 9, top + 54, cx - 10 + i * 9, top + 58, fill=col, outline="")
    elif role == "healer":                                        # leaf sash + healing glow
        canvas.create_line(cx + 18, top + 2, cx - 20, top + 44, fill="#15803d", width=4)
        for i in range(4):
            lx, ly = cx + 14 - i * 9, top + 8 + i * 10
            canvas.create_polygon(lx - 3, ly, lx, ly - 3, lx + 3, ly, lx, ly + 3, fill="#4ade80", outline="")
        hx, hy = hands[1]
        canvas.create_oval(hx - 8, hy - 8, hx + 8, hy + 8, outline="#4ade80", width=2)
    elif role == "tactical":                                      # pauldrons
        for side in (-1, 1):
            canvas.create_arc(cx + side * 22 - 10, top - 4, cx + side * 22 + 10, top + 14,
                              start=0, extent=180, style="chord", fill=P["gold_dk"], outline=P["gold"])
    elif role == "celestial":                                     # spirit glow
        for r in (40, 48):
            canvas.create_oval(cx - r, top - 6, cx + r, top + 90, outline="#c4b5fd", width=1)
        for i in range(6):
            a = p * 6.28 + i
            canvas.create_oval(cx + math.cos(a) * 44 - 1.5, top + 40 + math.sin(a) * 46 - 1.5,
                               cx + math.cos(a) * 44 + 1.5, top + 40 + math.sin(a) * 46 + 1.5,
                               fill="#ede9fe", outline="")


def draw_nyamekra(canvas, pose: str, progress: float = 0.0, palette: str | None = None) -> None:
    P = _BODY
    style = palette if palette in ENERGY else NYAMEKRA_DEFAULT_PALETTE
    canvas.delete("all")
    if pose in FACE_LEFT:
        canvas = _Mirror(canvas)
    p = progress % 1.0
    osc = math.sin(p * 2 * math.pi)
    own = NYAMEKRA_MOVES.get(pose)
    prm = pose_params(pose if own is None else "idle_bob", progress)
    body, eyes, extra = prm["body"], prm["eyes"], prm["extra"]
    shear = prm["lean"] * 30.0

    if own is not None:
        mood_name, arms, wing, bounce, sway, fx = own
        arms = tuple(a + osc * (10 if i % 2 == 0 else 6) * (1 if i < 2 else -1)
                     for i, a in enumerate(arms))
        dy = -abs(osc) * bounce
        dx = sway * osc
        mood = {"bright": "joy", "focused": "work", "uneasy": "fail", "calm": "calm"}[mood_name]
        symbol = next((f.split(":", 1)[1] for f in fx if f.startswith("symbol:")), None)
    else:
        fx, symbol = set(), None
        arms = _ARMS.get(prm["arms"], _ARMS["down"])
        if prm["arms"] == "wave":
            arms = (arms[0], arms[1], arms[2] + osc * 18, arms[3] + osc * 12)
        wing = _WING_FOR_BODY.get(body, 0.15)
        dy, dx = prm["bob"], 0.0
        mood = mood_of(pose)
    glow = MOOD_COLORS.get(mood, MOOD_COLORS["calm"])
    if "float" in fx:
        dy -= 8 + 2 * osc
    if "seat" in fx or "crouch" in fx:
        dy += 12
    if "flight" in fx:
        dy -= 8 + 4 * osc
    if "sprint" in fx:
        shear += 10
    expr = EXPRESSIONS[expression_of(pose, mood, own is not None)]
    role = ROLE_OF.get(pose)

    cx = 100 + shear + dx
    cy = 150 + dy + {"jump": -12, "fall": 14, "sit": 14, "tall": -5}.get(body, 0)
    top = cy - 58

    # ---- celestial halo: always present, always gold --------------------------
    hx, hy = cx + shear * 0.3, top - 38
    spin = p * (6.28 if "halo_fast" in fx else 1.2)
    for r, w in ((44, 1), (36, 2), (29, 1)):
        canvas.create_oval(hx - r, hy - r, hx + r, hy + r, outline=P["gold_dk"] if w == 1 else P["gold"],
                           width=w)
    for i in range(16):
        a = spin + i * 0.3927
        canvas.create_line(hx + math.cos(a) * 36, hy + math.sin(a) * 36,
                           hx + math.cos(a) * (40 if i % 2 else 44), hy + math.sin(a) * (40 if i % 2 else 44),
                           fill=P["gold"], width=1)
    for tilt in (0.32, -0.45):                                    # orbital rings
        pts = []
        for i in range(25):
            t = i / 24 * 2 * math.pi + spin * 0.5
            ox, oy = math.cos(t) * 52, math.sin(t) * 52 * 0.28
            pts += [hx + ox * math.cos(tilt) - oy * math.sin(tilt),
                    hy + ox * math.sin(tilt) + oy * math.cos(tilt)]
        canvas.create_line(*pts, fill=P["gold_dk"], width=1, smooth=True)
    for i in range(6):                                            # stars in the halo
        a = spin * 1.7 + i * 1.047
        sx, sy = hx + math.cos(a) * 50, hy + math.sin(a) * 50 * 0.6
        canvas.create_oval(sx - 1.3, sy - 1.3, sx + 1.3, sy + 1.3, fill=P["gold_hi"], outline="")
    # mood is shown by the inner glow so the halo itself never changes
    canvas.create_oval(hx - 24, hy - 24, hx + 24, hy + 24, outline=glow, width=2)

    _energy(canvas, style, cx, cy, p)

    # ---- wings (behind the robe) -------------------------------------------------
    beat = "beat" in fx or body == "jump"
    for side in (-1, 1):
        _wing(canvas, cx + side * 12, top + 10, side, wing, P, p + (0.25 if side > 0 else 0), beat)

    # ---- long feather cape: from the shoulders to the floor --------------------------
    hem = cy + 40
    for row in range(3):
        n = 11 - row * 2
        span = 46 - row * 8
        for i in range(n):
            t = i / (n - 1)
            fx0 = cx - span + 2 * span * t
            length = (hem + 10 - top) * (0.92 - row * 0.12) * (0.85 + 0.15 * math.sin(t * math.pi))
            sway_ang = math.pi / 2 + (t - 0.5) * 0.5 + math.sin(p * 6.28 + i) * 0.03
            _feather(canvas, fx0 * 0.6 + cx * 0.4, top + 4 + row * 6, sway_ang, length,
                     7 - row, (P["feather"], P["feather_hi"], P["sheen"])[row],
                     P["violet"] if row == 0 else P["feather"], P["violet"] if row == 0 else None)
    if "seat" in fx:                                              # a carved stone seat
        canvas.create_rectangle(cx - 40, hem - 22, cx + 40, hem + 6, fill="#2a2420", outline=P["gold_dk"])
        for i in range(5):
            canvas.create_line(cx - 34 + i * 17, hem - 18, cx - 26 + i * 17, hem + 2, fill=P["gold_dk"])

    # ---- feathered robe with kente-like gold weave -----------------------------------
    robe = [cx - 20, top - 2, cx + 20, top - 2, cx + 27, top + 30]
    n_hem = 9
    for i in range(n_hem + 1):                                    # feathered, flowing hem
        t = i / n_hem
        x = cx + 36 + osc * 2 - t * (72 + osc * 4)
        robe += [x, hem + (7 if i % 2 else 0) + math.sin(p * 6.28 + i) * 1.5]
    robe += [cx - 27, top + 30]
    canvas.create_polygon(*robe, fill=P["robe"], outline=P["gold_dk"], width=1, smooth=True)
    for row in range(5):                                          # feather scallops
        y = top + 16 + row * 13
        half = 20 + row * 3.2
        n = 5 + row
        for i in range(n):
            fx0 = cx - half + (2 * half) * (i + 0.5) / n
            canvas.create_arc(fx0 - 6, y - 5, fx0 + 6, y + 7, start=180, extent=180,
                              style="chord", fill=P["feather_hi"] if (i + row) % 2 else P["feather"],
                              outline=P["sheen"])
    for k, yy in enumerate((top + 30, hem - 8)):                  # woven gold bands
        half = 20 + (yy - top) * 0.2
        canvas.create_line(cx - half, yy, cx + half, yy, fill=P["gold_dk"], width=5)
        steps = 10
        for i in range(steps):
            bx = cx - half + 2 * half * (i + 0.5) / steps
            if (i + k) % 2:
                canvas.create_polygon(bx - 3, yy, bx, yy - 3, bx + 3, yy, bx, yy + 3,
                                      fill=P["gold_hi"], outline="")
            else:
                canvas.create_rectangle(bx - 2, yy - 2, bx + 2, yy + 2, fill=P["violet"], outline="")
    for side in (-1, 1):                                          # gold-patterned stoles
        x0 = cx + side * 10
        canvas.create_line(x0, top + 2, x0 + side * 4, hem + 2, fill=P["gold_dk"], width=8)
        for i in range(8):
            yy = top + 8 + i * 9.5
            xx = x0 + side * 4 * (yy - top) / (hem - top)
            if i % 2:
                canvas.create_polygon(xx - 3, yy, xx, yy - 3.5, xx + 3, yy, xx, yy + 3.5,
                                      fill="", outline=P["gold_hi"])
            else:
                canvas.create_line(xx - 3, yy - 2, xx + 3, yy + 2, fill=P["gold"], width=1)
                canvas.create_line(xx + 3, yy - 2, xx - 3, yy + 2, fill=P["gold"], width=1)
    belt = top + 46
    canvas.create_line(cx - 22, belt, cx + 22, belt, fill=P["gold"], width=3)
    for k, px in enumerate((-17, 0, 17)):                         # orb pendants on chains
        drop = 10 + (k % 2) * 6 + math.sin(p * 6.28 + k) * 1.5
        canvas.create_line(cx + px, belt, cx + px, belt + drop, fill=P["gold_dk"], width=1)
        _glow_dot(canvas, cx + px, belt + drop + 3, 2.6, P["gold"], P["gold_hi"])
    _symbol(canvas, "ankh", cx, hem - 18, 7, P["gold"], p)        # the lower ankh

    # ---- feathered shoulder mantle --------------------------------------------------
    for row, (rad, col) in enumerate(((30, P["feather"]), (24, P["feather_hi"]), (17, P["feather"]))):
        n = 9 - row * 2
        for i in range(n):
            a = math.pi * (0.05 + 0.9 * i / (n - 1))
            fx0 = cx + math.cos(a) * rad
            fy0 = top + 2 + math.sin(a) * rad * 0.35 + row * 4
            _feather(canvas, fx0, fy0 - 6, math.pi / 2 + (fx0 - cx) * 0.012, 16 - row * 2, 5,
                     col, P["sheen"], P["gold_dk"] if row == 0 else None)

    # ---- taloned feet ----------------------------------------------------------------
    for side in (-1, 1):
        fx_, fy = cx + side * 12 + (osc * 4 * side if "hop" in fx else 0), hem + 2
        canvas.create_rectangle(fx_ - 4, fy - 14, fx_ + 4, fy - 3, fill=P["gold"], outline=P["gold_dk"])
        for k in range(3):
            canvas.create_line(fx_ - 4, fy - 12 + k * 3.5, fx_ + 4, fy - 12 + k * 3.5,
                               fill=P["gold_dk"], width=1)
        for t in (-1, 0, 1):
            canvas.create_line(fx_, fy, fx_ + t * 6 + side * 2, fy + 7, fill=P["gold_dk"], width=2)
        canvas.create_oval(fx_ - 4, fy - 4, fx_ + 4, fy + 2, fill=P["talon"], outline=P["gold_dk"])

    # ---- golden ankh, glowing ---------------------------------------------------------
    ax_, ay_ = cx + 1, top + 30
    canvas.create_oval(ax_ - 9, ay_ - 9, ax_ + 9, ay_ + 21, outline=P["gold_dk"], width=1)
    _symbol(canvas, "ankh", ax_, ay_ + 6, 10, P["gold"], p)

    # ---- arms: feathered sleeves, gold bangles, talons --------------------------------
    sy = top + 9
    hands = []
    for side, (sh, el) in ((-1, arms[0:2]), (1, arms[2:4])):
        up = sh > 100
        ex, ey, hx2, hy2 = _limb(canvas, cx + side * 16, sy, min(sh, 100) if not up else 180 - sh,
                                 el, 18, 17, side, 9, P["feather"], flip_up=up)
        canvas.create_line(cx + side * 16, sy, ex, ey, fill=P["sheen"], width=2)
        gx0, gy0 = ex + (hx2 - ex) * 0.4, ey + (hy2 - ey) * 0.4
        canvas.create_line(gx0, gy0, hx2, hy2, fill=P["gold"], width=8, capstyle="round")
        for k in (0.5, 0.68, 0.86):
            bx, by = ex + (hx2 - ex) * k, ey + (hy2 - ey) * k
            canvas.create_oval(bx - 4.5, by - 2, bx + 4.5, by + 2, outline=P["gold_dk"], width=1)
        _glow_dot(canvas, ex + (hx2 - ex) * 0.6, ey + (hy2 - ey) * 0.6, 1.6, P["gold_hi"], P["gold_hi"])
        for t in (-1, 0, 1):                                      # talon fingers
            canvas.create_line(hx2, hy2, hx2 + t * 4 + side * 2, hy2 + 6, fill=P["talon"], width=2)
            canvas.create_line(hx2 + t * 4 + side * 2, hy2 + 6, hx2 + t * 4 + side * 3, hy2 + 8,
                               fill=P["gold"], width=1)
        hands.append((hx2, hy2))

    # world-orb above the raised hand, or juggled
    if "juggle" in fx or (own is None and prm["arms"] in ("up", "hold", "throw")) or pose == "idle_bob":
        ox, oy = hands[1][0], hands[1][1] - 14 - (abs(osc) * 18 if "juggle" in fx else 0)
        canvas.create_oval(ox - 9, oy - 9, ox + 9, oy + 9, fill="#2a3f7a", outline=P["gold_hi"])
        canvas.create_polygon(ox - 6, oy - 3, ox - 1, oy - 7, ox + 2, oy - 2, ox - 2, oy + 4,
                              fill="#3f6b3a", outline="")
        canvas.create_polygon(ox + 2, oy + 1, ox + 7, oy - 2, ox + 6, oy + 6, fill="#3f6b3a", outline="")
        canvas.create_oval(ox - 13, oy - 4, ox + 13, oy + 4, outline=P["gold"], width=1)

    # ---- neck rings + collar ---------------------------------------------------------------
    for i in range(4):
        y = top - 3 - i * 3.2
        canvas.create_oval(cx - 11 + i * 0.6, y - 2.2, cx + 11 - i * 0.6, y + 2.2,
                           fill=P["gold"] if i % 2 == 0 else P["gold_dk"], outline="")
    for i in range(9):                                            # medallion collar
        a = math.pi * (0.12 + 0.76 * i / 8)
        mx, my = cx + math.cos(a) * 19, top + 2 + math.sin(a) * 8
        canvas.create_oval(mx - 2.6, my - 2.6, mx + 2.6, my + 2.6, fill=P["gold"], outline=P["gold_dk"])

    # ---- crow head ---------------------------------------------------------------------------
    cock = 6 if "cock" in fx else 0
    hcx, hcy = cx + shear * 0.4 + cock * 0.5, top - 26 + (2 if "preen" in fx else 0)
    for i in range(7):                                            # ruffled crest
        a = math.pi * (1.1 + 0.8 * i / 6)
        ruff = 3 if "ruffle" in fx else 0
        r = 19 + (i % 2) * 4 + ruff * abs(osc)
        canvas.create_polygon(hcx + math.cos(a) * 12, hcy + math.sin(a) * 12,
                              hcx + math.cos(a + 0.15) * r, hcy + math.sin(a + 0.15) * r,
                              hcx + math.cos(a + 0.3) * 12, hcy + math.sin(a + 0.3) * 12,
                              fill=P["feather"], outline="")
    canvas.create_oval(hcx - 19, hcy - 18, hcx + 19, hcy + 19, fill=P["feather"], outline=P["sheen"])
    canvas.create_arc(hcx - 13, hcy - 14, hcx + 9, hcy + 8, start=95, extent=100, style="arc",
                      outline=P["sheen"], width=3)
    canvas.create_arc(hcx - 10, hcy - 4, hcx + 12, hcy + 16, start=200, extent=90, style="arc",
                      outline=P["violet"], width=2)
    # beak (open when cawing), gold-banded
    face = 1
    open_ = 5 if "caw" in fx and osc > 0 else max(expr[3], 3 if eyes == "wide" else 0)
    bx0, by0 = hcx + 12 * face, hcy + 2
    tip = bx0 + 27 * face
    canvas.create_polygon(bx0 - 2, by0 - 8, bx0 + 12, by0 - 6, tip, by0 + 2 - open_ * 0.3,
                          bx0, by0 + 1, fill=P["beak"], outline=P["gold"], smooth=True)
    canvas.create_line(bx0 + 2, by0 - 5, tip - 4, by0 + 1, fill=P["beak_hi"], width=1)
    canvas.create_polygon(bx0, by0 + 2 + open_, tip - 6, by0 + 4 + open_ * 0.6, bx0, by0 + 7,
                          fill=P["beak"], outline=P["gold"])
    canvas.create_line(bx0 + 4, by0 - 5, bx0 + 4, by0 + 5 + open_, fill=P["gold"], width=2)
    # galaxy eye: tinted by mood, pupil follows the gaze
    ex0, ey0 = hcx + 5, hcy - 5
    if eyes == "closed":
        canvas.create_arc(ex0 - 5, ey0 - 3, ex0 + 5, ey0 + 3, start=200, extent=140,
                          style="arc", width=2, outline=P["gold"])
    elif eyes == "xeyes":
        canvas.create_line(ex0 - 4, ey0 - 4, ex0 + 4, ey0 + 4, width=2, fill=P["gold"])
        canvas.create_line(ex0 - 4, ey0 + 4, ex0 + 4, ey0 - 4, width=2, fill=P["gold"])
    else:
        r = (7.5 if eyes == "wide" or "eye" in fx else 6.5) * expr[1]
        canvas.create_oval(ex0 - r, ey0 - r, ex0 + r, ey0 + r, fill="#1b1033", outline=P["gold"], width=1)
        canvas.create_oval(ex0 - r * 0.7, ey0 - r * 0.7, ex0 + r * 0.7, ey0 + r * 0.7, fill=P["violet"],
                           outline="")
        gx = {"left": -2, "right": 2}.get(eyes, 0)
        gy = {"up": -2, "down": 2}.get(eyes, 0)
        canvas.create_oval(ex0 - 2.2 + gx, ey0 - 2.2 + gy, ex0 + 2.2 + gx, ey0 + 2.2 + gy,
                           fill=glow, outline="")
        for i in range(4):                                       # stars in the eye
            a = p * 3 + i * 1.57
            canvas.create_oval(ex0 + math.cos(a) * r * 0.55 - 0.6, ey0 + math.sin(a) * r * 0.55 - 0.6,
                               ex0 + math.cos(a) * r * 0.55 + 0.6, ey0 + math.sin(a) * r * 0.55 + 0.6,
                               fill=P["gold_hi"], outline="")
        if "eye" in fx:
            canvas.create_oval(ex0 - r - 3, ey0 - r - 3, ex0 + r + 3, ey0 + r + 3, outline=glow, width=2)
        if expr[2] > 0:                                          # upper lid: calm, wise, sad
            lid = ey0 - r + 2 * r * expr[2]
            canvas.create_polygon(ex0 - r - 1, ey0 - r - 1, ex0 + r + 1, ey0 - r - 1,
                                  ex0 + r + 1, lid, ex0 - r - 1, lid,
                                  fill=P["feather"], outline="")
            canvas.create_line(ex0 - r, lid, ex0 + r, lid, fill=P["gold_dk"], width=1)
        if expr[4]:                                              # sparkle: curious, joyful, wise
            canvas.create_oval(ex0 + r * 0.3, ey0 - r * 0.6, ex0 + r * 0.3 + 2.2, ey0 - r * 0.6 + 2.2,
                               fill="white", outline="")
    tilt = expr[0]
    canvas.create_line(ex0 - 8, ey0 - 9 - tilt, ex0 + 7, ey0 - 9 + tilt,
                       fill=P["feather_hi"], width=3)
    # crown with sun-orb
    ctop = hcy - 15
    canvas.create_polygon(hcx - 13, ctop, hcx - 15, ctop - 11, hcx - 8, ctop - 6, hcx - 5, ctop - 16,
                          hcx, ctop - 8, hcx + 5, ctop - 16, hcx + 8, ctop - 6, hcx + 15, ctop - 11,
                          hcx + 13, ctop, fill=P["gold"], outline=P["gold_dk"])
    for gx in (-15, -5, 5, 15):
        _glow_dot(canvas, hcx + gx, ctop - (11 if abs(gx) > 10 else 16), 1.5, P["gold_hi"], P["violet"])
    canvas.create_line(hcx - 12, ctop - 1, hcx + 12, ctop - 1, fill=P["gold_hi"], width=1)
    _glow_dot(canvas, hcx, ctop - 17, 3.5, P["gold"], P["gold_hi"])

    # ---- channelled symbol of essence --------------------------------------------------------
    if symbol is not None:
        sx_, sy_ = hands[1][0], hands[1][1] - 20 - abs(osc) * 4
        canvas.create_oval(sx_ - 15, sy_ - 15, sx_ + 15, sy_ + 15, outline=glow, width=1)
        _symbol(canvas, symbol, sx_, sy_, 10 + 1.5 * abs(osc), P["gold_hi"], p)
    if "scepter" in fx:                                           # scepter + armillary sphere
        sx0, sy0 = hands[0]
        canvas.create_line(sx0, sy0 + 40, sx0, sy0 - 36, fill=P["gold"], width=3)
        ox, oy = sx0, sy0 - 46
        canvas.create_oval(ox - 9, oy - 9, ox + 9, oy + 9, outline=P["gold"], width=2)
        for tilt in (0.3, -0.6, 1.2):
            pts = []
            for i in range(17):
                t = i / 16 * 2 * math.pi + p * 2
                a, b = math.cos(t) * 13, math.sin(t) * 4.5
                pts += [ox + a * math.cos(tilt) - b * math.sin(tilt), oy + a * math.sin(tilt) + b * math.cos(tilt)]
            canvas.create_line(*pts, fill=P["gold_hi"], width=1, smooth=True)
        _glow_dot(canvas, ox, oy, 2.5, P["gold"], P["gold_hi"])
    if "cosmos" in fx:                                            # planets orbiting the body
        for k, (col, rad) in enumerate((("#c97b3a", 4), ("#3a6fc9", 5), ("#8a5ac9", 3), ("#d9c25a", 3.5))):
            t = p * 2 * math.pi * (1 + k * 0.3) + k * 1.6
            ox, oy = cx + math.cos(t) * (58 - k * 4), cy - 40 + math.sin(t) * (18 + k * 3)
            canvas.create_oval(ox - rad, oy - rad, ox + rad, oy + rad, fill=col, outline=P["gold_hi"])
        canvas.create_oval(cx - 58, cy - 58, cx + 58, cy - 22, outline=P["violet"], width=1)
    if "book" in fx:                                              # glowing open book
        bx0 = (hands[0][0] + hands[1][0]) / 2
        by0 = (hands[0][1] + hands[1][1]) / 2 - 4
        canvas.create_polygon(bx0 - 16, by0, bx0, by0 + 4, bx0 + 16, by0, bx0 + 16, by0 - 10,
                              bx0, by0 - 6, bx0 - 16, by0 - 10, fill="#f6e7b8", outline=P["gold_dk"])
        canvas.create_line(bx0, by0 - 6, bx0, by0 + 4, fill=P["gold_dk"])
        for i in range(3):
            canvas.create_line(bx0 - 13, by0 - 7 + i * 2.5, bx0 - 3, by0 - 5 + i * 2.5, fill=P["gold_dk"])
        canvas.create_oval(bx0 - 20, by0 - 22, bx0 + 20, by0 + 2, outline=P["gold_hi"], width=1)
    if "glyphs" in fx or "book" in fx:                            # floating glyph panels
        for k in range(3):
            gx = cx + 44 + k * 4
            gy = cy - 70 + k * 22 + math.sin(p * 6.28 + k) * 3
            canvas.create_rectangle(gx - 9, gy - 9, gx + 9, gy + 9, outline=P["gold"], width=1)
            _symbol(canvas, SYMBOLS[(k * 3 + int(p * 3)) % len(SYMBOLS)], gx, gy, 5, P["gold_hi"], p)
    if "back" in fx:                                              # back view: cloak and medallion
        canvas.create_oval(hcx - 20, hcy - 19, hcx + 20, hcy + 20, fill=P["feather"], outline=P["sheen"])
        canvas.create_polygon(cx - 30, top - 2, cx + 30, top - 2, cx + 38, hem + 6, cx - 38, hem + 6,
                              fill=P["feather"], outline=P["violet"])
        for i in range(6):
            yy = top + 12 + i * 12
            canvas.create_line(cx - 30 - i, yy, cx + 30 + i, yy, fill=P["feather_hi"], width=1)
        canvas.create_line(cx, top + 4, cx, hem + 4, fill=P["gold_dk"], width=8)
        _glow_dot(canvas, cx, top + 18, 6, P["gold"], P["gold_hi"])
        _symbol(canvas, "ankh", cx, top + 42, 8, P["gold"], p)
    if "scan" in fx:
        for i in range(3):
            canvas.create_arc(hcx + 20, hcy - 20 - i * 6, hcx + 60 + i * 10, hcy + 20 + i * 6,
                              start=-30, extent=60, style="arc", outline=glow, width=1)
    if "glide" in fx:
        for i in range(3):
            y = cy - 30 + i * 14
            canvas.create_line(cx - 50 - i * 6, y, cx - 72 - i * 6, y, fill=P["gold_dk"], width=2)

    # ---- role look + key-tool emblem ---------------------------------------------------
    if role is not None:
        _role_gear(canvas, role, cx, top, hcx, hcy, hands, P, p)
        mx, my = cx, top + 64
        canvas.create_oval(mx - 8, my - 8, mx + 8, my + 8, fill=P["robe"], outline=glow, width=2)
        _tool_icon(canvas, ROLE_TOOL[role], mx, my, P["gold_hi"])

    # ---- dynamic poses ----------------------------------------------------------------------
    if "land" in fx:
        for k in (-1, 1):
            for i in range(3):
                canvas.create_oval(cx + k * (24 + i * 8) - 3, cy + 46 - i * 3, cx + k * (24 + i * 8) + 3,
                                   cy + 50 - i * 3, fill="#6b6280", outline="")
    if "cast" in fx:
        hx, hy = hands[1]
        for i in range(4):
            canvas.create_line(hx, hy, hx + 14 + i * 7, hy - 6 + math.sin(p * 12 + i) * 6,
                               fill=glow if i % 2 else P["gold_hi"], width=2)
    if "sprint" in fx:
        for i in range(4):
            y = cy - 40 + i * 12
            canvas.create_line(cx - 40 - i * 6, y, cx - 66 - i * 6, y, fill=P["gold_dk"], width=2)
    if "shield" in fx:
        sx, sy2 = cx + 40, cy - 34
        pts = []
        for i in range(6):
            a = i * math.pi / 3 + math.pi / 6
            pts += [sx + math.cos(a) * 18, sy2 + math.sin(a) * 22]
        canvas.create_line(*pts, pts[0], pts[1], fill=glow, width=3)
        _tool_icon(canvas, "protection", sx, sy2, P["gold_hi"])
    if "interact" in fx:
        hx, hy = hands[1]
        canvas.create_rectangle(hx + 4, hy - 26, hx + 34, hy - 6, outline="#22d3ee", width=1)
        for i in range(3):
            canvas.create_line(hx + 8, hy - 21 + i * 5, hx + 26 - i * 4, hy - 21 + i * 5, fill="#67e8f9")
    if "flight" in fx:
        for i in range(3):
            canvas.create_line(cx - 20 + i * 20, cy + 52, cx - 26 + i * 20, cy + 64, fill=P["gold_dk"], width=1)

    # ---- shared cues: tools, effects, curiosity -----------------------------------------
    if extra == "zzz":
        for i in range(3):
            canvas.create_text(hcx + 26 + i * 7, hcy - 20 - i * 10 - p * 6, text="z",
                               fill=MOOD_COLORS["rest"], font=("Segoe UI", 9 + i * 3, "bold"))
    elif extra in ("speed_lines", "spin_lines"):
        for i in range(4):
            y = cy - 40 + i * 12
            canvas.create_line(cx - 36 - i * 6, y, cx - 60 - i * 6, y, fill=glow, width=2)
    elif extra in ("confetti", "spark"):
        for i in range(10):
            a = p * 6.28 + i * 0.628
            canvas.create_line(hcx + math.cos(a) * 30, hcy + math.sin(a) * 30,
                               hcx + math.cos(a) * 38, hcy + math.sin(a) * 38, fill=P["gold_hi"], width=2)
    elif extra == "sweat":
        canvas.create_oval(hcx - 18, hcy - 10, hcx - 12, hcy - 2, fill="#60a5fa", outline="")
    elif extra is not None:
        _prop(canvas, extra, cx - 40, top - 4, p, glow)

    if pose in EXCLAIM:
        _bubble(canvas, hcx - 26, hcy - 30, "!", glow)
    elif pose in WONDER:
        _bubble(canvas, hcx - 26, hcy - 30, "?", glow)


# ---- making every symbol mean something -----------------------------------
# Which Symbols of Essence Nyamekra channels for each kind of Hermes work.
# Each list spans moods so a fitting symbol exists whatever the chain's mood.
CATEGORY_SYMBOLS: dict[str, tuple[str, ...]] = {
    "terminal": ("pyramid", "sun", "spiral"),        # strength, creation, evolution
    "development": ("pyramid", "sun", "spiral"),
    "web": ("baobab", "crow", "orbit"),              # all knowledge, the messenger, all realms
    "browser": ("baobab", "crow", "orbit"),
    "file": ("adinkra", "sun", "moon"),              # wisdom, creation, order/cycles
    "learning": ("baobab", "ankh", "moon"),
    "planning": ("adinkra", "infinity", "moon"),
    "memory": ("baobab", "infinity", "spiral"),      # roots, eternity, cycles
    "media": ("adinkra", "sun", "moon"),
    "design": ("adinkra", "sun", "moon"),
    "delegation": ("pyramid", "infinity", "orbit"),  # strength, omnipresence, realms
    "general": ("adinkra", "ankh", "moon"),          # wisdom, life, balance
}


def flourish_hints() -> dict[str, tuple[str, ...]]:
    return {cat: tuple(m for m in NYAMEKRA_MOVES if m.rsplit("_", 1)[-1] in syms)
            for cat, syms in CATEGORY_SYMBOLS.items()}


# In-place moves Nyamekra uses when it notices you.
CURIOUS_MOVES = ("head_cock", "eye_glow", "caw", "survey_realms", "glyph_weave", "preen")

# Same meanings as everyone else, in the All-Doing Crow's voice.
VOICE = {
    "starting": "I see the path. On it.",
    "reviewing": "Reading what returned…",
    "needs-you": "Your OK is needed.",
    "issue": "A tool failed - I'm mending it.",
    "complete": "Done. Every path leads here.",
    "paused": "As you wish. Holding.",
}
GREETING = "I am Nyamekra. All paths, one being."
