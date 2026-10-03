"""Roadmap batch 1: live drawn companions, art packs, accessibility, demo GIF."""
from pathlib import Path

from PIL import Image

from hermes_companion.cli.emit import build_parser
from hermes_companion.renderer.smooth import ArtPack, FrameRenderer, mood_label


def test_live_accepts_drawn_companion_and_explicit_follow():
    args = build_parser().parse_args(
        ["live", "--companion", "nyamekra", "--follow", "--palette", "fire"])
    assert args.companion == "nyamekra" and args.follow and args.palette == "fire"


def test_play_accessibility_flags_parse():
    args = build_parser().parse_args(
        ["play", "--reduced-motion", "--high-contrast", "--artpack", "x", "--seconds", "1"])
    assert args.reduced_motion and args.high_contrast and args.artpack == "x"


def test_artpack_replaces_only_poses_it_has(tmp_path):
    for i, col in enumerate(("#ff0000", "#00ff00")):
        Image.new("RGBA", (50, 80), col).save(tmp_path / f"wave_{i}.png")
    Image.new("RGBA", (40, 40), "#0000ff").save(tmp_path / "idle_bob.png")
    pack = ArtPack(str(tmp_path))
    assert pack.poses == {"wave", "idle_bob"}
    r = FrameRenderer("nyamekra", artpack=str(tmp_path), glow=False, squash=False)
    a, b = r.frame("wave", 0.1), r.frame("wave", 0.6)
    assert a.getpixel((100, 200))[:3] == (255, 0, 0)       # first frame
    assert b.getpixel((100, 200))[:3] == (0, 255, 0)       # second frame
    procedural = r.frame("terminal_work", 0.3)
    assert procedural.getpixel((100, 200))[:3] not in ((255, 0, 0), (0, 255, 0), (0, 0, 255))


def test_high_contrast_adds_a_word_label():
    plain = FrameRenderer("nyamekra").frame("wave", 0.3)
    hc = FrameRenderer("nyamekra", high_contrast=True).frame("wave", 0.3)
    assert plain.tobytes() != hc.tobytes()
    assert mood_label("wave") == "Needs you"
    assert mood_label("terminal_work") == "Working"
    assert mood_label("shock") == "Problem"


def test_reduced_motion_is_calmer():
    calm = FrameRenderer("nyamekra", reduced_motion=True)
    assert calm.steps < FrameRenderer("nyamekra").steps and not calm.squash
    frames = {calm.frame("celebrate", i / 24).tobytes() for i in range(24)}
    assert len(frames) <= 3


def test_demo_gif_is_committed_and_animated():
    gif = Path(__file__).resolve().parents[2] / "docs" / "demo.gif"
    im = Image.open(gif)
    assert im.n_frames > 50
