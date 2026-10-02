"""Explicit-consent, one-shot camera-awareness control boundary.

No camera library is imported here.  The caller must supply a local probe only
after a visible consent ceremony.  Frames never enter this controller; it
accepts only a strict coarse result and revokes the temporary grant in finally.
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
import re
from typing import Callable

from hermes_companion.core.permissioned_context import ContextScope, PermissionedContext


_ID = re.compile(r"[A-Za-z0-9][A-Za-z0-9_.-]{0,63}\Z")


@dataclass(frozen=True)
class CameraProbeResult:
    camera_read: bool
    person_detected: bool
    observed_at: datetime

    def __post_init__(self) -> None:
        if type(self.camera_read) is not bool or type(self.person_detected) is not bool:
            raise ValueError("camera probe flags must be booleans")
        if not isinstance(self.observed_at, datetime) or self.observed_at.tzinfo is None:
            raise ValueError("camera probe timestamp must be timezone-aware")
        if self.person_detected and not self.camera_read:
            raise ValueError("detection requires a successful camera read")


@dataclass(frozen=True)
class CameraCheckResult:
    camera_read: bool
    presence: str
    observed_at: datetime


def camera_status() -> dict[str, bool]:
    """Import-safe default status; checking it never opens or imports a camera."""
    return {"enabled": False, "camera_opened": False}


class CameraAwarenessController:
    """Authorize exactly one pinned-session probe, then revoke immediately."""

    def __init__(self, *, context: PermissionedContext | None = None) -> None:
        self.context = context or PermissionedContext()

    def check(self, *, companion_id: str, session_id: str,
              bound_session_id: str, mode: str, source_id: str,
              confirmed: bool, probe: Callable[[str], CameraProbeResult]) -> CameraCheckResult:
        if confirmed is not True:
            raise PermissionError("explicit local camera consent required")
        if mode != "pinned":
            raise PermissionError("one-shot camera awareness requires pinned mode")
        if (not isinstance(session_id, str) or not session_id
                or session_id != bound_session_id):
            raise PermissionError("camera check requires the exact pinned session")
        if not isinstance(companion_id, str) or not _ID.fullmatch(companion_id):
            raise ValueError("invalid companion identity")
        if not isinstance(source_id, str) or not re.fullmatch(r"[A-Za-z0-9_-]{1,64}", source_id):
            raise ValueError("invalid opaque camera source")
        if not callable(probe):
            raise TypeError("camera probe must be callable")

        grant = self.context.grant(ContextScope.CAMERA, source_id,
                                   confirmed=True, ttl_seconds=30)
        try:
            result = probe(source_id)
            if not isinstance(result, CameraProbeResult):
                raise ValueError("invalid camera probe result")
            presence = "present" if result.camera_read and result.person_detected else "unknown"
            if presence == "present":
                self.context.observe(
                    grant_id=grant.grant_id,
                    scope=ContextScope.CAMERA,
                    source_id=source_id,
                    signal="presence_present",
                    observed_at=result.observed_at,
                    max_age_seconds=15,
                )
            return CameraCheckResult(result.camera_read, presence, result.observed_at)
        finally:
            self.context.revoke(grant.grant_id)
