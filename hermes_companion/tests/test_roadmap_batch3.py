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
                 "Companions on screen", "Open Home…", "Quit"):
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


def test_real_pystray_menu_builds():
    """pystray rejects handlers with extra parameters; build the real menu."""
    import os
    os.environ.setdefault("PYSTRAY_BACKEND", "dummy")
    pystray = __import__("pytest").importorskip("pystray")
    from hermes_companion.renderer.tray import build_menu
    menu = build_menu(pystray, dict(S.DEFAULTS), lambda: None, lambda: None)
    labels = [item.text for item in menu.items]
    assert "Character" in labels and "Quit" in labels


def test_every_companion_can_be_started_from_play_and_live():
    """Home, the tray and --with launch companions through these parsers."""
    from hermes_companion.animation.characters import COMPANIONS
    parser = build_parser()
    for name in S.COMPANIONS:
        assert name in COMPANIONS
        assert parser.parse_args(["play", "--companion", name]).companion == name
        assert parser.parse_args(["live", "--companion", name]).companion == name
        assert parser.parse_args(S.play_command(dict(S.DEFAULTS, companion=name))[3:]).companion == name
        assert parser.parse_args(S.live_command(dict(S.DEFAULTS, companion=name))[3:]).companion == name


def test_unknown_guests_are_dropped():
    args = build_parser().parse_args(["play", "--with", "master,nobody,duet"])
    assert resolve_play_settings(args, S.DEFAULTS)["with"] == ["master", "duet"]


def test_tray_and_home_offer_every_palette_by_name():
    from hermes_companion.animation.characters import COMPANIONS
    from hermes_companion.renderer import tray
    for name in S.COMPANIONS:
        assert tray.ENERGIES.get(name, ()) == tuple(COMPANIONS[name]["palettes"])
    labels = [label for label, _, _ in dict((i[0], i) for i in tray.menu_model(S.DEFAULTS))["Character"][2]]
    assert "Sensei" in labels and "Ade & Rae" in labels
