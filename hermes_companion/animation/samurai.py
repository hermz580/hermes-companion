"""Procedural SAMURAI companion renderer (a new Hermes Companion pet).

A tall, lanky ronin with two swords (katana on the back + wakizashi at the
waist), a yellow accent (headband + obi), and CHANGEABLE materials. The two
traditional pieces — the kasa (bamboo hat) and the geta (wooden sandals) —
are deliberately FIXED and never change color, so the silhouette reads as
samurai in every variant.

Renders on the same 200x220 tkinter Canvas contract as the round pet
(`animation/animator.py`), reusing `pose_params` so the ENTIRE behavior-engine
pose vocabulary (idle, run, slash, bow, memory_vault, celebrate, ...) drives
this character too. No image assets.

Palettes (changeable material/element themes):
    crimson (default), jade, indigo, ember, sakura, void
"""
from __future__ import annotations

import math

from hermes_companion.animation.animator import BG, CONFETTI, PUPIL, pose_params

# -- fixed traditional pieces (never change color) ---------------------------
KASA = "#2b2b3a"        # bamboo hat body — FIXED
KASA_DARK = "#3c3c52"   # hat brim — FIXED
KASA_RING = "#4a4a63"   # hat ring — FIXED
GETA = "#a0703c"        # wooden sandal — FIXED
GETA_DARK = "#7d542b"   # sandal base — FIXED
# integer-RGB forms for pixel-verification (proof code must not parse hex)
KASA_RGB = (43, 43, 58)
GETA_RGB = (160, 112, 60)
SKIN = "#f0c291"
SKIN_DARK = "#dba878"
YELLOW = "#f1c40f"      # accent (headband + obi) — yellow card
STEEL = "#cfd8dc"
STEEL_DARK = "#90a4ae"
TSUKA = "#b8860b"       # sword hilt wrap

# -- changeable material palettes --------------------------------------------
SAMURAI_PALETTES: dict[str, dict[str, str]] = {
    "crimson": {"gi": "#c0392b", "gi_dark": "#96281b", "sleeve": "#a93226",
                "hakama": "#2c3e50", "hakama_dark": "#1d2c3a"},
    "jade":    {"gi": "#1e8449", "gi_dark": "#166638", "sleeve": "#27ae60",
                "hakama": "#173b2b", "hakama_dark": "#0f2a1e"},
    "indigo":  {"gi": "#3949ab", "gi_dark": "#2b3a8f", "sleeve": "#5c6bc0",
                "hakama": "#141f3d", "hakama_dark": "#0d1529"},
    "ember":   {"gi": "#d35400", "gi_dark": "#a84300", "sleeve": "#e67e22",
                "hakama": "#3d2010", "hakama_dark": "#2a150a"},
    "sakura":  {"gi": "#e0759c", "gi_dark": "#c25680", "sleeve": "#f1a9c4",
                "hakama": "#5b2540", "hakama_dark": "#3f1830"},
    "void":    {"gi": "#37474f", "gi_dark": "#263238", "sleeve": "#455a64",
                "hakama": "#1c262c", "hakama_dark": "#12191d"},
}

SAMURAI_DEFAULT_PALETTE = "crimson"


def _palette(name: str | None) -> dict[str, str]:
    return SAMURAI_PALETTES.get(name or "", SAMURAI_PALETTES[SAMURAI_DEFAULT_PALETTE])


def draw_samurai(canvas, pose: str, progress: float = 0.0,
                 palette: str | None = None) -> None:
    """Draw the samurai in `pose` at `progress` (0..1) with the given material
    palette. Same Canvas contract as `animator.draw_pet`."""
    P = _palette(palette)
    canvas.delete("all")
    W, H = 200, 220
    cx, base_y = 100, 156
    prm = pose_params(pose, progress)
    p = progress % 1.0
    bob = prm["bob"]
    cy = base_y + bob
    shear = prm["lean"] * 30.0

    body = prm["body"]
    if body == "jump":
        cy -= 26
    elif body == "fall":
        cy += 14
    elif body == "sit":
        cy += 10
    elif body == "tall":
        cy -= 4

    # ---- geta (fixed wooden sandals) ---------------------------------------
    foot_y = cy + 38
    for fdx in (-16, 16):
        canvas.create_rectangle(cx + fdx - 7 + shear, foot_y,
                                cx + fdx + 9 + shear, foot_y + 10,
                                fill=GETA, outline="")
        canvas.create_rectangle(cx + fdx - 5 + shear, foot_y - 3,
                                cx + fdx + 7 + shear, foot_y + 1,
                                fill=GETA_DARK, outline="")

    # ---- legs: long, lanky hakama -------------------------------------------------
    # two thin legs with hakama (wide at hip, tapering)
    for side, ldx in (("l", -11), ("r", 11)):
        hip_y = cy + 6
        canvas.create_rectangle(cx + ldx - 4 + shear, hip_y,
                                cx + ldx + 4 + shear, foot_y - 2,
                                fill=P["hakama_dark"], outline="")
        # hakama flare at the hip
        canvas.create_rectangle(cx + ldx - 8 + shear, hip_y,
                                cx + ldx + 8 + shear, hip_y + 16,
                                fill=P["hakama"], outline="")

    # ---- torso: long gi ------------------------------------------------------------
    # tall, lanky: a narrow long torso
    torso_top = cy - 52
    torso_bot = cy + 8
    canvas.create_rectangle(cx - 15 + shear, torso_top,
                            cx + 15 + shear, torso_bot,
                            fill=P["gi"], outline="")
    # kimono cross-collar (white under-collar + V)
    canvas.create_polygon(cx - 15 + shear, torso_top,
                          cx + 15 + shear, torso_top,
                          cx + 15 + shear, torso_top + 16,
                          cx - 15 + shear, torso_top + 16,
                          fill=P["gi_dark"], outline="")
    canvas.create_polygon(cx - 12 + shear, torso_top + 4,
                          cx, torso_top + 26,
                          cx + 12 + shear, torso_top + 4,
                          fill="#f8fafc", outline="")

    # ---- obi (yellow accent sash) -------------------------------------------------
    obi_y = cy - 6
    canvas.create_rectangle(cx - 17 + shear, obi_y,
                            cx + 17 + shear, obi_y + 13,
                            fill=YELLOW, outline="")
    canvas.create_oval(cx + 8 + shear, obi_y + 3,
                       cx + 14 + shear, obi_y + 9, fill=GETA_DARK, outline="")

    # ---- swords: katana (back) + wakizashi (waist) --------------------------------
    arms = prm["arms"]
    # katana on the back: diagonal sheath rising behind the shoulder
    canvas.create_line(cx - 2 + shear, cy - 40,
                       cx - 34 + shear, cy - 92,
                       width=8, fill=TSUKA, capstyle="round")
    canvas.create_line(cx - 4 + shear, cy - 40,
                       cx - 36 + shear, cy - 92,
                       width=6, fill=STEEL_DARK, capstyle="round")
    # wakizashi at the waist: short blade angled at the hip
    canvas.create_line(cx + 14 + shear, cy - 2,
                       cx + 40 + shear, cy + 18,
                       width=7, fill=TSUKA, capstyle="round")
    canvas.create_line(cx + 16 + shear, cy - 2,
                       cx + 42 + shear, cy + 18,
                       width=5, fill=STEEL_DARK, capstyle="round")

    # ---- arms (long, lanky sleeves) --------------------------------------------------
    ax, ay = cx + shear, cy - 18
    if arms == "down":
        canvas.create_line(ax - 17, ay, ax - 26, ay + 34, width=10, capstyle="round", fill=P["sleeve"])
        canvas.create_line(ax + 17, ay, ax + 26, ay + 34, width=10, capstyle="round", fill=P["sleeve"])
        canvas.create_oval(ax - 28, ay + 30, ax - 21, ay + 37, fill=SKIN, outline="")
        canvas.create_oval(ax + 21, ay + 30, ax + 28, ay + 37, fill=SKIN, outline="")
    elif arms == "up":
        canvas.create_line(ax - 16, ay - 4, ax - 30, ay - 40, width=10, capstyle="round", fill=P["sleeve"])
        canvas.create_line(ax + 16, ay - 4, ax + 30, ay - 40, width=10, capstyle="round", fill=P["sleeve"])
        canvas.create_oval(ax - 32, ay - 46, ax - 25, ay - 39, fill=SKIN, outline="")
        canvas.create_oval(ax + 25, ay - 46, ax + 32, ay - 39, fill=SKIN, outline="")
    elif arms == "wave":
        canvas.create_line(ax + 16, ay - 4, ax + 34, ay - 36 - 6 * math.sin(progress * 8.0),
                           width=10, capstyle="round", fill=P["sleeve"])
        canvas.create_line(ax - 16, ay - 4, ax - 24, ay + 20, width=10, capstyle="round", fill=P["sleeve"])
    elif arms in ("work", "hold"):
        canvas.create_line(ax - 16, ay + 2, ax - 14, ay + 26, width=10, capstyle="round", fill=P["sleeve"])
        canvas.create_line(ax + 16, ay + 2, ax + 14, ay + 26, width=10, capstyle="round", fill=P["sleeve"])
    elif arms == "bent":
        canvas.create_line(ax - 16, ay - 4, ax - 8, ay - 26, width=10, capstyle="round", fill=P["sleeve"])
        canvas.create_line(ax + 16, ay - 4, ax + 8, ay - 26, width=10, capstyle="round", fill=P["sleeve"])
    elif arms == "throw":
        canvas.create_line(ax - 14, ay - 6, ax - 34, ay - 30, width=10, capstyle="round", fill=P["sleeve"])
    elif arms == "stretch":
        canvas.create_line(ax - 16, ay - 6, ax - 32, ay - 48, width=10, capstyle="round", fill=P["sleeve"])
        canvas.create_line(ax + 16, ay - 6, ax + 32, ay - 48, width=10, capstyle="round", fill=P["sleeve"])

    # ---- head + face -----------------------------------------------------------------
    head_cy = cy - 74
    head_r = 16
    # face
    canvas.create_oval(cx - head_r + shear, head_cy - head_r,
                       cx + head_r + shear, head_cy + head_r,
                       fill=SKIN, outline="")
    # topknot (chonmage)
    canvas.create_oval(cx - 3 + shear, head_cy - head_r - 8,
                       cx + 3 + shear, head_cy - head_r + 4,
                       fill="#241d2e", outline="")

    # eyes
    eye_y = head_cy - 4
    ex_l, ex_r = cx - 7 + shear, cx + 7 + shear
    eyes = prm["eyes"]
    if eyes == "closed":
        canvas.create_line(ex_l - 3, eye_y, ex_l + 3, eye_y, width=2, fill=PUPIL)
        canvas.create_line(ex_r - 3, eye_y, ex_r + 3, eye_y, width=2, fill=PUPIL)
    elif eyes == "xeyes":
        for ex in (ex_l, ex_r):
            canvas.create_line(ex - 3, eye_y - 3, ex + 3, eye_y + 3, width=2, fill=PUPIL)
            canvas.create_line(ex - 3, eye_y + 3, ex + 3, eye_y - 3, width=2, fill=PUPIL)
    else:
        dx = {"left": -3, "right": 3, "up": 0, "down": 0}.get(eyes, 0)
        dy = {"up": -2, "down": 2}.get(eyes, 0)
        for ex in (ex_l, ex_r):
            canvas.create_oval(ex - 4, eye_y - 5, ex + 4, eye_y + 5, fill="white", outline="")
            canvas.create_oval(ex - 2 + dx, eye_y - 2 + dy, ex + 2 + dx, eye_y + 2 + dy,
                               fill=PUPIL, outline="")

    # mouth
    if eyes not in ("closed",):
        if eyes == "wide":
            canvas.create_oval(cx - 3 + shear, head_cy + 8,
                               cx + 3 + shear, head_cy + 13, fill=PUPIL, outline="")
        else:
            canvas.create_arc(cx - 4 + shear, head_cy + 6,
                              cx + 4 + shear, head_cy + 12,
                              start=20, extent=140, style="arc", width=2, outline=PUPIL)

    # ---- headband (yellow accent) — sits on the brow --------------------------------
    canvas.create_rectangle(cx - head_r + shear, head_cy - head_r + 3,
                            cx + head_r + shear, head_cy - head_r + 8,
                            fill=YELLOW, outline="")

    # ---- kasa hat (FIXED traditional bamboo hat) — always on top ---------------------
    hat_cy = head_cy - head_r - 6
    # wide cone brim
    canvas.create_oval(cx - 34 + shear, hat_cy - 10,
                       cx + 34 + shear, hat_cy + 12,
                       fill=KASA_DARK, outline="")
    canvas.create_oval(cx - 28 + shear, hat_cy - 12,
                       cx + 28 + shear, hat_cy + 8,
                       fill=KASA, outline="")
    # peak
    canvas.create_polygon(cx - 8 + shear, hat_cy - 12,
                          cx + 8 + shear, hat_cy - 12,
                          cx, hat_cy - 30,
                          fill=KASA, outline="")
    # ring seam
    canvas.create_oval(cx - 20 + shear, hat_cy - 4,
                       cx + 20 + shear, hat_cy + 4,
                       outline=KASA_RING, width=1)
    # face shadow line under the brim
    canvas.create_oval(cx - 13 + shear, head_cy - 12,
                       cx + 13 + shear, head_cy - 5,
                       fill="#c98b57", outline="")

    # ---- extras (reuse the round pet's vocabulary where it reads on a ronin) ---------
    extra = prm["extra"]
    if extra == "terminal":
        tx, ty = cx + shear, cy - 66
        canvas.create_rectangle(tx - 24, ty - 12, tx + 24, ty + 12, fill="#0f172a",
                                outline="#22d3ee", width=2)
        for i in range(3):
            canvas.create_line(tx - 18, ty - 4 + i * 6, tx + 6, ty - 4 + i * 6,
                               fill="#5eead4", width=2)
        canvas.create_text(tx - 14, ty - 8, text=">_", fill="#f1c40f",
                           font=("Consolas", 8, "bold"))
    elif extra == "web":
        wx, wy = cx + 26 + shear, cy - 52
        canvas.create_oval(wx - 12, wy - 12, wx + 12, wy + 12, outline="#22d3ee", width=2)
        canvas.create_line(wx - 8, wy, wx + 8, wy, fill="#22d3ee", width=1)
        canvas.create_line(wx, wy - 8, wx, wy + 8, fill="#22d3ee", width=1)
    elif extra == "vault":
        vx, vy = cx + 26 + shear, cy - 46
        canvas.create_rectangle(vx - 12, vy - 14, vx + 12, vy + 4, fill="#0f766e",
                                outline="#f1c40f", width=2)
        canvas.create_oval(vx - 2, vy - 7, vx + 4, vy - 1, fill="#f1c40f", outline="")
    elif extra == "confetti":
        for i, col in enumerate(CONFETTI):
            ang = p * 6.28 + i
            canvas.create_oval(cx + math.cos(ang) * (30 + i * 5) + shear,
                               cy - 34 + math.sin(ang) * (18 + i * 4),
                               cx + math.cos(ang) * (30 + i * 5) + 5 + shear,
                               cy - 34 + math.sin(ang) * (18 + i * 4) + 5,
                               fill=col, outline="")
    elif extra == "spark":
        for i in range(6):
            ang = p * 6.28 + i * 3.14159 / 3
            canvas.create_line(cx + math.cos(ang) * 26 + shear,
                               cy - 28 + math.sin(ang) * 26,
                               cx + math.cos(ang) * 36 + shear,
                               cy - 28 + math.sin(ang) * 36,
                               fill="#f1c40f", width=3)
    elif extra == "speed_lines":
        for i in range(3):
            y = cy - 20 + i * 12
            canvas.create_line(cx - 46 - i * 10 + shear, y, cx - 24 + shear, y,
                               fill="#5eead4", width=3)
    elif extra == "zzz":
        for i, off in enumerate((0, -10, -20)):
            canvas.create_text(cx + 22 + shear + i * 4, cy - 40 + off,
                               text="z", fill="#93c5fd", font=("Segoe UI", 10 + i * 3))
    elif extra == "sweat":
        canvas.create_oval(cx + 22 + shear, cy - 60, cx + 28 + shear, cy - 52,
                           fill="#60a5fa", outline="")
    elif extra == "portal":
        canvas.create_oval(cx + 24 + shear, cy - 60, cx + 46 + shear, cy - 38,
                           outline="#f1c40f", width=3)
        canvas.create_oval(cx + 28 + shear, cy - 56, cx + 42 + shear, cy - 42,
                           outline="#f472b6", width=2)
