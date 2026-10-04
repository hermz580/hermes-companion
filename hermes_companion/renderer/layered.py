"""Per-pixel-alpha companion window (Windows ``UpdateLayeredWindow``).

``SmoothLiveOverlay`` is a drop-in for ``ProceduralLiveOverlay``: the Director
still calls ``set_pose`` / ``set_x``, but each frame comes from
``renderer.smooth.FrameRenderer`` and is pushed to the screen with true alpha,
so edges are anti-aliased and the mood glow fades into the desktop.

If any Win32 step fails (not Windows, old driver, remote session), it falls
back to the colour-keyed Tk path with a matted edge, so the pet still shows.
"""
from __future__ import annotations

import ctypes
import tkinter as tk

from hermes_companion.renderer.overlay import (
    GWL_EXSTYLE, WS_EX_LAYERED, WS_EX_TOOLWINDOW, WS_EX_TRANSPARENT,
    ProceduralLiveOverlay,
)
from hermes_companion.renderer.smooth import (
    FRAME_H, FRAME_W, FrameRenderer, chroma_fallback, premultiplied_bgra,
)

ULW_ALPHA = 0x00000002
AC_SRC_OVER = 0x00
AC_SRC_ALPHA = 0x01
DIB_RGB_COLORS = 0
BI_RGB = 0


class _BLENDFUNCTION(ctypes.Structure):
    _fields_ = [("BlendOp", ctypes.c_ubyte), ("BlendFlags", ctypes.c_ubyte),
                ("SourceConstantAlpha", ctypes.c_ubyte), ("AlphaFormat", ctypes.c_ubyte)]


class _BITMAPINFOHEADER(ctypes.Structure):
    _fields_ = [("biSize", ctypes.c_uint32), ("biWidth", ctypes.c_int32),
                ("biHeight", ctypes.c_int32), ("biPlanes", ctypes.c_uint16),
                ("biBitCount", ctypes.c_uint16), ("biCompression", ctypes.c_uint32),
                ("biSizeImage", ctypes.c_uint32), ("biXPelsPerMeter", ctypes.c_int32),
                ("biYPelsPerMeter", ctypes.c_int32), ("biClrUsed", ctypes.c_uint32),
                ("biClrImportant", ctypes.c_uint32)]


class _POINT(ctypes.Structure):
    _fields_ = [("x", ctypes.c_long), ("y", ctypes.c_long)]


class _SIZE(ctypes.Structure):
    _fields_ = [("cx", ctypes.c_long), ("cy", ctypes.c_long)]


class LayeredBlitter:
    """Owns a 32-bit DIB section and pushes frames with UpdateLayeredWindow."""

    def __init__(self, hwnd: int, w: int, h: int) -> None:
        self.user32 = ctypes.windll.user32
        self.gdi32 = ctypes.windll.gdi32
        self.hwnd, self.w, self.h = hwnd, w, h
        u, g = self.user32, self.gdi32
        u.GetDC.restype = ctypes.c_void_p
        g.CreateCompatibleDC.restype = ctypes.c_void_p
        g.CreateDIBSection.restype = ctypes.c_void_p
        g.SelectObject.restype = ctypes.c_void_p
        u.UpdateLayeredWindow.argtypes = [
            ctypes.c_void_p, ctypes.c_void_p, ctypes.POINTER(_POINT),
            ctypes.POINTER(_SIZE), ctypes.c_void_p, ctypes.POINTER(_POINT),
            ctypes.c_uint32, ctypes.POINTER(_BLENDFUNCTION), ctypes.c_uint32]

        # A layered window that ever had SetLayeredWindowAttributes (Tk's
        # -transparentcolor) refuses UpdateLayeredWindow until WS_EX_LAYERED is
        # cleared and set again.
        style = u.GetWindowLongW(hwnd, GWL_EXSTYLE)
        u.SetWindowLongW(hwnd, GWL_EXSTYLE, style & ~WS_EX_LAYERED)
        u.SetWindowLongW(hwnd, GWL_EXSTYLE,
                         style | WS_EX_LAYERED | WS_EX_TRANSPARENT | WS_EX_TOOLWINDOW)

        self.screen_dc = u.GetDC(None)
        self.mem_dc = g.CreateCompatibleDC(ctypes.c_void_p(self.screen_dc))
        bmi = _BITMAPINFOHEADER()
        bmi.biSize = ctypes.sizeof(_BITMAPINFOHEADER)
        bmi.biWidth, bmi.biHeight = w, -h          # negative: top-down rows
        bmi.biPlanes, bmi.biBitCount, bmi.biCompression = 1, 32, BI_RGB
        self.bits = ctypes.c_void_p()
        self.dib = g.CreateDIBSection(ctypes.c_void_p(self.mem_dc), ctypes.byref(bmi),
                                      DIB_RGB_COLORS, ctypes.byref(self.bits), None, 0)
        if not self.dib or not self.bits:
            raise OSError("CreateDIBSection failed")
        self.old = g.SelectObject(ctypes.c_void_p(self.mem_dc), ctypes.c_void_p(self.dib))
        self.blend = _BLENDFUNCTION(AC_SRC_OVER, 0, 255, AC_SRC_ALPHA)

    def blit(self, img, x: int, y: int) -> None:
        data = premultiplied_bgra(img)
        ctypes.memmove(self.bits, data, len(data))
        ok = self.user32.UpdateLayeredWindow(
            ctypes.c_void_p(self.hwnd), ctypes.c_void_p(self.screen_dc),
            ctypes.byref(_POINT(int(x), int(y))), ctypes.byref(_SIZE(self.w, self.h)),
            ctypes.c_void_p(self.mem_dc), ctypes.byref(_POINT(0, 0)), 0,
            ctypes.byref(self.blend), ULW_ALPHA)
        if not ok:
            raise OSError(f"UpdateLayeredWindow failed ({ctypes.GetLastError()})")

    def close(self) -> None:
        try:
            self.gdi32.SelectObject(ctypes.c_void_p(self.mem_dc), ctypes.c_void_p(self.old))
            self.gdi32.DeleteObject(ctypes.c_void_p(self.dib))
            self.gdi32.DeleteDC(ctypes.c_void_p(self.mem_dc))
            self.user32.ReleaseDC(None, ctypes.c_void_p(self.screen_dc))
        except Exception:
            pass


class SmoothLiveOverlay(ProceduralLiveOverlay):
    """High-quality procedural companion with true alpha where possible."""

    def __init__(self, *, companion: str, home_x: int | None = None,
                 home_y: int | None = None, palette: str | None = None,
                 glow: bool = True, scale: float = 1.0, reduced_motion: bool = False,
                 high_contrast: bool = False, artpack: str | None = None) -> None:
        super().__init__(companion=companion, home_x=home_x, home_y=home_y,
                         palette=palette)
        self.renderer = FrameRenderer(companion, palette, glow=glow, scale=scale,
                                      reduced_motion=reduced_motion,
                                      high_contrast=high_contrast, artpack=artpack)
        self.w = int(self.renderer.fw * scale)
        self.h = int(self.renderer.fh * scale)
        if (self.w, self.h) != (FRAME_W, FRAME_H):
            # keep the feet on the same floor line when the frame grows/shrinks
            self.home_y += FRAME_H - self.h
            self.canvas.configure(width=self.w, height=self.h)
        self._pose = ("idle_bob", 0.0)
        self._y = self.home_y
        self._photo = None
        self._image_item = None
        self.blitter: LayeredBlitter | None = None
        self.mode = "windowed" if getattr(self, "windowed", False) else "chroma"
        try:
            if self.mode == "windowed":
                raise OSError("no per-pixel alpha outside Windows")
            self.root.update_idletasks()
            self.root.wm_attributes("-transparentcolor", "")
            self.blitter = LayeredBlitter(self._hwnd(), self.w, self.h)
            self.mode = "layered"
        except Exception:
            self.blitter = None
            if self.mode != "windowed":
                try:
                    from hermes_companion.animation.animator import BG
                    self.root.wm_attributes("-transparentcolor", BG)
                except tk.TclError:
                    pass

    # The Director drives these -------------------------------------------
    def set_pose(self, pose: str, progress: float = 0.0) -> None:
        if not hasattr(self, "renderer"):
            return
        self._pose = (pose, progress)
        self._present()

    def _place(self, x: int, y: int) -> None:
        if not hasattr(self, "renderer"):       # during base-class __init__
            super()._place(x, y)
            return
        self.x, self._y = int(x), int(y)
        if self.blitter is None:
            super()._place(x, y)
        self._present()

    def set_y(self, y: int) -> None:
        """Vertical anchor (perching); the Director only moves x."""
        self.home_y = int(y)
        self._place(self.x, self.home_y)

    def _present(self) -> None:
        frame = self.renderer.frame(*self._pose)
        text = getattr(self, "_bubble_text", None)
        if text:                                     # no bubble window: draw it in-frame
            from hermes_companion.renderer.voice import bubble_image
            b = bubble_image(text, width=self.w - 8)
            b.thumbnail((self.w - 4, self.h // 3))
            frame = frame.copy()
            frame.alpha_composite(b, ((self.w - b.width) // 2, 2))
        if self.blitter is not None:
            try:
                self.blitter.blit(frame, self.x, self._y)
                return
            except OSError:
                self.blitter.close()
                self.blitter = None
                self.mode = "chroma"
                from hermes_companion.animation.animator import BG
                self.root.wm_attributes("-transparentcolor", BG)
                super()._place(self.x, self._y)
        from PIL import Image, ImageTk
        if getattr(self, "windowed", False):
            self.mode = "windowed"
            from hermes_companion.renderer.overlay import WINDOWED_BG
            shown = Image.alpha_composite(Image.new("RGBA", frame.size, WINDOWED_BG), frame)
        else:
            shown = chroma_fallback(frame)
        self._photo = ImageTk.PhotoImage(shown)
        if self._image_item is None:
            self.canvas.delete("all")
            self._image_item = self.canvas.create_image(0, 0, image=self._photo, anchor="nw")
        else:
            self.canvas.itemconfigure(self._image_item, image=self._photo)

    # -- voice: speech bubbles + opt-in chimes -------------------------------
    def attach_voice(self, *, bubbles: bool = True, sound: bool = False, lines=None):
        from hermes_companion.renderer.voice import BubbleWindow, Chimes, Voice
        self._bubble_text = None
        self._bubble_window = None
        show = self._show_bubble_inline
        if bubbles and self.blitter is not None:
            try:
                self._bubble_window = BubbleWindow(self)
                show = self._bubble_window.show
            except Exception:
                self._bubble_window = None
        if not bubbles:
            show = lambda _text: None   # noqa: E731
        self.voice = Voice(show, Chimes() if sound else None, lines=lines)
        return self.voice

    def _show_bubble_inline(self, text) -> None:
        self._bubble_text = text
        self._present()

    def set_attention(self, state: str, label: str) -> None:
        voice = getattr(self, "voice", None)
        if voice is not None:
            voice.on_attention(state, label)

    def _tick(self) -> None:
        voice = getattr(self, "voice", None)
        if voice is not None:
            voice.tick()
        super()._tick()

    def close(self) -> None:
        if getattr(self, "_bubble_window", None) is not None:
            self._bubble_window.close()
        if self.blitter is not None:
            self.blitter.close()
        super().close()
