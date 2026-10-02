"""Procedural ASTRO BOY companion renderer (black astro boy).

A sleek black humanoid with LED red/yellow eyes, chrome limbs,
futuristic HUD visor, and glowing neon accents. Built for the
hermes_companion pet engine — same Canvas contract as `animator.draw_pet`.

Design language: black matte body · chrome joints · red LED accents
· yellow HUD trim · subtle glow particles. Think "futuristic
street kid" meets "Hermon's AI agent" — a compact, confident
character that reads as both cyber and warm.

Palette is changeable (the same `pose_params` from animator.py
drives ALL movement vocabulary so behavior-engine chains work
unchanged).

Visual vocabulary (distinct from pet/samurai):
    - Round black head with HUD visor instead of simple circle
    - LED eyes (red = working, yellow = idle, white = alert)
    - Chrome arm cylinders instead of rounded limbs
    - Glowing neon accents on joints and chest
    - Floating holographic HUD elements
    - Exhaust particles from feet when moving
    - Data streams as side effects

Palettes (changeable accent colors):
    crimson (default) — red LED + gold trim
    arctic — blue LED + ice trim
    neon — green LED + neon trim
    plasma — purple LED + magenta trim
    mono — white LED + silver trim
    void — dark red LED + obsidian trim
"""
from __future__ import annotations

import math

from hermes_companion.animation.animator import BG, PUPIL, pose_params

# ---- fixed structural pieces (never change color) ---------------------
HEAD_R = 18            # head radius
CHROME = "#6b7280"     # chrome limb / joint color
CHROME_DARK = "#4b5563"
LEDS = "#ef4444"       # LED red
LED_GLOW = "#fca5a5"    # LED ambient glow
HUD_COLOR = "#fbbf24"   # HUD gold trim
HUD_BG = "#0f172a"      # HUD background
NECK_COLOR = "#374151"  # dark connector
CHEST_COLOR = "#1f2937" # dark chest panel
FOOT_COLOR = "#111827"  # black foot

# ---- changeable palettes ------------------------------------------------
ASTRO_PALETTES: dict[str, dict[str, str]] = {
    "crimson": {"led": "#ef4444", "led_glow": "#fca5a5", "hud": "#fbbf24",
                "hud_bg": "#0f172a", "accent": "#dc2626"},
    "arctic":  {"led": "#3b82f6", "led_glow": "#93c5fd", "hud": "#06b6d4",
                "hud_bg": "#0c4a6e", "accent": "#0284c7"},
    "neon":    {"led": "#22c55e", "led_glow": "#86efac", "hud": "#a855f7",
                "hud_bg": "#1e1b4b", "accent": "#7c3aed"},
    "plasma":  {"led": "#a855f7", "led_glow": "#c084fc", "hud": "#ec4899",
                "hud_bg": "#500724", "accent": "#db2777"},
    "mono":    {"led": "#e2e8f0", "led_glow": "#f1f5f9", "hud": "#94a3b8",
                "hud_bg": "#1e293b", "accent": "#64748b"},
    "void":    {"led": "#dc2626", "led_glow": "#7f1d1d", "hud": "#57534e",
                "hud_bg": "#0c0a09", "accent": "#44403c"},
}

ASTRO_DEFAULT_PALETTE = "crimson"


def _palette(name: str | None) -> dict[str, str]:
    return ASTRO_PALETTES.get(name or "", ASTRO_PALETTES[ASTRO_DEFAULT_PALETTE])


# ---- drawing helpers ---------------------------------------------------
def _glow(canvas, x, y, radius, color, s=1.0):
    """Draw a soft circular glow behind an element."""
    r = radius * s
    canvas.create_oval(x - r, y - r, x + r, y + r,
                       fill=color, outline="", stipple="gray50")


def _hud_rect(canvas, x, y, w, h, palette: dict, s=1.0):
    """Draw a futuristic HUD panel rectangle."""
    cx, cy = x * s, y * s
    cw, ch = w * s, h * s
    canvas.create_rectangle(cx - cw/2, cy - ch/2, cx + cw/2, cy + ch/2,
                            fill=palette["hud_bg"], outline=palette["hud"],
                            width=2)


def _led_circle(canvas, x, y, r, color, glow, s=1.0):
    """Draw an LED circle with ambient glow."""
    sr = r * s
    _glow(canvas, x, y, sr * 2.5, glow, s)
    canvas.create_oval(x - sr, y - sr, x + sr, y + sr,
                       fill=color, outline="")
    canvas.create_oval(x - sr * 0.6, y - sr * 0.6,
                       x + sr * 0.6, y + sr * 0.6,
                       fill="white", outline="")


def _chrome_cylinder(canvas, x1, y1, x2, y2, r, palette: dict, s=1.0):
    """Draw a chrome cylinder (arm/leg)."""
    canvas.create_line(x1 * s, y1 * s, x2 * s, y2 * s,
                       width=r * 2 * s, capstyle="round", fill=CHROME)
    canvas.create_line(x1 * s, y1 * s, x2 * s, y2 * s,
                       width=r * s, capstyle="round", fill=CHROME_DARK)


# ---- main render -------------------------------------------------------
def draw_astro(canvas, pose: str, progress: float = 0.0,
               palette: str | None = None) -> None:
    """Draw the astro boy in `pose` at `progress` (0..1) with the given
    material palette. Same Canvas contract as `animator.draw_pet`."""
    P = _palette(palette)
    canvas.delete("all")
    W, H = 200, 240
    cx, base_y = 100, 160
    prm = pose_params(pose, progress)
    p = progress % 1.0
    bob = prm["bob"]
    cy = base_y + bob
    shear = prm["lean"] * 30.0
    led_col = P["led"]
    led_glow = P["led_glow"]
    hud_col = P["hud"]

    # body vertical offset (jump/fall/sit/tall)
    body = prm["body"]
    if body == "jump":
        cy -= 26
    elif body == "fall":
        cy += 14
    elif body == "sit":
        cy += 10
    elif body == "tall":
        cy -= 4

    # ---- feet with exhaust particles -----------------------------------
    foot_y = cy + 36
    for fdx in (-14, 14):
        canvas.create_oval(cx + fdx - 9 + shear, foot_y,
                           cx + fdx + 9 + shear, foot_y + 10,
                           fill=FOOT_COLOR, outline="")
        # exhaust glow when moving
        if prm["arms"] in ("down",) or body in ("jump",):
            ex_y = foot_y + 12 + int(math.sin(p * 12.56) * 4)
            _glow(canvas, cx + fdx + shear, ex_y, 4, led_glow)
            canvas.create_oval(cx + fdx + shear - 3, ex_y - 3,
                               cx + fdx + shear + 3, ex_y + 3,
                               fill=led_col, outline="")

    # ---- legs (chrome cylinders) ---------------------------------------
    for side, ldx in (("l", -12), ("r", 12)):
        hip_y = cy + 6
        canvas.create_rectangle(cx + ldx - 7 + shear, hip_y,
                                cx + ldx + 7 + shear, foot_y - 2,
                                fill=CHEST_COLOR, outline="")
        # chrome knee joint
        knee_y = hip_y + (foot_y - 2 - hip_y) * 0.55
        _glow(canvas, cx + ldx + shear, knee_y, 5, led_glow)
        canvas.create_oval(cx + ldx - 8 + shear, knee_y - 2,
                           cx + ldx + 8 + shear, knee_y + 2,
                           fill=CHROME, outline="")

    # ---- torso (dark chest panel with HUD) -----------------------------
    torso_top = cy - 56
    torso_bot = cy + 8
    canvas.create_rectangle(cx - 18 + shear, torso_top,
                            cx + 18 + shear, torso_bot,
                            fill=CHEST_COLOR, outline="")
    # HUD visor panel on chest
    hud_w, hud_h = 28, 14
    _hud_rect(canvas, cx + 8 + shear, torso_top + 6, hud_w, hud_h, P, 1.0)
    # HUD scan line
    scan_y = torso_top + 6 + 4 + int(math.sin(p * 6.28) * 3)
    canvas.create_line(cx - 10 + shear, scan_y,
                       cx + 10 + shear, scan_y,
                       width=1, fill=hud_col)

    # ---- chest LED accent ----------------------------------------------
    chest_led_y = torso_top + 20
    _led_circle(canvas, cx + 10 + shear, chest_led_y, 3, led_col, led_glow)

    # ---- neck connector --------------------------------------------------
    neck_y = torso_top - 2
    canvas.create_rectangle(cx - 8 + shear, neck_y - 4,
                            cx + 8 + shear, neck_y + 4,
                            fill=NECK_COLOR, outline="")

    # ---- arms (chrome) ---------------------------------------------------
    ax, ay = cx + shear, cy - 16
    arms = prm["arms"]
    arm_r = 7
    if arms == "down":
        canvas.create_line(ax - 18, ay + 4, ax - 28, ay + 32,
                           width=arm_r * 2, capstyle="round", fill=CHROME)
        canvas.create_line(ax + 18, ay + 4, ax + 28, ay + 32,
                           width=arm_r * 2, capstyle="round", fill=CHROME)
    elif arms == "up":
        canvas.create_line(ax - 16, ay - 6, ax - 32, ay - 44,
                           width=arm_r * 2, capstyle="round", fill=CHROME)
        canvas.create_line(ax + 16, ay - 6, ax + 32, ay - 44,
                           width=arm_r * 2, capstyle="round", fill=CHROME)
    elif arms == "wave":
        canvas.create_line(ax + 16, ay - 6, ax + 36, ay - 40 - 6 * math.sin(p * 8),
                           width=arm_r * 2, capstyle="round", fill=CHROME)
        canvas.create_line(ax - 16, ay - 6, ax - 26, ay + 14,
                           width=arm_r * 2, capstyle="round", fill=CHROME)
    elif arms in ("work", "hold"):
        canvas.create_line(ax - 18, ay + 6, ax - 14, ay + 28,
                           width=arm_r * 2, capstyle="round", fill=CHROME)
        canvas.create_line(ax + 18, ay + 6, ax + 14, ay + 28,
                           width=arm_r * 2, capstyle="round", fill=CHROME)
    elif arms == "bent":
        canvas.create_line(ax - 18, ay - 4, ax - 8, ay - 30,
                           width=arm_r * 2, capstyle="round", fill=CHROME)
        canvas.create_line(ax + 18, ay - 4, ax + 8, ay - 30,
                           width=arm_r * 2, capstyle="round", fill=CHROME)
    elif arms == "throw":
        canvas.create_line(ax - 14, ay - 4, ax - 40, ay - 32,
                           width=arm_r * 2, capstyle="round", fill=CHROME)
    elif arms == "stretch":
        canvas.create_line(ax - 18, ay - 4, ax - 44, ay - 50,
                           width=arm_r * 2, capstyle="round", fill=CHROME)
        canvas.create_line(ax + 18, ay - 4, ax + 44, ay - 50,
                           width=arm_r * 2, capstyle="round", fill=CHROME)

    # ---- chrome hand circles -------------------------------------------
    hand_y_down = ay + 32 if arms in ("down", "work", "hold") else ay + 14
    if arms in ("down", "work", "hold"):
        canvas.create_oval(ax - 28 - 5 + shear, hand_y_down - 5,
                           ax - 28 + 5 + shear, hand_y_down + 5,
                           fill=CHROME, outline="")
        canvas.create_oval(ax + 28 + shear, hand_y_down - 5,
                           ax + 28 + 10 + shear, hand_y_down + 5,
                           fill=CHROME, outline="")

    # ---- head with HUD visor -------------------------------------------
    head_cy = cy - 78
    head_r = HEAD_R

    # face plate (black matte)
    canvas.create_oval(cx - head_r + shear, head_cy - head_r,
                       cx + head_r + shear, head_cy + head_r,
                       fill="#0a0a0a", outline="")
    # HUD visor strip across forehead
    visor_y = head_cy - head_r + 4
    canvas.create_rectangle(cx - head_r + 2 + shear, visor_y - 3,
                            cx + head_r - 2 + shear, visor_y + 3,
                            fill=hud_col, outline="")
    # visor glow line
    canvas.create_line(cx - head_r + 4 + shear, visor_y,
                       cx + head_r - 4 + shear, visor_y,
                       width=2, fill=led_col)

    # LED eyes (distinct shape: angular LED slits)
    eye_y = head_cy - 4
    ex_l, ex_r = cx - 9 + shear, cx + 9 + shear
    eyes = prm["eyes"]
    if eyes == "closed":
        canvas.create_line(ex_l - 5, eye_y, ex_l + 5, eye_y,
                           width=3, fill=led_col)
        canvas.create_line(ex_r - 5, eye_y, ex_r + 5, eye_y,
                           width=3, fill=led_col)
    elif eyes == "xeyes":
        for ex in (ex_l, ex_r):
            canvas.create_line(ex - 5, eye_y - 5, ex + 5, eye_y + 5,
                               width=3, fill=led_col)
            canvas.create_line(ex - 5, eye_y + 5, ex + 5, eye_y - 5,
                               width=3, fill=led_col)
    elif eyes == "up":
        # LED slit looking up
        canvas.create_oval(ex_l - 5, eye_y - 7, ex_l + 5, eye_y + 2,
                           fill=led_col, outline="")
        canvas.create_oval(ex_r - 5, eye_y - 7, ex_r + 5, eye_y + 2,
                           fill=led_col, outline="")
    elif eyes == "down":
        canvas.create_oval(ex_l - 3, eye_y - 2, ex_l + 5, eye_y + 7,
                           fill=led_col, outline="")
        canvas.create_oval(ex_r - 3, eye_y - 2, ex_r + 5, eye_y + 7,
                           fill=led_col, outline="")
    elif eyes == "wide":
        # wide LED ring
        canvas.create_oval(ex_l - 7, eye_y - 7, ex_l + 7, eye_y + 7,
                           fill=led_glow, outline=led_col, width=2)
        canvas.create_oval(ex_r - 7, eye_y - 7, ex_r + 7, eye_y + 7,
                           fill=led_glow, outline=led_col, width=2)
        canvas.create_oval(ex_l - 3, eye_y - 3, ex_l + 3, eye_y + 3,
                           fill=led_col, outline="")
        canvas.create_oval(ex_r - 3, eye_y - 3, ex_r + 3, eye_y + 3,
                           fill=led_col, outline="")
    elif eyes == "left":
        # LED slits shifted toward the gaze direction (with a leading glow edge)
        for ex in (ex_l, ex_r):
            canvas.create_oval(ex - 7, eye_y - 3, ex + 1, eye_y + 3,
                               fill=led_col, outline="")
            canvas.create_oval(ex - 9, eye_y - 1, ex - 6, eye_y + 1,
                               fill=led_glow, outline="")
    elif eyes == "right":
        for ex in (ex_l, ex_r):
            canvas.create_oval(ex - 1, eye_y - 3, ex + 7, eye_y + 3,
                               fill=led_col, outline="")
            canvas.create_oval(ex + 6, eye_y - 1, ex + 9, eye_y + 1,
                               fill=led_glow, outline="")
    elif eyes == "half_closed":
        for ex in (ex_l, ex_r):
            canvas.create_rectangle(ex - 5, eye_y - 1, ex + 5, eye_y + 2,
                                    fill=led_col, outline="")
    elif eyes == "smug":
        canvas.create_line(ex_l - 5, eye_y + 1, ex_l + 5, eye_y - 1,
                           width=3, fill=led_col)
        canvas.create_line(ex_r - 5, eye_y - 1, ex_r + 5, eye_y + 1,
                           width=3, fill=led_col)
    elif eyes == "neutral":
        # small LED dot
        canvas.create_oval(ex_l - 3, eye_y - 3, ex_l + 3, eye_y + 3,
                           fill=led_col, outline="")
        canvas.create_oval(ex_r - 3, eye_y - 3, ex_r + 3, eye_y + 3,
                           fill=led_col, outline="")
    else:
        # default: small dot
        canvas.create_oval(ex_l - 3, eye_y - 3, ex_l + 3, eye_y + 3,
                           fill=led_col, outline="")
        canvas.create_oval(ex_r - 3, eye_y - 3, ex_r + 3, eye_y + 3,
                           fill=led_col, outline="")

    # mouth slit (under visor)
    if eyes not in ("closed",):
        canvas.create_rectangle(cx - 6 + shear, head_cy + 8,
                                cx + 6 + shear, head_cy + 13,
                                fill="", outline=led_col, width=1)

    # ---- headband / visor accent ---------------------------------------
    canvas.create_rectangle(cx - head_r + shear, head_cy - head_r + 2,
                            cx + head_r + shear, head_cy - head_r + 7,
                            fill=hud_col, outline="")
    # antenna tip
    canvas.create_line(cx + shear, head_cy - head_r - 6,
                       cx + shear, head_cy - head_r - 16,
                       width=3, fill=CHROME)
    _led_circle(canvas, cx + shear, head_cy - head_r - 18, 3, led_col, led_glow)

    # ---- floating HUD data streams --------------------------------------
    if pose in ("terminal_work", "web_scan", "dev_merge", "work",
                "terminal", "file_organize", "design_draft",
                "audio_tune", "read", "memory_vault"):
        # floating data panels around the head
        for i, (dx, dy) in enumerate(((28, -30), (-30, -20), (32, -10))):
            px = cx + dx + shear
            py = head_cy + dy + int(math.sin(p * 4 + i) * 3)
            _hud_rect(canvas, px, py, 16, 10, P, 0.7)
            # tiny text indicator
            canvas.create_text(px + shear, py + 2,
                               text=str(i), fill=hud_col,
                               font=("Consolas", 6))

    # ---- extras (props — same vocabulary, rendered with astro aesthetic) --
    extra = prm["extra"]
    if extra == "terminal":
        tx, ty = cx + 26 + shear, cy - 66
        canvas.create_rectangle(tx - 22, ty - 12, tx + 22, ty + 12,
                                fill=HUD_BG, outline=led_col, width=2)
        for i in range(3):
            canvas.create_line(tx - 16, ty - 4 + i * 6, tx + 4, ty - 4 + i * 6,
                               fill=led_col, width=2)
        canvas.create_text(tx - 12, ty - 8, text=">_>", fill=hud_col,
                           font=("Consolas", 8, "bold"))
    elif extra == "web":
        wx, wy = cx + 34 + shear, cy - 50
        canvas.create_oval(wx - 14, wy - 14, wx + 14, wy + 14,
                           outline=led_col, width=2)
        canvas.create_line(wx - 10, wy, wx + 10, wy, fill=led_col, width=1)
        canvas.create_line(wx, wy - 10, wx, wy + 10, fill=led_col, width=1)
        canvas.create_arc(wx - 14, wy - 14, wx + 14, wy + 14,
                          start=0, extent=90, style="arc",
                          outline=led_glow, width=1)
    elif extra == "files":
        for i, off in enumerate((0, 7, 14)):
            canvas.create_rectangle(cx - 18 + shear + i * 5, cy - 34 + off,
                                    cx + 6 + shear + i * 5, cy - 10 + off,
                                    fill=HUD_BG, outline=CHROME, width=1)
    elif extra == "git":
        gx, gy = cx + 30 + shear, cy - 46
        canvas.create_line(gx - 8, gy - 10, gx - 8, gy + 10,
                           fill=led_col, width=2)
        canvas.create_line(gx + 8, gy - 10, gx + 8, gy + 10,
                           fill=led_col, width=2)
        canvas.create_line(gx - 8, gy - 4, gx + 8, gy - 4,
                           fill=led_col, width=2)
        canvas.create_oval(gx - 10, gy - 13, gx - 6, gy - 9,
                           fill=hud_col, outline="")
    elif extra == "palette":
        for i, col in enumerate((led_col, hud_col, "#f472b6", "#60a5fa")):
            ang = p * 3.14 + i * 1.26
            canvas.create_oval(cx + 26 + shear + int(math.cos(ang) * 8),
                               cy - 40 + int(math.sin(ang) * 8),
                               cx + 34 + shear + int(math.cos(ang) * 8),
                               cy - 32 + int(math.sin(ang) * 8),
                               fill=col, outline="")
    elif extra == "vault":
        vx, vy = cx + 30 + shear, cy - 42
        canvas.create_rectangle(vx - 12, vy - 16, vx + 12, vy + 4,
                                fill=HUD_BG, outline=led_col, width=2)
        canvas.create_oval(vx - 2, vy - 8, vx + 4, vy - 2,
                           fill=hud_col, outline="")
    elif extra == "terminal":
        pass  # already handled above
    elif extra == "terminal_work":
        tx, ty = cx + 26 + shear, cy - 66
        canvas.create_rectangle(tx - 22, ty - 12, tx + 22, ty + 12,
                                fill=HUD_BG, outline=led_col, width=2)
        for i in range(3):
            canvas.create_line(tx - 16, ty - 4 + i * 6, tx + 4, ty - 4 + i * 6,
                               fill=led_col, width=2)
        canvas.create_text(tx - 12, ty - 8, text=">_>", fill=hud_col,
                           font=("Consolas", 8, "bold"))
    elif extra == "spark":
        for i in range(6):
            ang = p * 6.28 + i * 3.14159 / 3
            canvas.create_line(cx + int(math.cos(ang) * 30) + shear,
                               cy - 10 + int(math.sin(ang) * 30),
                               cx + int(math.cos(ang) * 40) + shear,
                               cy - 10 + int(math.sin(ang) * 40),
                               fill=led_col, width=3)
    elif extra == "speed_lines":
        for i in range(3):
            y = cy - 14 + i * 14
            canvas.create_line(cx - 48 - i * 12 + shear, y,
                               cx - 20 + shear, y,
                               fill=led_glow, width=3)
    elif extra == "confetti":
        for i, col in enumerate((led_col, hud_col, "#f472b6", "#60a5fa")):
            ang = p * 6.28 + i
            canvas.create_oval(cx + int(math.cos(ang) * (34 + i * 6)) + shear,
                               cy - 20 + int(math.sin(ang) * (20 + i * 4)),
                               cx + int(math.cos(ang) * (34 + i * 6)) + 5 + shear,
                               cy - 20 + int(math.sin(ang) * (20 + i * 4)) + 5,
                               fill=col, outline="")
    elif extra == "sweat":
        canvas.create_oval(cx + 28 + shear, cy - 24, cx + 36 + shear, cy - 14,
                           fill=led_col, outline="")
        canvas.create_oval(cx + 20 + shear, cy - 16, cx + 26 + shear, cy - 8,
                           fill=led_col, outline="")
    elif extra == "zzz":
        for i, off in enumerate((0, -12, -24)):
            canvas.create_text(cx + 28 + shear + i * 4, cy - 34 + off,
                               text="z", fill=led_col,
                               font=("Segoe UI", 12 + i * 3))
    elif extra == "watch":
        canvas.create_oval(cx + 20 + shear, cy - 14, cx + 32 + shear, cy - 2,
                           fill=HUD_BG, outline=led_col, width=1)
        canvas.create_line(cx + 26 + shear, cy - 6, cx + 26 + shear, cy - 10,
                           width=1, fill=led_col)
        canvas.create_line(cx + 26 + shear, cy - 6, cx + 28 + shear, cy - 4,
                           width=1, fill=led_col)
    elif extra == "think":
        for i, (dx, dy, r) in enumerate(((22, -46, 2), (30, -54, 3), (40, -62, 4))):
            canvas.create_oval(cx + dx + shear - r, cy + dy - r,
                               cx + dx + shear + r, cy + dy + r,
                               fill=HUD_BG, outline=led_col, width=1)
        canvas.create_oval(cx + 42 + shear, cy - 78, cx + 66 + shear, cy - 54,
                           fill=HUD_BG, outline=led_col, width=1)
    elif extra == "book":
        bx, by = cx + 28 + shear, cy - 28
        canvas.create_arc(bx - 12, by - 14, bx, by + 6,
                          start=270, extent=180, style="chord",
                          fill=HUD_BG, outline=led_col, width=1)
        canvas.create_arc(bx, by - 14, bx + 12, by + 6,
                          start=270, extent=180, style="chord",
                          fill="#1a1a2e", outline=led_col, width=1)
    elif extra == "notes":
        for i, (dx, dy) in enumerate(((26, -40), (40, -30))):
            nx, ny = cx + dx + shear, cy + dy
            canvas.create_text(nx, ny, text="♫", fill=led_col,
                               font=("Segoe UI Symbol", 16))
    elif extra == "pen":
        canvas.create_line(cx + 22 + shear, cy - 30, cx + 48 + shear, cy - 26,
                           width=3, fill=led_col)
        canvas.create_line(cx + 48 + shear, cy - 26, cx + 34 + shear, cy - 10,
                           width=3, fill=hud_col)
        canvas.create_line(cx + 34 + shear, cy - 10, cx + 46 + shear, cy - 4,
                           width=3, fill=led_glow)
    elif extra == "yawn":
        canvas.create_arc(cx - 10 + shear, cy + 6, cx + 10 + shear, cy + 22,
                          start=0, extent=180, style="chord",
                          fill=HUD_BG, outline=led_col, width=1)
    elif extra == "portal":
        canvas.create_oval(cx + 28 + shear, cy - 56, cx + 54 + shear, cy - 30,
                           outline=led_col, width=3)
        canvas.create_oval(cx + 32 + shear, cy - 50, cx + 50 + shear, cy - 36,
                           outline=led_glow, width=2)
    elif extra == "orb_exit" or extra == "orb_return":
        t = p * 40
        oy = cy - 56 - t
        _led_circle(canvas, cx + 34 + shear, oy, 4, led_col, led_glow)
    elif extra == "absorb":
        _glow(canvas, cx + 10 + shear, cy - 38, 8, led_glow)
        canvas.create_oval(cx + 8 + shear, cy - 38, cx + 20 + shear, cy - 26,
                           fill=led_col, outline="")


# ---- stand-alone prop renderer (mirrors draw_extra from animator.py) ---
def draw_extra(canvas, extra: str, progress: float = 0.0,
               cx: float = 100, cy: float = 150, s: float = 1.0) -> None:
    """Draw ONE named prop/effect at (cx, cy) scaled by s."""
    P = _palette(ASTRO_DEFAULT_PALETTE)
    if extra is None:
        return
    p = progress % 1.0
    led_col = P["led"]
    hud_col = P["hud"]
    led_glow = P["led_glow"]

    if extra == "terminal":
        tx, ty = cx * s, cy * s
        canvas.create_rectangle(tx - 22 * s, ty - 12 * s, tx + 22 * s, ty + 12 * s,
                                fill=HUD_BG, outline=led_col, width=2)
        for i in range(3):
            canvas.create_line(tx - 16 * s, ty - 4 * s + i * 6 * s,
                               tx + 4 * s, ty - 4 * s + i * 6 * s,
                               fill=led_col, width=2)
        canvas.create_text(tx - 12 * s, ty - 8 * s, text=">_>",
                           fill=hud_col, font=("Consolas", 8, "bold"))
    elif extra == "spark":
        for i in range(6):
            ang = p * 6.28 + i * 3.14159 / 3
            canvas.create_line(cx * s + int(math.cos(ang) * 30 * s),
                               cy * s + int(math.sin(ang) * 30 * s),
                               cx * s + int(math.cos(ang) * 40 * s),
                               cy * s + int(math.sin(ang) * 40 * s),
                               fill=led_col, width=3)
    elif extra == "speed_lines":
        for i in range(3):
            y = cy * s - 14 * s + i * 14 * s
            canvas.create_line(cx * s - 48 * s - i * 12 * s, y,
                               cx * s - 20 * s, y,
                               fill=led_glow, width=3)
    elif extra == "sweat":
        canvas.create_oval(cx * s + 28, cy * s - 24, cx * s + 36, cy * s - 14,
                           fill=led_col, outline="")
        canvas.create_oval(cx * s + 20, cy * s - 16, cx * s + 26, cy * s - 8,
                           fill=led_col, outline="")
    elif extra == "zzz":
        for i, off in enumerate((0, -12, -24)):
            canvas.create_text(cx * s + 28 + i * 4, cy * s - 34 + off,
                               text="z", fill=led_col, font=("Segoe UI", 12 + i * 3))
    elif extra == "confetti":
        for i, col in enumerate((led_col, hud_col, "#f472b6", "#60a5fa")):
            ang = p * 6.28 + i
            canvas.create_oval(cx * s + int(math.cos(ang) * (34 + i * 6)),
                               cy * s - 20 + int(math.sin(ang) * (20 + i * 4)),
                               cx * s + int(math.cos(ang) * (34 + i * 6)) + 5,
                               cy * s - 20 + int(math.sin(ang) * (20 + i * 4)) + 5,
                               fill=col, outline="")
