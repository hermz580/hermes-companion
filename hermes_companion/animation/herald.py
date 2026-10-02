"""Herald - a winged messenger built to show everything the companion does.

Hermes's own herald: winged helmet and sandals, a caduceus staff, a scarf
that trails behind every move. Every part of the rig carries meaning:

* **mood aura** - a soft halo coloured by what the pose means (working teal,
  delegating violet, failure rose, approval amber, celebration gold,
  curiosity cyan, rest lavender), so variety flourishes still read correctly;
* **staff orb** - the same mood colour, brightest when Hermes is busy; tool
  props (terminal, web, files, git, vault ...) float above it;
* **wings** - on helmet and sandals, flap faster the more energetic the pose;
* **scarf** - streams opposite the lean, so travel and gait swaps are visible;
* **curiosity marks** - "!" when it notices something, "?" while it peeks,
  squints or wonders, so desktop curiosity never looks like Hermes work.

Same Canvas contract as ``animator.draw_pet``; all movement comes from
``animator.pose_params`` so the whole behavior vocabulary works.
"""
from __future__ import annotations

import math

from hermes_companion.animation.animator import CONFETTI, PUPIL, pose_params

HERALD_PALETTES: dict[str, dict[str, str]] = {
    "olympus": {"skin": "#f2c9a0", "tunic": "#f8fafc", "trim": "#f59e0b",
                "scarf": "#2563eb", "helmet": "#fbbf24", "wing": "#ffffff",
                "staff": "#b45309", "hair": "#7c2d12", "sandal": "#92400e"},
    "midnight": {"skin": "#e8b48a", "tunic": "#1e293b", "trim": "#cbd5e1",
                 "scarf": "#7c3aed", "helmet": "#94a3b8", "wing": "#e2e8f0",
                 "staff": "#475569", "hair": "#0f172a", "sandal": "#334155"},
    "ember": {"skin": "#d9a27a", "tunic": "#7f1d1d", "trim": "#fb923c",
              "scarf": "#facc15", "helmet": "#ea580c", "wing": "#fff7ed",
              "staff": "#78350f", "hair": "#1c1917", "sandal": "#451a03"},
    "verdant": {"skin": "#c68e64", "tunic": "#14532d", "trim": "#a3e635",
                "scarf": "#f472b6", "helmet": "#65a30d", "wing": "#f0fdf4",
                "staff": "#3f6212", "hair": "#422006", "sandal": "#365314"},
    "nebula": {"skin": "#f5d0c5", "tunic": "#312e81", "trim": "#f0abfc",
               "scarf": "#22d3ee", "helmet": "#a78bfa", "wing": "#faf5ff",
               "staff": "#4c1d95", "hair": "#831843", "sandal": "#3b0764"},
}
HERALD_DEFAULT_PALETTE = "olympus"

MOOD_COLORS = {
    "work": "#2dd4bf", "delegate": "#a78bfa", "fail": "#fb7185",
    "approve": "#fbbf24", "joy": "#facc15", "curious": "#22d3ee",
    "rest": "#c4b5fd", "calm": "#e2e8f0",
}

_MOOD_OF: dict[str, str] = {}
for _mood, _poses in {
    "work": ("work", "lean_work", "terminal_work", "web_scan", "file_organize",
             "dev_merge", "media_paint", "memory_vault", "design_draft",
             "audio_tune", "read", "crack_knuckles", "dash_to_workspace",
             "run_to_workspace", "walk_to_workspace", "sprint_to_workspace",
             "channel", "point", "sneak"),
    "delegate": ("open_portal", "orb_exits", "orb_returns", "absorb"),
    "fail": ("shock", "fall", "recover", "repair", "retry", "scratch_head",
             "arm_flap", "sit_back", "huff", "shake_head", "discard"),
    "approve": ("panic", "run_to_user", "wave", "attention", "wait"),
    "joy": ("celebrate", "spin", "full_bounce", "leap_double_joy", "spin_joy",
            "excited", "double_jump", "dance", "smug", "jump"),
    "curious": ("notice", "watch", "look_at_input", "look_at_user", "peeking",
                "squint", "eyebrow_raise", "head_tilt", "tilt", "look_around",
                "think", "inspect", "tip_to_workspace"),
    "rest": ("sleep", "yawn", "sit", "head_drop", "stretch_lazy"),
}.items():
    for _p in _poses:
        _MOOD_OF[_p] = _mood

EXCLAIM = frozenset({"notice", "shock", "attention", "eyebrow_raise", "wake"})
WONDER = frozenset({"peeking", "squint", "think", "head_tilt", "tilt",
                    "scratch_head", "inspect"})
ENERGY = {"jump": 3.0, "walk": 2.0, "lean_forward": 2.0, "tall": 1.5,
          "normal": 1.0, "sit": 0.6, "fall": 0.4}


def mood_of(pose: str) -> str:
    return _MOOD_OF.get(pose, "calm")


def _palette(name: str | None) -> dict[str, str]:
    return HERALD_PALETTES.get(name or HERALD_DEFAULT_PALETTE,
                               HERALD_PALETTES[HERALD_DEFAULT_PALETTE])


def _wing(canvas, x, y, side, flap, color, size=1.0):
    """A three-feather wing; `side` -1 left / +1 right, `flap` -1..1."""
    lift = flap * 7 * size
    for i, (length, drop) in enumerate(((20, 0), (16, 5), (11, 9))):
        tip_x = x + side * length * size
        tip_y = y - (10 - drop) * size - lift * (1 - i * 0.25)
        canvas.create_polygon(x, y - 2 * size, tip_x, tip_y,
                              x + side * (length - 6) * size, y + drop * 0.6 * size,
                              fill=color, outline="#cbd5e1", smooth=True)


def _bubble(canvas, x, y, text, color):
    canvas.create_oval(x - 9, y - 9, x + 9, y + 9, fill="white", outline=color, width=2)
    canvas.create_polygon(x - 3, y + 7, x + 2, y + 7, x - 6, y + 14,
                          fill="white", outline="")
    canvas.create_text(x, y, text=text, fill=color, font=("Segoe UI", 10, "bold"))


def _prop(canvas, extra, x, y, p, accent):
    """Tool/prop icons floating above the staff orb."""
    if extra is None:
        return
    if extra == "terminal":
        canvas.create_rectangle(x - 16, y - 10, x + 16, y + 10, fill="#0f172a",
                                outline=accent, width=2)
        canvas.create_text(x - 6, y - 2, text=">_", fill="#5eead4",
                           font=("Consolas", 8, "bold"))
        if int(p * 6) % 2:
            canvas.create_line(x + 2, y + 4, x + 8, y + 4, fill="#5eead4", width=2)
    elif extra == "web":
        canvas.create_oval(x - 11, y - 11, x + 11, y + 11, outline=accent, width=2)
        canvas.create_oval(x - 5, y - 11, x + 5, y + 11, outline=accent)
        canvas.create_line(x - 11, y, x + 11, y, fill=accent)
    elif extra == "files":
        for i in range(3):
            canvas.create_rectangle(x - 10 + i * 4, y - 10 + i * 3, x + 6 + i * 4,
                                    y + 8 + i * 3, fill="#f8fafc", outline=accent)
    elif extra == "git":
        canvas.create_line(x - 8, y + 10, x - 8, y - 10, fill=accent, width=3)
        canvas.create_line(x - 8, y + 2, x + 8, y - 6, fill=accent, width=3)
        for gx, gy in ((x - 8, y + 10), (x - 8, y - 10), (x + 8, y - 6)):
            canvas.create_oval(gx - 4, gy - 4, gx + 4, gy + 4, fill="#f8fafc", outline=accent)
    elif extra == "vault":
        canvas.create_rectangle(x - 12, y - 10, x + 12, y + 10, fill="#0f766e",
                                outline=accent, width=2)
        canvas.create_oval(x - 4, y - 4, x + 4, y + 4, outline="#fde68a", width=2)
    elif extra == "palette":
        canvas.create_oval(x - 13, y - 9, x + 13, y + 9, fill="#fef3c7", outline=accent)
        for i, col in enumerate(CONFETTI[:4]):
            canvas.create_oval(x - 9 + i * 5, y - 4, x - 5 + i * 5, y, fill=col, outline="")
    elif extra == "notes":
        for i in range(2):
            nx = x - 6 + i * 12
            ny = y + math.sin(p * 6.28 + i) * 4
            canvas.create_oval(nx - 4, ny + 2, nx + 2, ny + 7, fill=accent, outline="")
            canvas.create_line(nx + 2, ny + 4, nx + 2, ny - 8, fill=accent, width=2)
    elif extra in ("book", "pen", "glass", "wrench", "watch", "tap",
                   "retry", "discard_item", "think", "yawn"):
        glyph = {"book": "📖", "pen": "✎", "glass": "🔍", "wrench": "🔧",
                 "watch": "⌚", "tap": "☝", "retry": "↻", "discard_item": "✖",
                 "think": "…", "yawn": "~"}[extra]
        canvas.create_text(x, y, text=glyph, fill=accent, font=("Segoe UI", 14, "bold"))
    elif extra in ("hologram", "hologram_fade"):
        alpha_lines = 4 if extra == "hologram" else 2
        for i in range(alpha_lines):
            canvas.create_line(x - 14, y - 8 + i * 5, x + 14, y - 8 + i * 5,
                               fill="#67e8f9", width=1)
        canvas.create_rectangle(x - 14, y - 10, x + 14, y + 10, outline="#67e8f9")
    elif extra in ("portal", "orb_exit", "orb_return", "absorb"):
        r = 12 + (math.sin(p * 6.28) * 3 if extra == "portal" else 0)
        canvas.create_oval(x - r, y - r, x + r, y + r, outline="#a78bfa", width=3)
        canvas.create_oval(x - r / 2, y - r / 2, x + r / 2, y + r / 2,
                           outline="#c4b5fd", width=2)
        if extra != "portal":
            ox = x + (p * 30 if extra == "orb_exit" else (1 - p) * 30)
            canvas.create_oval(ox - 4, y - 4, ox + 4, y + 4, fill="#e9d5ff", outline="")


def draw_herald(canvas, pose: str, progress: float = 0.0,
                palette: str | None = None) -> None:
    P = _palette(palette)
    canvas.delete("all")
    prm = pose_params(pose, progress)
    p = progress % 1.0
    body, eyes, arms, extra = prm["body"], prm["eyes"], prm["arms"], prm["extra"]
    shear = prm["lean"] * 30.0
    cx, cy = 100, 150 + prm["bob"]
    cy += {"jump": -28, "fall": 14, "sit": 12, "tall": -5}.get(body, 0)
    mood = mood_of(pose)
    glow = MOOD_COLORS[mood]
    energy = ENERGY.get(body, 1.0) * (1.4 if mood in ("joy", "approve") else 1.0)
    flap = math.sin(p * 6.28 * energy * 2)

    # ---- mood aura -------------------------------------------------------
    pulse = 1.0 + 0.06 * math.sin(p * 6.28 * 2)
    for ring, width in ((54, 1), (46, 2)):
        r = ring * pulse
        canvas.create_oval(cx - r + shear, cy - 40 - r, cx + r + shear, cy - 40 + r,
                           outline=glow, width=width)

    # ---- scarf, streaming opposite the lean ------------------------------
    trail = -1 if prm["lean"] >= 0 else 1
    length = 40 + abs(prm["lean"]) * 160 + (14 if body in ("jump", "walk") else 0)
    nx, ny = cx + shear, cy - 58
    pts = [nx, ny]
    for i in range(1, 6):
        t = i / 5
        pts += [nx + trail * length * t,
                ny + 4 + t * 10 + math.sin(p * 12.56 + i) * 4 * t]
    for i in range(5, 0, -1):
        t = i / 5
        pts += [nx + trail * length * t, ny + 10 + t * 12 + math.sin(p * 12.56 + i) * 4 * t]
    canvas.create_polygon(*pts, fill=P["scarf"], outline="", smooth=True)

    # ---- legs + winged sandals --------------------------------------------
    hip_y, foot_y = cy - 4, cy + 36
    stride = math.sin(p * 12.56) * 8 if body in ("walk", "lean_forward") else 0
    legs = ((-9 + stride, -1), (9 - stride, 1)) if body != "sit" else ((-16, -1), (16, 1))
    for dx, side in legs:
        fx = cx + dx + shear * 0.4
        fy = foot_y if body != "sit" else cy + 20
        canvas.create_line(cx + side * 6 + shear, hip_y, fx, fy, width=8,
                           capstyle="round", fill=P["skin"])
        canvas.create_oval(fx - 8, fy - 2, fx + 8, fy + 6, fill=P["sandal"], outline="")
        _wing(canvas, fx - side * 2, fy - 2, side, flap, P["wing"], size=0.45)

    # ---- tunic -----------------------------------------------------------
    top = cy - 56
    canvas.create_polygon(cx - 16 + shear, top, cx + 16 + shear, top,
                          cx + 22 + shear * 0.5, cy + 4, cx - 22 + shear * 0.5, cy + 4,
                          fill=P["tunic"], outline=P["trim"], width=2)
    canvas.create_line(cx - 18 + shear * 0.7, cy - 18, cx + 18 + shear * 0.7, cy - 18,
                       fill=P["trim"], width=3)
    canvas.create_oval(cx - 4 + shear * 0.7, cy - 22, cx + 4 + shear * 0.7, cy - 14,
                       fill=glow, outline=P["trim"])

    # ---- arms + caduceus ------------------------------------------------------
    sx, sy = cx + shear, top + 8
    lh, rh = {
        "down": ((-24, 24), (24, 22)), "up": ((-22, -34), (22, -34)),
        "cross": ((10, 6), (-10, 6)), "hold": ((-14, 8), (16, 6)),
        "wave": ((-24, 24), (26 + math.sin(p * 18.8) * 8, -30)),
        "bent": ((-18, 4), (18, 4)), "stretch": ((-38, -10), (38, -10)),
        "throw": ((-24, 20), (34, -26 + p * 30)), "work": ((-12, 2), (18, 0)),
    }.get(arms, ((-24, 24), (24, 22)))
    for (hx, hy), side in ((lh, -1), (rh, 1)):
        canvas.create_line(sx + side * 14, sy, sx + hx, sy + hy, width=7,
                           capstyle="round", fill=P["skin"])
    # staff in the left hand; it rises with the arm
    hx, hy = sx + lh[0] - 14, sy + lh[1]
    canvas.create_line(sx + lh[0], hy, hx, hy, width=6, capstyle="round", fill=P["skin"])
    top_y = hy - 58
    canvas.create_line(hx, hy + 22, hx, top_y, width=4, fill=P["staff"])
    for k in (-1, 1):
        coil = []
        for i in range(9):
            t = i / 8
            coil += [hx + k * math.sin(t * 9.4 + p * 6.28) * 6, hy + 10 - t * 60]
        canvas.create_line(*coil, fill="#10b981", width=2, smooth=True)
    _wing(canvas, hx - 3, top_y + 6, -1, flap, P["wing"], size=0.4)
    _wing(canvas, hx + 3, top_y + 6, 1, flap, P["wing"], size=0.4)
    orb_r = 7 + (2 if mood in ("work", "delegate") else 0) * (0.5 + 0.5 * math.sin(p * 12.56))
    canvas.create_oval(hx - orb_r - 3, top_y - orb_r - 3, hx + orb_r + 3, top_y + orb_r + 3,
                       outline=glow, width=2)
    canvas.create_oval(hx - orb_r, top_y - orb_r, hx + orb_r, top_y + orb_r,
                       fill=glow, outline="white")

    # ---- head --------------------------------------------------------------
    hcx, hcy = cx + shear * 1.2, top - 20
    if body == "sit" and pose in ("sleep", "head_drop"):
        hcy += 6
    canvas.create_oval(hcx - 18, hcy - 18, hcx + 18, hcy + 18, fill=P["skin"], outline="")
    # Tk arc angles run counter-clockwise from 3 o'clock: 20..160 is the top.
    canvas.create_arc(hcx - 19, hcy - 20, hcx + 19, hcy + 12, start=20, extent=140,
                      style="chord", fill=P["hair"], outline="")
    # petasos helmet with wings
    canvas.create_oval(hcx - 24, hcy - 14, hcx + 24, hcy - 6, fill=P["helmet"],
                       outline=P["trim"])
    canvas.create_arc(hcx - 17, hcy - 30, hcx + 17, hcy + 2, start=0, extent=180,
                      style="chord", fill=P["helmet"], outline=P["trim"])
    _wing(canvas, hcx - 16, hcy - 14, -1, flap, P["wing"], size=0.8)
    _wing(canvas, hcx + 16, hcy - 14, 1, flap, P["wing"], size=0.8)

    # eyes
    ey, gap = hcy + 1, 7
    for ex in (hcx - gap, hcx + gap):
        if eyes == "closed":
            canvas.create_arc(ex - 4, ey - 3, ex + 4, ey + 3, start=200, extent=140,
                              style="arc", width=2, outline=PUPIL)
        elif eyes == "xeyes":
            canvas.create_line(ex - 3, ey - 3, ex + 3, ey + 3, width=2, fill=PUPIL)
            canvas.create_line(ex - 3, ey + 3, ex + 3, ey - 3, width=2, fill=PUPIL)
        else:
            r = 5 if eyes == "wide" else 4
            canvas.create_oval(ex - r, ey - r - 1, ex + r, ey + r + 1, fill="white",
                               outline=PUPIL)
            dx = {"left": -2, "right": 2}.get(eyes, 0)
            dy = {"up": -2, "down": 2}.get(eyes, 0)
            canvas.create_oval(ex - 2 + dx, ey - 2 + dy, ex + 2 + dx, ey + 2 + dy,
                               fill=PUPIL, outline="")
            canvas.create_oval(ex - 1 + dx, ey - 2 + dy, ex + dx, ey - 1 + dy,
                               fill="white", outline="")
    # brows and mouth carry the mood
    tilt = {"fail": 3, "approve": -2, "curious": -1}.get(mood, 0)
    canvas.create_line(hcx - gap - 4, ey - 8 - tilt, hcx - gap + 4, ey - 8 + tilt,
                       width=2, fill=P["hair"])
    canvas.create_line(hcx + gap - 4, ey - 8 + tilt, hcx + gap + 4, ey - 8 - tilt,
                       width=2, fill=P["hair"])
    my = hcy + 10
    if mood == "joy":
        canvas.create_arc(hcx - 6, my - 5, hcx + 6, my + 5, start=180, extent=180,
                          style="chord", fill="#9f1239", outline="")
    elif mood == "fail":
        canvas.create_arc(hcx - 5, my, hcx + 5, my + 6, start=20, extent=140,
                          style="arc", width=2, outline=PUPIL)
    elif eyes == "wide" or mood == "approve":
        canvas.create_oval(hcx - 3, my - 2, hcx + 3, my + 4, fill=PUPIL, outline="")
    elif mood == "rest":
        canvas.create_line(hcx - 3, my + 1, hcx + 3, my + 1, width=2, fill=PUPIL)
    else:
        canvas.create_arc(hcx - 5, my - 4, hcx + 5, my + 3, start=200, extent=140,
                          style="arc", width=2, outline=PUPIL)

    # ---- effects -------------------------------------------------------------
    _prop(canvas, extra if extra not in ("confetti", "spark", "speed_lines", "spin_lines",
                                         "zzz", "sweat") else None,
          hx, top_y - 26, p, glow)
    if extra == "confetti":
        for i, col in enumerate(CONFETTI * 2):
            ang = p * 6.28 + i * 0.8
            r = 34 + i * 3
            px, py = hcx + math.cos(ang) * r, hcy + 10 + math.sin(ang) * r * 0.6
            canvas.create_rectangle(px, py, px + 4, py + 4, fill=col, outline="")
    elif extra == "spark":
        for i in range(8):
            ang = p * 6.28 + i * 0.785
            canvas.create_line(hcx + math.cos(ang) * 28, hcy + math.sin(ang) * 28,
                               hcx + math.cos(ang) * 38, hcy + math.sin(ang) * 38,
                               fill=MOOD_COLORS["joy"], width=3)
    elif extra in ("speed_lines", "spin_lines"):
        for i in range(4):
            y = cy - 40 + i * 12
            x0 = cx - trail * (30 + i * 6)
            canvas.create_line(x0, y, x0 + trail * -26, y, fill=glow, width=2)
    elif extra == "zzz":
        for i in range(3):
            canvas.create_text(hcx + 22 + i * 7, hcy - 16 - i * 10 - p * 6, text="z",
                               fill=MOOD_COLORS["rest"], font=("Segoe UI", 9 + i * 3, "bold"))
    elif extra == "sweat":
        canvas.create_oval(hcx + 16, hcy - 10, hcx + 22, hcy - 2, fill="#60a5fa", outline="")

    if pose in EXCLAIM:
        _bubble(canvas, hcx + 26, hcy - 30, "!", glow)
    elif pose in WONDER:
        _bubble(canvas, hcx + 26, hcy - 30, "?", glow)
