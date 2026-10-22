"""The invisible-companion bug: frames must reach the real desktop window."""
import sys

import pytest
from PIL import Image

from hermes_companion.renderer import visibility


def test_changed_pixels_counts_only_inside_the_window():
    before = Image.new("RGB", (400, 300), "black")
    after = before.copy()
    after.paste((255, 200, 0), (100, 100, 150, 150))           # 50x50 drawn
    assert visibility.changed_pixels(before, after, (100, 100, 200, 200)) == 2500
    assert visibility.changed_pixels(before, after, (0, 0, 90, 90)) == 0


def test_changed_pixels_handles_a_desktop_left_of_zero():
    before = Image.new("RGB", (400, 300), "black")
    after = before.copy()
    after.paste((255, 255, 255), (0, 0, 20, 20))
    # virtual desktop starts at x=-100: screen x=-100 is image column 0
    assert visibility.changed_pixels(before, after, (-100, 0, -80, 20), origin=(-100, 0)) == 400


def test_unknown_without_a_screenshot():
    assert visibility.check(object(), None) is None


@pytest.mark.skipif(sys.platform != "win32", reason="Win32 windows only")
def test_frames_go_to_the_top_level_window_not_a_child():
    import ctypes
    from hermes_companion.renderer.layered import SmoothLiveOverlay
    overlay = SmoothLiveOverlay(companion="nyamekra")
    try:
        overlay.root.update()
        style = ctypes.windll.user32.GetWindowLongW(overlay._hwnd(), -16) & 0xFFFFFFFF
        assert not style & 0x40000000, "drawing into a WS_CHILD window is invisible"
        ex = ctypes.windll.user32.GetWindowLongW(overlay._hwnd(), -20) & 0xFFFFFFFF
        assert ex & 0x20, "click-through must be on the real window"
    finally:
        overlay.close()
