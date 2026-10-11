"""One companion on the desktop at a time, and Home can always see which one."""
import json

from hermes_companion.core import presence as P


class Clock:
    def __init__(self, t=1000.0):
        self.t = t

    def __call__(self):
        return self.t


def test_a_running_companion_is_visible_and_beats(tmp_path):
    path, clock = tmp_path / "running.json", Clock()
    claim = P.Claim("play", "nia", path=path, clock=clock)
    seen = P.current(path, now=clock.t)
    assert seen["mode"] == "play" and seen["companion"] == "nia"
    clock.t += P.BEAT_S
    assert claim.check()
    assert json.loads(path.read_text())["beat"] == clock.t


def test_a_crashed_companion_goes_stale_on_its_own(tmp_path):
    path, clock = tmp_path / "running.json", Clock()
    P.Claim("live", "nyamekra", path=path, clock=clock)
    assert P.current(path, now=clock.t + P.STALE_S - 1) is not None
    assert P.current(path, now=clock.t + P.STALE_S + 1) is None       # no PID probing needed


def test_a_newer_companion_takes_over_and_the_old_one_hands_over(tmp_path):
    path, clock = tmp_path / "running.json", Clock()
    old = P.Claim("play", "herald", path=path, clock=clock)
    new = P.Claim("live", "nia", path=path, clock=clock)
    assert not old.check()                      # old sees the new claim: close
    assert new.check()
    old.release()                               # must not delete the new claim
    assert P.current(path, now=clock.t)["companion"] == "nia"


def test_a_stale_foreign_claim_does_not_evict_a_live_companion(tmp_path):
    path, clock = tmp_path / "running.json", Clock()
    mine = P.Claim("play", "nia", path=path, clock=clock)
    path.write_text(json.dumps({"token": "dead", "beat": clock.t - 60}))
    assert mine.check() and P.current(path, now=clock.t)["token"] == mine.token


def test_stop_request_closes_the_companion(tmp_path):
    path, clock = tmp_path / "running.json", Clock()
    claim = P.Claim("play", "astro", path=path, clock=clock)
    P._write(path, dict(P.current(path, now=clock.t), stop=True))
    assert P.current(path, now=clock.t) is None   # Home shows "stopping" as not running
    assert not claim.check()


def test_request_stop_does_nothing_when_nothing_runs(tmp_path):
    assert P.request_stop(tmp_path / "running.json") is False


def test_release_and_missing_or_corrupt_file(tmp_path):
    path, clock = tmp_path / "running.json", Clock()
    claim = P.Claim("play", "nia", path=path, clock=clock)
    claim.release()
    assert not path.exists() and P.current(path) is None
    path.write_text("{not json")
    assert P.current(path) is None
    assert claim.check() and P.current(path, now=clock.t)["token"] == claim.token  # reclaims
