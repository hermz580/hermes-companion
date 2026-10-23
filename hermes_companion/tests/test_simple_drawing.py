"""Simple drawing: the fix for PCs where smooth companions show as a black square."""
import json
import sys

import pytest
from PIL import Image

from hermes_companion.cli.emit import build_parser, resolve_play_settings
from hermes_companion.core import settings as S
from hermes_companion.renderer import visibility


def test_drawing_is_saved_and_bad_values_fall_back(tmp_path):
    path = tmp_path / "settings.json"
    S.save(dict(S.DEFAULTS, render="simple"), path)
    assert S.load(path)["render"] == "simple"
    path.write_text(json.dumps({"render": "sparkly"}))
    assert S.load(path)["render"] == "smooth"


def test_home_and_tray_launches_carry_the_drawing():
    values = dict(S.DEFAULTS, render="simple")
    for cmd in (S.play_command(values), S.live_command(values)):
        assert cmd[cmd.index("--render") + 1] == "simple"
    cmd = S.play_command(values)
    args = build_parser().parse_args(cmd[cmd.index("play"):])
    assert resolve_play_settings(args, S.DEFAULTS)["render"] == "simple"


def test_saved_drawing_applies_unless_the_command_line_says_otherwise():
    saved = dict(S.DEFAULTS, render="simple")
    assert resolve_play_settings(build_parser().parse_args(["play"]), saved)["render"] == "simple"
    args = build_parser().parse_args(["play", "--render", "classic"])
    assert resolve_play_settings(args, saved)["render"] == "classic"


def _desktop():
    return Image.new("RGB", (400, 300), (40, 110, 180))          # a blue wallpaper


def test_verdict_sees_a_companion():
    before = _desktop()
    after = before.copy()
    after.paste((255, 200, 0), (120, 120, 160, 180))             # a figure, not the whole window
    assert visibility.verdict(before, after, (100, 100, 200, 200)) == "visible"


def test_verdict_sees_nothing():
    before = _desktop()
    assert visibility.verdict(before, before.copy(), (100, 100, 200, 200)) == "invisible"


def test_verdict_sees_a_black_square():
    before = _desktop()
    after = before.copy()
    after.paste((0, 0, 0), (100, 100, 200, 200))                 # the whole window went black
    after.paste((255, 200, 0), (140, 130, 160, 170))             # maybe a sliver of the art too
    assert visibility.verdict(before, after, (100, 100, 200, 200)) == "black"


@pytest.mark.skipif(sys.platform != "win32", reason="Win32 windows only")
def test_simple_drawing_uses_the_colour_key_window():
    from conftest import shared_tk_root
    from hermes_companion.renderer.layered import SmoothLiveOverlay
    overlay = SmoothLiveOverlay(companion="kai", master=shared_tk_root(), layered=False)
    try:
        assert overlay.mode == "chroma" and overlay.blitter is None
        overlay.set_pose("wave", 0.3)
        overlay.root.update()
        assert overlay._photo is not None
    finally:
        overlay.close()
