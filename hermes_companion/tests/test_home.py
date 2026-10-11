"""Companion Home: one window that makes the companion make sense."""
import os

import pytest

from hermes_companion.cli.emit import build_parser
from hermes_companion.core import settings as S
from hermes_companion.renderer import home as H


def test_every_setting_has_a_home():
    """Each saved setting is reachable from a Home page, so nothing is CLI-only."""
    covered = {"companion", "with", "palette", "size", "notice"}
    covered |= {key for _g, items in H.BEHAVIOR_GROUPS for key, _l, _h in items}
    assert covered == set(S.DEFAULTS)


def test_every_companion_has_a_card_and_a_human_description():
    cards = H.companion_cards(dict(S.DEFAULTS))
    assert [c["name"] for c in cards] == list(S.COMPANIONS)
    assert all(c["tagline"] and c["title"] for c in cards)
    assert sum(c["selected"] for c in cards) == 1
    assert not next(c for c in cards if c["selected"])["can_join"]


def test_choosing_a_companion_resets_energy_and_guest_list():
    v = dict(S.DEFAULTS, palette="fire", **{"with": ["nia", "herald"]})
    v = H.choose_companion(v, "nia")
    assert v["companion"] == "nia" and v["palette"] is None and v["with"] == ["herald"]
    with pytest.raises(ValueError):
        H.choose_companion(v, "nobody")


def test_guests_cap_at_three_and_never_include_the_main_one():
    v = dict(S.DEFAULTS)
    for name in ("nia", "herald", "samurai", "astro", "nyamekra"):
        v = H.toggle_guest(v, name)
    assert v["with"] == ["nia", "herald", "samurai"]
    assert H.toggle_guest(v, "nia")["with"] == ["herald", "samurai"]


def test_pending_changes_reads_like_a_sentence():
    saved = dict(S.DEFAULTS)
    staged = dict(saved, palette="fire", sound=True)
    assert H.pending_changes(saved, staged) == ["Energy: Fire", "Sound: on"]
    assert H.pending_changes(saved, dict(saved)) == []


def test_readiness_and_status_are_plain_language():
    assert H.readiness(None)[0] == "unknown"
    assert H.readiness([("PASS", "Python", "3.12")])[0] == "ok"
    assert H.readiness([("WARN", "Hermes", "x - y")])[1].startswith("Ready, with 1 note")
    assert "Tk" in H.readiness([("FAIL", "Tk", "missing")])[1]
    assert "Press Start" in H.status_line(dict(S.DEFAULTS), None)[1]
    assert "live" in H.status_line(dict(S.DEFAULTS), "live")[1]
    assert H.fix_for("not found - 'play' works") == ("not found", "'play' works")


def test_glow_legend_matches_the_real_mood_colours():
    from hermes_companion.animation.herald import MOOD_COLORS
    for key, color, _name, _meaning in H.MEANINGS:
        assert MOOD_COLORS[key] == color


def test_no_arguments_opens_home_and_settings_still_works():
    assert build_parser().parse_args([]).fn is not None
    args = build_parser().parse_args(["home", "--page", "check"])
    assert args.page == "check"
    build_parser().parse_args(["settings"])


def test_live_command_is_accepted_by_the_real_parser():
    v = dict(S.DEFAULTS, palette="fire", sound=True, bubbles=False)
    cmd = S.live_command(v)
    args = build_parser().parse_args(cmd[cmd.index("live"):])
    assert args.companion == "nyamekra" and args.follow and args.palette == "fire"
    assert args.sound and args.no_bubbles


@pytest.fixture
def tk_root():
    tk = pytest.importorskip("tkinter")
    if os.name != "nt" and not os.environ.get("DISPLAY"):
        pytest.skip("no display")
    from conftest import shared_tk_root
    try:
        return shared_tk_root()       # one interpreter per process (see conftest)
    except tk.TclError:
        pytest.skip("Tk cannot open a window here")


class _Proc:
    def __init__(self, cmd):
        self.cmd, self.alive = cmd, True

    def poll(self):
        return None if self.alive else 0

    def terminate(self):
        self.alive = False


def test_home_window_walks_every_page_and_starts_a_companion(tk_root, tmp_path):
    from hermes_companion.core.feed import HermesFeed
    saved, started = [], []

    def runner(cmd, **_kw):
        started.append(_Proc(cmd))
        return started[-1]

    w = H.HomeWindow(dict(S.DEFAULTS), runner=runner, saver=saved.append,
                     feed=HermesFeed(tmp_path / "e.jsonl", tmp_path / "k"), master=tk_root)
    try:
        for key, _l, _s in H.NAV:
            w.show(key)
            w.win.update()
        w.show("companions")
        w._set(H.choose_companion(w.staged, "herald"))
        assert w.bar.winfo_ismapped() or w.bar.winfo_manager() == "pack"
        w.apply()
        assert saved[-1]["companion"] == "herald" and not w.bar.winfo_manager()
        w.start("play")
        assert w.mode == "play" and "play" in started[-1].cmd
        w.start("live")
        assert not started[0].alive and "live" in started[-1].cmd
        w.stop()
        assert w.mode is None and not started[-1].alive
    finally:
        w.close()
