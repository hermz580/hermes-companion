"""The camera command must be safe by default and impossible to trip into.

Nothing here opens a real device: the probe is injected. What is being pinned is
the *policy* — no device without explicit consent, never in follow mode, never a
presence claim without a real frame, and no captured data leaking anywhere.
"""
from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path

import pytest

from hermes_companion.cli import emit as emit_mod
from hermes_companion.renderer import camera_probe as probe_mod


NOW = datetime(2026, 9, 12, 22, 0, tzinfo=timezone.utc)


class StubProbe:
    """A probe that stamps its frame WHEN CALLED, like the real adapter.

    The timestamp is part of the contract, not decoration: the controller only
    accepts a frame acquired inside the temporary grant window, so a stub that
    stamps at construction time (before the grant exists) is correctly refused.
    """

    def __init__(self, read=True, detected=False, error=None):
        self.calls = []
        self.read = read
        self.detected = detected
        self.error = error

    def __call__(self, source_id):
        self.calls.append(source_id)
        if self.error:
            raise self.error
        return _result(self.read, self.detected)


def _result(read=True, detected=False):
    """A probe result stamped now, as a real one-frame read would be."""
    from hermes_companion.core.camera_awareness import CameraProbeResult
    return CameraProbeResult(camera_read=read, person_detected=detected,
                             observed_at=datetime.now(timezone.utc))


@pytest.fixture
def pinned_home(tmp_path, monkeypatch):
    """A Hermes home whose only companion is pinned to one exact session."""
    from hermes_companion.core import binding as bind_mod

    home = tmp_path / "hermes"
    (home / "companion").mkdir(parents=True)
    monkeypatch.setenv("HERMES_HOME", str(home))
    monkeypatch.setenv("HERMES_COMPANION_HOME", str(home / "companion"))
    bindings = home / "companion" / "bindings.json"
    bind_mod.bind("the-alpha-and", "session-a", path=bindings)
    monkeypatch.setattr(bind_mod, "following_companion", lambda *a, **k: None)
    return home


def test_status_reports_readiness_without_opening_anything(capsys):
    code = emit_mod.main(["camera", "status"])
    out = capsys.readouterr().out
    assert code == 0
    assert "camera_opened=false" in out.lower()
    assert "enabled=false" in out.lower()


def test_check_without_consent_refuses_and_never_probes(pinned_home, capsys, monkeypatch):
    stub = StubProbe()
    monkeypatch.setattr(probe_mod, "probe_camera", stub)

    code = emit_mod.main(["camera", "check", "--session-id", "session-a"])

    out = capsys.readouterr().out
    assert code == 2
    assert stub.calls == []
    assert "consent" in out.lower()


def test_check_refuses_in_follow_mode(tmp_path, monkeypatch, capsys):
    from hermes_companion.core import binding as bind_mod

    home = tmp_path / "hermes"
    (home / "companion").mkdir(parents=True)
    monkeypatch.setenv("HERMES_HOME", str(home))
    monkeypatch.setenv("HERMES_COMPANION_HOME", str(home / "companion"))
    bind_mod.set_mode(bind_mod.MODE_FOLLOW, "the-alpha-and",
                      path=home / "companion" / "bindings.json")
    monkeypatch.setattr(bind_mod, "following_companion",
                        lambda *a, **k: "the-alpha-and")
    stub = StubProbe()
    monkeypatch.setattr(probe_mod, "probe_camera", stub)

    code = emit_mod.main(["camera", "check", "--consent"])

    out = capsys.readouterr().out
    assert code == 2
    assert stub.calls == []
    assert "pinned" in out.lower()


def test_check_with_consent_probes_once_and_reports_honestly(pinned_home, capsys, monkeypatch):
    stub = StubProbe(read=True, detected=True)
    monkeypatch.setattr(probe_mod, "probe_camera", stub)

    code = emit_mod.main(["camera", "check", "--consent",
                          "--session-id", "session-a"])

    out = capsys.readouterr().out
    assert code == 0, out
    assert stub.calls == ["camera-0"]          # exactly one read, default source
    assert "camera_read=true" in out
    assert "presence=present" in out


def test_a_frame_without_detection_reports_unknown_not_absent(pinned_home, capsys, monkeypatch):
    stub = StubProbe(read=True, detected=False)
    monkeypatch.setattr(probe_mod, "probe_camera", stub)

    emit_mod.main(["camera", "check", "--consent", "--session-id", "session-a"])

    out = capsys.readouterr().out
    assert "presence=unknown" in out
    assert "absent" not in out.lower()


def test_check_requires_the_exact_bound_session(pinned_home, capsys, monkeypatch):
    stub = StubProbe()
    monkeypatch.setattr(probe_mod, "probe_camera", stub)

    code = emit_mod.main(["camera", "check", "--consent",
                          "--session-id", "some-other-session"])

    assert code == 2
    assert stub.calls == []


def test_camera_check_writes_no_events_or_audit_trail_of_content(pinned_home, capsys, monkeypatch):
    stub = StubProbe(read=True, detected=True)
    monkeypatch.setattr(probe_mod, "probe_camera", stub)

    emit_mod.main(["camera", "check", "--consent", "--session-id", "session-a"])
    capsys.readouterr()

    companion_dir = pinned_home / "companion"
    leftovers = sorted(p.name for p in companion_dir.iterdir()
                       if p.name not in ("bindings.json",))
    assert leftovers == [], f"camera check left state behind: {leftovers}"


def test_probe_adapter_reports_unavailable_instead_of_claiming_a_reading(monkeypatch):
    """With no camera library installed the adapter must not invent a frame."""
    monkeypatch.setattr(probe_mod.importlib.util, "find_spec", lambda name: None)
    result = probe_mod.probe_camera("camera-0")
    assert result.camera_read is False
    assert result.person_detected is False


def test_no_launcher_ever_passes_camera_flags():
    launchers = Path(__file__).resolve().parents[1] / "launch"
    for path in sorted(launchers.glob("*.cmd")):
        text = path.read_text(encoding="utf-8", errors="ignore").lower()
        assert "camera" not in text, f"{path.name} references the camera"
