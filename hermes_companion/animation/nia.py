"""Nia - a detailed Afrocentric companion with the largest move set.

Design draws on West and East African textile and adornment traditions,
rendered respectfully and in the same proportions as the other companions:

* hair: a full textured afro, swinging locs with gold cuffs and cowrie
  shells, or a folded headwrap - chosen by palette;
* a kente-inspired woven sash (bands of colour with stepped blocks), a
  beaded collar, gold hoops and bangles;
* mudcloth (bogolan)-inspired wrap trousers - light motifs on deep earth;
* a talking drum carried at the hip, played in Nia's own moves;
* an Akoma (heart) emblem - patience and goodwill - that glows when Nia is
  waiting on you, and a heart-and-spiral emblem when Nia returns or retries.

Rig: jointed arms (shoulder + elbow angles) and legs (hip + knee), so on
top of every shared engine pose Nia performs ``NIA_MOVES`` - a dance and
storytelling repertoire no other companion has. Those moves are pure body
language, sorted by mood, and are only ever used as *flourishes*, so they
never change what a Hermes action means.

Same Canvas contract as ``animator.draw_pet``. Mood colour, curiosity
bubbles and tool props are shared with Herald so meaning reads the same on
every companion.
"""
from __future__ import annotations

import math

from hermes_companion.animation.animator import CONFETTI, PUPIL, pose_params
from hermes_companion.animation.herald import (
    MOOD_COLORS, EXCLAIM, WONDER, _bubble, _prop, mood_of,
)

NIA_PALETTES: dict[str, dict[str, str]] = {
    # skin, hair style, and a cloth colourway
    "kente": {"skin": "#5c3a21", "skin_hi": "#7a4e2d", "hair": "#1b120c",
              "style": "afro", "tunic": "#f4e9d8", "trim": "#d4a017",
              "sash": "#d4a017,#1f7a3a,#b22222,#111111", "wrap": "#3b2416",
              "motif": "#e8d9bf", "gold": "#e0b13a", "beads": "#b22222,#f4e9d8,#1f7a3a,#d4a017"},
    "indigo": {"skin": "#4a2e1b", "skin_hi": "#664127", "hair": "#120c08",
               "style": "locs", "tunic": "#1e2a5a", "trim": "#e6edf7",
               "sash": "#2c3e8f,#e6edf7,#14204a,#7da3d8", "wrap": "#141c3d",
               "motif": "#c8d6f0", "gold": "#d9a531", "beads": "#e6edf7,#2c3e8f,#d9a531,#7da3d8"},
    "ochre": {"skin": "#6b4428", "skin_hi": "#8a5a36", "hair": "#21150d",
              "style": "wrap", "tunic": "#c46a1c", "trim": "#2b1a10",
              "sash": "#e3a03a,#2b1a10,#f2dfb8,#8c3b12", "wrap": "#2b1a10",
              "motif": "#f2dfb8", "gold": "#e8b84a", "beads": "#f2dfb8,#8c3b12,#e3a03a,#2b1a10",
              "headwrap": "#e3a03a"},
    "emerald": {"skin": "#3f2616", "skin_hi": "#5a3720", "hair": "#0f0a06",
                "style": "locs", "tunic": "#0f5132", "trim": "#e0b13a",
                "sash": "#e0b13a,#0f5132,#f4e9d8,#7a1f1f", "wrap": "#1d140c",
                "motif": "#d9c79f", "gold": "#e0b13a", "beads": "#e0b13a,#f4e9d8,#7a1f1f,#0f5132"},
    "royal": {"skin": "#7a5032", "skin_hi": "#956641", "hair": "#24160e",
              "style": "afro", "tunic": "#4b1d6b", "trim": "#e0b13a",
              "sash": "#e0b13a,#4b1d6b,#f4e9d8,#111111", "wrap": "#2a1238",
              "motif": "#e9d6f5", "gold": "#e8bf4f", "beads": "#e0b13a,#f4e9d8,#9b59b6,#111111"},
}
NIA_DEFAULT_PALETTE = "kente"

# --- Nia's own repertoire -------------------------------------------------
# name -> (mood, arms (l_sh, l_el, r_sh, r_el) deg, legs (l_hip, l_knee,
#          r_hip, r_knee) deg, bounce px, sway px, extras)
# Angles: shoulder 0 = arm straight down, + = forward/out; elbow bend.
NIA_MOVES: dict[str, tuple] = {
    "drum_roll":        ("bright", (35, 70, 35, 70), (5, 0, 5, 0), 2, 0, {"drum", "fast"}),
    "drum_flourish":    ("bright", (40, 60, 120, 20), (5, 0, 5, 0), 3, 2, {"drum", "spark"}),
    "shoulder_bounce":  ("bright", (15, 80, 15, 80), (6, 4, 6, 4), 4, 0, {"shoulders"}),
    "footwork":         ("bright", (25, 40, 25, 40), (20, 40, -10, 10), 3, 4, {"steps"}),
    "spin_wrap":        ("bright", (70, 10, 70, 10), (4, 0, 4, 0), 2, 0, {"spin"}),
    "arm_wave_dance":   ("bright", (100, 20, 100, 20), (5, 0, 5, 0), 2, 3, {"wave"}),
    "step_clap":        ("bright", (55, 95, 55, 95), (15, 20, 0, 0), 3, 3, {"clap"}),
    "high_knee":        ("bright", (60, 40, 20, 60), (70, 90, 0, 0), 5, 0, {}),
    "kick_step":        ("bright", (40, 30, 40, 30), (0, 0, 50, 5), 3, 2, {}),
    "sway":             ("calm", (15, 15, 15, 15), (6, 0, 6, 0), 1, 6, {}),
    "head_nod_groove":  ("calm", (20, 50, 20, 50), (6, 0, 6, 0), 3, 1, {"nod"}),
    "hip_sway":         ("calm", (30, 60, 30, 60), (10, 6, 10, 6), 1, 8, {}),
    "arms_open_welcome": ("calm", (75, 10, 75, 10), (6, 0, 6, 0), 1, 0, {}),
    "bow_respect":      ("calm", (20, 70, 20, 70), (6, 0, 6, 0), 0, 0, {"bow"}),
    "stretch_reach":    ("calm", (170, 0, 170, 0), (4, 0, 4, 0), 2, 0, {}),
    "storyteller":      ("focused", (60, 70, 90, 40), (6, 0, 6, 0), 1, 2, {"gesture"}),
    "drum_rest":        ("focused", (30, 60, 10, 20), (6, 0, 6, 0), 0, 0, {"drum"}),
    "count_beats":      ("focused", (20, 40, 80, 100), (6, 0, 6, 0), 2, 0, {"tap"}),
    "hand_on_chin":     ("uneasy", (20, 40, 60, 140), (6, 0, 6, 0), 0, 0, {}),
    "deep_breath":      ("uneasy", (45, 30, 45, 30), (6, 0, 6, 0), 0, 0, {"breath"}),
    "shake_it_off":     ("uneasy", (30, 20, 30, 20), (8, 4, 8, 4), 2, 5, {"shake"}),
}


def nia_flourishes() -> dict[str, tuple[str, ...]]:
    out: dict[str, list[str]] = {}
    for name, spec in NIA_MOVES.items():
        out.setdefault(spec[0], []).append(name)
    return {k: tuple(v) for k, v in out.items()}


# Shared engine arm states -> joint angles.
_ARMS = {
    "down": (12, 10, 12, 10), "up": (165, 10, 165, 10), "cross": (50, 120, 50, 120),
    "hold": (40, 70, 40, 70), "wave": (12, 10, 150, 30), "bent": (30, 90, 30, 90),
    "stretch": (90, 0, 90, 0), "throw": (20, 20, 140, 10), "work": (45, 80, 50, 75),
}
_LEGS = {"sit": (80, 90, 80, 90), "walk": (25, 20, -15, 10), "lean_forward": (15, 10, -5, 5),
         "jump": (30, 60, 30, 60), "fall": (5, 0, 5, 0)}


def _palette(name: str | None) -> dict[str, str]:
    return NIA_PALETTES.get(name or NIA_DEFAULT_PALETTE, NIA_PALETTES[NIA_DEFAULT_PALETTE])


def _limb(canvas, x, y, ang1, ang2, l1, l2, side, width, color, flip_up=False):
    """Two-segment limb from (x, y). Angles in degrees from straight down,
    swinging outward on `side` (-1 left, +1 right). Returns the end point."""
    a1 = math.radians(ang1)
    ex = x + side * math.sin(a1) * l1
    ey = y + math.cos(a1) * l1 * (-1 if flip_up else 1)
    a2 = a1 + math.radians(ang2) * (1 if side > 0 else 1)
    hx = ex + side * math.sin(a2) * l2 * (0.6 if ang2 > 90 else 1)
    hy = ey + math.cos(a2) * l2
    canvas.create_line(x, y, ex, ey, hx, hy, width=width, fill=color,
                       capstyle="round", joint="round", smooth=False)
    return ex, ey, hx, hy


def _kente_band(canvas, x0, y0, x1, y1, colors, width, phase=0.0):
    """A woven strip: alternating colour blocks with small stepped inlays."""
    n = 9
    for i in range(n):
        t0, t1 = i / n, (i + 1) / n
        ax, ay = x0 + (x1 - x0) * t0, y0 + (y1 - y0) * t0
        bx, by = x0 + (x1 - x0) * t1, y0 + (y1 - y0) * t1
        col = colors[(i + int(phase)) % len(colors)]
        canvas.create_line(ax, ay, bx, by, width=width, fill=col)
        if i % 2 == 0:
            mx, my = (ax + bx) / 2, (ay + by) / 2
            canvas.create_rectangle(mx - 1.5, my - 1.5, mx + 1.5, my + 1.5,
                                    fill=colors[(i + 2) % len(colors)], outline="")


def _akoma(canvas, x, y, size, color, spiral=False):
    """Akoma (heart) emblem; with spirals it echoes the Sankofa heart."""
    s = size
    canvas.create_polygon(x, y + s, x - s, y - s * 0.1, x - s * 0.55, y - s * 0.75,
                          x, y - s * 0.35, x + s * 0.55, y - s * 0.75, x + s, y - s * 0.1,
                          fill=color, outline="white", smooth=True)
    if spiral:
        for k in (-1, 1):
            pts = []
            for i in range(10):
                t = i / 9
                r = s * 0.55 * (1 - t)
                ang = t * 5.5
                pts += [x + k * (s * 0.6 + math.cos(ang) * r * 0.6), y + s * 0.9 + math.sin(ang) * r * 0.6]
            canvas.create_line(*pts, fill=color, width=2, smooth=True)


def draw_nia(canvas, pose: str, progress: float = 0.0, palette: str | None = None) -> None:
    P = _palette(palette)
    canvas.delete("all")
    p = progress % 1.0
    wave = math.sin(p * 2 * math.pi)
    own = NIA_MOVES.get(pose)
    prm = pose_params(pose if own is None else "idle_bob", progress)
    body, eyes, extra = prm["body"], prm["eyes"], prm["extra"]
    shear = prm["lean"] * 30.0
    mood = own[0] if own else mood_of(pose)
    mood_key = {"bright": "joy", "focused": "work", "uneasy": "fail", "calm": "calm"}.get(mood, mood)
    glow = MOOD_COLORS.get(mood_key, MOOD_COLORS["calm"])

    if own is not None:
        _m, arms, legs, bounce, sway, fx = own
        osc = math.sin(p * 2 * math.pi * (3 if "fast" in fx else 2))
        arms = tuple(a + osc * (14 if i % 2 == 0 else 10) * (1 if i < 2 else -1)
                     for i, a in enumerate(arms))
        if "steps" in fx or "clap" in fx:
            legs = (legs[0] * (0.5 + 0.5 * osc), legs[1] * (0.5 + 0.5 * osc),
                    legs[2] * (0.5 - 0.5 * osc), legs[3] * (0.5 - 0.5 * osc))
        dy = -abs(osc) * bounce
        dx = sway * math.sin(p * 2 * math.pi)
        eyes = "closed" if "breath" in fx or "bow" in fx else ("up" if "nod" in fx and osc > 0 else eyes)
    else:
        fx = set()
        arms = _ARMS.get(prm["arms"], _ARMS["down"])
        if prm["arms"] == "wave":
            arms = (arms[0], arms[1], arms[2] + wave * 18, arms[3] + wave * 12)
        legs = _LEGS.get(body, (6, 0, 6, 0))
        if body == "walk" or pose.endswith("_to_workspace") or pose in ("return_home", "run_to_user", "panic"):
            legs = (25 * wave, 20 + 15 * wave, -25 * wave, 20 - 15 * wave)
        dy, dx = prm["bob"], 0.0

    cx = 100 + shear + dx
    cy = 150 + dy + {"jump": -28, "fall": 14, "sit": 14, "tall": -5}.get(body, 0)
    bow = 8 if "bow" in fx else 0

    # ---- mood ring: a circle of beads, coloured by meaning -----------------
    for i in range(24):
        ang = i / 24 * 2 * math.pi + p * 0.6
        r = 56 + 2 * math.sin(p * 4 * math.pi + i)
        bx, by = cx + math.cos(ang) * r, cy - 40 + math.sin(ang) * r
        size = 2.2 if i % 3 else 3.2
        canvas.create_oval(bx - size, by - size, bx + size, by + size,
                           fill=glow if i % 3 else P["gold"], outline="")

    # ---- talking drum (behind the hip) ----------------------------------------
    drum = "drum" in fx or pose in ("celebrate", "dance", "audio_tune")
    if drum:
        dxp, dyp = cx + 24, cy - 6
        canvas.create_polygon(dxp - 9, dyp - 14, dxp + 9, dyp - 14, dxp + 5, dyp,
                              dxp + 9, dyp + 14, dxp - 9, dyp + 14, dxp - 5, dyp,
                              fill="#8b5a2b", outline="#3b2416", smooth=False)
        for k in range(-3, 4):
            canvas.create_line(dxp + k * 2.4, dyp - 13, dxp + k * 1.2, dyp + 13,
                               fill="#e8d9bf", width=1)
        canvas.create_oval(dxp - 9, dyp - 17, dxp + 9, dyp - 11, fill="#e8d9bf", outline="#3b2416")

    # ---- legs: mudcloth wrap trousers + sandals -------------------------------
    hip_y = cy - 2
    for side, (hip, knee) in ((-1, legs[0:2]), (1, legs[2:4])):
        hx = cx + side * 8
        kx, ky, fx_, fy = _limb(canvas, hx, hip_y, hip, knee, 20, 20, side, 11, P["wrap"])
        for t in (0.3, 0.7):
            mx, my = hx + (kx - hx) * t, hip_y + (ky - hip_y) * t
            canvas.create_line(mx - 3, my, mx + 3, my, fill=P["motif"], width=1)
            canvas.create_oval(mx - 1, my + 3, mx + 1, my + 5, fill=P["motif"], outline="")
        canvas.create_line(kx, ky, fx_, fy, width=8, fill=P["skin"], capstyle="round")
        canvas.create_oval(fx_ - 7, fy - 2, fx_ + 7, fy + 5, fill="#3b2416", outline="")
        canvas.create_line(fx_ - 4, fy, fx_ + 4, fy - 1, fill=P["gold"], width=2)

    # ---- tunic with embroidered neckline ------------------------------------
    top = cy - 56 + bow
    canvas.create_polygon(cx - 17, top, cx + 17, top, cx + 23, cy + 6, cx - 23, cy + 6,
                          fill=P["tunic"], outline=P["trim"], width=2)
    for i in range(6):                                  # hem: stepped triangles
        hx0 = cx - 21 + i * 7
        canvas.create_polygon(hx0, cy + 6, hx0 + 3.5, cy + 1, hx0 + 7, cy + 6,
                              fill=P["trim"], outline="")
    canvas.create_polygon(cx - 7, top, cx + 7, top, cx, top + 12,
                          fill=P["trim"], outline="")
    for i in range(4):
        canvas.create_line(cx - 6 + i * 0.5, top + 2 + i * 2.5, cx + 6 - i * 0.5, top + 2 + i * 2.5,
                           fill=P["tunic"], width=1)
    # kente sash across the chest
    sash = P["sash"].split(",")
    _kente_band(canvas, cx - 18, top + 4, cx + 20, cy - 4, sash, 7, phase=p * 3)

    # Akoma emblem: patience while waiting on you; spiral heart on return/retry
    if mood in ("approve",) or pose in ("wait", "wave"):
        _akoma(canvas, cx + 8, top + 26, 5, MOOD_COLORS["approve"])
    elif pose in ("return_home", "retry", "recover"):
        _akoma(canvas, cx + 8, top + 26, 5, glow, spiral=True)

    # ---- arms with bangles --------------------------------------------------
    sy = top + 7
    hands = []
    for side, (sh, el) in ((-1, arms[0:2]), (1, arms[2:4])):
        up = sh > 100
        ex, ey, hx, hy = _limb(canvas, cx + side * 15, sy, min(sh, 100) if not up else 180 - sh,
                               el, 17, 16, side, 7, P["skin"], flip_up=up)
        for k in (0.75, 0.88):
            bx, by = ex + (hx - ex) * k, ey + (hy - ey) * k
            canvas.create_oval(bx - 3.5, by - 2, bx + 3.5, by + 2, outline=P["gold"], width=2)
        canvas.create_oval(hx - 3.5, hy - 3.5, hx + 3.5, hy + 3.5, fill=P["skin_hi"], outline="")
        hands.append((hx, hy))
    if "clap" in fx and abs(math.sin(p * 4 * math.pi)) > 0.8:
        mx = (hands[0][0] + hands[1][0]) / 2
        my = (hands[0][1] + hands[1][1]) / 2
        for k in range(5):
            ang = k * 1.256
            canvas.create_line(mx + math.cos(ang) * 6, my + math.sin(ang) * 6,
                               mx + math.cos(ang) * 11, my + math.sin(ang) * 11,
                               fill=P["gold"], width=2)

    # ---- beaded collar ----------------------------------------------------------
    beads = P["beads"].split(",")
    for row, rad in enumerate((11, 15)):
        for i in range(11):
            ang = math.pi * (0.15 + 0.7 * i / 10)
            bx = cx + math.cos(ang) * rad
            by = top - 2 + math.sin(ang) * rad * 0.55
            canvas.create_oval(bx - 1.8, by - 1.8, bx + 1.8, by + 1.8,
                               fill=beads[(i + row) % len(beads)], outline="")

    # ---- head ----------------------------------------------------------------------
    hcx = cx + shear * 0.3 + (2 if "nod" in fx else 0)
    hcy = top - 20 + bow + (2 * math.sin(p * 4 * math.pi) if "nod" in fx else 0)
    style = P["style"]
    if style == "afro":
        R = 27
        canvas.create_oval(hcx - R, hcy - R - 8, hcx + R, hcy + R - 12, fill=P["hair"], outline="")
        for i in range(36):                                   # coil texture
            ang = i * 2.399
            rr = R * math.sqrt((i + 0.5) / 36) * 0.95
            tx, ty = hcx + math.cos(ang) * rr, hcy - 10 + math.sin(ang) * rr
            canvas.create_oval(tx - 2.2, ty - 2.2, tx + 2.2, ty + 2.2, outline="#3a2a1e")
    elif style == "locs":
        swing = prm["lean"] * 40 + 3 * math.sin(p * 2 * math.pi + 1) + dx * 0.6
        canvas.create_oval(hcx - 20, hcy - 26, hcx + 20, hcy + 4, fill=P["hair"], outline="")
        for i in range(11):
            ox = -18 + i * 3.6
            pts = []
            for k in range(6):
                t = k / 5
                pts += [hcx + ox * (1 + t * 0.35) - swing * t * t,
                        hcy - 14 + t * 34 + abs(ox) * 0.15]
            canvas.create_line(*pts, fill=P["hair"], width=4, smooth=True, capstyle="round")
            if i % 3 == 0:
                cxl, cyl = pts[-4], pts[-3]
                canvas.create_oval(cxl - 2.5, cyl - 2, cxl + 2.5, cyl + 2, fill=P["gold"], outline="")
            if i % 4 == 1:
                cxl, cyl = pts[-2], pts[-1]
                canvas.create_oval(cxl - 2.6, cyl - 1.8, cxl + 2.6, cyl + 1.8, fill="#fbf6ea",
                                   outline="#c9bfa8")
                canvas.create_line(cxl - 1.6, cyl, cxl + 1.6, cyl, fill="#8a7f6a")
    if style == "wrap":
        wrap = P.get("headwrap", P["trim"])
        canvas.create_oval(hcx - 22, hcy - 34, hcx + 22, hcy - 4, fill=wrap, outline="")
        canvas.create_polygon(hcx - 24, hcy - 14, hcx - 14, hcy - 40, hcx + 4, hcy - 32,
                              hcx + 22, hcy - 46, hcx + 26, hcy - 16,
                              fill=wrap, outline="#2b1a10", smooth=True)
        for i in range(4):
            canvas.create_line(hcx - 18 + i * 9, hcy - 30, hcx - 12 + i * 9, hcy - 10,
                               fill="#2b1a10", width=1)
            canvas.create_oval(hcx - 15 + i * 9, hcy - 22, hcx - 12 + i * 9, hcy - 19,
                               fill="#f2dfb8", outline="")

    # face
    canvas.create_oval(hcx - 17, hcy - 17, hcx + 17, hcy + 18, fill=P["skin"], outline="")
    canvas.create_oval(hcx - 11, hcy - 13, hcx - 3, hcy - 7, fill=P["skin_hi"], outline="")
    if style == "afro":
        canvas.create_arc(hcx - 18, hcy - 22, hcx + 18, hcy + 4, start=20, extent=140,
                          style="chord", fill=P["hair"], outline="")
    # gold hoops
    for side in (-1, 1):
        ex = hcx + side * 17
        canvas.create_oval(ex - 4, hcy + 2, ex + 4, hcy + 12, outline=P["gold"], width=2)

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
            canvas.create_oval(ex - r, ey - r, ex + r, ey + r, fill="white", outline="")
            ddx = {"left": -2, "right": 2}.get(eyes, 0)
            ddy = {"up": -2, "down": 2}.get(eyes, 0)
            canvas.create_oval(ex - 2.6 + ddx, ey - 2.6 + ddy, ex + 2.6 + ddx, ey + 2.6 + ddy,
                               fill="#2b1a10", outline="")
            canvas.create_oval(ex - 0.8 + ddx, ey - 2 + ddy, ex + 0.6 + ddx, ey - 0.6 + ddy,
                               fill="white", outline="")
            canvas.create_line(ex - 4, ey - r, ex - 5.5, ey - r - 1.5, fill=PUPIL, width=1)
    tilt = {"fail": 3, "uneasy": 3, "approve": -2, "curious": -1}.get(mood, 0)
    for k, ex in ((-1, hcx - gap), (1, hcx + gap)):
        canvas.create_line(ex - 4, ey - 8 + k * tilt * -1, ex + 4, ey - 8 + k * tilt,
                           width=2, fill=P["hair"])
    canvas.create_arc(hcx - 3, ey + 3, hcx + 3, ey + 8, start=200, extent=140,
                      style="arc", width=1, outline="#2b1a10")
    my = hcy + 11
    if mood in ("joy", "bright"):
        canvas.create_arc(hcx - 6, my - 4, hcx + 6, my + 5, start=180, extent=180,
                          style="chord", fill="#5a1414", outline="")
        canvas.create_line(hcx - 4, my, hcx + 4, my, fill="white", width=2)
    elif mood in ("fail", "uneasy"):
        canvas.create_arc(hcx - 5, my, hcx + 5, my + 6, start=20, extent=140,
                          style="arc", width=2, outline="#5a1414")
    elif eyes == "wide" or mood == "approve":
        canvas.create_oval(hcx - 3, my - 2, hcx + 3, my + 4, fill="#5a1414", outline="")
    else:
        canvas.create_arc(hcx - 5, my - 3, hcx + 5, my + 3, start=200, extent=140,
                          style="arc", width=2, outline="#5a1414")

    # ---- effects -----------------------------------------------------------------
    if "spin" in fx:
        for i in range(3):
            canvas.create_arc(cx - 30 - i * 5, cy - 10 - i * 3, cx + 30 + i * 5, cy + 16 + i * 3,
                              start=200 + p * 360, extent=90, style="arc",
                              outline=sash[i % len(sash)], width=2)
    if "spark" in fx or extra == "spark":
        for i in range(8):
            ang = p * 6.28 + i * 0.785
            canvas.create_line(hcx + math.cos(ang) * 30, hcy + math.sin(ang) * 30,
                               hcx + math.cos(ang) * 40, hcy + math.sin(ang) * 40,
                               fill=P["gold"], width=3)
    if "shake" in fx:
        for k in (-1, 1):
            canvas.create_arc(cx + k * 30 - 6, cy - 50, cx + k * 30 + 6, cy - 20,
                              start=90 - k * 90, extent=180, style="arc", outline=glow, width=2)
    if "gesture" in fx:
        for i in range(3):
            canvas.create_text(hands[1][0] + 8 + i * 7, hands[1][1] - 10 - i * 6 - p * 4,
                               text="·", fill=P["gold"], font=("Segoe UI", 14, "bold"))
    if extra == "confetti":
        for i, col in enumerate(CONFETTI + sash):
            ang = p * 6.28 + i * 0.7
            r = 34 + i * 3
            px, py = hcx + math.cos(ang) * r, hcy + 10 + math.sin(ang) * r * 0.6
            canvas.create_rectangle(px, py, px + 4, py + 4, fill=col, outline="")
    elif extra == "zzz":
        for i in range(3):
            canvas.create_text(hcx + 24 + i * 7, hcy - 18 - i * 10 - p * 6, text="z",
                               fill=MOOD_COLORS["rest"], font=("Segoe UI", 9 + i * 3, "bold"))
    elif extra == "sweat":
        canvas.create_oval(hcx + 16, hcy - 10, hcx + 22, hcy - 2, fill="#60a5fa", outline="")
    elif extra in ("speed_lines", "spin_lines"):
        for i in range(4):
            y = cy - 40 + i * 12
            canvas.create_line(cx - 30 - i * 6, y, cx - 56 - i * 6, y, fill=glow, width=2)
    elif extra is not None:
        _prop(canvas, extra, cx - 34, top - 30, p, glow)

    if pose in EXCLAIM:
        _bubble(canvas, hcx + 28, hcy - 34, "!", glow)
    elif pose in WONDER:
        _bubble(canvas, hcx + 28, hcy - 34, "?", glow)
