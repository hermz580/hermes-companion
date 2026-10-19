"""Petdex/Codex spritesheet overlay for The Alpha And.

Uses the user's existing Hermes pet assets (no replacement pet). Supports the
current 8-column x 9-row Codex atlas and maps semantic work events to the
existing rows: idle, run-right/left, wave, jump, failed, waiting, review.

v0.2 changes (diversity + grab):
- `play_chain(chain)` renders a real engine chain (poses + moves from the
  behavior engine) instead of the coarse `semantic_event` mapping, so the
  visible pet finally shows the engine's full movement vocabulary.
- Tool CATEGORY flavors the work row and travel distance (the engine already
  emits per-category moves; we map pose -> atlas row here).
- Optional `enable_grab`: the sprite becomes a real hitbox you can click and
  drag. Spec §25 keeps pointer interaction default-OFF — grab is opt-in.
  While enabled, WS_EX_TRANSPARENT is toggled per-tick so the pet is
  clickable only where the sprite is and never blocks the UI under it (§33).
"""
from __future__ import annotations

import ctypes
import hashlib
import math
import os
import time
import tkinter as tk
from collections import deque
from dataclasses import dataclass
from pathlib import Path
from typing import Callable

from hermes_companion.renderer.intent_bridge import CompanionIntentEmitter

from PIL import Image, ImageTk

BG = "#00FE00"
GWL_EXSTYLE = -20
WS_EX_TRANSPARENT = 0x00000020
from hermes_companion.renderer.pet_rows import DEFAULT_ROW_ORDER, load_row_order

WS_EX_TOOLWINDOW = 0x00000080

FRAME_W = 192
FRAME_H = 208
# The row order is per-pet data (renderer/pet_rows.py): a v2 sheet draws a
# different animation on the same physical row, so a sidecar rowmap.json - or
# this v1 default - decides which animation a semantic row name means.
STATE_ROWS = list(DEFAULT_ROW_ORDER)

# Engine pose -> atlas row. Movement poses carry a move dict (dx/dy/duration);
# static poses map to the row that best reads as that behavior on the 9-row
# atlas. Category work poses deliberately land on different rows so a
# terminal build (waiting, hunched) reads differently from a web scan
# (review, leaning).
POSE_ROW: dict[str, str] = {
    # movement
    "dash_to_workspace": "running",
    "run_to_workspace": "running-right",
    "walk_to_workspace": "running-right",
    "tip_to_workspace": "running-right",
    "sprint_to_workspace": "running",
    "run_to_user": "running-left",
    "return_home": "running-left",
    "hop": "jumping",
    "leap": "jumping",
    "bounce": "jumping",
    "fly_up": "jumping",
    "fly_down": "jumping",
    # martial / energy vocabulary
    "sneak": "running",
    "channel": "waving",
    "point": "review",
    # attention
    "notice": "waiting",
    "look_at_input": "review",
    "watch": "review",
    "look_at_user": "idle",
    "jump": "jumping",
    "double_jump": "jumping",
    "attention": "waving",
    "crack_knuckles": "review",
    "wake": "waving",
    "stretch": "waving",
    "stretch_lazy": "waving",
    "excited": "jumping",
    "smug": "idle",
    "check_watch": "review",
    "tilt": "idle",
    "head_tilt": "idle",
    "peeking": "review",
    "squint": "review",
    "eyebrow_raise": "idle",
    "head_drop": "idle",
    # work (category-flavored)
    "work": "waiting",
    "lean_work": "waiting",
    "terminal_work": "waiting",
    "web_scan": "review",
    "file_organize": "review",
    "dev_merge": "waiting",
    "media_paint": "review",
    "memory_vault": "waiting",
    "design_draft": "review",
    "audio_tune": "waiting",
    "read": "review",
    "open_portal": "review",
    "orb_exits": "running",
    "orb_returns": "jumping",
    "absorb": "review",
    # completion
    "close_workstation": "idle",
    "celebrate": "jumping",
    "spin": "waving",
    "full_bounce": "jumping",
    "leap_double_joy": "jumping",
    "spin_joy": "waving",
    "nod": "idle",
    "discard": "review",
    # failure / recovery
    "shock": "failed",
    "fall": "failed",
    "recover": "waiting",
    "inspect": "review",
    "repair": "review",
    "retry": "waiting",
    "shake_head": "idle",
    "shrug": "idle",
    "scratch_head": "failed",
    "arm_flap": "failed",
    "sit_back": "failed",
    "huff": "failed",
    "think": "review",
    "look_up": "idle",
    "look_down": "idle",
    # waiting / approval
    "panic": "running-left",
    "wave": "waving",
    "wait": "waiting",
    "dance": "waving",
    "yawn": "idle",
    # idle
    "idle_bob": "idle",
    "look_around": "idle",
    "sit": "idle",
    "play_with_object": "idle",
    "sleep": "waiting",
}

# v0.3: visible props drawn OVER the sprite per pose (the live pet shows
# confetti, a terminal, a portal, sweat, Zzz — not just a spritesheet swap).
POSE_PROP: dict[str, str] = {
    "terminal_work": "terminal",
    "web_scan": "web",
    "file_organize": "files",
    "dev_merge": "git",
    "media_paint": "palette",
    "memory_vault": "vault",
    "design_draft": "pen",
    "audio_tune": "notes",
    "read": "book",
    "retry": "retry",
    "think": "think",
    "check_watch": "watch",
    "yawn": "yawn",
    "dance": "notes",
    "panic": "sweat",
    "scratch_head": "sweat",
    "inspect": "glass",
    "repair": "wrench",
    "shock": "spark",
    "sleep": "zzz",
    "open_portal": "portal",
    "orb_exits": "orb_exit",
    "orb_returns": "orb_return",
    "absorb": "absorb",
    "celebrate": "confetti",
    "excited": "spark",
    "discard": "discard_item",
    "lean_work": "hologram",
    "work": "hologram",
}

# Default duration when an engine step carries none (fallback).
DEFAULT_MS = 1000


SM_XVIRTUALSCREEN = 76
SM_YVIRTUALSCREEN = 77
SM_CXVIRTUALSCREEN = 78
SM_CYVIRTUALSCREEN = 79


def _virtual_screen_bounds() -> tuple[int, int, int, int]:
    """Return the Windows virtual desktop bounds.

    This is the full multi-monitor rectangle, not just the primary display.
    It lets the pet move and be placed on any attached screen.
    """
    try:
        user32 = ctypes.windll.user32
        left = int(user32.GetSystemMetrics(SM_XVIRTUALSCREEN))
        top = int(user32.GetSystemMetrics(SM_YVIRTUALSCREEN))
        width = int(user32.GetSystemMetrics(SM_CXVIRTUALSCREEN))
        height = int(user32.GetSystemMetrics(SM_CYVIRTUALSCREEN))
        if width > 0 and height > 0:
            return left, top, width, height
    except Exception:
        pass
    # Fallback: primary screen only.
    return 0, 0, 0, 0


def _monitors() -> list[tuple[int, int, int, int]]:
    """Enumerate attached display rectangles in desktop coordinates
    (left, top, right, bottom). Same proven pattern as cli/emit.py."""
    try:
        import ctypes.wintypes as wt

        user32 = ctypes.windll.user32
        monitors: list[tuple[int, int, int, int]] = []

        MonitorEnumProc = ctypes.WINFUNCTYPE(
            ctypes.c_int, wt.HMONITOR, wt.HDC,
            ctypes.POINTER(wt.RECT), wt.LPARAM)

        def callback(_hmon, _hdc, rect_ptr, _lparam):
            rect = rect_ptr.contents
            monitors.append((rect.left, rect.top, rect.right, rect.bottom))
            return 1

        enum_proc = MonitorEnumProc(callback)
        user32.EnumDisplayMonitors(0, 0, enum_proc, 0)
        if monitors:
            return monitors
    except Exception:
        pass
    return []


@dataclass(frozen=True)
class MotionRecipe:
    """Deterministic micro-animation for one semantic pose.

    This does not replace truthful movement paths or props. It only varies frame
    timing, tiny in-window bob/sway, and a small accent so repeated uses of the
    same atlas row do not all read as the same move.
    """
    frame_ms: int
    phase: int
    direction: int
    ping_pong: bool
    bob_px: int
    sway_px: int
    effect: str | None = None


def motion_recipe(pose: str, category: str = "", ordinal: int = 0) -> MotionRecipe:
    """Create stable visual variation from pose/category/order.

    Same event chain + category produces the same recipe on relay peers.
    """
    key = f"v3|{pose}|{category.lower()}|{ordinal}".encode("utf-8")
    digest = hashlib.blake2s(key, digest_size=8).digest()
    n = int.from_bytes(digest, "big")
    category_effect = {
        "terminal": "terminal",
        "web": "scan",
        "file": "files",
        "development": "git",
        "dev": "git",
        "media": "spark",
        "memory": "orb",
    }
    pose_effect = {
        "open_portal": "portal",
        "orb_exits": "orb",
        "orb_returns": "orb",
        "celebrate": "spark",
        "excited": "spark",
        "spin": "spark",
        "spin_joy": "spark",
        "repair": "spark",
        "retry": "spark",
        "panic": "sweat",
        "sleep": "zzz",
    }
    authored_order = pose in {"jump", "fall", "recover", "run_to_workspace"}
    return MotionRecipe(
        frame_ms=88 + n % 54,
        phase=(n >> 8) % 16,
        direction=1 if authored_order else (-1 if (n >> 13) & 1 else 1),
        ping_pong=False if authored_order else bool((n >> 14) & 1),
        bob_px=1 + (n >> 15) % 4,
        sway_px=(n >> 18) % 4,
        effect=category_effect.get(category.lower()) or pose_effect.get(pose),
    )


@dataclass(frozen=True)
class Beat:
    row: str
    duration_ms: int
    move_dx: int = 0
    move_dy: int = 0
    move_type: str = ""          # movement/paths.py: dash|run|walk|creep|sprint|
                                 # hop|leap|tip|pounce|bounce|fly|orbit|figure8|
                                 # zigzag|hover|overshoot|anticipate
    prop: str | None = None      # visible prop drawn over the sprite
    ease: str = "easeOutCubic"
    recipe: MotionRecipe | None = None


def usable_frame_count(image: Image.Image, frame_w: int = FRAME_W,
                       frame_h: int = FRAME_H, cols: int | None = None) -> int:
    """Count the leading frames of ONE row that actually contain art.

    Sheets are not uniformly filled. The Alpha's idle row holds 6 real frames
    while its walk rows hold 8; aeon-loom's idle row holds 7 of 8. A fixed
    column count therefore either discards real frames or animates into
    transparent cells, which reads as the pet flickering out of existence.
    """
    total = cols if cols is not None else image.width // frame_w
    count = 0
    for col in range(total):
        cell = image.crop((col * frame_w, 0, (col + 1) * frame_w, frame_h))
        if cell.getchannel("A").getextrema()[1] == 0:
            break
        count += 1
    return count


class PetdexOverlay:
    def __init__(self, spritesheet: str, scale: float = 0.85,
                 home_x: int | None = None, home_y: int | None = None,
                 enable_grab: bool = False,
                 on_grab: Callable[[int, int], None] | None = None,
                 intent_emitter: CompanionIntentEmitter | None = None) -> None:
        self.root = tk.Tk()
        self.root.overrideredirect(True)
        self.root.wm_attributes("-topmost", True)
        self.root.wm_attributes("-transparentcolor", BG)
        self.root.configure(bg=BG)

        self.scale = scale
        self.draw_w = max(1, round(FRAME_W * scale))
        self.draw_h = max(1, round(FRAME_H * scale))
        # Room for sprite art plus recipe-driven micro motion/effects.
        self.pad = 20
        self.w = self.draw_w + self.pad * 2
        self.h = self.draw_h + self.pad * 2
        self.canvas = tk.Canvas(self.root, width=self.w, height=self.h, bg=BG,
                                highlightthickness=0, bd=0)
        self.canvas.pack()

        left, top, sw, sh = _virtual_screen_bounds()
        if sw > 0 and sh > 0:
            default_x = left + (sw - self.w) // 2
            default_y = top + sh - self.h - 58
        else:
            default_x = (self.root.winfo_screenwidth() - self.w) // 2
            default_y = self.root.winfo_screenheight() - self.h - 58
        self.home_x = default_x if home_x is None else home_x
        self.home_y = default_y if home_y is None else home_y
        self.x = self.home_x
        self.y = self.home_y
        self._place(self.x, self.y)

        image = Image.open(spritesheet).convert("RGBA")
        cols = image.width // FRAME_W
        rows = image.height // FRAME_H
        if cols < 6 or rows < 9:
            raise ValueError(f"unsupported pet atlas {image.size}: expected >=6x9 cells")
        self.frames: dict[str, list[ImageTk.PhotoImage]] = {}
        # Names come from this pet's own map, so a pose lands on the row that
        # actually draws it on THIS sheet.
        self.row_order = load_row_order(spritesheet)
        for row_i, row_name in enumerate(self.row_order):
            if row_i >= rows:
                break
            row_frames = []
            strip = image.crop((0, row_i * FRAME_H, image.width, (row_i + 1) * FRAME_H))
            for col in range(usable_frame_count(strip, cols=cols)):
                crop = image.crop((col * FRAME_W, row_i * FRAME_H,
                                   (col + 1) * FRAME_W, (row_i + 1) * FRAME_H))
                crop = crop.resize((self.draw_w, self.draw_h), Image.Resampling.NEAREST)
                row_frames.append(ImageTk.PhotoImage(crop, master=self.root))
            if not row_frames:
                # An entirely empty row must still yield a frame, because the
                # renderer indexes row_frames[0] and never expects an empty list.
                blank = Image.new("RGBA", (self.draw_w, self.draw_h), (0, 0, 0, 0))
                row_frames = [ImageTk.PhotoImage(blank, master=self.root)]
            self.frames[row_name] = row_frames

        self.row = "idle"
        self.frame_i = 0
        self._image_item = self.canvas.create_image(
            self.pad, self.pad, anchor="nw", image=self.frames["idle"][0])
        self._queue: deque[Beat] = deque()
        self._beat: Beat | None = None
        self._beat_started = 0
        self._move_started_x = self.x
        self._last_frame_at = 0
        self._recipe = motion_recipe("idle_bob")
        self._attention_state = "quiet"
        self._attention_label = "Hermes is ready"
        self._attention_started = int(time.monotonic() * 1000)
        self.on_ready: Callable[[], None] | None = None

        # Grab (opt-in, spec §25 pointer interaction default-OFF).
        self.enable_grab = enable_grab
        self.on_grab = on_grab
        self.intent_emitter = intent_emitter
        # Set by the live tail so the double-click panel can only ever describe
        # events this overlay actually observed. None means "no panel".
        self.panel_state_provider = None
        self._panel = None
        self._dragging = False
        self._drag_off_x = 0
        self._drag_off_y = 0
        self._interactive = False  # True when WS_EX_TRANSPARENT is cleared
        self.canvas.bind("<Double-Button-1>", self._on_double_click)
        if self.enable_grab:
            self.canvas.bind("<Button-1>", self._on_press)
            self.canvas.bind("<B1-Motion>", self._on_drag)
            self.canvas.bind("<ButtonRelease-1>", self._on_release)

        self._apply_click_through()
        self.root.bind("<Map>", lambda event: self.root.after_idle(self._keep_above), add="+")
        self._keep_above()

    # -- window plumbing ----------------------------------------------------
    def _hwnd(self) -> int:
        from hermes_companion.renderer.overlay import TkOverlay
        return TkOverlay._hwnd(self)

    def _keep_above(self) -> None:
        from hermes_companion.renderer.overlay import TkOverlay
        TkOverlay._keep_above(self)

    def _set_transparent(self, on: bool) -> None:
        hwnd = self._hwnd()
        style = ctypes.windll.user32.GetWindowLongW(hwnd, GWL_EXSTYLE)
        if on:
            style |= WS_EX_TRANSPARENT
        else:
            style &= ~WS_EX_TRANSPARENT
        ctypes.windll.user32.SetWindowLongW(hwnd, GWL_EXSTYLE, style)
        self._interactive = not on

    def _apply_click_through(self) -> None:
        # tkinter's -transparentcolor already owns WS_EX_LAYERED. Add only
        # click-through/toolwindow flags; re-setting layered corrupts the surface.
        hwnd = self._hwnd()
        style = ctypes.windll.user32.GetWindowLongW(hwnd, GWL_EXSTYLE)
        ctypes.windll.user32.SetWindowLongW(
            hwnd, GWL_EXSTYLE, style | WS_EX_TRANSPARENT | WS_EX_TOOLWINDOW)

    def _nearest_monitor_point(
            self, x: int, y: int,
            mons: list[tuple[int, int, int, int]]) -> tuple[int, int]:
        """Pick the monitor whose clamped position is closest to (x, y).

        Handles gaps between monitors naturally: the nearest screen wins and
        the pet is pinned inside it, never in dead space between displays.
        """
        best: tuple[int, int, int] | None = None  # (dist2, cx, cy)
        for left, top, right, bottom in mons:
            if right - left < self.w or bottom - top < self.h:
                continue
            cx = max(left, min(x, right - self.w))
            cy = max(top, min(y, bottom - self.h))
            d = (cx - x) ** 2 + (cy - y) ** 2
            if best is None or d < best[0]:
                best = (d, cx, cy)
        if best is None:
            return x, y
        return best[1], best[2]

    def _place(self, x: int, y: int | None = None) -> None:
        target_x = int(x)
        target_y = int(y if y is not None else self.home_y)
        mons = _monitors()
        if mons:
            # Clamp into the NEAREST monitor rectangle, not the virtual
            # desktop bounding box. The bounding box includes dead gaps
            # between monitors at different offsets — clamping there let the
            # pet park in empty space (e.g. x=-887 between DISPLAY4/1).
            self.x, self.y = self._nearest_monitor_point(target_x, target_y, mons)
        else:
            left, top, sw, sh = _virtual_screen_bounds()
            if sw > 0 and sh > 0:
                max_x = left + sw - self.w
                max_y = top + sh - self.h
                self.x = max(left, min(target_x, max_x))
                self.y = max(top, min(target_y, max_y))
            else:
                sw = self.root.winfo_screenwidth()
                sh = self.root.winfo_screenheight()
                self.x = max(0, min(target_x, sw - self.w))
                self.y = max(0, min(target_y, sh - self.h))
        self.root.geometry(f"{self.w}x{self.h}+{self.x}+{self.y}")

    def place_at(self, x: int, y: int) -> None:
        """Absolute move (grab + relay)."""
        self._place(x, y)

    def home(self) -> None:
        self._place(self.home_x, self.home_y)

    # -- ambient attention label --------------------------------------------
    def set_attention(self, state: str, label: str) -> None:
        """Set the content-free status displayed above the sprite.

        The live tail owns the truth. The overlay only displays its state and
        never derives success, recovery, or user need from animation alone.
        """
        state = str(state or "quiet")
        label = str(label or "Hermes is ready")
        if state != self._attention_state:
            self._attention_started = int(time.monotonic() * 1000)
        self._attention_state = state
        self._attention_label = label[:56]

    def _draw_attention(self) -> None:
        self.canvas.delete("attention_label")
        colors = {
            "quiet": "#cbd5e1",
            "starting": "#93c5fd",
            "working": "#5eead4",
            "delegating": "#a78bfa",
            "reviewing": "#fde68a",
            "needs-you": "#fbbf24",
            "issue": "#fb7185",
            "stuck": "#ef4444",
            "complete": "#86efac",
            "paused": "#cbd5e1",
        }
        color = colors.get(self._attention_state, colors["quiet"])
        cx = self.w // 2
        self.canvas.create_text(
            cx, 13, text=self._attention_label, fill=color,
            font=("Segoe UI", max(7, int(10 * self.scale)), "bold"),
            tags="attention_label",
        )

    # -- chain rendering -----------------------------------------------------
    def _beats_for_step(self, step: dict, category: str = "", ordinal: int = 0) -> list[Beat]:
        pose = step.get("pose", "idle_bob")
        ms = int(step.get("duration_ms") or DEFAULT_MS)
        move = step.get("move") or {}
        dx = int(move.get("dx", 0)) if move else 0
        dy = int(move.get("dy", 0)) if move else 0
        mtype = move.get("type", "") if move else ""
        ease = move.get("easing", "easeOutCubic") if move else "easeOutCubic"
        row = POSE_ROW.get(pose, "idle")
        prop = POSE_PROP.get(pose)
        recipe = motion_recipe(pose, category, ordinal)
        if pose == "return_home":
            # Walk to the ABSOLUTE home position, not the engine's fixed
            # -520 relative step. Relative returns let drift accumulate when
            # chains are interrupted mid-flight, so the pet ended up stranded
            # hundreds of px from home (or in a monitor gap). Delta is
            # computed from the current position, so the walk always lands
            # back at home even if a previous chain was cancelled.
            dx = self.home_x - self.x
            dy = self.home_y - self.y
            return [Beat(row, ms, dx, dy, "walk", prop, "easeInOutQuad", recipe)]
        if pose == "double_jump":
            # Two hops on the jumping row.
            return [Beat(row, ms // 2, dx, 0, "", prop, ease, recipe),
                    Beat(row, ms // 2, 0, 0, "", None, ease,
                         motion_recipe(pose, category, ordinal + 1))]
        if pose == "bounce":
            # Repeated vertical bounces.
            hops = max(2, ms // 180)
            beats = []
            per = ms // hops
            for _ in range(hops):
                beats.append(Beat(row, per, 0, dy, "bounce", prop, "bounce",
                                  motion_recipe(pose, category, ordinal + len(beats))))
            return beats
        return [Beat(row, ms, dx, dy, mtype, prop, ease, recipe)]

    def _beat_from_pose(self, pose: str, duration_ms: int = DEFAULT_MS) -> Beat:
        """A single idle/progression pose as a beat (for engine idle_tick
        poses: look_around, sit, play_with_object, sleep, dance, yawn ...)."""
        return Beat(POSE_ROW.get(pose, "idle"), duration_ms,
                    prop=POSE_PROP.get(pose),
                    recipe=motion_recipe(pose, "idle", 0))

    def play_chain(self, chain, category: str = "") -> None:
        """Play a real engine Chain (poses + moves). Replaces the coarse
        semantic_event mapping so the visible pet matches the engine."""
        beats: list[Beat] = []
        for ordinal, step in enumerate(chain.steps):
            beats.extend(self._beats_for_step(step, category, ordinal))
        self.enqueue(beats, replace=True)

    def enqueue(self, beats: list[Beat], *, replace: bool = False) -> None:
        if replace:
            self._queue.clear()
            self._beat = None
        self._queue.extend(beats)

    # -- companion intents ---------------------------------------------------
    def _emit_show_status_intent(self) -> None:
        if self.intent_emitter is None:
            return
        self.intent_emitter.show_status(source="double_click")

    def _on_double_click(self, _event) -> None:
        self._emit_show_status_intent()
        self._open_status_panel()

    def _open_status_panel(self) -> None:
        """Open (or refresh) the status panel from evidence, never from guesswork.

        A read-only view: any failure leaves the pet unaffected.
        """
        provider = self.panel_state_provider
        if provider is None:
            return
        try:
            from hermes_companion.renderer.companion_panel import CompanionPanelWindow
            existing = self._panel
            if existing is not None:
                try:
                    if existing.winfo_exists():
                        existing.close()
                except Exception:
                    pass
            self._panel = CompanionPanelWindow(self.root, provider())
        except Exception:
            self._panel = None

    # -- grab (opt-in) -------------------------------------------------------
    def _cursor_over_pet(self) -> bool:
        try:
            pt = ctypes.wintypes.POINT()
            ctypes.windll.user32.GetCursorPos(ctypes.byref(pt))
            return self.x <= pt.x < self.x + self.w and self.y <= pt.y < self.y + self.h
        except Exception:
            return False

    def _on_press(self, event) -> None:
        self._dragging = True
        self._drag_off_x = event.x_root - self.x
        self._drag_off_y = event.y_root - self.y

    def _on_drag(self, event) -> None:
        if not self._dragging:
            return
        self.place_at(event.x_root - self._drag_off_x,
                      event.y_root - self._drag_off_y)

    def _on_release(self, event) -> None:
        if self._dragging:
            self._dragging = False
            if self.on_grab:
                try:
                    self.on_grab(self.x, self.y)
                except Exception:
                    pass

    # -- animation loop ------------------------------------------------------
    def _start_next(self, now: int) -> None:
        if self._queue:
            self._beat = self._queue.popleft()
            self.row = self._beat.row if self._beat.row in self.frames else "idle"
            self.frame_i = 0
            self._beat_started = now
            self._move_started_x = self.x
            self._move_started_y = self.y
            self._recipe = self._beat.recipe or motion_recipe("idle_bob")
            self._draw_prop()
        elif self._beat is None:
            state = self._attention_state
            age = now - self._attention_started
            if state == "needs-you":
                self.row = "waving"
            elif state == "issue":
                self.row = "failed"
            elif state == "complete" and age < 1800:
                self.row = "jumping"
            elif state == "paused":
                self.row = "waiting"
            else:
                self.row = "idle"
            self._recipe = motion_recipe("wave" if state == "needs-you" else "idle_bob")
            self._clear_prop()
            canvas = getattr(self, "canvas", None)
            if canvas is not None:
                canvas.delete("motion_fx")

    def _clear_prop(self) -> None:
        canvas = getattr(self, "canvas", None)
        if canvas is None:
            return
        try:
            canvas.delete("companion_prop")
        except tk.TclError:
            pass

    def _draw_prop(self) -> None:
        """Draw the current beat's prop (if any) over the sprite, scaled to
        the live window. Cleared on the next beat."""
        self._clear_prop()
        if self._beat is None or not self._beat.prop:
            return
        try:
            from hermes_companion.animation.animator import draw_extra
            # draw_extra works in the animator's 200x220 logical space with the
            # pet center at (100,150). We scale by self.scale and then shift by
            # the canvas pad so the prop lands over the live sprite.
            before = set(self.canvas.find_all())
            draw_extra(self.canvas, self._beat.prop, 0.0, 100, 150, s=self.scale)
            for item in self.canvas.find_all():
                if item not in before:
                    self.canvas.addtag_withtag("companion_prop", item)
            self.canvas.move("companion_prop", self.pad, self.pad)
        except Exception as exc:
            print(f"[prop draw failed: {exc}]", flush=True)


    def _frame_for_recipe(self, elapsed: int) -> int:
        """Pick an atlas frame with recipe-specific timing and loop mode."""
        frames = self.frames.get(self.row, self.frames["idle"])
        count = len(frames)
        if count < 2:
            return 0
        recipe = self._recipe
        tick = elapsed // max(recipe.frame_ms, 1)
        if recipe.ping_pong:
            cycle = tuple(range(count)) + tuple(range(count - 2, 0, -1))
        else:
            cycle = tuple(range(count))
        return cycle[(recipe.phase + recipe.direction * tick) % len(cycle)]

    def _draw_motion_effect(self, elapsed: int) -> None:
        """Draw a lightweight animated accent without replacing truthful props."""
        self.canvas.delete("motion_fx")
        effect = self._recipe.effect
        if not effect:
            return
        t = elapsed / 1000.0
        cx = self.pad + self.draw_w // 2
        cy = self.pad + self.draw_h // 3
        if effect == "scan":
            radius = 12 + int((math.sin(t * 5) + 1) * 5)
            self.canvas.create_oval(cx + 26 - radius, cy - radius,
                                    cx + 26 + radius, cy + radius,
                                    outline="#22d3ee", width=2, tags="motion_fx")
        elif effect == "terminal":
            self.canvas.create_line(cx - 28, cy - 30, cx + 22, cy - 30,
                                    fill="#5eead4", width=2, tags="motion_fx")
            self.canvas.create_rectangle(cx - 30, cy - 42, cx + 24, cy - 22,
                                         outline="#334155", tags="motion_fx")
        elif effect == "files":
            for offset in (0, 5, 10):
                self.canvas.create_rectangle(cx + 20 + offset, cy - 14 + offset,
                                             cx + 37 + offset, cy + 2 + offset,
                                             outline="#94a3b8", tags="motion_fx")
        elif effect == "git":
            self.canvas.create_line(cx + 28, cy - 18, cx + 28, cy + 16,
                                    fill="#f472b6", width=2, tags="motion_fx")
            self.canvas.create_line(cx + 28, cy, cx + 46, cy - 10,
                                    fill="#22d3ee", width=2, tags="motion_fx")
        elif effect in ("spark", "orb", "portal"):
            color = "#a78bfa" if effect == "portal" else "#fbbf24"
            for i in range(3):
                angle = t * (3 if effect == "spark" else 2) + i * 2.1
                x = cx + math.cos(angle) * (25 + i * 5)
                y = cy + math.sin(angle) * (18 + i * 4)
                self.canvas.create_oval(x - 3, y - 3, x + 3, y + 3,
                                        fill=color, outline="", tags="motion_fx")
        elif effect == "sweat":
            self.canvas.create_oval(cx + 35, cy - 26, cx + 43, cy - 14,
                                    fill="#38bdf8", outline="", tags="motion_fx")
        elif effect == "zzz":
            self.canvas.create_text(cx + 32, cy - 32, text="Zzz", fill="#cbd5e1",
                                    font=("Segoe UI", max(8, int(14 * self.scale)), "bold"),
                                    tags="motion_fx")

    def _render_recipe(self, elapsed: int) -> None:
        recipe = self._recipe
        bob = int(math.sin(elapsed / max(recipe.frame_ms * 3, 1)) * recipe.bob_px)
        sway = int(math.sin(elapsed / max(recipe.frame_ms * 5, 1)) * recipe.sway_px)
        self.canvas.coords(self._image_item, self.pad + sway, self.pad + bob)
        self.frame_i = self._frame_for_recipe(elapsed)
        frames = self.frames.get(self.row, self.frames["idle"])
        self.canvas.itemconfigure(self._image_item, image=frames[self.frame_i])
        self._draw_motion_effect(elapsed)
        self._draw_attention()

    def tick(self) -> None:
        now = int(self.root.tk.call("clock", "milliseconds"))

        # Grab: keep the sprite hitbox interactive only while the cursor is
        # over it; everything else stays click-through (§33).
        if self.enable_grab:
            over = self._cursor_over_pet() or self._dragging
            if over and not self._interactive:
                self._set_transparent(False)
            elif not over and self._interactive:
                self._set_transparent(True)

        if self._beat is None:
            self._start_next(now)
        beat = self._beat
        if beat is not None:
            elapsed = now - self._beat_started
            duration = max(beat.duration_ms, 1)
            t = min(1.0, elapsed / duration)
            from hermes_companion.movement.paths import is_moving as _is_moving
            if _is_moving(beat.move_type, beat.move_dx, beat.move_dy):
                from hermes_companion.movement.paths import offset as _offset
                ox, oy = _offset(beat.move_type, beat.move_dx, beat.move_dy,
                                 beat.ease, t)
                self._place(int(round(self._move_started_x + ox)),
                            int(round(self._move_started_y + oy)))
            if elapsed >= beat.duration_ms:
                # Snap movement to exact end, then advance.
                if _is_moving(beat.move_type, beat.move_dx, beat.move_dy):
                    from hermes_companion.movement.paths import net_offset as _net
                    nx, ny = _net(beat.move_type, beat.move_dx, beat.move_dy)
                    self._place(int(round(self._move_started_x + nx)),
                                int(round(self._move_started_y + ny)))
                self._beat = None
                self._start_next(now)

        elapsed_for_render = now - self._beat_started if self._beat is not None else now
        self._render_recipe(elapsed_for_render)
        self.root.after(25, self.tick)

    def run(self) -> None:
        self.tick()
        if self.on_ready:
            self.on_ready()
        self.root.mainloop()

    def close(self) -> None:
        try:
            self.root.destroy()
        except tk.TclError:
            pass
