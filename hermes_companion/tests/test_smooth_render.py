"""High-quality frames: anti-aliased, glowing, and safe on both window paths."""
import sys

import pytest

from hermes_companion.animation.characters import list_companions
from hermes_companion.renderer.smooth import (
    FRAME_H, FRAME_W, FrameRenderer, chroma_fallback, premultiplied_bgra,
)

POSES = ("idle_bob", "notice", "terminal_work", "celebrate", "shock", "wave",
         "dash_to_workspace", "sleep", "peeking", "open_portal", "return_home")


@pytest.mark.parametrize("companion", [c for c in list_companions() if c != "pet"])
def test_every_companion_renders_smoothly(companion):
    r = FrameRenderer(companion)
    for pose in POSES:
        img = r.frame(pose, 0.4)
        assert img.size == (FRAME_W, FRAME_H) and img.mode == "RGBA"
        alpha = img.getchannel("A")
        lo, hi = alpha.getextrema()
        assert hi == 255
        # anti-aliasing + glow leave soft, partially transparent pixels
        assert sum(1 for v in alpha.tobytes() if 0 < v < 255) > 200


def test_frames_are_cached():
    r = FrameRenderer("herald")
    assert r.frame("wave", 0.30) is r.frame("wave", 0.31)


def test_premultiplied_bgra():
    from PIL import Image
    img = Image.new("RGBA", (1, 1), (200, 100, 50, 128))
    b, g, r, a = premultiplied_bgra(img)
    assert a == 128 and abs(r - 100) <= 1 and abs(g - 50) <= 1 and abs(b - 25) <= 1


def test_chroma_fallback_has_hard_alpha_and_no_green_fringe():
    img = chroma_fallback(FrameRenderer("herald").frame("idle_bob", 0.0))
    raw = img.tobytes()
    px = [tuple(raw[i:i + 4]) for i in range(0, len(raw), 4)]
    assert {p[3] for p in px} == {255}
    key = (0, 254, 0)
    greenish = [p for p in px if p[:3] != key and p[1] > 200 and p[0] < 60 and p[2] < 60]
    assert not greenish


@pytest.mark.skipif(sys.platform != "win32", reason="Win32 layered windows only")
def test_smooth_overlay_opens_and_draws_on_windows():
    from hermes_companion.renderer.layered import SmoothLiveOverlay
    overlay = SmoothLiveOverlay(companion="herald")
    try:
        assert overlay.mode in ("layered", "chroma")
        overlay.set_pose("celebrate", 0.5)
        overlay.set_y(overlay.home_y - 100)
        overlay.set_x(overlay.x + 50)
        overlay.root.update()
        print("smooth overlay mode:", overlay.mode)
    finally:
        overlay.close()
