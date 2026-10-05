"""Masque - the many behind the mask (Shegoth variant).

A vast, many-eyed form of hair-like tendrils, crowned with a thorn halo,
holding a porcelain mask in front of herself with delicate hands. The mask
is what Hermes shows you; the body is the work you don't see. Every part of
her is driven by real Hermes signals, not just her moves:

* mask face (7 expressions)     <- what the event means (work, failure, approval...)
* cracks on the mask            <- failures this session, healed by a success streak
* tendrils reaching up          <- tools running at once, each holding its tool glyph
* colour of tendrils + aura     <- the kind of work (terminal green, web blue, ...)
* eyes opening across the body  <- Hermes thinking (pre_llm_call)
* body form                     <- typist, lantern, library, scribe, vault,
                                   cathedral crawler, split selves, leaning close
* body size and pulse           <- how much work this session has done, heartbeats
* small masked copies           <- helpers (subagents) running

Layers, back to front (from the sheet): thorn halo, colour aura, hair-like
tendrils and body, eyes in the dark, roses and jewels, form props, tool
tendrils, hands, the mask (always on top of the body), front effects.

Spook level is the palette: ``eerie`` (default, lace), ``cute`` (soft, few
eyes, no teeth) or ``monster`` (many eyes, full grin).
"""
from __future__ import annotations

import math
import random
import time
from dataclasses import dataclass, field

FRAME = (320, 300)
CX, FLOOR = 160, 292

INK = "#0b0910"
INK_HI = "#2a2235"
PORCELAIN = "#f4efe9"
PORCELAIN_SH = "#d9d0c8"
GOLD = "#d4a54a"
GOLD_HI = "#f3d48a"
GOLD_DK = "#8a6526"
ROSE = "#7a0f24"
ROSE_HI = "#b3243d"
EYE_IRIS = "#e8b04a"

# Colour by tool category (from the sheet's legend).
CATEGORY_COLOUR = {
    "terminal": "#39ff7a", "development": "#39ff7a", "web": "#3aa0ff",
    "file": "#ffb547", "learning": "#ffb547", "planning": "#ffb547",
    "memory": "#b066ff", "browser": "#2ee6e6", "delegation": "#ff4fd8",
    "media": "#ffb547", "design": "#ffb547", "general": "#9b7bd6",
    "failure": "#ff3b3b", "approval": "#ffd34d",
}

# Which tool glyph a tendril holds for each category.
CATEGORY_GLYPH = {
    "terminal": "terminal", "development": "terminal", "web": "globe",
    "browser": "window", "file": "page", "learning": "page", "planning": "page",
    "media": "page", "design": "page", "memory": "orb", "delegation": "people",
    "general": "spark",
}

# Body form for each kind of work.
CATEGORY_FORM = {
    "terminal": "typist", "development": "typist", "web": "lantern",
    "browser": "crawler", "file": "library", "learning": "library",
    "planning": "scribe", "media": "scribe", "design": "scribe",
    "memory": "vault", "delegation": "split", "general": None,
}
FORM_OF_POSE = {
    "terminal_work": "typist", "dev_merge": "typist", "web_scan": "lantern",
    "read": "library", "file_organize": "library", "media_paint": "scribe",
    "design_draft": "scribe", "memory_vault": "vault", "open_portal": "split",
    "channel": "split", "orb_exits": "split", "orb_returns": "split",
    "run_to_user": "lean", "wait": "lean", "attention": "lean", "panic": "lean",
    "approval_request": "lean",
}
MASQUE_MOVES_LEAN = ("approval_request",)

EXPRESSIONS = ("cute", "sad", "confused", "focused", "scary", "evil", "blank")

PALETTES = {
    #          eyes  teeth  tendrils  lace
    "eerie":   (1.0, True, 14, True),
    "cute":    (0.4, False, 10, True),
    "monster": (1.8, True, 18, False),
}
DEFAULT_PALETTE = "eerie"


# ---------------------------------------------------------------------------
# Live state: what Hermes is doing right now (content-free counts only)
# ---------------------------------------------------------------------------
@dataclass
class MasqueState:
    category: str = "general"
    cracks: int = 0            # failures not yet healed
    streak: int = 0            # successes in a row (3 heal one crack)
    work: int = 0              # tool runs this session -> body size
    running: int = 0           # tools in flight -> tendrils up
    helpers: int = 0           # subagents in flight -> small masked copies
    danger: bool = False       # a destructive command is waiting for approval
    think_until: float = 0.0
    beat_until: float = 0.0
    tools: list = field(default_factory=list)   # categories of the tools in flight
    swap_until: float = 0.0    # a tendril is pulling a new mask over the face
    rest_until: float = 0.0    # session over: folded in, a small smiling mask and a rose
    clock: object = field(default=time.monotonic, repr=False)

    def _mood(self) -> str:
        return {"failure": "sad", "approval": "ask"}.get(self.category, "work" if self.running else "calm")

    def observe(self, ev) -> None:
        kind = getattr(ev.kind, "value", str(ev.kind))
        now = self.clock()
        cat = ev.category or "general"
        before = self._mood()
        self._apply(kind, cat, now)
        if self._mood() != before:                  # her mood changed: swap the mask on screen
            self.swap_until = now + 0.8

    def _apply(self, kind: str, cat: str, now: float) -> None:
        if kind != "agent.idle" and kind != "task.complete":
            self.rest_until = 0.0
        if kind == "agent.started":
            self.work, self.running, self.helpers = 0, 0, 0
            self.tools = []
        elif kind == "user.prompt_submitted":
            self.think_until = now + 3.0
        elif kind == "tool.started":
            self.running = min(self.running + 1, 6)
            self.work += 1
            self.category = cat
            self.tools = (self.tools + [cat])[-6:]
        elif kind == "tool.progress":
            self.beat_until = now + 1.5
            self.category = cat
        elif kind == "tool.finished":
            self.running = max(0, self.running - 1)
            self._done(cat)
            self.streak += 1
            if self.streak >= 3 and self.cracks:
                self.cracks -= 1
                self.streak = 0
        elif kind == "tool.failed":
            self.running = max(0, self.running - 1)
            self._done(cat)
            self.cracks = min(self.cracks + 1, 3)
            self.streak = 0
            self.category = "failure"
        elif kind == "approval.required":
            self.category = "approval"
            self.danger = cat == "dangerous"
        elif kind in ("approval.approved", "approval.rejected"):
            self.danger = False
            self.category = "general"
        elif kind == "agent.subagent_spawned":
            self.helpers = min(self.helpers + 1, 4)
            self.category = "delegation"
        elif kind in ("agent.subagent_finished", "agent.subagent_failed"):
            self.helpers = max(0, self.helpers - 1)
            if kind.endswith("failed"):
                self.cracks = min(self.cracks + 1, 3)
        elif kind in ("agent.idle", "task.complete"):
            self.running, self.helpers, self.danger = 0, 0, False
            self.category = "general"
            self.tools = []
            self.rest_until = now + 8.0

    def _done(self, cat: str) -> None:
        if cat in self.tools:
            self.tools.remove(cat)
        elif self.tools:
            self.tools.pop(0)

    @property
    def swapping(self) -> bool:
        return self.clock() < self.swap_until

    @property
    def resting(self) -> bool:
        return self.clock() < self.rest_until

    @property
    def thinking(self) -> bool:
        return self.clock() < self.think_until

    @property
    def pulsing(self) -> bool:
        return self.clock() < self.beat_until

    def key(self) -> tuple:
        size = min(4, self.work // 6)
        return (self.category, self.cracks, size, self.running, self.helpers,
                self.danger, self.thinking, self.pulsing, tuple(self.tools), self.swapping,
                self.resting)


STATE = MasqueState()


def observe(ev) -> None:
    STATE.observe(ev)


def state_key() -> tuple:
    return STATE.key()


# ---------------------------------------------------------------------------
# Her own moves: name -> (grammar mood, fx set)
# ---------------------------------------------------------------------------
MASQUE_MOVES: dict[str, tuple[str, frozenset]] = {
    # bright
    "tendril_bloom": ("bright", frozenset({"bloom", "mask:cute"})),
    "rose_bloom": ("bright", frozenset({"roses", "mask:cute"})),
    "mask_twirl": ("bright", frozenset({"swap", "mask:cute"})),
    "halo_flare": ("bright", frozenset({"halo", "mask:cute"})),
    "eye_bloom": ("bright", frozenset({"alleyes", "mask:cute"})),
    "spin_veil": ("bright", frozenset({"spin", "mask:cute"})),
    # calm
    "veil_sway": ("calm", frozenset({"sway"})),
    "coil_rest": ("calm", frozenset({"coil"})),
    "mask_peek": ("calm", frozenset({"slip"})),
    "cradle_mask": ("calm", frozenset({"cradle", "mask:cute"})),
    "lantern_drift": ("calm", frozenset({"lantern"})),
    # focused
    "eyes_scan": ("focused", frozenset({"scan", "mask:focused"})),
    "tendril_type": ("focused", frozenset({"type", "mask:focused"})),
    "glyph_orbit": ("focused", frozenset({"glyphs", "mask:focused"})),
    "reach_out": ("focused", frozenset({"reach", "mask:focused"})),
    "weave_sigil": ("focused", frozenset({"sigil", "mask:focused"})),
    # uneasy
    "mask_slip": ("uneasy", frozenset({"slip", "mask:sad"})),
    "tendrils_recoil": ("uneasy", frozenset({"recoil", "mask:confused"})),
    "petals_fall": ("uneasy", frozenset({"petals", "mask:sad"})),
    "shrink_back": ("uneasy", frozenset({"shrink", "mask:confused"})),
    "mask_swap_scary": ("uneasy", frozenset({"swap", "mask:scary"})),
}
# Movement actions and special moves from the turnaround / actions sheets.
MASQUE_MOVES.update({
    "turn_left": ("calm", frozenset({"turn:-1"})),
    "turn_right": ("calm", frozenset({"turn:1"})),
    "turn_back": ("calm", frozenset({"back"})),
    "crouch": ("uneasy", frozenset({"crouch", "mask:confused"})),
    "stretch": ("bright", frozenset({"stretch", "bloom", "mask:cute"})),
    "look_up": ("calm", frozenset({"lookup"})),
    "look_down": ("calm", frozenset({"lookdown"})),
    "float_walk": ("calm", frozenset({"side", "float"})),
    "run_trail": ("focused", frozenset({"side", "slide", "mask:focused"})),
    "jump_leap": ("bright", frozenset({"jump", "mask:cute"})),
    "follow_cursor": ("focused", frozenset({"follow"})),
    "react_click": ("focused", frozenset({"click", "mask:confused"})),
    "celebrate": ("bright", frozenset({"spin", "roses", "mask:cute"})),
    "curious_peek": ("calm", frozenset({"peek", "slip"})),
    "wake_up": ("calm", frozenset({"wake"})),
    "angry": ("uneasy", frozenset({"angry", "recoil", "mask:scary"})),
    "window_perch": ("calm", frozenset({"perch"})),
    "land": ("calm", frozenset({"land", "crouch", "mask:cute"})),
    "enter_crack": ("focused", frozenset({"portal_in"})),
    "exit_crack": ("bright", frozenset({"portal_out", "mask:cute"})),
})
TRAVEL_MOVES = {
    "ink_slide": ("bright", frozenset({"slide", "side", "mask:focused"})),
    "crack_portal": ("bright", frozenset({"portal"})),
    "lunge": ("bright", frozenset({"lunge", "side", "mask:cute"})),
    "hover": ("calm", frozenset({"hover", "side"})),
}
for _n, _s in list(TRAVEL_MOVES.items()):
    TRAVEL_MOVES[_n + "_back"] = _s
MASQUE_MOVES.update(TRAVEL_MOVES)
FACE_LEFT = frozenset(n for n in TRAVEL_MOVES if n.endswith("_back")) | \
    {"run_to_user", "return_home", "panic", "orb_returns"}


def masque_flourishes() -> dict[str, tuple[str, ...]]:
    out: dict[str, list[str]] = {}
    for name, (mood, _fx) in MASQUE_MOVES.items():
        if name not in TRAVEL_MOVES:
            out.setdefault(mood, []).append(name)
    return {k: tuple(v) for k, v in out.items()}


CATEGORY_HINTS = {
    "terminal": ("tendril_type", "glyph_orbit"), "development": ("tendril_type", "glyph_orbit"),
    "web": ("lantern_drift", "eyes_scan", "reach_out"), "browser": ("reach_out", "eyes_scan"),
    "file": ("weave_sigil", "glyph_orbit"), "memory": ("eye_bloom", "halo_flare"),
    "delegation": ("tendril_bloom", "glyph_orbit"), "general": ("veil_sway", "rose_bloom"),
}


def flourish_hints() -> dict[str, tuple[str, ...]]:
    return dict(CATEGORY_HINTS)


CURIOUS_MOVES = ("mask_peek", "eyes_scan", "reach_out", "eye_bloom", "veil_sway")
VOICE = {
    "starting": "So many hands. Let's begin.",
    "reviewing": "A thousand eyes are reading…",
    "needs-you": "Your word, before I reach further.",
    "issue": "That one cracked. Still smiling.",
    "complete": "Done. The mask never lies about that.",
    "paused": "Holding still. Watching.",
}
GREETING = "I am Masque. The face you see; the many behind it."


# ---------------------------------------------------------------------------
# Drawing helpers
# ---------------------------------------------------------------------------
def _mix(a: str, b: str, t: float) -> str:
    a_, b_ = int(a[1:], 16), int(b[1:], 16)
    out = 0
    for sh in (16, 8, 0):
        ca, cb = (a_ >> sh) & 255, (b_ >> sh) & 255
        out |= int(ca + (cb - ca) * t) << sh
    return f"#{out:06x}"


def _strand(canvas, pts, w0, w1, fill, sheen=None):
    """A tapered tendril along pts (thick at the root, fine at the tip).

    Drawn as one filled outline instead of a line per segment: the same look,
    a fraction of the drawing work (Masque draws dozens of these per frame).
    """
    n = len(pts)
    if n < 2:
        return
    left, right = [], []
    for i, (x, y) in enumerate(pts):
        ax, ay = pts[max(0, i - 1)]
        bx, by = pts[min(n - 1, i + 1)]
        dx, dy = bx - ax, by - ay
        ln = math.hypot(dx, dy) or 1.0
        nx, ny = -dy / ln, dx / ln
        half = max(0.6, (w0 + (w1 - w0) * i / (n - 1)) / 2)
        left.append((x + nx * half, y + ny * half))
        right.append((x - nx * half, y - ny * half))
    outline = left + right[::-1]
    canvas.create_polygon(*[c for q in outline for c in q], fill=fill, outline="")
    r0 = w0 / 2                                              # a rounded root
    canvas.create_oval(pts[0][0] - r0, pts[0][1] - r0, pts[0][0] + r0, pts[0][1] + r0,
                       fill=fill, outline="")
    if sheen:
        flat = [c for p in pts[1:-1] for c in p]
        if len(flat) >= 4:
            canvas.create_line(*flat, fill=sheen, width=1.2, smooth=True)


def _curve(x, y, ang, length, curl, phase, segs=9):
    pts = [(x, y)]
    a = ang
    step = length / segs
    for i in range(segs):
        a += curl * (0.6 + 0.4 * math.sin(phase + i * 0.7)) / segs
        x += math.cos(a) * step
        y += math.sin(a) * step
        pts.append((x, y))
    return pts


def _eye(canvas, x, y, r, openness, iris=EYE_IRIS, look=(0.0, 0.0)):
    if openness <= 0.08:
        canvas.create_line(x - r, y, x + r, y, fill=INK_HI, width=1.2)
        return
    h = r * 0.62 * openness
    canvas.create_polygon(x - r, y, x - r * 0.4, y - h, x + r * 0.4, y - h, x + r, y,
                          x + r * 0.4, y + h, x - r * 0.4, y + h,
                          fill="#f0e6d2", outline=GOLD_DK, smooth=True)
    ir = min(r * 0.5, h * 0.95)
    ix, iy = x + look[0] * r * 0.35, y + look[1] * h * 0.3
    canvas.create_oval(ix - ir * 1.12, iy - ir * 1.12, ix + ir * 1.12, iy + ir * 1.12,
                       fill="#7a4a12", outline="")                       # dark limbal ring
    canvas.create_oval(ix - ir, iy - ir, ix + ir, iy + ir, fill=iris, outline="")
    canvas.create_oval(ix - ir * 0.75, iy - ir * 0.75, ix + ir * 0.75, iy + ir * 0.75,
                       outline="#f7d27a", width=0.6)
    canvas.create_oval(ix - ir * 0.45, iy - ir * 0.45, ix + ir * 0.45, iy + ir * 0.45,
                       fill="#140b06", outline="")
    canvas.create_oval(ix - ir * 0.6, iy - ir * 0.75, ix - ir * 0.2, iy - ir * 0.35,
                       fill="white", outline="")
    canvas.create_line(x - r, y, x - r * 0.4, y - h, x + r * 0.4, y - h, x + r, y,
                       fill="#050307", width=1.6, smooth=True)          # upper lid line
    if r >= 5:
        for i in range(3):                                               # lashes
            lx = x - r * 0.45 + i * r * 0.45
            canvas.create_line(lx, y - h, lx + (i - 1) * r * 0.18, y - h - r * 0.35,
                               fill="#050307", width=1.2)


def _rose(canvas, x, y, r, bloom=1.0, leaves=True):
    if leaves:
        for k in (-1, 1):
            canvas.create_polygon(x + k * r * 0.6, y + r * 0.4, x + k * r * 1.9, y + r * 0.2,
                                  x + k * r * 1.2, y + r * 1.1, fill="#1f3a22", outline="#2f5a34",
                                  smooth=True)
    canvas.create_oval(x - r, y - r, x + r, y + r, fill=ROSE, outline="#3a0610")
    for i in range(5):
        a = i * 1.2566
        rr = r * 0.55 * bloom
        canvas.create_arc(x + math.cos(a) * rr * 0.5 - rr, y + math.sin(a) * rr * 0.5 - rr,
                          x + math.cos(a) * rr * 0.5 + rr, y + math.sin(a) * rr * 0.5 + rr,
                          start=math.degrees(a), extent=150, style="arc",
                          outline=ROSE_HI, width=1.2)
    canvas.create_oval(x - r * 0.25, y - r * 0.25, x + r * 0.25, y + r * 0.25,
                       fill="#4d0815", outline="")


def glyph(canvas, kind, x, y, s, colour):
    """The tool a tendril holds, in a small glowing frame."""
    canvas.create_rectangle(x - s, y - s, x + s, y + s, fill="#07130c" if kind == "terminal"
                            else "#0a0d18", outline=colour, width=2)
    if kind == "terminal":
        canvas.create_line(x - s * 0.6, y - s * 0.3, x - s * 0.15, y, x - s * 0.6, y + s * 0.3,
                           fill=colour, width=2)
        canvas.create_line(x, y + s * 0.35, x + s * 0.55, y + s * 0.35, fill=colour, width=2)
    elif kind == "globe":
        canvas.create_oval(x - s * 0.7, y - s * 0.7, x + s * 0.7, y + s * 0.7, outline=colour, width=2)
        canvas.create_oval(x - s * 0.3, y - s * 0.7, x + s * 0.3, y + s * 0.7, outline=colour, width=1)
        canvas.create_line(x - s * 0.7, y, x + s * 0.7, y, fill=colour, width=1)
    elif kind == "page":
        canvas.create_rectangle(x - s * 0.5, y - s * 0.7, x + s * 0.5, y + s * 0.7, outline=colour, width=2)
        for i in range(3):
            canvas.create_line(x - s * 0.3, y - s * 0.3 + i * s * 0.3, x + s * 0.3,
                               y - s * 0.3 + i * s * 0.3, fill=colour, width=1)
    elif kind == "orb":
        canvas.create_oval(x - s * 0.7, y - s * 0.7, x + s * 0.7, y + s * 0.7, outline=colour, width=2)
        canvas.create_oval(x - s * 0.3, y - s * 0.3, x + s * 0.3, y + s * 0.3, fill=colour, outline="")
    elif kind == "window":
        canvas.create_rectangle(x - s * 0.7, y - s * 0.55, x + s * 0.7, y + s * 0.55, outline=colour, width=2)
        canvas.create_line(x - s * 0.7, y - s * 0.25, x + s * 0.7, y - s * 0.25, fill=colour, width=1)
    elif kind == "people":
        for dx in (-0.3, 0.3):
            canvas.create_oval(x + s * dx - s * 0.2, y - s * 0.5, x + s * dx + s * 0.2, y - s * 0.1,
                               outline=colour, width=2)
            canvas.create_arc(x + s * dx - s * 0.32, y - s * 0.05, x + s * dx + s * 0.32, y + s * 0.6,
                              start=0, extent=180, style="arc", outline=colour, width=2)
    elif kind == "warning":
        canvas.create_polygon(x, y - s * 0.7, x + s * 0.7, y + s * 0.55, x - s * 0.7, y + s * 0.55,
                              fill="", outline=colour)
        canvas.create_line(x, y - s * 0.25, x, y + s * 0.15, fill=colour, width=2)
    else:                                                          # spark
        for i in range(4):
            a = i * math.pi / 4
            canvas.create_line(x - math.cos(a) * s * 0.7, y - math.sin(a) * s * 0.7,
                               x + math.cos(a) * s * 0.7, y + math.sin(a) * s * 0.7,
                               fill=colour, width=2)


# ---------------------------------------------------------------------------
# The mask: 7 faces, cracks, slipping
# ---------------------------------------------------------------------------
def _mask_outline(x, y, w, h):
    pts = []
    for i in range(24):
        a = i / 24 * 2 * math.pi
        # an egg: wider brow, narrow chin
        rx = w * (1.0 - 0.18 * max(0.0, math.sin(a)))
        pts += [x + math.cos(a) * rx, y + math.sin(a) * h]
    return pts


def draw_mask(canvas, x, y, w, h, face, cracks=0, tilt=0.0, teeth=True, lace=True, p=0.0,
              vy=0.0):
    """The porcelain mask. (x, y) is its centre; w/h half-sizes.

    ``tilt`` turns it sideways (features slide toward the facing side) and
    ``vy`` tips it up (-1) or down (+1): features slide and a shadow falls
    under the brow or the chin.
    """
    sx = math.sin(tilt) * w * 0.25                      # slip/turn shifts the features
    fy = vy * h * 0.16                                  # look up/down shifts them vertically
    canvas.create_polygon(*_mask_outline(x + 2, y + 3, w, h), fill="#1a1520", outline="",
                          smooth=True)
    canvas.create_polygon(*_mask_outline(x, y, w, h), fill=PORCELAIN, outline=GOLD_DK, smooth=True)
    canvas.create_polygon(*_mask_outline(x + w * 0.12, y + h * 0.05, w * 0.82, h * 0.9),
                          fill="#fbf8f4", outline="", smooth=True)
    # gold filigree on the brow, a gem at the centre
    for k in (-1, 1):
        canvas.create_arc(x + k * w * 0.35 - w * 0.35, y - h * 0.95, x + k * w * 0.35 + w * 0.35,
                          y - h * 0.35, start=200 if k < 0 else -40, extent=120, style="arc",
                          outline=GOLD, width=1.5)
        canvas.create_arc(x + k * w * 0.55 - w * 0.2, y - h * 0.75, x + k * w * 0.55 + w * 0.2,
                          y - h * 0.35, start=90, extent=180 * k, style="arc", outline=GOLD, width=1)
    # porcelain sheen down one cheek, and the shadow of the tip
    canvas.create_arc(x - w * 0.85, y - h * 0.8, x + w * 0.2, y + h * 0.8, start=120, extent=110,
                      style="arc", outline="#ffffff", width=2)
    if vy < -0.2:                                       # looking up: the chin falls into shadow
        canvas.create_arc(x - w * 0.8, y + h * 0.2, x + w * 0.8, y + h * 1.05, start=200, extent=140,
                          style="chord", fill=PORCELAIN_SH, outline="")
    elif vy > 0.2:                                      # looking down: the brow shades the eyes
        canvas.create_arc(x - w * 0.85, y - h * 1.0, x + w * 0.85, y - h * 0.1, start=20, extent=140,
                          style="chord", fill=PORCELAIN_SH, outline="")
    # temple curls and a dotted brow line
    for k in (-1, 1):
        cxk, cyk = x + k * w * 0.62, y - h * 0.38
        for rr in (6, 3.5):
            canvas.create_arc(cxk - rr, cyk - rr, cxk + rr, cyk + rr, start=90 if k < 0 else -90,
                              extent=270 * k, style="arc", outline=GOLD, width=1)
        for i in range(5):
            bx = x + k * w * (0.12 + 0.11 * i)
            by = y - h * (0.52 - 0.03 * i)
            canvas.create_oval(bx - 0.9, by - 0.9, bx + 0.9, by + 0.9, fill=GOLD, outline="")
    # crescent moon and gem on the brow
    canvas.create_arc(x - 7, y - h * 0.98, x + 7, y - h * 0.7, start=200, extent=140, style="chord",
                      fill=GOLD, outline="")
    canvas.create_arc(x - 6, y - h * 1.02, x + 6, y - h * 0.76, start=200, extent=140, style="chord",
                      fill="#fbf8f4", outline="")
    canvas.create_polygon(x, y - h * 0.72, x + 4, y - h * 0.62, x, y - h * 0.52, x - 4, y - h * 0.62,
                          fill="#c0304a", outline=GOLD_DK)
    canvas.create_oval(x - 1, y - h * 0.66, x + 1, y - h * 0.62, fill="#ffd0d8", outline="")
    if lace:
        for i in range(7):
            a = math.pi * (0.15 + 0.7 * i / 6)
            canvas.create_oval(x - math.cos(a) * w * 0.95 - 1.2, y + math.sin(a) * h * 0.98 - 1.2,
                               x - math.cos(a) * w * 0.95 + 1.2, y + math.sin(a) * h * 0.98 + 1.2,
                               fill=GOLD, outline="")

    ex, ey, er = w * 0.38, y - h * 0.08 + fy, w * 0.24     # eye spacing / height / size
    mx, my = x + sx, y + h * 0.42 + fy * 0.8                # mouth centre
    L, R = (x - ex + sx, ey), (x + ex + sx, ey)

    def lids(shape):
        for (cx, cy), k in ((L, -1), (R, 1)):
            if shape == "smile":                            # ^ ^
                canvas.create_arc(cx - er, cy - er * 0.4, cx + er, cy + er * 1.2, start=20, extent=140,
                                  style="arc", outline=INK, width=2.5)
                canvas.create_line(cx + k * er * 0.95, cy, cx + k * er * 1.25, cy - er * 0.25,
                                   fill=INK, width=1.2)
            elif shape == "sad":
                canvas.create_arc(cx - er, cy - er * 0.2, cx + er, cy + er * 0.9, start=200, extent=140,
                                  style="arc", outline=INK, width=2.5)
                canvas.create_line(cx - k * er * 0.9, cy - er * 0.9, cx + k * er * 0.6, cy - er * 0.55,
                                   fill=INK_HI, width=1.5)
            elif shape == "almond":
                canvas.create_polygon(cx - er, cy, cx - er * 0.3, cy - er * 0.45, cx + er * 0.5, cy - er * 0.35,
                                      cx + er, cy + er * 0.05, cx + er * 0.2, cy + er * 0.4, cx - er * 0.5, cy + er * 0.35,
                                      fill="#0d0a10", outline=GOLD_DK, smooth=True)
            elif shape == "slit":
                canvas.create_polygon(cx - er * 1.1, cy - k * 0 - er * 0.1 * (-k), cx + er, cy - er * 0.5 * k * (-1),
                                      cx + er * 0.6, cy + er * 0.2, cx - er * 0.8, cy + er * 0.15,
                                      fill="#0d0a10", outline="", smooth=True)
            elif shape == "hollow":
                canvas.create_oval(cx - er * 0.9, cy - er * 0.7, cx + er * 0.9, cy + er * 0.8,
                                   fill="#050307", outline="")
                for j in range(2):                          # dripping ink
                    dx = cx - er * 0.4 + j * er * 0.8
                    canvas.create_line(dx, cy + er * 0.6, dx, cy + er * (1.6 + 0.6 * j + 0.3 * math.sin(p * 6)),
                                       fill="#050307", width=2, capstyle="round")

    if face == "cute":
        lids("smile")
        for c in (L, R):
            canvas.create_oval(c[0] - er * 0.7, c[1] + er * 0.9, c[0] + er * 0.7, c[1] + er * 1.5,
                               fill="#f4b3b8", outline="")
        canvas.create_arc(mx - w * 0.3, my - h * 0.28, mx + w * 0.3, my + h * 0.12, start=200, extent=140,
                          style="arc", outline=INK, width=2.5)
    elif face == "sad":
        lids("sad")
        canvas.create_line(L[0] + er * 0.4, L[1] + er * 0.5, L[0] + er * 0.4, L[1] + er * 1.6,
                           fill="#9fc5e8", width=2, capstyle="round")      # a tear
        canvas.create_arc(mx - w * 0.22, my - h * 0.02, mx + w * 0.22, my + h * 0.22, start=20, extent=140,
                          style="arc", outline=INK, width=2)
    elif face == "confused":
        lids("almond")
        canvas.create_line(L[0] - er, L[1] - er * 0.9, L[0] + er, L[1] - er * 1.2, fill=INK_HI, width=1.8)
        canvas.create_line(R[0] - er, R[1] - er * 0.7, R[0] + er, R[1] - er * 0.5, fill=INK_HI, width=1.8)
        canvas.create_line(mx - w * 0.18, my + h * 0.06, mx, my, mx + w * 0.18, my + h * 0.08,
                           fill=INK, width=2, smooth=True)
    elif face == "focused":
        lids("almond")
        for c, k in ((L, 1), (R, -1)):
            canvas.create_line(c[0] - er * 1.1, c[1] - er * 0.6 - k * er * 0.1, c[0] + er * 1.1,
                               c[1] - er * 0.6 + k * er * 0.25, fill=INK_HI, width=1.8)
        canvas.create_line(mx - w * 0.14, my + h * 0.04, mx + w * 0.14, my + h * 0.04, fill=INK, width=2)
    elif face == "scary":
        lids("hollow")
        canvas.create_arc(mx - w * 0.4, my - h * 0.32, mx + w * 0.4, my + h * 0.2, start=195, extent=150,
                          style="chord", fill="#050307", outline="")
        if teeth:
            for i in range(7):
                tx = mx - w * 0.3 + i * w * 0.1
                canvas.create_polygon(tx - 3, my - h * 0.02, tx + 3, my - h * 0.02, tx, my + h * 0.1,
                                      fill=PORCELAIN, outline="")
    elif face == "evil":
        lids("slit")
        for c in (L, R):
            canvas.create_oval(c[0] - 2.2, c[1] - 1.5, c[0] + 2.2, c[1] + 2.5, fill="#ff2a2a", outline="")
        canvas.create_polygon(mx - w * 0.45, my - h * 0.15, mx, my + h * 0.05, mx + w * 0.45, my - h * 0.15,
                              mx + w * 0.3, my + h * 0.12, mx, my + h * 0.2, mx - w * 0.3, my + h * 0.12,
                              fill="#050307", outline="", smooth=True)
        if teeth:
            for i in range(9):
                tx = mx - w * 0.36 + i * w * 0.09
                ty = my - h * 0.08 + abs(i - 4) * -h * 0.012
                canvas.create_polygon(tx - 2.5, ty, tx + 2.5, ty, tx, ty + h * 0.11, fill=PORCELAIN, outline="")
    # blank: no features at all

    # damage: crack -> worse -> broken
    if cracks >= 1:
        canvas.create_line(x + w * 0.15, y - h, x + w * 0.05, y - h * 0.6, x + w * 0.25, y - h * 0.35,
                           x + w * 0.1, y, fill="#3a2f2a", width=1.5)
    if cracks >= 2:
        canvas.create_line(x - w * 0.8, y + h * 0.2, x - w * 0.45, y + h * 0.1, x - w * 0.3, y + h * 0.45,
                           x - w * 0.05, y + h * 0.6, fill="#3a2f2a", width=1.5)
        canvas.create_line(x + w * 0.25, y - h * 0.35, x + w * 0.6, y - h * 0.2, fill="#3a2f2a", width=1.2)
    if cracks >= 3:                                            # a piece is missing
        canvas.create_polygon(x + w * 0.1, y - h * 0.55, x + w * 0.62, y - h * 0.45, x + w * 0.5, y + h * 0.05,
                              x + w * 0.12, y - h * 0.1, fill="#050307", outline="#3a2f2a")
        _eye(canvas, x + w * 0.35, y - h * 0.25, w * 0.13, 1.0)
        for j in range(3):
            dx = x + w * (0.18 + 0.12 * j)
            canvas.create_line(dx, y - h * 0.05, dx, y + h * (0.2 + 0.12 * j), fill="#050307", width=2,
                               capstyle="round")


# ---------------------------------------------------------------------------
# The whole creature
# ---------------------------------------------------------------------------
# Hand-placed so they sit in the mane like the sheet: framing the mask, down the body.
_EYE_SPOTS = [(-62, 92, 8), (62, 96, 8), (-50, 175, 9), (52, 180, 9), (0, 236, 10),
              (-88, 140, 7), (90, 145, 7), (-30, 240, 8), (34, 245, 8), (-72, 60, 6),
              (74, 62, 6), (-100, 210, 7), (102, 215, 7), (0, 262, 7), (-58, 270, 6),
              (60, 268, 6), (-110, 105, 6), (112, 110, 6), (-20, 150, 6), (24, 152, 6),
              (-120, 250, 6), (120, 255, 6), (0, 40, 6), (-36, 30, 5), (38, 32, 5)]


def _mane_strand(mcx, mcy, side, t, k, p, i, form, fx, facing=0.0):
    """One hair-like tendril: from the crown out and down in an S-wave, curling at the tip."""
    a0 = -math.pi / 2 + side * (0.35 + 2.3 * t)              # root angle around the head
    rx, ry = mcx + math.cos(a0) * 34, mcy - 8 + math.sin(a0) * 46
    out = side * (30 + 120 * t) * k                           # how far it fans sideways
    # Turned side-on, the mane streams behind her: short in front, long behind.
    out *= 1.0 - 0.6 * facing * side if facing * side > 0 else 1.0 + 0.45 * abs(facing)
    rx -= facing * 14
    drop = (FLOOR - ry) * (0.75 + 0.25 * ((i * 5) % 7) / 6)
    if form == "crawler":
        out, drop = side * (90 + 60 * t) * k, (FLOOR - ry)
    if "recoil" in fx or "coil" in fx:
        drop *= 0.55
    wave = (8 + 14 * t) * (1 if i % 3 else -1)
    phase = p * 2 * math.pi + i * 0.9
    pts = []
    n = 12
    for j in range(n + 1):
        s_ = j / n
        x = rx + out * math.sin(s_ * math.pi * 0.55) + wave * math.sin(s_ * 5 + phase)
        y = ry + drop * (s_ ** 1.15)
        pts.append((x, y))
    tx, ty = pts[-1]                                          # curl the tip
    for j in range(1, 5):
        a = j * 1.2 * (1 if side > 0 else -1)
        rr = 9 - j * 1.6
        pts.append((tx + side * 6 + math.cos(a + math.pi) * rr * side, ty - 6 + math.sin(a) * rr - j))
    pts = [(min(max(x, 4), FRAME[0] - 4), min(y, FLOOR)) for x, y in pts]
    return pts, (12 - 4 * t) * k


# Generic engine poses that travel: Masque turns side-on (left ones are mirrored).
SIDE_POSES = frozenset({"walk_to_workspace", "dash_to_workspace", "sprint_to_workspace",
                        "run_to_workspace", "tip_to_workspace", "return_home", "run_to_user",
                        "sneak", "leap", "creep"})
LOOK_AROUND = frozenset({"idle_bob", "wait", "notice", "look_around", "watch", "head_tilt",
                         "think", "look_at_input", "look_at_user"})


def view_of(pose: str, p: float, fx) -> tuple[float, bool]:
    """(facing, back): facing -1 left .. 0 front .. 1 right; back = seen from behind."""
    if "back" in fx:
        return 0.0, True
    if "spin" in fx:                                         # a full turn: front, side, back, side
        a = p * 2 * math.pi
        return math.sin(a), math.cos(a) < -0.2
    for f in fx:
        if f.startswith("turn:"):
            k = float(f[5:])
            return k * min(1.0, p * 2.5), False
    if "side" in fx or pose in SIDE_POSES:
        return 1.0, False
    if "follow" in fx:
        return 0.7 * math.sin(p * 2 * math.pi), False
    if "peek" in fx:
        return 0.45, False
    if pose in LOOK_AROUND and p >= 0.6:                     # glance over each shoulder
        return 0.6 * math.sin((p - 0.6) / 0.4 * 2 * math.pi), False
    return 0.0, False


def expression_for(pose: str, fx, state: MasqueState) -> str:
    for f in fx:
        if f.startswith("mask:"):
            return f[5:]
    from hermes_companion.animation.herald import mood_of
    mood = mood_of(pose)
    if pose in ("sleep",) or mood == "rest":
        return "blank"
    if mood == "fail" or state.category == "failure":
        return "sad"
    if mood == "approve" or state.category == "approval":
        return "evil" if state.danger else "confused"
    if mood in ("work", "delegate"):
        return "scary" if state.running >= 3 or state.helpers >= 3 else "focused"
    if mood == "curious":
        return "confused"
    return "cute"


def draw_masque(canvas, pose: str, progress: float = 0.0, palette: str | None = None) -> None:
    eyes_k, teeth, n_tendrils, lace = PALETTES.get(palette or DEFAULT_PALETTE, PALETTES[DEFAULT_PALETTE])
    st = STATE
    canvas.delete("all")
    if pose in FACE_LEFT:
        from hermes_companion.animation.nyamekra import _Mirror
        canvas = _Mirror(canvas, FRAME[0])
    p = progress % 1.0
    osc = math.sin(p * 2 * math.pi)
    own = MASQUE_MOVES.get(pose)
    fx = set(own[1]) if own else set()
    if st.resting and own is None and pose in ("idle_bob", "celebrate", "sleep", "smug", "excited"):
        fx |= {"coil", "shrink", "rest", "mask:cute"}            # session over: folded in, a rose
    form = FORM_OF_POSE.get(pose)
    if form is None and own is None and st.running and pose not in ("idle_bob", "sleep"):
        form = CATEGORY_FORM.get(st.category)
    if st.helpers and form is None:
        form = "split"
    face = expression_for(pose, fx, st)
    colour = CATEGORY_COLOUR.get(st.category, CATEGORY_COLOUR["general"])
    if "angry" in fx:
        colour = CATEGORY_COLOUR["failure"]
    if ("portal" in fx and 0.3 <= p <= 0.7) or ("portal_in" in fx and p >= 0.45) or \
            ("portal_out" in fx and p <= 0.55):              # gone through a crack in the world
        _portal(canvas, CX, 170, p if "portal" in fx else (0.5 + abs(p - 0.5)), colour)
        return
    facing, back = view_of(pose, p, fx)
    turn = abs(facing)

    size = 1.0 + 0.04 * min(4, st.work // 6) + (0.05 * abs(osc) if st.pulsing else 0.0)
    if "shrink" in fx or pose == "sleep":
        size *= 0.85
    lean = form == "lean" or "lunge" in fx
    sway = 6 * osc if ("sway" in fx or "slide" in fx or own is None) else 2 * osc
    hover = -14 - 6 * osc if ("hover" in fx or "float" in fx) else 0
    if "jump" in fx:
        hover = -12 * math.sin(p * math.pi)                  # the window itself does the big lift
    if "crouch" in fx:
        hover = 18
        size *= 0.92
    if "stretch" in fx:
        hover = -8 - 4 * abs(osc)
    mcx = CX + sway * 0.4
    mcy = 118 + hover + (14 if lean else 0) - (4 * abs(osc) if "bloom" in fx else 0)
    mw, mh = (38, 50) if not lean else (46, 60)
    if "lookup" in fx or "lookdown" in fx:
        mh *= 0.9                                            # foreshortened as it tips

    # 0. a real window to sit on (behind everything else)
    if "perch" in fx:
        _window(canvas, PERCH_TOP)

    # 1. thorn halo
    hx, hy = CX + sway * 0.2, 70 + hover
    spin = p * (2 * math.pi if "halo" in fx else 0.6)
    canvas.create_oval(hx - 62, hy - 62, hx + 62, hy + 62, outline=GOLD_DK, width=2)
    canvas.create_oval(hx - 54, hy - 54, hx + 54, hy + 54, outline=GOLD, width=1)
    for i in range(18):
        a = spin + i * math.pi / 9
        if math.sin(a) > 0.55:
            continue                                         # the head hides the lower thorns
        r0, r1 = 58, 70 + (6 if i % 3 == 0 else 0)
        canvas.create_polygon(hx + math.cos(a - 0.06) * r0, hy + math.sin(a - 0.06) * r0,
                              hx + math.cos(a) * r1, hy + math.sin(a) * r1,
                              hx + math.cos(a + 0.06) * r0, hy + math.sin(a + 0.06) * r0,
                              fill=GOLD if i % 2 else GOLD_DK, outline="")
    for i in range(36):                                      # dotted inner ring
        a = -spin * 0.5 + i * math.pi / 18
        if math.sin(a) > 0.6:
            continue
        canvas.create_oval(hx + math.cos(a) * 48 - 0.9, hy + math.sin(a) * 48 - 0.9,
                           hx + math.cos(a) * 48 + 0.9, hy + math.sin(a) * 48 + 0.9,
                           fill=GOLD_HI, outline="")
    for a in (math.pi, -math.pi / 4, -3 * math.pi / 4, 0.0):  # gems at the quarters
        gx, gy = hx + math.cos(a) * 62, hy + math.sin(a) * 62
        canvas.create_polygon(gx, gy - 4, gx + 3, gy, gx, gy + 4, gx - 3, gy, fill="#9b2c4a",
                              outline=GOLD_HI)
    canvas.create_arc(hx - 10, hy - 84, hx + 10, hy - 62, start=200, extent=140, style="chord",
                      fill=GOLD, outline=GOLD_DK)                # crescent moon crowning the halo
    canvas.create_arc(hx - 9, hy - 88, hx + 9, hy - 67, start=200, extent=140, style="chord",
                      fill="#160f1f", outline="")
    canvas.create_line(hx, hy - 62, hx, hy - 56, fill=GOLD, width=2)
    for k in (-1, 1):                                        # dangling gold charms
        canvas.create_line(hx + k * 56, hy + 10, hx + k * 58, hy + 40, fill=GOLD_DK, width=1)
        canvas.create_polygon(hx + k * 58, hy + 40, hx + k * 62, hy + 47, hx + k * 58, hy + 54,
                              hx + k * 54, hy + 47, fill=GOLD, outline="")

    # 2. the mane: a dark mass of hair-like tendrils pouring to the floor
    tint = _mix("#3b2a55", colour, 0.55)
    spread = 1.0 + (0.35 if "bloom" in fx else 0.0) - (0.3 if ("coil" in fx or "recoil" in fx) else 0.0)
    if "perch" not in fx:                                  # a soft shadow pooling on the floor
        sw = 120 * size * spread
        canvas.create_oval(mcx - sw, FLOOR - 7, mcx + sw, FLOOR + 5, fill="#0d0a12", outline="")
        if st.category != "general" or st.running:         # the work glows on the floor around her
            for k_ in range(3):
                g = sw * (0.8 + 0.12 * k_) + 6 * osc
                canvas.create_oval(mcx - g, FLOOR - 9 - k_ * 2, mcx + g, FLOOR + 7 + k_ * 2,
                                   outline=_mix(colour, "#120f17", 0.3 + 0.25 * k_), width=1.5)
    for k in range(7):                                     # soft volume behind the strands
        t = k / 6
        rx = (40 + 70 * t) * size * spread
        cy_ = mcy - 20 + 150 * t
        canvas.create_oval(mcx - rx, cy_ - 46, mcx + rx, cy_ + 46, fill=INK, outline="")
    if lace and not back:                                  # lace veil over the body, under the strands
        _veil(canvas, mcx, mcy, mw, size, p)
    count = n_tendrils + 2 * st.running
    strands = []
    for i in range(count):
        side = -1 if i % 2 == 0 else 1
        t = (i // 2) / max(1, (count - 1) // 2)
        strands.append(_mane_strand(mcx, mcy, side, t, size * spread, p, i, form, fx, facing))
    for pts, w0 in strands:                                # rim light so strands read as volume
        _strand(canvas, pts, w0 + 2.4, 4.0, "#3a2d4d")
    for pts, w0 in strands:                                # then thick ink
        _strand(canvas, pts, w0, 2.5, INK)
    _starfield(canvas, mcx, mcy, size, p, tint)              # the void inside her twinkles
    for i, (pts, w0) in enumerate(strands):                  # fine wisps peel off each tendril
        for j in (4, 8):
            if j < len(pts) - 1:
                (x0, y0), (x1, y1) = pts[j], pts[j + 1]
                side = 1 if (i + j) % 2 else -1
                ang = math.atan2(y1 - y0, x1 - x0) + side * 0.7
                ln = 9 + 4 * math.sin(p * 6 + i + j)
                canvas.create_line(x0, y0, x0 + math.cos(ang) * ln * 0.6 + side * 2,
                                   y0 + math.sin(ang) * ln * 0.6, x0 + math.cos(ang - side * 0.5) * ln,
                                   y0 + math.sin(ang - side * 0.5) * ln, fill=INK, width=1.6, smooth=True)
    # sheen catches the colour of the work - several kinds of tools at once braid their colours
    kinds = list(dict.fromkeys(st.tools)) if len(set(st.tools)) > 1 else []
    tints = [_mix("#3b2a55", CATEGORY_COLOUR.get(c, colour), 0.6) for c in kinds] or [tint]
    for i, (pts, w0) in enumerate(strands):
        tn = tints[i % len(tints)]
        flat = [c for q in pts[1:-2] for c in q]
        canvas.create_line(*flat, fill=tn, width=1.6, smooth=True)
        tx, ty = pts[-1]
        canvas.create_oval(tx - 2.2, ty - 2.2, tx + 2.2, ty + 2.2, fill=tn, outline="")
        gloss = [c for q in pts[1:max(3, len(pts) // 2)] for c in (q[0] - 1.6, q[1])]
        if len(gloss) >= 4:                                   # a wet, glossy highlight
            canvas.create_line(*gloss, fill="#9d86c9", width=0.9, smooth=True)

    # 3. eyes in the dark
    eye_count = int(9 * eyes_k + (9 if st.thinking or "alleyes" in fx or back else 0))
    if "wake" in fx:
        eye_count = int(eye_count * p) + 1
    blink = 0.5 + 0.5 * math.cos(p * 2 * math.pi * 2)
    for i, (dx, dy, r) in enumerate(_EYE_SPOTS[:min(eye_count, len(_EYE_SPOTS))]):
        ex, ey = mcx + dx * size * 0.9 * (1 - 0.35 * turn) - facing * 16, dy + hover * 0.5
        if not back and abs(ex - mcx - facing * mw * 0.5) < mw + 10 and abs(ey - mcy) < mh + 10:
            continue                                         # never behind the mask edge
        own_blink = math.sin(p * 2 * math.pi + i * 1.7) > 0.92  # each eye blinks on its own beat
        opn = (1.0 if st.thinking or "alleyes" in fx else (0.1 if own_blink else 0.55 + 0.45 * blink)) \
            if face != "blank" else 0.0
        opn *= 0.65 + 0.35 * ((i * 7) % 5) / 4
        look = (osc, 0.0) if ("scan" in fx or "follow" in fx) else \
            (-1.0, -0.6) if "lookup" in fx else (0.4 * math.sin(i) + facing, 0.0)
        canvas.create_oval(ex - r * 1.35, ey - r * 0.95, ex + r * 1.35, ey + r * 0.95,
                           fill="#050307", outline=tint, width=1)
        _eye(canvas, ex, ey, r * 1.15, opn, look=look)

    # 4a. gold chains draped across the mane, and a lantern on a tendril
    if not back:
        for row, (y0, sag) in enumerate(((mcy + mh + 24, 16), (mcy + mh + 70, 22))):
            span = (78 + 30 * row) * size
            pts = []
            for j in range(13):
                t = j / 12
                pts.append((mcx - span + 2 * span * t, y0 + sag * math.sin(t * math.pi)
                            + 2 * math.sin(p * 2 * math.pi + j)))
            flat = [c for q in pts for c in q]
            canvas.create_line(*flat, fill=GOLD_DK, width=1.4, smooth=True)
            for j in range(1, 12, 2):
                bx, by = pts[j]
                canvas.create_oval(bx - 1.6, by - 1.6, bx + 1.6, by + 1.6, fill=GOLD_HI, outline="")
            mx_, my_ = pts[6]                                # a pendant at the lowest point
            canvas.create_polygon(mx_, my_ + 2, mx_ + 4, my_ + 8, mx_, my_ + 14, mx_ - 4, my_ + 8,
                                  fill="#7a3fd1" if row else "#c0304a", outline=GOLD_HI)
    lx_, ly_ = mcx - 112 * size, 150 + 4 * osc                # the lantern from the sheet
    canvas.create_line(lx_ + 14, 118, lx_, ly_ - 10, fill=GOLD_DK, width=1)
    canvas.create_polygon(lx_ - 6, ly_ - 10, lx_ + 6, ly_ - 10, lx_ + 8, ly_ + 8, lx_ - 8, ly_ + 8,
                          fill="#2a1d0a", outline=GOLD)
    canvas.create_oval(lx_ - 3.5, ly_ - 4, lx_ + 3.5, ly_ + 4, fill="#ffcf6b", outline="")
    canvas.create_line(lx_ - 9, ly_ + 8, lx_ + 9, ly_ + 8, fill=GOLD, width=2)
    canvas.create_polygon(lx_ - 4, ly_ - 10, lx_, ly_ - 15, lx_ + 4, ly_ - 10, fill=GOLD, outline="")

    # 4. roses + jewels
    for (dx, dy, r) in ((-58, 70, 7), (54, 58, 6), (-70, 150, 6), (66, 165, 7), (-30, 210, 5)):
        _rose(canvas, mcx + dx * size, dy + hover * 0.5, r * (1.3 if "roses" in fx else 1.0),
              bloom=1.2 if "roses" in fx else 1.0)
    canvas.create_line(mcx - 30, mcy + mh + 6, mcx, mcy + mh + 16, mcx + 30, mcy + mh + 6,
                       fill=GOLD, width=1.5, smooth=True)
    if not back:
        _bodice(canvas, mcx, mcy + mh + 30)
    canvas.create_oval(mcx - 4, mcy + mh + 12, mcx + 4, mcy + mh + 20, fill=GOLD_HI, outline=GOLD_DK)

    # 5. form props
    _form(canvas, form, fx, mcx, mcy, mw, mh, p, osc, colour, st)

    # 6. tool tendrils: one reaching up per tool in flight, holding its glyph
    gl = CATEGORY_GLYPH.get(st.category, "spark") if st.category not in ("failure", "approval") \
        else ("warning" if st.category == "failure" else "spark")
    for j in range(st.running):
        side = -1 if j % 2 == 0 else 1
        rx, ry = mcx + side * (34 + 10 * j), mcy + 10
        tip = (rx + side * (40 + 14 * j) + 6 * osc, 40 + 18 * j - 8 * abs(osc))
        pts = [(rx, ry)] + [((rx * (1 - t) + tip[0] * t) + side * 18 * math.sin(t * math.pi),
                             ry * (1 - t) + tip[1] * t) for t in (0.25, 0.5, 0.75, 1.0)]
        cat_j = st.tools[j] if j < len(st.tools) else None     # each tendril holds its own tool
        col_j = CATEGORY_COLOUR.get(cat_j, colour) if cat_j else colour
        gl_j = CATEGORY_GLYPH.get(cat_j, gl) if cat_j else gl
        _strand(canvas, pts, 7, 3, INK, sheen=col_j)
        glyph(canvas, gl_j, min(max(tip[0], 14), FRAME[0] - 14), max(tip[1], 14), 10, col_j)

    # 7. hands holding the mask (delicate, gold rings)
    hands_later: list = []                                   # drawn over the mask's edges
    if back:
        pass                                                 # seen from behind: no hands, no face
    elif "slip" not in fx and form != "lean":
        for k in ((-1, 1) if turn < 0.55 else ((1,) if facing > 0 else (-1,))):
            hx_, hy_ = mcx + facing * mw * 0.5 + k * (mw * (1 - 0.5 * turn) + 8), mcy + mh * 0.55
            hands_later.append((hx_, hy_, k))
    elif form == "lean":                                      # hands together, hopeful
        for k in (-1, 1):
            canvas.create_line(mcx + k * 40, mcy + mh + 30, mcx + k * 8, mcy + mh + 8,
                               fill=INK, width=8, capstyle="round")
        _rose(canvas, mcx, mcy + mh + 8, 7)

    # 8. the mask - always on top of the body
    tilt, mx_off, my_off = 0.0, 0.0, 0.0
    if "slip" in fx:
        tilt = 0.5 * max(0.0, math.sin(p * math.pi))
        mx_off, my_off = 26 * tilt / 0.5, 6 * tilt
        _true_face(canvas, mcx, mcy, mw, mh)
    if "swap" in fx and 0.4 < p < 0.6:
        face = "blank"
    if "lookup" in fx:
        my_off -= 10
    if "lookdown" in fx:
        my_off += 12
    if "wake" in fx and p < 0.5:
        face = "blank"
    if back:
        _back_of_head(canvas, mcx, mcy, mw, mh, p, tint)
    else:
        mw_eff = mw * (1.0 - 0.5 * turn)
        mx = mcx + mx_off + facing * mw * 0.5
        vy = -1.0 if "lookup" in fx else 1.0 if "lookdown" in fx else 0.0
        draw_mask(canvas, mx, mcy + my_off, mw_eff, mh, face, cracks=st.cracks,
                  tilt=tilt + facing * 1.1, teeth=teeth, lace=lace, p=p, vy=vy)
        if turn > 0.7:                                       # profile: brow and nose ridge
            sgn = 1 if facing > 0 else -1
            ex_ = mx + sgn * mw_eff
            canvas.create_polygon(ex_ - sgn * 2, mcy + my_off - mh * 0.15, ex_ + sgn * 6, mcy + my_off + mh * 0.05,
                                  ex_ - sgn * 2, mcy + my_off + mh * 0.2, fill=PORCELAIN, outline=GOLD_DK)

    for hx_, hy_, k in hands_later:                          # fingers curl over the mask's edge
        _hand(canvas, hx_, hy_, k, p)
    if st.swapping and not back:                             # a tendril carries the old mask away
        ox, oy = mcx + mw + 46 + 14 * p, mcy - 10 - 10 * p
        _strand(canvas, [(mcx + 30, mcy + 40), (mcx + mw + 20, mcy + 20), (ox - 10, oy + 26)], 7, 3,
                INK, sheen=colour)
        draw_mask(canvas, ox, oy, mw * 0.55, mh * 0.55, "blank", lace=False, p=p)
    if not back:
        _emote(canvas, face, mcx + facing * mw * 0.5, mcy, mw, mh, p)
    cat_now = st.tools[-1] if st.tools else st.category
    if not back and (st.running or st.category in ("failure", "approval")) and "rest" not in fx:
        _charm(canvas, cat_now, mcx, mcy + mh + 58, p, CATEGORY_COLOUR.get(cat_now, colour))
    if "land" in fx:
        _splash(canvas, mcx, FLOOR, p, tint)
    if "rest" in fx and not back:                            # the small smile keeps a rose
        _rose(canvas, mcx, mcy + mh + 12, 9)

    # 9. front effects
    _effects(canvas, fx, form, mcx, mcy, mw, mh, p, osc, colour, st, pose)
    _move_effects(canvas, fx, mcx, mcy, mw, mh, p, osc, colour)


GLOVE, GLOVE_EDGE = "#2e2340", "#8a74a8"


def _hand(canvas, x, y, k, p):
    """A slender gloved hand cupping the mask's cheek: lace cuff, gold nails, a ring."""
    # forearm sleeve rising from the mane
    canvas.create_polygon(x + k * 18, y + 58, x + k * 6, y + 58, x - k * 1, y + 14, x + k * 12, y + 10,
                          fill=GLOVE, outline=GLOVE_EDGE, smooth=True)
    # lace cuff: a scalloped band with pearls
    for i in range(5):
        cx_, cy_ = x + k * (2 + i * 2.6), y + 14 + i * 0.8
        canvas.create_oval(cx_ - 3, cy_ - 3, cx_ + 3, cy_ + 3, fill="#e9e1f2", outline=GLOVE_EDGE)
    canvas.create_line(x - k * 1, y + 18, x + k * 14, y + 20, fill=GOLD, width=1.6)
    # palm against the mask's cheek
    canvas.create_polygon(x + k * 10, y + 14, x - k * 4, y + 10, x - k * 8, y - 4, x - k * 2, y - 16,
                          x + k * 8, y - 12, x + k * 12, y + 2, fill=GLOVE, outline=GLOVE_EDGE, smooth=True)
    # four long fingers curving over the mask's edge, gold-tipped
    for f in range(4):
        bx, by = x - k * (2 + f), y - 14 + f * 7
        tx, ty = x - k * (15 + 2 * f), y - 22 + f * 9 + 1.5 * math.sin(p * 6 + f)
        canvas.create_line(bx, by, (bx + tx) / 2 - k * 1, (by + ty) / 2 - 3, tx, ty,
                           fill=GLOVE_EDGE, width=5.2, smooth=True, capstyle="round")
        canvas.create_line(bx, by, (bx + tx) / 2 - k * 1, (by + ty) / 2 - 3, tx, ty,
                           fill=GLOVE, width=3.6, smooth=True, capstyle="round")
        canvas.create_polygon(tx, ty - 1.6, tx - k * 4.5, ty - 0.5, tx, ty + 1.6, fill=GOLD_HI,
                              outline="")
    # thumb and a ring with a stone
    canvas.create_line(x + k * 4, y + 4, x - k * 6, y + 12, fill=GLOVE_EDGE, width=5, capstyle="round")
    canvas.create_line(x + k * 4, y + 4, x - k * 6, y + 12, fill=GLOVE, width=3.4, capstyle="round")
    rx_, ry_ = x - k * 7, y - 5
    canvas.create_oval(rx_ - 2.6, ry_ - 2.6, rx_ + 2.6, ry_ + 2.6, outline=GOLD, width=1.4)
    canvas.create_oval(rx_ - 1.4, ry_ - 3.6, rx_ + 1.4, ry_ - 0.8, fill="#c0304a", outline=GOLD_HI)


def _back_of_head(canvas, x, y, w, h, p, tint):
    """Seen from behind: the mask's gold ribbon tied over a crown of tendrils."""
    canvas.create_oval(x - w - 6, y - h - 4, x + w + 6, y + h + 8, fill=INK, outline="#3a2d4d", width=2)
    for i in range(9):                                       # strands from the crown, down the back
        a = -math.pi / 2 + (i - 4) * 0.32
        pts = [(x + math.cos(a) * 8, y - h * 0.6)]
        for j in range(1, 7):
            pts.append((x + math.cos(a) * (8 + j * 7) + 3 * math.sin(p * 6 + i + j),
                        y - h * 0.6 + j * 16))
        _strand(canvas, pts, 6, 2, INK)
        flat = [c for q in pts for c in q]
        canvas.create_line(*flat, fill=tint, width=1.2, smooth=True)
    for k in (-1, 1):                                        # the ribbon and its bow
        canvas.create_line(x - w - 4, y - h * 0.15, x + w + 4, y - h * 0.15, fill=GOLD, width=3)
        canvas.create_polygon(x, y - h * 0.15, x + k * 16, y - h * 0.35, x + k * 18, y,
                              fill=GOLD, outline=GOLD_DK)
        canvas.create_line(x + k * 4, y - h * 0.1, x + k * 12, y + h * 0.5 + 4 * math.sin(p * 6),
                           fill=GOLD_DK, width=2)
    canvas.create_oval(x - 4, y - h * 0.15 - 4, x + 4, y - h * 0.15 + 4, fill=GOLD_HI, outline=GOLD_DK)


PERCH_TOP = 232


def _window(canvas, top):
    """The window Masque perches on: title bar, buttons, a glimpse of its content."""
    canvas.create_rectangle(6, top, 314, FRAME[1], fill="#141a28", outline="#6a7dab", width=2)
    canvas.create_rectangle(6, top, 314, top + 22, fill="#2d3a58", outline="#6a7dab", width=2)
    canvas.create_text(58, top + 11, text="Hermes", fill="#d6def5", font=("Segoe UI", 8, "bold"))
    for i, col in enumerate(("#e0b84a", "#57b86b", "#d65a5a")):     # min / max / close
        bx = 262 + i * 17
        canvas.create_oval(bx - 5, top + 6, bx + 5, top + 16, fill=col, outline="")
    for i in range(3):                                        # lines of text in the window
        canvas.create_line(20, top + 34 + i * 12, 150 - i * 30, top + 34 + i * 12, fill="#3c4a6e", width=3)


def _veil(canvas, x, y, mw, size, p):
    """A lace veil from the crown, scalloped at the hem (the sheet's optional drapery)."""
    top, hem = y - 52, y + 70
    half_top, half_hem = mw + 10, (mw + 46) * size
    sway = 3 * math.sin(p * 2 * math.pi)
    canvas.create_polygon(x - half_top, top, x + half_top, top, x + half_hem + sway, hem,
                          x - half_hem + sway, hem, fill="#1a1325", outline="", smooth=True)
    n = 9
    for i in range(n):                                       # scalloped hem
        t0 = i / n
        sx = x - half_hem + sway + 2 * half_hem * t0
        w = 2 * half_hem / n
        canvas.create_arc(sx, hem - w * 0.5, sx + w, hem + w * 0.5, start=180, extent=180, style="arc",
                          outline="#5d4a78", width=1.2)
        canvas.create_oval(sx + w / 2 - 1.2, hem + w * 0.42 - 1.2, sx + w / 2 + 1.2, hem + w * 0.42 + 1.2,
                           fill="#cbbfe0", outline="")
    for r_ in range(3):                                      # lace pattern: rows of tiny rosettes
        yy = top + 30 + r_ * 26
        span = half_top + (half_hem - half_top) * (yy - top) / (hem - top)
        for k in range(-3, 4):
            xx = x + k * span / 3.6 + sway * (yy - top) / (hem - top)
            canvas.create_oval(xx - 3, yy - 3, xx + 3, yy + 3, outline="#4a3b62", width=0.8)
            canvas.create_oval(xx - 0.8, yy - 0.8, xx + 0.8, yy + 0.8, fill="#6d5a8c", outline="")


_STARS = [((i * 37) % 200 - 100, 80 + (i * 53) % 190, 0.6 + (i % 3) * 0.4) for i in range(46)]


def _starfield(canvas, x, y, size, p, tint):
    """Tiny stars glinting in the dark of her body; a few twinkle each beat."""
    for i, (dx, dy, r) in enumerate(_STARS):
        sx, sy = x + dx * size * 0.95, dy + (y - 118)
        if abs(dx) < 34 and dy < 175:                        # keep the mask area clean
            continue
        tw = 0.5 + 0.5 * math.sin(p * 2 * math.pi * 2 + i)
        rr = r * (0.6 + 0.8 * tw)
        col = "#e9dcff" if i % 4 else tint
        canvas.create_oval(sx - rr, sy - rr, sx + rr, sy + rr, fill=col, outline="")
        if i % 7 == 0 and tw > 0.8:                          # a four-point glint
            canvas.create_line(sx - 4, sy, sx + 4, sy, fill=col, width=0.8)
            canvas.create_line(sx, sy - 4, sx, sy + 4, fill=col, width=0.8)


def _bodice(canvas, x, y):
    """Gold filigree on the bodice: mirrored curls around a teardrop gem."""
    for k in (-1, 1):
        for i, (dx, dy, r) in enumerate(((10, 0, 7), (22, 6, 5), (32, 14, 4))):
            cx_, cy_ = x + k * dx, y + dy
            canvas.create_arc(cx_ - r, cy_ - r, cx_ + r, cy_ + r, start=90 if k > 0 else -90,
                              extent=270 * k, style="arc", outline=GOLD, width=1.2)
        canvas.create_line(x + k * 4, y - 6, x + k * 36, y + 20, fill=GOLD_DK, width=1, smooth=True)
    canvas.create_polygon(x, y - 8, x + 5, y + 2, x, y + 10, x - 5, y + 2, fill="#7a3fd1", outline=GOLD_HI)


def _move_effects(canvas, fx, x, y, w, h, p, osc, colour):
    """Extra visuals for the movement actions and special moves."""
    if "click" in fx:                                        # a ripple where you clicked
        cx_, cy_ = x + w + 70, y + 40
        for k in range(3):
            r = 6 + (p * 30 + k * 10) % 30
            canvas.create_oval(cx_ - r, cy_ - r, cx_ + r, cy_ + r, outline=colour, width=2)
        _strand(canvas, [(x + w, y + 30), (x + w + 30, y + 20 + 6 * osc), (cx_ - 8, cy_)], 6, 2, INK,
                sheen=colour)
    if "follow" in fx:                                       # the cursor she is following
        cx_, cy_ = x + 120 * math.sin(p * 2 * math.pi), 30
        canvas.create_polygon(cx_, cy_, cx_, cy_ + 14, cx_ + 4, cy_ + 10, cx_ + 9, cy_ + 10,
                              fill="#ffffff", outline="#111111")
    if "perch" in fx:                                        # tendrils grip the title bar's edge
        top = PERCH_TOP
        for i in range(7):
            gx = 66 + i * 30
            canvas.create_arc(gx - 9, top - 8, gx + 9, top + 12, start=-30, extent=240, style="arc",
                              outline=INK, width=6)
            canvas.create_arc(gx - 9, top - 8, gx + 9, top + 12, start=-30, extent=240, style="arc",
                              outline="#3a2d4d", width=1.4)
    if "angry" in fx:                                        # red pulse
        r = 120 + 10 * abs(osc)
        canvas.create_oval(x - r, y - r * 0.8, x + r, y + r * 1.2, outline="#ff3b3b", width=2)
    if "stretch" in fx:                                      # reaching up for the UI
        for k in (-1, 1):
            _strand(canvas, [(x + k * 30, y + 10), (x + k * 50, y - 40), (x + k * 60, 20 + 4 * osc)], 6, 2,
                    INK, sheen=colour)


def _true_face(canvas, x, y, w, h):
    """What the mask hides: a cluster of eyes in the dark."""
    canvas.create_oval(x - w, y - h, x + w, y + h, fill="#050307", outline="")
    for i, (dx, dy, r) in enumerate(((-14, -18, 7), (12, -22, 6), (0, 0, 10), (-18, 16, 6), (16, 14, 7),
                                     (0, 30, 5), (-26, -2, 5), (26, -4, 5))):
        _eye(canvas, x + dx, y + dy, r, 1.0, look=(0.3 * math.sin(i), 0.0))


def _portal(canvas, x, y, p, colour):
    """The crack she slips through: a jagged violet tear with light spilling out."""
    spread = math.sin(min(max(p, 0.0), 1.0) * math.pi)
    h = 30 + 110 * spread
    pts_l, pts_r = [], []
    for j in range(9):
        t = j / 8
        yy = y - h + 2 * h * t
        jag = (6 + 10 * spread) * (1 if j % 2 else -0.6) * math.sin(t * math.pi)
        pts_l.append((x - 4 - jag - 8 * spread * math.sin(t * math.pi), yy))
        pts_r.append((x + 4 + jag * 0.7 + 8 * spread * math.sin(t * math.pi), yy))
    for k, col in ((1.8, "#3b1d6e"), (1.0, colour), (0.45, "#f2e8ff")):
        poly = [(x + (px - x) * k, py) for px, py in pts_l] + \
               [(x + (px - x) * k, py) for px, py in pts_r[::-1]]
        canvas.create_polygon(*[c for q in poly for c in q], fill=col, outline="")
    for i in range(10):                                       # shards flung out of the crack
        a = i * 0.628 + p * 4
        r = 30 + 60 * spread
        sx, sy = x + math.cos(a) * r, y + math.sin(a) * r * 1.2
        canvas.create_polygon(sx, sy - 4, sx + 3, sy, sx, sy + 4, sx - 3, sy, fill=colour, outline="")
    _eye(canvas, x, y, 6 + 6 * spread, 1.0)


def _ghost(canvas, x, y, p, colour):
    """A small masked helper: a soft ghost with a wavy hem and a tiny halo."""
    pts = [(x - 15, y + 4), (x - 15, y - 6)]
    for j in range(9):                                         # rounded head
        a = math.pi + j * math.pi / 8
        pts.append((x + math.cos(a) * 15, y - 6 + math.sin(a) * 15))
    pts.append((x + 15, y + 4))
    for j in range(7):                                         # wavy hem
        t = j / 6
        pts.append((x + 15 - 30 * t, y + 16 + 4 * math.sin(t * 9 + p * 12)))
    canvas.create_polygon(*[c for q in pts for c in q], fill=_mix(colour, "#ffffff", 0.35),
                          outline=colour, smooth=True)
    canvas.create_oval(x - 8, y - 12, x + 8, y + 5, fill=PORCELAIN, outline=GOLD_DK)
    for k in (-1, 1):
        canvas.create_arc(x + k * 3.5 - 2.5, y - 7, x + k * 3.5 + 2.5, y - 3, start=20, extent=140,
                          style="arc", outline=INK, width=1)
    canvas.create_arc(x - 3, y - 3, x + 3, y + 2, start=200, extent=140, style="arc", outline=INK, width=1)
    canvas.create_oval(x - 4, y - 27, x + 4, y - 23, outline=GOLD_HI, width=1)


EMOTES = {"cute": "hearts", "sad": "tears", "confused": "questions", "focused": "crosshair",
          "scary": "sparks", "evil": "smoke", "blank": "dots"}


def _emote(canvas, face, x, y, w, h, p):
    """Floating feelings around the mask, one kind per face (from the sheet)."""
    kind = EMOTES.get(face)
    t = p * 2 * math.pi
    if kind == "hearts":
        for i, (dx, dy, r) in enumerate(((-w - 20, -h * 0.55, 10), (w + 18, -h * 0.25, 7),
                                         (w + 26, -h * 0.9, 5))):
            hx, hy = x + dx, y + dy - 10 * ((p + i * 0.33) % 1.0)
            canvas.create_oval(hx - r, hy - r, hx, hy, fill="#ff5fa2", outline="")
            canvas.create_oval(hx, hy - r, hx + r, hy, fill="#ff5fa2", outline="")
            canvas.create_polygon(hx - r, hy - r * 0.45, hx + r, hy - r * 0.45, hx, hy + r * 0.9,
                                  fill="#ff5fa2", outline="")
    elif kind == "tears":
        for i, dx in enumerate((-w - 10, w + 8)):
            dy = 14 * ((p + i * 0.4) % 1.0)
            tx, ty = x + dx, y - h * 0.2 + dy
            canvas.create_polygon(tx, ty - 10, tx + 6, ty + 2, tx, ty + 7, tx - 6, ty + 2,
                                  fill="#6aa8ff", outline="#bcd8ff", smooth=True)
    elif kind == "questions":
        for i, (dx, dy, sz) in enumerate(((-w - 16, -h * 0.7, 18), (w + 14, -h * 0.85, 13),
                                          (-w - 4, -h * 1.05, 10))):
            canvas.create_text(x + dx, y + dy - 3 * math.sin(t + i), text="?", fill="#c9a4ff",
                               font=("Segoe UI", sz, "bold"))
    elif kind == "crosshair":
        cx_, cy_ = x - w - 18, y - h * 0.3
        r = 11 + 2 * math.sin(t * 2)
        canvas.create_oval(cx_ - r, cy_ - r, cx_ + r, cy_ + r, outline="#ff4d5e", width=1.4)
        for a in range(4):
            ang = a * math.pi / 2
            canvas.create_line(cx_ + math.cos(ang) * (r - 3), cy_ + math.sin(ang) * (r - 3),
                               cx_ + math.cos(ang) * (r + 4), cy_ + math.sin(ang) * (r + 4),
                               fill="#ff4d5e", width=1.4)
    elif kind == "sparks":
        for i in range(5):
            a = t + i * 1.256
            sx, sy = x + math.cos(a) * (w + 20), y - h * 0.4 + math.sin(a) * 20
            canvas.create_polygon(sx, sy - 8, sx + 2.4, sy, sx, sy + 8, sx - 2.4, sy, fill="#ff3b3b",
                                  outline="")
            canvas.create_polygon(sx - 8, sy, sx, sy + 2.4, sx + 8, sy, sx, sy - 2.4, fill="#ff3b3b",
                                  outline="")
    elif kind == "smoke":
        for k in (-1, 1):
            pts = []
            for j in range(10):
                u = j / 9
                pts += [x + k * (w + 6 + 18 * u + 6 * math.sin(u * 9 + t)), y + h * 0.4 - 70 * u]
            canvas.create_line(*pts, fill="#ff2a6d", width=2.2, smooth=True)
            canvas.create_line(*[v + (1.5 if n % 2 == 0 else 0) for n, v in enumerate(pts)],
                               fill="#ff8ab0", width=0.8, smooth=True)
    elif kind == "dots":
        for i in range(3):
            on = (int(p * 6) % 4) > i
            dx = x + w + 12 + i * 10
            canvas.create_oval(dx - 3.2, y - h - 3.2, dx + 3.2, y - h + 3.2, fill="#cbbfe0" if on else "#4a3b62",
                               outline="")


def _charm(canvas, cat, x, y, p, colour):
    """The tool charm glowing in front of her: a hexagon holding the work's glyph."""
    pulse = 1.0 + 0.06 * math.sin(p * 2 * math.pi * 2)
    r = 15 * pulse
    for k, col in ((1.55, _mix(colour, "#120f17", 0.65)), (1.25, _mix(colour, "#120f17", 0.35))):
        canvas.create_oval(x - r * k, y - r * k, x + r * k, y + r * k, outline=col, width=2)
    hexa = [c for i in range(6) for c in (x + math.cos(i * math.pi / 3 + math.pi / 6) * r,
                                          y + math.sin(i * math.pi / 3 + math.pi / 6) * r)]
    canvas.create_polygon(*hexa, fill="#0d0a14", outline=colour)
    kind = "warning" if cat == "failure" else "spark" if cat == "approval" else \
        CATEGORY_GLYPH.get(cat, "spark")
    glyph(canvas, kind, x, y, 9, colour)


def _splash(canvas, x, y, p, tint):
    """Landing: a ring of ink splashes out across the floor."""
    s_ = math.sin(min(p, 1.0) * math.pi)
    for k in range(3):
        rx = 40 + 70 * s_ + k * 16
        canvas.create_arc(x - rx, y - 10 - k * 3, x + rx, y + 10 + k * 3, start=0, extent=180, style="arc",
                          outline=tint, width=2.5 - k * 0.6)
    for i in range(8):
        a = math.pi + i * math.pi / 7
        d = 50 + 80 * s_
        dx_, dy_ = x + math.cos(a) * d, y + math.sin(a) * d * 0.35
        canvas.create_oval(dx_ - 3, dy_ - 3, dx_ + 3, dy_ + 3, fill=INK, outline=tint)


def _form(canvas, form, fx, x, y, w, h, p, osc, colour, st):
    if form == "typist" or "type" in fx:                      # floating keys + screens
        for i in range(5):
            kx, ky = x - 60 + i * 30, 228 + (4 * math.sin(p * 12 + i) if i % 2 else 0)
            canvas.create_rectangle(kx - 9, ky - 5, kx + 9, ky + 5, fill="#07130c", outline=colour)
            canvas.create_line(kx, y + h, kx, ky - 6, fill=INK, width=4, capstyle="round")
        for k in (-1, 1):
            glyph(canvas, "terminal", x + k * 95, 150, 14, colour)
    elif form == "lantern" or "lantern" in fx:                # one tendril carries a light
        lx, ly = x + 100 + 6 * osc, 120 + 10 * math.sin(p * 4)
        _strand(canvas, [(x + 30, y + 30), (x + 60, y - 10), (lx - 10, ly - 30), (lx, ly - 12)], 6, 2, INK)
        canvas.create_oval(lx - 12, ly - 12, lx + 12, ly + 12, fill=colour, outline=GOLD_HI, width=2)
        glyph(canvas, "globe", lx, ly, 8, "#ffffff")
    elif form == "library":                                    # tendrils with books
        bx, by = x, 236
        canvas.create_polygon(bx - 50, by, bx, by + 8, bx + 50, by, bx + 50, by + 24, bx, by + 30, bx - 50, by + 24,
                              fill="#efe3c8", outline=GOLD_DK)
        canvas.create_line(bx, by + 8, bx, by + 30, fill=GOLD_DK, width=2)
        for i in range(3):
            canvas.create_line(bx - 40, by + 8 + i * 5, bx - 8, by + 12 + i * 5, fill="#7a6a50", width=1)
        for k in (-1, 1):
            glyph(canvas, "page", x + k * (85 + 8 * osc), 120, 11, colour)
    elif form == "scribe":                                     # quill tendril carving runes
        qx, qy = x + 70, 200 + 6 * osc
        _strand(canvas, [(x + 30, y + 40), (x + 50, 180), (qx, qy)], 6, 2, INK)
        canvas.create_line(qx, qy, qx + 20, qy - 28, fill=GOLD_HI, width=3)
        for i in range(4):
            canvas.create_text(x - 70 + i * 22, 250 - 8 * math.sin(p * 6 + i), text="ᚱᛟᚾᛖ"[i],
                               fill=colour, font=("Segoe UI", 11, "bold"))
    elif form == "vault":                                      # swallows a glowing orb
        oy = y + h + 28 - 20 * p
        canvas.create_oval(x - 16, oy - 16, x + 16, oy + 16, fill=colour, outline=GOLD_HI, width=2)
        canvas.create_oval(x - 26, oy - 26, x + 26, oy + 26, outline=colour, width=1)
    elif form == "crawler":                                    # gothic arches behind the legs
        for k in (-1, 1):
            ax = x + k * 110
            canvas.create_arc(ax - 18, 150, ax + 18, 230, start=0, extent=180, style="arc", outline=colour, width=2)
            canvas.create_line(ax - 18, 190, ax - 18, 285, fill=colour, width=2)
            canvas.create_line(ax + 18, 190, ax + 18, 285, fill=colour, width=2)
    elif form == "split":                                      # small masked copies, one per helper
        n = max(1, st.helpers)
        for i in range(n):
            bx = x + (-1) ** i * (74 + 30 * (i // 2))
            by = 236 - 8 * abs(math.sin(p * 2 * math.pi + i))
            _ghost(canvas, bx, by, p + i * 0.3, colour)


def _effects(canvas, fx, form, x, y, w, h, p, osc, colour, st, pose):
    if st.category == "failure" or "petals" in fx:            # red pulse, petals fall
        for i in range(6):
            px = x - 70 + i * 28 + 8 * math.sin(p * 6 + i)
            py = 60 + ((p * 200 + i * 37) % 200)
            canvas.create_polygon(px, py, px + 5, py + 3, px + 2, py + 8, px - 3, py + 4,
                                  fill=ROSE_HI, outline="")
    if st.category == "approval" or form == "lean":            # the question sigil
        qx, qy = x + w + 22, y - h - 6
        canvas.create_oval(qx - 12, qy - 12, qx + 12, qy + 12, outline="#ffd34d", width=2)
        canvas.create_text(qx, qy, text="?", fill="#ffd34d", font=("Segoe UI", 12, "bold"))
    if st.thinking:                                            # sigils swirl while thinking
        for i in range(5):
            a = p * 2 * math.pi + i * 1.2566
            canvas.create_oval(x + math.cos(a) * (w + 30) - 3, y - 10 + math.sin(a) * 26 - 3,
                               x + math.cos(a) * (w + 30) + 3, y - 10 + math.sin(a) * 26 + 3,
                               fill=colour, outline="")
    if "glyphs" in fx or "sigil" in fx:
        for i in range(4):
            a = p * 2 * math.pi + i * math.pi / 2
            glyph(canvas, ("terminal", "globe", "page", "orb")[i],
                  x + math.cos(a) * (w + 40), y + math.sin(a) * 40, 8, colour)
    if "reach" in fx:
        _strand(canvas, [(x + w, y + 20), (x + w + 40, y - 10 + 10 * osc), (x + w + 80, y - 30),
                         (min(x + w + 110, 312), y - 40)], 7, 2, INK, sheen=colour)
    if "slide" in fx or "lunge" in fx:                         # ink trailing behind
        for i in range(5):
            yy = 170 + i * 20
            canvas.create_line(x - 90 - i * 4, yy, x - 140 - i * 6 - 10 * abs(osc), yy + 4,
                               fill=INK, width=6 - i, capstyle="round")
    if pose == "sleep":
        for i in range(3):
            canvas.create_text(x + w + 14 + i * 9, y - h - i * 12 - p * 6, text="z",
                               fill="#9b7bd6", font=("Segoe UI", 9 + i * 3, "bold"))


# ---------------------------------------------------------------------------
# Travel (the same contract as Nyamekra's)
# ---------------------------------------------------------------------------
TOWARD_USER = ("run_to_user", "to_user", "panic")


ROAM = 1.6


def travel(step: dict, rng) -> dict:
    move = step.get("move")
    if not move or not move.get("dx"):
        return step
    dx = move["dx"]
    kind = move.get("type", "")
    pose = step.get("pose", "")
    far = abs(dx) >= 300
    if any(k in pose for k in TOWARD_USER):
        name = "lunge"
    elif kind in ("fly", "hop", "leap", "pounce", "drift", "zigzag"):
        name = "hover"
    elif far and rng.random() < 0.4:
        name = "crack_portal"
    elif kind in ("dash", "run", "sprint", "walk", "creep") or far:
        name = "ink_slide"
    else:
        return step
    # Travel further than the plain walk would: a big, readable crossing of the
    # screen (the overlay clamps to the monitors, and may carry on to the next one).
    out = dict(step, pose=name + ("_back" if dx < 0 else ""),
               move=dict(move, dx=int(dx * ROAM)))
    if name == "crack_portal":
        out["move"] = dict(out["move"], easing="teleport")
        out["duration_ms"] = max(int(step.get("duration_ms", 0)), 900)
    return out
