"""Roadmap batch 3: saved settings, tray menu, several companions on screen."""
import json

from hermes_companion.cli.emit import build_parser, resolve_play_settings
from hermes_companion.core import settings as S
from hermes_companion.renderer.tray import apply_choice, menu_model


def test_settings_roundtrip_and_validation(tmp_path):
    path = tmp_path / "settings.json"
    S.save(dict(S.DEFAULTS, companion="nia", palette="indigo", sound=True,
                **{"with": ["herald", "nia", "bogus"]}), path)
    v = S.load(path)
    assert v["companion"] == "nia" and v["palette"] == "indigo" and v["sound"] is True
    assert v["with"] == ["herald"]                       # self and unknown names dropped
    path.write_text(json.dumps({"companion": "nope", "size": 7}))
    assert S.load(path)["companion"] == "nyamekra" and S.load(path)["size"] == "standard"


def test_play_command_round_trips_through_the_parser():
    values = dict(S.DEFAULTS, companion="herald", palette="ember", size="large", sound=True,
                  bubbles=False, reduced_motion=True, **{"with": ["nia"]})
    cmd = S.play_command(values)
    args = build_parser().parse_args(cmd[cmd.index("play"):])
    again = resolve_play_settings(args, S.DEFAULTS)
    for key in ("companion", "palette", "size", "sound", "bubbles", "reduced_motion", "with"):
        assert again[key] == values[key], key


def test_command_line_beats_saved_settings():
    saved = dict(S.DEFAULTS, companion="nia", palette="indigo", size="large", sound=True)
    args = build_parser().parse_args(["play", "--companion", "herald", "--no-bubbles"])
    v = resolve_play_settings(args, saved)
    assert v["companion"] == "herald" and v["palette"] is None   # nia's palette not carried over
    assert v["size"] == "large" and v["sound"] is True and v["bubbles"] is False
    v2 = resolve_play_settings(build_parser().parse_args(["play"]), saved)
    assert v2["companion"] == "nia" and v2["palette"] == "indigo"


def test_tray_menu_covers_every_setting():
    model = menu_model(dict(S.DEFAULTS))
    labels = [m[0] for m in model]
    for want in ("Character", "Energy", "Size", "Curiosity", "Speech bubbles", "Sound",
                 "Learn my rhythm", "Live on my windows", "Reduced motion", "High contrast",
                 "Companions on screen", "Settings…", "Quit"):
        assert want in labels


def test_tray_choices_apply_cleanly():
    v = dict(S.DEFAULTS, palette="fire")
    v = apply_choice(v, "radio", ("companion", "nia"))
    assert v["companion"] == "nia" and v["palette"] is None
    v = apply_choice(v, "toggle", "sound")
    assert v["sound"] is True
    for c in ("herald", "samurai", "astro", "nyamekra"):
        v = apply_choice(v, "toggle_with", c)
    assert len(v["with"]) == 3                             # at most three extras
    v = apply_choice(v, "toggle_with", "herald")
    assert "herald" not in v["with"]
