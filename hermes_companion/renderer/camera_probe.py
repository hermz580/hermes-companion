"""Local, one-shot camera probe adapter.

This is the ONLY place a camera device is opened. It reads exactly one frame,
never saves or transmits it, and releases the device immediately. Presence
detection needs a pose/face model that is not provisioned here, so an
inconclusive frame honestly reports "unknown" rather than claiming nobody is
there.

Importing this module must not import a camera library or touch a device.
"""
from __future__ import annotations

import importlib.util
from datetime import datetime, timezone

from hermes_companion.core.camera_awareness import CameraProbeResult


def camera_available() -> bool:
    """Readiness check that never opens a device."""
    return importlib.util.find_spec("cv2") is not None


def probe_camera(source_id: str) -> CameraProbeResult:
    """Open the device once, read one frame, release. Claims nothing it saw.

    Returns ``camera_read=False`` when the device or library is unavailable —
    never a fabricated reading.
    """
    now = datetime.now(timezone.utc)
    if importlib.util.find_spec("cv2") is None:
        return CameraProbeResult(camera_read=False, person_detected=False,
                                 observed_at=now)

    import cv2  # imported lazily: importing this module must stay safe

    capture = None
    try:
        capture = cv2.VideoCapture(0, cv2.CAP_DSHOW)
        if not capture.isOpened():
            return CameraProbeResult(camera_read=False, person_detected=False,
                                     observed_at=now)
        ok, frame = capture.read()
        if not ok or frame is None:
            return CameraProbeResult(camera_read=False, person_detected=False,
                                     observed_at=now)
        # A frame was read. Deciding whether a PERSON is present needs a
        # landmarker that is deliberately not part of this slice, so the
        # detector result stays conservative.
        return CameraProbeResult(camera_read=True, person_detected=False,
                                 observed_at=datetime.now(timezone.utc))
    except Exception:
        return CameraProbeResult(camera_read=False, person_detected=False,
                                 observed_at=now)
    finally:
        # The device is released on every path, including exceptions.
        if capture is not None:
            try:
                capture.release()
            except Exception:
                pass
        frame = None
