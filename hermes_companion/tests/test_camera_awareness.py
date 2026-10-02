"""One-shot camera awareness controller; no device opens without consent."""
from __future__ import annotations

from datetime import datetime, timezone

import pytest

from hermes_companion.core.permissioned_context import PermissionedContext


NOW = datetime(2026, 9, 12, 21, 0, tzinfo=timezone.utc)


class Probe:
    def __init__(self, result=None, error=None):
        self.calls = 0
        self.result = result
        self.error = error

    def __call__(self, source_id):
        self.calls += 1
        assert source_id == "camera-0"
        if self.error:
            raise self.error
        return self.result


def _controller():
    from hermes_companion.core.camera_awareness import CameraAwarenessController

    context = PermissionedContext(clock=lambda: NOW)
    return CameraAwarenessController(context=context), context


def test_default_status_and_denied_consent_never_construct_or_call_probe():
    from hermes_companion.core.camera_awareness import camera_status

    assert camera_status() == {"enabled": False, "camera_opened": False}
    controller, context = _controller()
    probe = Probe()
    with pytest.raises(PermissionError):
        controller.check(companion_id="alpha", session_id="s", bound_session_id="s",
                         mode="pinned", source_id="camera-0", confirmed=False,
                         probe=probe)
    assert probe.calls == 0
    assert context.snapshot() == ()


def test_follow_or_wrong_session_fails_before_acquisition():
    controller, context = _controller()
    for mode, session, bound in (("follow", "s", "s"), ("pinned", "other", "s")):
        probe = Probe()
        with pytest.raises(PermissionError):
            controller.check(companion_id="alpha", session_id=session,
                             bound_session_id=bound, mode=mode,
                             source_id="camera-0", confirmed=True, probe=probe)
        assert probe.calls == 0
    assert context.snapshot() == ()


def test_real_read_with_detection_reports_present_then_revokes():
    from hermes_companion.core.camera_awareness import CameraProbeResult

    controller, context = _controller()
    probe = Probe(CameraProbeResult(camera_read=True, person_detected=True,
                                    observed_at=NOW))
    result = controller.check(companion_id="alpha", session_id="s",
                              bound_session_id="s", mode="pinned",
                              source_id="camera-0", confirmed=True, probe=probe)
    assert result.camera_read is True
    assert result.presence == "present"
    assert probe.calls == 1
    assert context.snapshot() == ()


def test_read_without_detection_is_unknown_not_absent():
    from hermes_companion.core.camera_awareness import CameraProbeResult

    controller, context = _controller()
    probe = Probe(CameraProbeResult(camera_read=True, person_detected=False,
                                    observed_at=NOW))
    result = controller.check(companion_id="alpha", session_id="s",
                              bound_session_id="s", mode="pinned",
                              source_id="camera-0", confirmed=True, probe=probe)
    assert result.camera_read is True
    assert result.presence == "unknown"
    assert context.snapshot() == ()


def test_failure_and_exception_are_unknown_and_always_revoke():
    from hermes_companion.core.camera_awareness import CameraProbeResult

    controller, context = _controller()
    failed = Probe(CameraProbeResult(camera_read=False, person_detected=False,
                                     observed_at=NOW))
    result = controller.check(companion_id="alpha", session_id="s",
                              bound_session_id="s", mode="pinned",
                              source_id="camera-0", confirmed=True, probe=failed)
    assert (result.camera_read, result.presence) == (False, "unknown")
    assert context.snapshot() == ()

    broken = Probe(error=RuntimeError("camera unavailable"))
    with pytest.raises(RuntimeError):
        controller.check(companion_id="alpha", session_id="s",
                         bound_session_id="s", mode="pinned",
                         source_id="camera-0", confirmed=True, probe=broken)
    assert context.snapshot() == ()
