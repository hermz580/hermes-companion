"""Is the companion really visible on screen? (Windows)

Screenshots the desktop before and after a smooth companion window draws, and
checks that pixels changed where the window says it is. "The window opened"
is not enough: a frame pushed into the wrong window still reports success
while nothing reaches the screen (the invisible-companion bug).

    python -m hermes_companion.renderer.visibility
"""
from __future__ import annotations

import sys
import time

MIN_CHANGED = 400        # pixels; a drawn companion changes thousands


def snapshot():
    """The whole desktop, or None where screenshots aren't possible."""
    try:
        from PIL import ImageGrab
        return ImageGrab.grab(all_screens=True)
    except Exception:
        return None


def changed_pixels(before, after, rect, origin=(0, 0)) -> int:
    """How many pixels differ inside ``rect`` (desktop coordinates)."""
    from PIL import ImageChops
    left, top, right, bottom = rect
    box = (left - origin[0], top - origin[1], right - origin[0], bottom - origin[1])
    diff = ImageChops.difference(before.crop(box).convert("RGB"),
                                 after.crop(box).convert("RGB")).convert("L")
    return sum(diff.point(lambda v: 1 if v > 24 else 0).getdata())


def desktop_origin() -> tuple[int, int]:
    import ctypes
    u = ctypes.windll.user32
    return u.GetSystemMetrics(76), u.GetSystemMetrics(77)    # virtual screen left/top


def check(overlay, before) -> bool | None:
    """True if the overlay's pixels reached the screen; None if we can't tell."""
    if before is None:
        return None
    for _ in range(10):
        overlay.set_pose("wave", 0.3)
        overlay.root.update()
        time.sleep(0.05)
    after = snapshot()
    if after is None:
        return None
    rect = (overlay.x, overlay._y, overlay.x + overlay.w, overlay._y + overlay.h)
    return changed_pixels(before, after, rect, desktop_origin()) >= MIN_CHANGED


def main(companions=("nyamekra", "kai")) -> int:
    if sys.platform != "win32":
        print("visibility probe: Windows only")
        return 0
    from hermes_companion.renderer.layered import SmoothLiveOverlay
    from hermes_companion.renderer.overlay import top_level_hwnd
    failed = False
    for name in companions:
        before = snapshot()
        overlay = SmoothLiveOverlay(companion=name)
        try:
            seen = check(overlay, before)
            print(f"{name}: mode={overlay.mode} window={overlay._hwnd():#x} "
                  f"top-level={top_level_hwnd(overlay.canvas):#x} "
                  f"at=({overlay.x},{overlay._y}) visible={seen}")
        finally:
            overlay.close()
        if seen is False:
            print(f"INVISIBLE: {name} drew nothing on screen")
            failed = True
    if failed:
        return 1
    print("VISIBLE")
    return 0


if __name__ == "__main__":
    sys.exit(main())
