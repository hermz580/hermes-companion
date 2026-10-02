"""Procedural sprite animator (spec rev1 §12 emotes rendered).

Draws a small round pet on a tkinter Canvas from a pose name + step progress.
No image assets — every pose is parameterized so the pipeline (event -> state
-> chain -> pose) is testable without art.
"""
from __future__ import annotations

import math

BG = "#00FE00"  # chroma key, made transparent by the overlay
BODY = "#14b8a6"
BODY_DARK = "#0f766e"
BELLY = "#99f6e4"
PUPIL = "#0f172a"
ACCENT = "#fbbf24"
CONFETTI = ["#f472b6", "#fbbf24", "#60a5fa", "#a3e635", "#f87171"]


def pose_params(pose: str, progress: float) -> dict:
    """Map pose -> (body, eyes, arms, extra, lean, bob) parameters."""
    p = progress % 1.0
    body, eyes, arms, extra, lean, bob = "normal", "neutral", "down", None, 0.0, 0.0

    if pose in ("idle_bob", "idle"):
        bob = math.sin(p * 6.28) * 2.5
        eyes = "neutral"
    elif pose == "look_at_input":
        eyes = "right"; lean = 0.08
    elif pose == "watch":
        eyes = "right"; bob = math.sin(p * 6.28) * 1.5
    elif pose == "look_at_user":
        eyes = "left"; lean = -0.08
    elif pose == "jump":
        body = "jump"; eyes = "wide"
    elif pose in ("hop", "leap", "bounce", "fly_up", "fly_down"):
        body = "jump"; eyes = "wide"
        if pose == "fly_up":
            extra = "speed_lines" if p < 0.4 else None
        elif pose == "bounce":
            bob = abs(math.sin(p * 12.56)) * 5.0
    elif pose == "attention":
        body = "tall"; eyes = "wide"; arms = "up"
    elif pose == "crack_knuckles":
        arms = "bent"; bob = math.sin(p * 12.56) * 2.0
    elif pose in ("run_to_workspace", "run_to_user", "walk_to_workspace",
                  "tip_to_workspace", "sprint_to_workspace"):
        body = "lean_forward"; eyes = "right" if "workspace" in pose else "left"
        extra = "speed_lines" if p < 0.5 else None
        bob = abs(math.sin(p * 12.56)) * 3.0
    elif pose == "notice":
        eyes = "wide"; lean = 0.06
    elif pose == "dash_to_workspace":
        body = "lean_forward"; eyes = "right"; extra = "speed_lines"
    elif pose == "work":
        arms = "work"; extra = "hologram"; eyes = "down"
    elif pose == "terminal_work":
        arms = "work"; extra = "terminal"; eyes = "down"
        bob = math.sin(p * 10.0) * 1.2
    elif pose == "web_scan":
        eyes = "wide"; extra = "web"; lean = 0.12
        bob = math.sin(p * 6.28) * 1.0
    elif pose == "file_organize":
        arms = "hold"; extra = "files"; eyes = "down"
        bob = math.sin(p * 5.0) * 1.5
    elif pose == "dev_merge":
        arms = "work"; extra = "git"; eyes = "down"
        bob = math.sin(p * 8.0) * 1.8
    elif pose == "media_paint":
        arms = "throw"; extra = "palette"; eyes = "wide"
        bob = math.sin(p * 6.28) * 2.0
    elif pose == "memory_vault":
        arms = "hold"; extra = "vault"; eyes = "neutral"
        bob = math.sin(p * 4.0) * 1.0
    elif pose == "double_jump":
        body = "jump"; eyes = "wide"; extra = "speed_lines" if p > 0.5 else None
        bob = abs(math.sin(p * 12.56)) * 6.0
    elif pose == "spin":
        body = "tall"; eyes = "wide"; extra = "spin_lines"
        bob = abs(math.sin(p * 12.56)) * 3.0
    elif pose == "close_workstation":
        arms = "work"; extra = "hologram_fade" if p < 0.5 else None; eyes = "down"
    elif pose == "celebrate":
        arms = "up"; extra = "confetti"; body = "jump" if p < 0.3 else "normal"
    elif pose == "return_home":
        body = "walk"; bob = abs(math.sin(p * 8.0)) * 2.0
    elif pose == "shock":
        eyes = "xeyes"; arms = "up"; extra = "spark" if p < 0.4 else None
    elif pose == "fall":
        body = "fall"; eyes = "xeyes"; arms = "up"
    elif pose == "recover":
        body = "sit"; arms = "hold"; eyes = "neutral"
    elif pose == "inspect":
        arms = "hold"; extra = "glass"; eyes = "wide"; lean = 0.12
    elif pose == "repair":
        arms = "work"; extra = "wrench"; eyes = "down"; bob = math.sin(p * 6.28) * 1.5
    elif pose == "wake":
        eyes = "wide"; arms = "up"; body = "tall"
    elif pose == "panic":
        eyes = "wide"; extra = "sweat"; body = "jump"; bob = abs(math.sin(p * 12.56)) * 4.0
    elif pose == "wave":
        arms = "wave"; bob = math.sin(p * 6.28) * 1.5
    elif pose == "wait":
        arms = "down"; extra = "tap"; bob = (abs(math.sin(p * 4.0)) * 2.0) if p < 0.5 else 0.0
    elif pose == "nod":
        lean = -0.15 if p < 0.5 else 0.0
    elif pose == "discard":
        arms = "throw"; extra = "discard_item"
    elif pose == "sleep":
        body = "sit"; eyes = "closed"; extra = "zzz"; bob = 0.0
    elif pose == "stretch":
        arms = "stretch"; body = "tall"
    elif pose == "look_around":
        eyes = "left" if p < 0.33 else ("right" if p < 0.66 else "neutral")
    elif pose == "sit":
        body = "sit"; eyes = "neutral"
    elif pose == "play_with_object":
        arms = "bent"; eyes = "down"; bob = math.sin(p * 6.28) * 3.0
    elif pose == "open_portal":
        arms = "up"; extra = "portal"; eyes = "wide"
    elif pose == "orb_exits":
        extra = "orb_exit"; arms = "up"
    elif pose == "orb_returns":
        extra = "orb_return"; arms = "up"
    elif pose == "absorb":
        extra = "absorb"; arms = "hold"
    # v0.3 new emotes
    elif pose == "lean_work":
        arms = "work"; eyes = "down"; lean = 0.10
        bob = math.sin(p * 8.0) * 1.0
    elif pose == "design_draft":
        arms = "hold"; extra = "pen"; eyes = "down"
        bob = math.sin(p * 5.0) * 1.5
    elif pose == "audio_tune":
        arms = "hold"; extra = "notes"; eyes = "closed"
        bob = math.sin(p * 7.0) * 2.0
    elif pose == "read":
        arms = "hold"; extra = "book"; eyes = "down"
        bob = math.sin(p * 4.0) * 1.0
    elif pose == "retry":
        arms = "bent"; extra = "retry"; eyes = "wide"
        bob = math.sin(p * 10.0) * 2.0
    elif pose == "shake_head":
        lean = math.sin(p * 10.0) * 0.12
    elif pose == "shrug":
        arms = "up"; lean = 0.05
    elif pose == "scratch_head":
        arms = "bent"; eyes = "wide"; extra = "sweat" if p < 0.5 else None
        bob = math.sin(p * 8.0) * 1.5
    elif pose == "think":
        arms = "hold"; extra = "think"; eyes = "up"
        bob = math.sin(p * 4.0) * 1.0
    elif pose == "look_up":
        eyes = "up"; lean = -0.10
    elif pose == "look_down":
        eyes = "down"; lean = 0.10
    elif pose == "dance":
        arms = "up"; body = "tall"; eyes = "closed"; extra = "notes"
        bob = abs(math.sin(p * 12.56)) * 3.0
    elif pose == "yawn":
        arms = "stretch"; eyes = "closed"; body = "tall"; extra = "yawn"
        bob = math.sin(p * 3.0) * 1.5
    elif pose == "stretch_lazy":
        arms = "stretch"; body = "tall"; eyes = "closed"
    elif pose == "check_watch":
        arms = "bent"; extra = "watch"; eyes = "down"; lean = 0.10
    elif pose == "excited":
        arms = "up"; body = "tall"; eyes = "wide"; extra = "spark"
        bob = abs(math.sin(p * 14.0)) * 4.0
    elif pose == "smug":
        arms = "down"; eyes = "closed"; lean = -0.04

    # ---- v0.4 emotional band poses (Band 1: Curiosity) --------------
    elif pose == "tilt":
        eyes = "right"; lean = 0.15; bob = math.sin(p * 4) * 1.0
    elif pose == "head_tilt":
        eyes = "right"; lean = 0.20; bob = math.sin(p * 3) * 0.8
    elif pose == "peeking":
        eyes = "right"; lean = 0.12; bob = 1.0
    elif pose == "squint":
        eyes = "down"; lean = -0.05; bob = math.sin(p * 6) * 1.5
    elif pose == "periscope":
        eyes = "up"; lean = 0.25; bob = math.sin(p * 5) * 2.0
    elif pose == "eyebrow_raise":
        eyes = "wide"; lean = 0.0; bob = abs(math.sin(p * 8)) * 1.5
    elif pose == "lip_quirk":
        eyes = "smug"; lean = -0.03; bob = math.sin(p * 4) * 0.5

    # ---- Band 2: Focus ------------------------------------------------
    elif pose == "deep_gaze":
        eyes = "down"; lean = -0.15; bob = math.sin(p * 2) * 0.5
    elif pose == "brow_furrow":
        eyes = "wide"; lean = -0.12; bob = abs(math.sin(p * 3)) * 2.0
    elif pose == "chin_stroke":
        arms = "bent"; eyes = "up"; lean = 0.15; bob = math.sin(p * 3) * 1.0
    elif pose == "finger_tap":
        arms = "bent"; eyes = "down"; bob = abs(math.sin(p * 10)) * 1.5
    elif pose == "screen_scan":
        eyes = "down"; lean = -0.10; bob = math.sin(p * 6) * 1.2
    elif pose == "blink_slow":
        eyes = "closed"; bob = math.sin(p * 1.5) * 2.0
    elif pose == "blink_fast":
        eyes = "closed"; bob = abs(math.sin(p * 20)) * 0.5

    # ---- Band 3: Joy ---------------------------------------------------
    elif pose == "full_bounce":
        body = "jump"; eyes = "wide"; bob = abs(math.sin(p * 14)) * 8.0
        arms = "up"; extra = "confetti"
    elif pose == "spin_joy":
        body = "tall"; eyes = "wide"; arms = "up"
        extra = "spin_lines"; bob = abs(math.sin(p * 12)) * 4.0
    elif pose == "leap_double_joy":
        body = "jump"; eyes = "wide"; bob = abs(math.sin(p * 16)) * 10.0
        extra = "speed_lines" if p > 0.3 else None
    elif pose == "wiggle":
        body = "tall"; eyes = "wide"; arms = "up"
        bob = abs(math.sin(p * 14)) * 3.0
    elif pose == "skip":
        body = "jump"; eyes = "wide"; arms = "wave"
        bob = abs(math.sin(p * 8)) * 5.0

    # ---- Band 4: Frustration ------------------------------------------
    elif pose == "arm_flap":
        eyes = "xeyes"; arms = "up"; bob = abs(math.sin(p * 8)) * 6.0
        extra = "spark"
    elif pose == "desk_bonk":
        body = "sit"; eyes = "xeyes"; bob = abs(math.sin(p * 4)) * 3.0
        extra = "spark" if p < 0.3 else None
    elif pose == "huff":
        eyes = "xeyes"; arms = "down"; body = "sit"
        extra = "sweat" if p < 0.5 else None
    elif pose == "growl":
        eyes = "xeyes"; arms = "bent"; body = "sit"
        bob = math.sin(p * 6) * 3.0
    elif pose == "sit_back":
        body = "sit"; eyes = "xeyes"; arms = "cross"; bob = 0

    # ---- Band 5: Rest --------------------------------------------------
    elif pose == "head_drop":
        eyes = "closed"; body = "sit"; bob = 0; lean = 0.15
    elif pose == "sleepy_nod":
        eyes = "half_closed"; body = "sit"; bob = abs(math.sin(p * 2)) * 1.0
    elif pose == "curl_up":
        body = "sit"; eyes = "closed"; arms = "hold"
        bob = math.sin(p * 2) * 2.0
    elif pose == "chin_on_paws":
        arms = "hold"; eyes = "closed"; body = "sit"
        bob = math.sin(p * 3) * 1.5
    elif pose == "soft_blink":
        eyes = "closed"; bob = math.sin(p * 1.5) * 1.5

    # ---- Band 6: Interaction -------------------------------------------
    elif pose == "wave_gentle":
        arms = "wave"; bob = math.sin(p * 3) * 1.0; lean = 0.0
    elif pose == "wave_excited":
        arms = "wave"; bob = abs(math.sin(p * 8)) * 3.0; lean = 0.05
    elif pose == "wave_salute":
        arms = "wave"; bob = 0; lean = 0.1
    elif pose == "point_left":
        arms = "bent"; eyes = "left"; bob = 0; lean = 0.0
    elif pose == "point_right":
        arms = "bent"; eyes = "right"; bob = 0; lean = 0.0
    elif pose == "beckon":
        arms = "wave"; eyes = "wide"; bob = math.sin(p * 4) * 2.0
    elif pose == "come_here":
        arms = "wave"; eyes = "left"; body = "tall"; bob = math.sin(p * 5) * 2.0

    # ---- 3D movement primitives ----------------------------------------
    elif pose == "drift":
        body = "normal"; eyes = "neutral"; arms = "down"
        bob = math.sin(p * 2) * 1.5; extra = "speed_lines"
    elif pose == "pop":
        body = "jump"; eyes = "wide"; arms = "up"
        bob = abs(math.sin(p * 20)) * 12.0
    elif pose == "orbit":
        body = "tall"; eyes = "wide"; arms = "up"
        extra = "spin_lines"; bob = abs(math.sin(p * 6)) * 3.0
    elif pose == "fold":
        body = "sit"; eyes = "closed"; arms = "hold"
        bob = abs(math.sin(p * 6)) * 2.0; extra = "hologram_fade"
    elif pose == "unfold":
        body = "tall"; eyes = "wide"; arms = "stretch"
        bob = abs(math.sin(p * 6)) * 4.0; extra = "spark"
    elif pose == "shimmer":
        body = "normal"; eyes = "wide"; arms = "down"
        bob = abs(math.sin(p * 16)) * 1.5; extra = "spark"

    # ---- martial / energy vocabulary --------------------------------------
    # v0.5: these three previously fell through to the neutral default, so the
    # rig drew a plain idle body for channel/point/sneak — the moves existed in
    # the chains but never appeared on screen. scripts/render_pose_sheet.py
    # flags any pose that renders as the fallback, and this is that fix.
    elif pose == "sneak":
        body = "lean_forward"; eyes = "left"; arms = "down"
        bob = abs(math.sin(p * 8)) * 1.2
    elif pose == "channel":
        arms = "hold"; eyes = "closed"; extra = "spark"
        bob = math.sin(p * 4) * 1.0
    elif pose == "point":
        arms = "throw"; eyes = "right"; lean = 0.12
        bob = abs(math.sin(p * 6)) * 1.0

    # ---- v0.4 half-closed eyes (for sleepy poses) -----------------
    elif pose == "half_closed":
        eyes = "half_closed"

    return {"body": body, "eyes": eyes, "arms": arms, "extra": extra,
            "lean": lean, "bob": bob}


# ---------------------------------------------------------------------------
# BLEND SYSTEM (v0.4) — smooth transitions between consecutive poses
# ---------------------------------------------------------------------------
def blend_pose(pose_a: str, pose_b: str, blend_progress: float) -> str:
    """Interpolate between two poses for smooth transitions.

    Returns the dominant pose at blend_progress (0..1).
    At 0 = pose_a, at 1 = pose_b. During the blend, a
    blended visual state emerges (e.g., idle_bob -> look_around
    produces a transitional sway).
    """
    if blend_progress <= 0.0:
        return pose_a
    if blend_progress >= 1.0:
        return pose_b

    # Categories of poses that can blend naturally
    # Each tuple is a group of compatible poses; blend_groups maps
    # pose -> group_index for O(1) lookup
    _blend_map = {}
    for _i, _group in enumerate([
        ("idle_bob", "look_around", "look_at_input", "watch",
         "look_at_user", "idle", "idle_bob", "peeking"),
        ("look_around", "look_at_input", "watch", "look_at_user",
         "idle", "idle_bob", "tilt", "head_tilt"),
        ("work", "terminal_work", "web_scan", "file_organize",
         "dev_merge", "media_paint", "memory_vault"),
        ("celebrate", "double_jump", "spin", "excited",
         "full_bounce", "wiggle", "skip"),
        ("shock", "fall", "panic", "xeyes", "arm_flap",
         "huff", "growl", "sit_back"),
        ("wave", "wave_gentle", "wave_excited", "wave_salute",
         "beckon", "come_here", "point_left", "point_right"),
    ]):
        for _pose in _group:
            _blend_map[_pose] = _i

    # If both poses are in the same blend group, return a transitional
    # variant at mid-blend; otherwise just snap at boundaries
    _a_group = _blend_map.get(pose_a)
    _b_group = _blend_map.get(pose_b)
    if _a_group is not None and _a_group == _b_group:
        if 0.3 < blend_progress < 0.7:
            return f"{pose_a}_blend"

    return pose_b if blend_progress > 0.5 else pose_a


def blend_eyes(eyes_a: str, eyes_b: str, blend_progress: float) -> str:
    """Blend eye states between two poses."""
    if blend_progress <= 0.5:
        return eyes_a
    return eyes_b


# ---------------------------------------------------------------------------
# Movement primitives v0.4 (3D moves)
# ---------------------------------------------------------------------------
DRIFT = {"type": "drift", "dx": +320, "dy": -40, "duration_ms": 2000,
          "easing": "easeInOutQuad"}
POP = {"type": "pop", "dx": 0, "dy": -200, "duration_ms": 300, "easing": "bounce"}
ORBIT = {"type": "orbit", "dx": 0, "dy": 0, "duration_ms": 2400,
          "easing": "easeInOutQuad"}
FOLD = {"type": "fold", "dx": 0, "dy": 0, "duration_ms": 1200, "easing": "easeIn"}
UNFOLD = {"type": "unfold", "dx": 0, "dy": 0, "duration_ms": 1200, "easing": "easeOut"}
SHIMMER = {"type": "shimmer", "dx": 0, "dy": 0, "duration_ms": 800, "easing": "easeOutQuad"}



def draw_pet(canvas, pose: str, progress: float = 0.0) -> None:
    canvas.delete("all")
    W, H = 200, 220
    cx, base_y = 100, 150
    prm = pose_params(pose, progress)
    bob = prm["bob"]
    cy = base_y + bob

    # lean (whole-body shear via x offset)
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

    # feet
    foot_y = cy + 34
    canvas.create_oval(cx - 22 + shear, foot_y, cx - 6 + shear, foot_y + 12,
                       fill=BODY_DARK, outline="")
    canvas.create_oval(cx + 6 + shear, foot_y, cx + 22 + shear, foot_y + 12,
                       fill=BODY_DARK, outline="")

    # body (rounded)
    r = 30
    canvas.create_oval(cx - r + shear, cy - r, cx + r + shear, cy + r,
                       fill=BODY, outline="")
    # belly
    canvas.create_oval(cx - 14 + shear, cy - 8, cx + 14 + shear, cy + 24,
                       fill=BELLY, outline="")

    # arms
    ax, ay = cx + shear, cy
    arms = prm["arms"]
    if arms == "down":
        canvas.create_line(ax - 26, ay - 6, ax - 34, ay + 22, width=7, capstyle="round")
        canvas.create_line(ax + 26, ay - 6, ax + 34, ay + 22, width=7, capstyle="round")
    elif arms == "up":
        canvas.create_line(ax - 24, ay - 10, ax - 34, ay - 34, width=7, capstyle="round")
        canvas.create_line(ax + 24, ay - 10, ax + 34, ay - 34, width=7, capstyle="round")
    elif arms == "wave":
        canvas.create_line(ax + 24, ay - 10, ax + 36, ay - 30 - 6 * math.sin(progress * 8.0),
                           width=7, capstyle="round")
        canvas.create_line(ax - 24, ay - 10, ax - 30, ay + 8, width=7, capstyle="round")
    elif arms in ("work", "hold"):
        canvas.create_line(ax - 26, ay + 4, ax - 20, ay + 22, width=7, capstyle="round")
        canvas.create_line(ax + 26, ay + 4, ax + 20, ay + 22, width=7, capstyle="round")
    elif arms == "bent":
        canvas.create_line(ax - 26, ay - 6, ax - 14, ay - 22, width=7, capstyle="round")
        canvas.create_line(ax + 26, ay - 6, ax + 14, ay - 22, width=7, capstyle="round")
    elif arms == "throw":
        canvas.create_line(ax - 22, ay - 8, ax - 40, ay - 26, width=7, capstyle="round")
    elif arms == "stretch":
        canvas.create_line(ax - 26, ay - 8, ax - 40, ay - 44, width=7, capstyle="round")
        canvas.create_line(ax + 26, ay - 8, ax + 40, ay - 44, width=7, capstyle="round")

    # eyes
    eye_y = cy - 10
    ex_l, ex_r = cx - 13 + shear, cx + 13 + shear
    eyes = prm["eyes"]
    if eyes == "closed":
        canvas.create_line(ex_l - 6, eye_y, ex_l + 6, eye_y, width=3, fill=PUPIL)
        canvas.create_line(ex_r - 6, eye_y, ex_r + 6, eye_y, width=3, fill=PUPIL)
    elif eyes == "xeyes":
        for ex in (ex_l, ex_r):
            canvas.create_line(ex - 6, eye_y - 6, ex + 6, eye_y + 6, width=3, fill=PUPIL)
            canvas.create_line(ex - 6, eye_y + 6, ex + 6, eye_y - 6, width=3, fill=PUPIL)
    else:
        dx = {"left": -5, "right": 5, "up": 0, "down": 0}.get(eyes, 0)
        dy = {"up": -4, "down": 4}.get(eyes, 0)
        for ex in (ex_l, ex_r):
            canvas.create_oval(ex - 7, eye_y - 8, ex + 7, eye_y + 8, fill="white", outline="")
            canvas.create_oval(ex - 3 + dx, eye_y - 4 + dy, ex + 3 + dx, eye_y + 4 + dy,
                               fill=PUPIL, outline="")

    # mouth
    if eyes not in ("closed",):
        m = {"wide": (cx - 6 + shear, cy + 12, cx + 6 + shear, cy + 20),
             "xeyes": (cx - 8 + shear, cy + 22, cx + 8 + shear, cy + 22)}
        if eyes == "wide":
            canvas.create_oval(*m["wide"], fill=PUPIL, outline="")
        elif eyes == "xeyes":
            canvas.create_line(*m["xeyes"], width=3, fill=PUPIL)
        else:
            canvas.create_arc(cx - 7 + shear, cy + 8, cx + 7 + shear, cy + 18,
                              start=20, extent=140, style="arc", width=3, outline=PUPIL)

    # extras
    extra = prm["extra"]
    if extra == "hologram":
        hx, hy = cx + shear, cy - 52
        canvas.create_rectangle(hx - 26, hy - 14, hx + 26, hy + 14, fill="#0f172a",
                                outline=ACCENT, width=2)
        for i in range(3):
            canvas.create_line(hx - 18, hy - 4 + i * 8, hx + 8, hy - 4 + i * 8,
                               fill="#22d3ee", width=2)
    elif extra == "hologram_fade":
        hx, hy = cx + shear, cy - 52
        canvas.create_rectangle(hx - 26, hy - 14, hx + 26, hy + 14,
                                outline=ACCENT, width=2)
    elif extra == "glass":
        canvas.create_oval(cx + 30 + shear, cy - 20, cx + 46 + shear, cy - 4,
                           outline=ACCENT, width=2)
        canvas.create_line(cx + 46 + shear, cy - 4, cx + 56 + shear, cy + 8,
                           width=3, fill=ACCENT)
    elif extra == "wrench":
        canvas.create_rectangle(cx + 24 + shear, cy - 16, cx + 34 + shear, cy - 4,
                                fill=ACCENT, outline="")
        canvas.create_line(cx + 29 + shear, cy - 16, cx + 22 + shear, cy - 26,
                           width=4, fill=ACCENT)
    elif extra == "confetti":
        for i, col in enumerate(CONFETTI):
            ang = progress * 6.28 + i
            canvas.create_oval(cx + math.cos(ang) * (34 + i * 6) + shear,
                               cy - 20 + math.sin(ang) * (20 + i * 4),
                               cx + math.cos(ang) * (34 + i * 6) + 5 + shear,
                               cy - 20 + math.sin(ang) * (20 + i * 4) + 5,
                               fill=col, outline="")
    elif extra == "sweat":
        canvas.create_oval(cx + 26 + shear, cy - 24, cx + 34 + shear, cy - 14,
                           fill="#60a5fa", outline="")
        canvas.create_oval(cx + 18 + shear, cy - 16, cx + 24 + shear, cy - 8,
                           fill="#60a5fa", outline="")
    elif extra == "zzz":
        for i, off in enumerate((0, -12, -24)):
            canvas.create_text(cx + 26 + shear + i * 4, cy - 34 + off,
                               text="z", fill="#93c5fd", font=("Segoe UI", 12 + i * 3))
    elif extra == "spark":
        for i in range(6):
            ang = progress * 6.28 + i * 3.14159 / 3
            canvas.create_line(cx + math.cos(ang) * 30 + shear, cy - 10 + math.sin(ang) * 30,
                               cx + math.cos(ang) * 40 + shear, cy - 10 + math.sin(ang) * 40,
                               fill=ACCENT, width=3)
    elif extra == "speed_lines":
        for i in range(3):
            y = cy - 14 + i * 14
            canvas.create_line(cx - 44 - i * 12 + shear, y, cx - 20 + shear, y,
                               fill="#5eead4", width=3)
    elif extra == "terminal":
        tx, ty = cx + shear, cy - 52
        canvas.create_rectangle(tx - 26, ty - 14, tx + 26, ty + 14, fill="#0f172a",
                                outline="#22d3ee", width=2)
        for i in range(3):
            canvas.create_line(tx - 20, ty - 6 + i * 6, tx + 6, ty - 6 + i * 6,
                               fill="#5eead4", width=2)
        canvas.create_text(tx - 16, ty - 8, text=">_", fill="#fbbf24",
                           font=("Consolas", 9, "bold"))
    elif extra == "web":
        wx, wy = cx + 30 + shear, cy - 40
        canvas.create_oval(wx - 14, wy - 14, wx + 14, wy + 14, outline="#22d3ee", width=2)
        canvas.create_line(wx - 10, wy, wx + 10, wy, fill="#22d3ee", width=1)
        canvas.create_line(wx, wy - 10, wx, wy + 10, fill="#22d3ee", width=1)
        canvas.create_arc(wx - 14, wy - 14, wx + 14, wy + 14, start=0, extent=90,
                          style="arc", outline="#f472b6", width=1)
    elif extra == "files":
        for i, off in enumerate((0, 7, 14)):
            canvas.create_rectangle(cx - 20 + shear + i * 5, cy - 34 + off,
                                    cx + 8 + shear + i * 5, cy - 10 + off,
                                    fill="#334155", outline="#94a3b8", width=1)
    elif extra == "git":
        gx, gy = cx + 28 + shear, cy - 40
        canvas.create_line(gx - 8, gy - 10, gx - 8, gy + 10, fill="#f472b6", width=2)
        canvas.create_line(gx + 8, gy - 10, gx + 8, gy + 10, fill="#f472b6", width=2)
        canvas.create_line(gx - 8, gy - 4, gx + 8, gy - 4, fill="#22d3ee", width=2)
        canvas.create_oval(gx - 10, gy - 13, gx - 6, gy - 9, fill="#fbbf24", outline="")
        canvas.create_oval(gx + 6, gy + 7, gx + 10, gy + 11, fill="#fbbf24", outline="")
    elif extra == "palette":
        for i, col in enumerate(CONFETTI[:5]):
            ang = progress * 3.14 + i * 1.26
            canvas.create_oval(cx + 24 + shear + math.cos(ang) * 8,
                               cy - 34 + math.sin(ang) * 8,
                               cx + 32 + shear + math.cos(ang) * 8,
                               cy - 26 + math.sin(ang) * 8, fill=col, outline="")
        canvas.create_oval(cx + 26 + shear, cy - 40, cx + 38 + shear, cy - 28,
                           fill="#f8fafc", outline="#0f172a", width=1)
    elif extra == "vault":
        vx, vy = cx + 28 + shear, cy - 30
        canvas.create_rectangle(vx - 12, vy - 16, vx + 12, vy + 4, fill="#0f766e",
                                outline="#99f6e4", width=2)
        canvas.create_oval(vx - 2, vy - 8, vx + 4, vy - 2, fill="#fbbf24", outline="")
    elif extra == "spin_lines":
        for i in range(4):
            ang = progress * 12.56 + i * 3.14159 / 2
            canvas.create_line(cx + math.cos(ang) * 34 + shear, cy - 8 + math.sin(ang) * 20,
                               cx + math.cos(ang) * 44 + shear, cy - 8 + math.sin(ang) * 26,
                               fill="#5eead4", width=2)
    elif extra == "portal":
        canvas.create_oval(cx + 26 + shear, cy - 46, cx + 52 + shear, cy - 20,
                           outline=ACCENT, width=3)
        canvas.create_oval(cx + 30 + shear, cy - 42, cx + 48 + shear, cy - 24,
                           outline="#f472b6", width=2)
    elif extra in ("orb_exit", "orb_return"):
        t = progress * 40
        oy = cy - 46 - t
        canvas.create_oval(cx + 32 + shear, oy, cx + 44 + shear, oy + 12,
                           fill=ACCENT, outline="")
    elif extra == "absorb":
        canvas.create_oval(cx + 8 + shear, cy - 30, cx + 20 + shear, cy - 18,
                           fill=ACCENT, outline="")
    elif extra == "tap":
        canvas.create_line(cx + 24 + shear, cy + 26, cx + 30 + shear, cy + 26,
                           width=4, fill=BODY_DARK)
    elif extra == "discard_item":
        t = progress * 1.4
        canvas.create_rectangle(cx - 44 + shear, cy - 20 - t * 10, cx - 36 + shear,
                                cy - 12 - t * 10, fill="#94a3b8", outline="")
    elif extra == "pen":
        # design_draft: a pen sketching a curve.
        canvas.create_line(cx + 20 + shear, cy - 30, cx + 44 + shear, cy - 26,
                           width=3, fill=ACCENT)
        canvas.create_line(cx + 44 + shear, cy - 26, cx + 30 + shear, cy - 10,
                           width=3, fill="#22d3ee")
        canvas.create_line(cx + 30 + shear, cy - 10, cx + 42 + shear, cy - 4,
                           width=3, fill="#f472b6")
    elif extra == "notes":
        # audio_tune / dance: two floating eighth notes.
        for i, (dx, dy) in enumerate(((24, -40), (38, -30))):
            nx, ny = cx + dx + shear, cy + dy
            canvas.create_text(nx, ny, text="♪", fill=ACCENT,
                               font=("Segoe UI Symbol", 16))
    elif extra == "book":
        # read: an open book.
        bx, by = cx + 26 + shear, cy - 28
        canvas.create_arc(bx - 12, by - 14, bx, by + 6, start=270, extent=180,
                          style="chord", fill="#f8fafc", outline="#0f172a", width=1)
        canvas.create_arc(bx, by - 14, bx + 12, by + 6, start=270, extent=180,
                          style="chord", fill="#f1f5f9", outline="#0f172a", width=1)
        canvas.create_line(bx, by - 12, bx, by + 2, fill="#0f172a", width=1)
    elif extra == "retry":
        # retry: circular arrow.
        rx, ry = cx + 30 + shear, cy - 26
        canvas.create_arc(rx - 8, ry - 8, rx + 8, ry + 8, start=45, extent=290,
                          style="arc", outline="#22d3ee", width=2)
        canvas.create_line(rx + 6, ry - 6, rx + 9, ry + 2, fill="#22d3ee", width=2)
        canvas.create_line(rx + 6, ry - 6, rx - 1, ry - 7, fill="#22d3ee", width=2)
    elif extra == "think":
        # think: floating thought bubble + dots.
        for i, (dx, dy, r) in enumerate(((20, -46, 2), (28, -54, 3), (38, -62, 4))):
            canvas.create_oval(cx + dx + shear - r, cy + dy - r,
                               cx + dx + shear + r, cy + dy + r, fill="#cbd5e1", outline="")
        canvas.create_oval(cx + 40 + shear, cy - 78, cx + 64 + shear, cy - 54,
                           fill="#f8fafc", outline="#94a3b8", width=1)
    elif extra == "yawn":
        # yawn: open mouth arc + spark.
        canvas.create_arc(cx - 8 + shear, cy + 6, cx + 8 + shear, cy + 22,
                          start=0, extent=180, style="chord", fill=PUPIL, outline="")
    elif extra == "watch":
        # check_watch: wristwatch on the raised arm.
        canvas.create_oval(cx + 18 + shear, cy - 14, cx + 30 + shear, cy - 2,
                           fill="#f8fafc", outline="#0f172a", width=1)
        canvas.create_line(cx + 24 + shear, cy - 6, cx + 24 + shear, cy - 10, width=1, fill="#0f172a")
        canvas.create_line(cx + 24 + shear, cy - 6, cx + 26 + shear, cy - 4, width=1, fill="#0f172a")
    elif extra == "blink":
        canvas.create_line(cx - 12 + shear, eye_y, cx + 12 + shear, eye_y,
                           width=3, fill=PUPIL)


# ---------------------------------------------------------------------------
# Standalone prop renderer (v0.3) — draws ONE named prop/effect at (cx, cy)
# scaled by `s`. The live PetdexOverlay uses this to overlay props on top of
# the spritesheet, so the visible pet shows confetti, a terminal, a portal,
# sweat, Zzz etc. — not just a row swap. Mirrors the extras above.
# ---------------------------------------------------------------------------
def draw_extra(canvas, extra: str, progress: float = 0.0,
               cx: float = 100, cy: float = 150, s: float = 1.0) -> None:
    if extra is None:
        return
    p = progress % 1.0
    c = lambda v: v * s  # noqa: E731 — scale a coordinate

    if extra == "hologram":
        hx, hy = cx, cy - 52 * s
        canvas.create_rectangle(c(hx - 26), c(hy - 14), c(hx + 26), c(hy + 14),
                                fill="#0f172a", outline=ACCENT, width=max(1, round(2 * s)))
        for i in range(3):
            canvas.create_line(c(hx - 18), c(hy - 4 + i * 8), c(hx + 8), c(hy - 4 + i * 8),
                               fill="#22d3ee", width=max(1, round(2 * s)))
    elif extra == "hologram_fade":
        hx, hy = cx, cy - 52 * s
        canvas.create_rectangle(c(hx - 26), c(hy - 14), c(hx + 26), c(hy + 14),
                                outline=ACCENT, width=max(1, round(2 * s)))
    elif extra == "glass":
        canvas.create_oval(c(cx + 30), c(cy - 20), c(cx + 46), c(cy - 4),
                           outline=ACCENT, width=max(1, round(2 * s)))
        canvas.create_line(c(cx + 46), c(cy - 4), c(cx + 56), c(cy + 8),
                           width=max(1, round(3 * s)), fill=ACCENT)
    elif extra == "wrench":
        canvas.create_rectangle(c(cx + 24), c(cy - 16), c(cx + 34), c(cy - 4),
                                fill=ACCENT, outline="")
        canvas.create_line(c(cx + 29), c(cy - 16), c(cx + 22), c(cy - 26),
                           width=max(1, round(4 * s)), fill=ACCENT)
    elif extra == "confetti":
        for i, col in enumerate(CONFETTI):
            ang = p * 6.28 + i
            canvas.create_oval(c(cx + math.cos(ang) * (34 + i * 6)),
                               c(cy - 20 + math.sin(ang) * (20 + i * 4)),
                               c(cx + math.cos(ang) * (34 + i * 6) + 5),
                               c(cy - 20 + math.sin(ang) * (20 + i * 4) + 5),
                               fill=col, outline="")
    elif extra == "sweat":
        canvas.create_oval(c(cx + 26), c(cy - 24), c(cx + 34), c(cy - 14), fill="#60a5fa", outline="")
        canvas.create_oval(c(cx + 18), c(cy - 16), c(cx + 24), c(cy - 8), fill="#60a5fa", outline="")
    elif extra == "zzz":
        for i, off in enumerate((0, -12, -24)):
            canvas.create_text(c(cx + 26 + i * 4), c(cy - 34 + off),
                               text="z", fill="#93c5fd", font=("Segoe UI", max(8, round((12 + i * 3) * s))))
    elif extra == "spark":
        for i in range(6):
            ang = p * 6.28 + i * 3.14159 / 3
            canvas.create_line(c(cx + math.cos(ang) * 30), c(cy - 10 + math.sin(ang) * 30),
                               c(cx + math.cos(ang) * 40), c(cy - 10 + math.sin(ang) * 40),
                               fill=ACCENT, width=max(1, round(3 * s)))
    elif extra == "speed_lines":
        for i in range(3):
            y = cy - 14 + i * 14
            canvas.create_line(c(cx - 44 - i * 12), c(y), c(cx - 20), c(y),
                               fill="#5eead4", width=max(1, round(3 * s)))
    elif extra == "terminal":
        tx, ty = cx, cy - 52 * s
        canvas.create_rectangle(c(tx - 26), c(ty - 14), c(tx + 26), c(ty + 14),
                                fill="#0f172a", outline="#22d3ee", width=max(1, round(2 * s)))
        for i in range(3):
            canvas.create_line(c(tx - 20), c(ty - 6 + i * 6), c(tx + 6), c(ty - 6 + i * 6),
                               fill="#5eead4", width=max(1, round(2 * s)))
        canvas.create_text(c(tx - 16), c(ty - 8), text=">_", fill="#fbbf24",
                           font=("Consolas", max(7, round(9 * s)), "bold"))
    elif extra == "web":
        wx, wy = cx + 30 * s, cy - 40 * s
        canvas.create_oval(c(wx - 14), c(wy - 14), c(wx + 14), c(wy + 14),
                           outline="#22d3ee", width=max(1, round(2 * s)))
        canvas.create_line(c(wx - 10), c(wy), c(wx + 10), c(wy), fill="#22d3ee", width=max(1, round(s)))
        canvas.create_line(c(wx), c(wy - 10), c(wx), c(wy + 10), fill="#22d3ee", width=max(1, round(s)))
        canvas.create_arc(c(wx - 14), c(wy - 14), c(wx + 14), c(wy + 14), start=0, extent=90,
                          style="arc", outline="#f472b6", width=max(1, round(s)))
    elif extra == "files":
        for i, off in enumerate((0, 7, 14)):
            canvas.create_rectangle(c(cx - 20 + i * 5), c(cy - 34 + off),
                                    c(cx + 8 + i * 5), c(cy - 10 + off),
                                    fill="#334155", outline="#94a3b8", width=max(1, round(s)))
    elif extra == "git":
        gx, gy = cx + 28 * s, cy - 40 * s
        canvas.create_line(c(gx - 8), c(gy - 10), c(gx - 8), c(gy + 10), fill="#f472b6", width=max(1, round(2 * s)))
        canvas.create_line(c(gx + 8), c(gy - 10), c(gx + 8), c(gy + 10), fill="#f472b6", width=max(1, round(2 * s)))
        canvas.create_line(c(gx - 8), c(gy - 4), c(gx + 8), c(gy - 4), fill="#22d3ee", width=max(1, round(2 * s)))
        canvas.create_oval(c(gx - 10), c(gy - 13), c(gx - 6), c(gy - 9), fill="#fbbf24", outline="")
        canvas.create_oval(c(gx + 6), c(gy + 7), c(gx + 10), c(gy + 11), fill="#fbbf24", outline="")
    elif extra == "palette":
        for i, col in enumerate(CONFETTI[:5]):
            ang = p * 3.14 + i * 1.26
            canvas.create_oval(c(cx + 24 + math.cos(ang) * 8), c(cy - 34 + math.sin(ang) * 8),
                               c(cx + 32 + math.cos(ang) * 8), c(cy - 26 + math.sin(ang) * 8),
                               fill=col, outline="")
        canvas.create_oval(c(cx + 26), c(cy - 40), c(cx + 38), c(cy - 28),
                           fill="#f8fafc", outline="#0f172a", width=max(1, round(s)))
    elif extra == "vault":
        vx, vy = cx + 28 * s, cy - 30 * s
        canvas.create_rectangle(c(vx - 12), c(vy - 16), c(vx + 12), c(vy + 4),
                                fill="#0f766e", outline="#99f6e4", width=max(1, round(2 * s)))
        canvas.create_oval(c(vx - 2), c(vy - 8), c(vx + 4), c(vy - 2), fill="#fbbf24", outline="")
    elif extra == "spin_lines":
        for i in range(4):
            ang = p * 12.56 + i * 3.14159 / 2
            canvas.create_line(c(cx + math.cos(ang) * 34), c(cy - 8 + math.sin(ang) * 20),
                               c(cx + math.cos(ang) * 44), c(cy - 8 + math.sin(ang) * 26),
                               fill="#5eead4", width=max(1, round(2 * s)))
    elif extra == "portal":
        canvas.create_oval(c(cx + 26), c(cy - 46), c(cx + 52), c(cy - 20),
                           outline=ACCENT, width=max(1, round(3 * s)))
        canvas.create_oval(c(cx + 30), c(cy - 42), c(cx + 48), c(cy - 24),
                           outline="#f472b6", width=max(1, round(2 * s)))
    elif extra in ("orb_exit", "orb_return"):
        t = p * 40
        oy = cy - 46 * s - t
        canvas.create_oval(c(cx + 32), c(oy), c(cx + 44), c(oy + 12), fill=ACCENT, outline="")
    elif extra == "absorb":
        canvas.create_oval(c(cx + 8), c(cy - 30), c(cx + 20), c(cy - 18), fill=ACCENT, outline="")
    elif extra == "tap":
        canvas.create_line(c(cx + 24), c(cy + 26), c(cx + 30), c(cy + 26),
                           width=max(1, round(4 * s)), fill=BODY_DARK)
    elif extra == "discard_item":
        t = p * 1.4
        canvas.create_rectangle(c(cx - 44), c(cy - 20 - t * 10), c(cx - 36), c(cy - 12 - t * 10),
                                fill="#94a3b8", outline="")
    elif extra == "pen":
        canvas.create_line(c(cx + 20), c(cy - 30), c(cx + 44), c(cy - 26),
                           width=max(1, round(3 * s)), fill=ACCENT)
        canvas.create_line(c(cx + 44), c(cy - 26), c(cx + 30), c(cy - 10),
                           width=max(1, round(3 * s)), fill="#22d3ee")
        canvas.create_line(c(cx + 30), c(cy - 10), c(cx + 42), c(cy - 4),
                           width=max(1, round(3 * s)), fill="#f472b6")
    elif extra == "notes":
        for i, (dx, dy) in enumerate(((24, -40), (38, -30))):
            nx, ny = cx + dx * s, cy + dy * s
            canvas.create_text(c(nx), c(ny), text="♪", fill=ACCENT,
                               font=("Segoe UI Symbol", max(9, round(16 * s))))
    elif extra == "book":
        bx, by = cx + 26 * s, cy - 28 * s
        canvas.create_arc(c(bx - 12), c(by - 14), c(bx), c(by + 6), start=270, extent=180,
                          style="chord", fill="#f8fafc", outline="#0f172a", width=max(1, round(s)))
        canvas.create_arc(c(bx), c(by - 14), c(bx + 12), c(by + 6), start=270, extent=180,
                          style="chord", fill="#f1f5f9", outline="#0f172a", width=max(1, round(s)))
        canvas.create_line(c(bx), c(by - 12), c(bx), c(by + 2), fill="#0f172a", width=max(1, round(s)))
    elif extra == "retry":
        rx, ry = cx + 30 * s, cy - 26 * s
        canvas.create_arc(c(rx - 8), c(ry - 8), c(rx + 8), c(ry + 8), start=45, extent=290,
                          style="arc", outline="#22d3ee", width=max(1, round(2 * s)))
        canvas.create_line(c(rx + 6), c(ry - 6), c(rx + 9), c(ry + 2), fill="#22d3ee", width=max(1, round(2 * s)))
        canvas.create_line(c(rx + 6), c(ry - 6), c(rx - 1), c(ry - 7), fill="#22d3ee", width=max(1, round(2 * s)))
    elif extra == "think":
        for i, (dx, dy, r) in enumerate(((20, -46, 2), (28, -54, 3), (38, -62, 4))):
            canvas.create_oval(c(cx + dx - r), c(cy + dy - r), c(cx + dx + r), c(cy + dy + r),
                               fill="#cbd5e1", outline="")
        canvas.create_oval(c(cx + 40), c(cy - 78), c(cx + 64), c(cy - 54),
                           fill="#f8fafc", outline="#94a3b8", width=max(1, round(s)))
    elif extra == "yawn":
        canvas.create_arc(c(cx - 8), c(cy + 6), c(cx + 8), c(cy + 22),
                          start=0, extent=180, style="chord", fill=PUPIL, outline="")
    elif extra == "watch":
        canvas.create_oval(c(cx + 18), c(cy - 14), c(cx + 30), c(cy - 2),
                           fill="#f8fafc", outline="#0f172a", width=max(1, round(s)))
        canvas.create_line(c(cx + 24), c(cy - 6), c(cx + 24), c(cy - 10), width=max(1, round(s)), fill="#0f172a")
        canvas.create_line(c(cx + 24), c(cy - 6), c(cx + 26), c(cy - 4), width=max(1, round(s)), fill="#0f172a")
