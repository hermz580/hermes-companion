"""Is the companion really visible on screen? (Windows diagnostic)

Screenshots the desktop before and after a smooth companion window draws a
frame and reports where pixels actually changed, next to where the window
believes it is. Also prints the window chain Tk built, so a frame pushed into
the wrong window shows up as "expected at X, changed: nothing".

    python -m hermes_companion.scripts.visibility_probe
"""
from __future__ import annotations

import ctypes
import ctypes.wintypes as wt
import sys
import time

GA_ROOT = 2


def _info(hwnd: int) -> str:
    u = ctypes.windll.user32
    cls = ctypes.create_unicode_buffer(64)
    u.GetClassNameW(hwnd, cls, 64)
    r = wt.RECT()
    u.GetWindowRect(hwnd, ctypes.byref(r))
    style = u.GetWindowLongW(hwnd, -16) & 0xFFFFFFFF
    ex = u.GetWindowLongW(hwnd, -20) & 0xFFFFFFFF
    return (f"hwnd={hwnd:#x} class={cls.value} rect=({r.left},{r.top},{r.right},{r.bottom}) "
            f"visible={bool(u.IsWindowVisible(hwnd))} child={bool(style & 0x40000000)} "
            f"layered={bool(ex & 0x80000)} exstyle={ex:#x}")


def _changed(before, after):
    from PIL import ImageChops
    diff = ImageChops.difference(before.convert("RGB"), after.convert("RGB")).convert("L")
    return diff.point(lambda v: 255 if v > 24 else 0).getbbox()


def probe(label: str, patch_root: bool) -> bool:
    from PIL import ImageGrab
    from hermes_companion.renderer import overlay as ov
    from hermes_companion.renderer.layered import SmoothLiveOverlay

    original = ov.TkOverlay._hwnd
    if patch_root:
        ov.TkOverlay._hwnd = lambda self: ctypes.windll.user32.GetAncestor(
            self.canvas.winfo_id(), GA_ROOT)
    try:
        before = ImageGrab.grab(all_screens=True)
        o = SmoothLiveOverlay(companion="nyamekra")
        for _ in range(10):
            o.set_pose("wave", 0.3)
            o.root.update()
            time.sleep(0.05)
        u = ctypes.windll.user32
        canvas = o.canvas.winfo_id()
        print(f"[{label}] mode={o.mode} expected=({o.x},{o._y},{o.x + o.w},{o._y + o.h})")
        print(f"[{label}]   canvas  {_info(canvas)}")
        print(f"[{label}]   _hwnd() {_info(o._hwnd())}")
        print(f"[{label}]   root    {_info(u.GetAncestor(canvas, GA_ROOT))}")
        after = ImageGrab.grab(all_screens=True)
        box = _changed(before, after)
        left, top = ctypes.windll.user32.GetSystemMetrics(76), ctypes.windll.user32.GetSystemMetrics(77)
        shown = None if box is None else (box[0] + left, box[1] + top, box[2] + left, box[3] + top)
        print(f"[{label}]   pixels changed on screen: {shown or 'NOTHING (invisible)'}")
        o.close()
        return box is not None
    finally:
        ov.TkOverlay._hwnd = original


def main() -> int:
    if sys.platform != "win32":
        print("visibility probe: Windows only")
        return 0
    try:
        ctypes.windll.shcore.GetProcessDpiAwareness(None, ctypes.byref(aw := ctypes.c_int()))
        print(f"dpi awareness={aw.value}")
    except Exception as exc:
        print(f"dpi awareness unknown: {exc}")
    a = probe("current", patch_root=False)
    b = probe("root-hwnd", patch_root=True)
    print(f"VISIBLE current={a} root-hwnd={b}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
