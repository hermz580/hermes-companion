"""Transparent, always-on-top, click-through overlay window (spec rev1 §33).

- Chroma-key transparency via tkinter's -transparentcolor (Windows).
- Click-through: WS_EX_TRANSPARENT | WS_EX_LAYERED | WS_EX_TOOLWINDOW via
  ctypes. Pointer interaction is default-OFF per §25, so the whole window is
  click-through in v0.1 — the pet never blocks the UI under it.
- Window translation (dash/run/walk) is driven by the Director via set_x().
"""
from __future__ import annotations

import ctypes
import tkinter as tk

from hermes_companion.animation.animator import BG
from hermes_companion.animation.characters import draw_companion

WS_EX_LAYERED = 0x00080000
WS_EX_TRANSPARENT = 0x00000020
WS_EX_TOOLWINDOW = 0x00000080
GWL_EXSTYLE = -20
SM_XVIRTUALSCREEN = 76
SM_YVIRTUALSCREEN = 77
SM_CXVIRTUALSCREEN = 78
SM_CYVIRTUALSCREEN = 79


def _virtual_screen_bounds() -> tuple[int, int, int, int]:
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
    return 0, 0, 0, 0


def monitors() -> list[tuple[int, int, int, int]]:
    """Real monitor rectangles as (left, top, right, bottom); [] on failure.

    Enumerated rather than derived from the virtual-screen metrics: on a
    multi-monitor desk the panels can sit at vertical offsets, and the virtual
    bounding box then covers regions no monitor occupies.
    """
    try:
        import ctypes.wintypes as wt

        user32 = ctypes.windll.user32
        found: list[tuple[int, int, int, int]] = []
        proc_type = ctypes.WINFUNCTYPE(ctypes.c_int, wt.HMONITOR, wt.HDC,
                                       ctypes.POINTER(wt.RECT), wt.LPARAM)

        def _cb(_hmon, _hdc, rect_ptr, _lparam):
            rect = rect_ptr.contents
            found.append((rect.left, rect.top, rect.right, rect.bottom))
            return 1

        user32.EnumDisplayMonitors(0, 0, proc_type(_cb), 0)
        return found
    except Exception:
        return []


def primary_monitor(rects: list[tuple[int, int, int, int]] | None = None
                    ) -> tuple[int, int, int, int] | None:
    """The monitor containing the origin, else the first one."""
    rects = monitors() if rects is None else rects
    if not rects:
        return None
    for rect in rects:
        left, top, right, bottom = rect
        if left <= 0 < right and top <= 0 < bottom:
            return rect
    return rects[0]


def monitor_for_point(x: int, y: int,
                      rects: list[tuple[int, int, int, int]]) -> tuple[int, int, int, int] | None:
    """The monitor containing (x, y), else the nearest one, else None."""
    if not rects:
        return None
    for rect in rects:
        left, top, right, bottom = rect
        if left <= x < right and top <= y < bottom:
            return rect

    def _distance(rect: tuple[int, int, int, int]) -> float:
        left, top, right, bottom = rect
        return float((min(max(x, left), right) - x) ** 2
                     + (min(max(y, top), bottom) - y) ** 2)

    return min(rects, key=_distance)


def clamp_into(rect: tuple[int, int, int, int], x: int, y: int,
               w: int, h: int) -> tuple[int, int]:
    """Clamp a window position into one monitor's rectangle (x AND y)."""
    left, top, right, bottom = rect
    return (min(max(int(x), left), max(left, right - w)),
            min(max(int(y), top), max(top, bottom - h)))


def clamp_to_monitors(x: int, y: int, w: int, h: int,
                      rects: list[tuple[int, int, int, int]]) -> tuple[int, int]:
    """Clamp a window into a REAL monitor.

    Clamping to the virtual bounding box is not safe: with panels at vertical
    offsets the box includes dead space, so a left-running chain parked the pet
    at x=-2102, y=620 — the extreme left of the box, below every physical
    panel, where it could never be seen again. This picks the monitor nearest
    the requested position and clamps into it.
    """
    rect = monitor_for_point(x, y, rects)
    if rect is None:
        return x, y
    return clamp_into(rect, x, y, w, h)


class TkOverlay:
    """Surface the Director drives; owns the sprite window."""

    def __init__(self, w: int = 200, h: int = 220, home_x: int | None = None,
                 home_y: int | None = None, click_through: bool = True,
                 companion: str | None = None, palette: str | None = None) -> None:
        self.companion = companion
        self.palette = palette
        self.root = tk.Tk()
        self.root.overrideredirect(True)
        self.root.wm_attributes("-topmost", True)
        self.root.wm_attributes("-transparentcolor", BG)
        self.canvas = tk.Canvas(self.root, width=w, height=h, bg=BG,
                                highlightthickness=0, bd=0)
        self.canvas.pack()
        self.w, self.h = w, h

        left, top, sw, sh = _virtual_screen_bounds()
        # Home anchor: the PRIMARY monitor, bottom-centre, so dash (right) and
        # return (left) both stay on-screen for the walking-skeleton demo.
        # `home_anchor` is a per-character config value in the spec (§38
        # manifest), not fixed.
        primary = primary_monitor()
        if primary is not None:
            p_left, p_top, p_right, p_bottom = primary
            default_x = p_left + ((p_right - p_left) - w) // 2
            default_y = p_bottom - h - 64
        elif sw > 0 and sh > 0:
            default_x = left + (sw - w) // 2
            default_y = top + sh - h - 64
        else:
            default_x = (self.root.winfo_screenwidth() - w) // 2
            default_y = self.root.winfo_screenheight() - h - 64
        # Never start (or be told to start) in a region no monitor occupies:
        # resolve the panel for the requested home once, and stay on it.
        rects = monitors()
        requested_x = default_x if home_x is None else home_x
        requested_y = default_y if home_y is None else home_y
        self._home_rect = monitor_for_point(requested_x, requested_y, rects)
        if self._home_rect is not None:
            self.home_x, self.home_y = clamp_into(
                self._home_rect, requested_x, requested_y, w, h)
        else:
            self.home_x, self.home_y = requested_x, requested_y
        self.x = self.home_x
        self._place(self.home_x, self.home_y)

        if click_through:
            self._apply_click_through()

    # -- window plumbing ----------------------------------------------------
    def _place(self, x: int, y: int) -> None:
        self.root.geometry(f"{self.w}x{self.h}+{x}+{y}")

    def _hwnd(self) -> int:
        return ctypes.windll.user32.GetParent(self.canvas.winfo_id())

    def _apply_click_through(self) -> None:
        """Add click-through WITHOUT touching WS_EX_LAYERED.

        tkinter's -transparentcolor already configures the layered surface
        (WS_EX_LAYERED + proper per-pixel alpha). Re-setting WS_EX_LAYERED via
        SetWindowLongW corrupts that surface and makes the window render as an
        opaque black box (verified). We only add WS_EX_TRANSPARENT (mouse
        pass-through) and WS_EX_TOOLWINDOW (keeps it out of Alt-Tab)."""
        hwnd = self._hwnd()
        style = ctypes.windll.user32.GetWindowLongW(hwnd, GWL_EXSTYLE)
        style |= WS_EX_TRANSPARENT | WS_EX_TOOLWINDOW
        ctypes.windll.user32.SetWindowLongW(hwnd, GWL_EXSTYLE, style)
        self.ex_style = style  # verified via GetWindowLongW in the self-check

    # -- Director surface API ------------------------------------------------
    def _clamp(self, x: int, y: int) -> tuple[int, int]:
        """Keep the window on the monitor it was placed on (x AND y).

        Staying on the home panel is deliberate: clamping against the whole
        desktop instead would let one long run teleport the pet onto a
        different monitor, and clamping against the virtual bounding box is
        worse — with vertically offset panels that box covers dead space and
        the pet can be parked where no monitor exists at all.
        """
        rect = getattr(self, "_home_rect", None)
        if rect is not None:
            return clamp_into(rect, x, y, self.w, self.h)
        left, top, sw, sh = _virtual_screen_bounds()
        if sw > 0 and sh > 0:
            return max(left, min(int(x), left + sw - self.w)), int(y)
        return max(0, min(int(x), self.root.winfo_screenwidth() - self.w)), int(y)

    def set_pose(self, pose: str, progress: float = 0.0) -> None:
        draw_companion(self.canvas, self.companion, pose, progress,
                       palette=self.palette)

    def set_x(self, x: int) -> None:
        # Spec §14: clamp to monitor work area so the pet never travels
        # off-screen (dash from a right-anchored home can exceed screen width).
        self.x, self.home_y = self._clamp(int(x), self.home_y)
        self._place(self.x, self.home_y)

    def current_x(self) -> int:
        return self.x

    def set_state(self, state: str) -> None:
        self.root.title(f"hermes-companion [{state}]")

    def run(self) -> None:
        self.root.mainloop()

    def close(self) -> None:
        try:
            self.root.destroy()
        except tk.TclError:
            pass


class ProceduralLiveOverlay(TkOverlay):
    """Adapt a procedural companion to the live EventTail surface contract."""

    def __init__(self, *, companion: str, home_x: int | None = None,
                 home_y: int | None = None, palette: str | None = None) -> None:
        # Resolve before opening a window so unknown names fail without GUI side effects.
        from hermes_companion.animation.characters import get_companion
        get_companion(companion)
        super().__init__(home_x=home_x, home_y=home_y, click_through=True,
                         companion=companion, palette=palette)
        self.on_ready = None
        self._director = None

    def bind_engine(self, engine) -> None:
        from hermes_companion.animation.director import Director
        self._director = Director(engine, self)

    def play_chain(self, chain, _category: str = "") -> None:
        if self._director is None:
            raise RuntimeError("procedural live overlay has no behavior engine")
        self._director.start_chain(chain)

    def set_y(self, y: int) -> None:
        """Vertical anchor (perching on windows); the Director only moves x."""
        self.home_y = int(y)
        self._place(self.x, self.home_y)

    def place_at(self, x: int, y: int) -> None:
        # Re-resolve which panel this position belongs to (relay grabs and
        # multi-pet placement can move a companion to another screen) and keep
        # it there instead of letting it wander back across monitors.
        rect = monitor_for_point(int(x), int(y), monitors())
        if rect is not None:
            self._home_rect = rect
        self.home_y = int(y)
        self.set_x(int(x))

    def _tick(self) -> None:
        # Step the director EVERY tick, not only while a chain is active. With
        # the chain-only guard the companion froze solid the moment a chain
        # ended (the "it ran off and I never saw it again" report): idle
        # progression never advanced, and the return-to-anchor walk could never
        # run because it happens precisely when there is no active chain.
        if self._director is not None:
            self._director.step(1.0 / 30.0)
        self.root.after(33, self._tick)

    def run(self) -> None:
        self.set_pose("idle_bob", 0.0)
        if self.on_ready is not None:
            self.on_ready()
        self.root.after(33, self._tick)
        self.root.mainloop()
