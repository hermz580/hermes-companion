"""Is the companion really visible on screen? (Windows)

Screenshots the desktop before and after a companion window draws, and checks
that pixels changed where the window says it is. "The window opened" is not
enough: a frame pushed into the wrong window still reports success while
nothing reaches the screen (the invisible-companion bug), and a window whose
transparency failed shows a dark box instead of the companion.

    python -m hermes_companion.renderer.visibility
"""
from __future__ import annotations

import sys
import time

MIN_CHANGED = 400        # pixels; a drawn companion changes thousands
DARK = 24                # brightness at or below this counts as black
BLACK_SHARE = 0.5        # a companion fills well under half its window; a box fills it all


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


def verdict(before, after, rect, origin=(0, 0)) -> str:
    """"visible", "invisible" (nothing drew) or "black" (a dark box drew instead)."""
    from PIL import ImageChops
    left, top, right, bottom = rect
    box = (left - origin[0], top - origin[1], right - origin[0], bottom - origin[1])
    now = after.crop(box).convert("RGB")
    diff = ImageChops.difference(before.crop(box).convert("RGB"), now).convert("L")
    changed = diff.point(lambda v: 1 if v > 24 else 0).tobytes()
    dark = now.convert("L").point(lambda v: 1 if v <= DARK else 0).tobytes()
    if sum(changed) < MIN_CHANGED:
        return "invisible"
    black = sum(c & d for c, d in zip(changed, dark))
    return "black" if black >= BLACK_SHARE * len(changed) else "visible"


def desktop_origin() -> tuple[int, int]:
    import ctypes
    u = ctypes.windll.user32
    return u.GetSystemMetrics(76), u.GetSystemMetrics(77)    # virtual screen left/top


def check(overlay, before) -> str | None:
    """How the overlay looks on screen (see ``verdict``); None if we can't tell."""
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
    return verdict(before, after, rect, desktop_origin())


def probe(companion: str, render: str = "smooth") -> tuple[str | None, str]:
    """Open one companion with this drawing, look at the screen, close it.

    Returns (verdict, window mode)."""
    from hermes_companion.renderer.layered import SmoothLiveOverlay
    before = snapshot() if sys.platform == "win32" else None
    overlay = SmoothLiveOverlay(companion=companion, layered=render == "smooth")
    try:
        return check(overlay, before), overlay.mode
    finally:
        overlay.close()


def main(companions=("nyamekra", "kai"), renders=("smooth", "simple")) -> int:
    if sys.platform != "win32":
        print("visibility probe: Windows only")
        return 0
    import tkinter
    print(f"python {sys.version.split()[0]}, tk {tkinter.TkVersion}")
    failed = False
    for name in companions:
        for render in renders:
            seen, mode = probe(name, render)
            print(f"{name} {render}: mode={mode} looks={seen}")
            if seen in ("invisible", "black"):
                print(f"{seen.upper()}: {name} ({render} drawing) is not visible on screen")
                failed = True
    if failed:
        return 1
    print("VISIBLE")
    return 0


if __name__ == "__main__":
    sys.exit(main())
