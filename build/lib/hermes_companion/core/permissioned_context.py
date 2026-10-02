"""Local, memory-only context boundary; importing performs no I/O.

No device, capture, document reader, persistence or network adapter is supplied.
Only a trusted local consent controller should hold this object: ``confirmed``
is a caller assertion, not authentication or evidence of a UI consent ceremony.
Adapters must check permission BEFORE acquisition, submit only real observations
with acquisition timestamps, and read a fresh snapshot immediately before use.
Never send these records to the semantic-event log/relay or a model implicitly.

Source IDs must be opaque selection/device handles, not paths, titles or text.
A grant authorizes one exact source, not all documents or the foreground window.
Selecting a different source requires a new grant and revoking the old grant.
Call revoke/revoke_all on consent withdrawal, selection loss, lock or shutdown;
stop any future adapter separately. Already-returned Python objects cannot be
recalled; consumers must not cache them as continuing authority.
"""
from __future__ import annotations

import math
import re
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from enum import Enum
from uuid import uuid4


class ContextScope(str, Enum):
    CAMERA = "camera"
    SELECTED_DOCUMENT = "selected_document"
    SELECTED_WINDOW = "selected_window"


@dataclass(frozen=True)
class ContextGrant:
    grant_id: str
    scope: ContextScope
    source_id: str
    granted_at: datetime
    expires_at: datetime


@dataclass(frozen=True)
class ContextObservation:
    """Coarse source assertion, not verified perception or an instruction.

    No free text, pixels, document body, window title, biometric identity or
    confidence guess is accepted. Missing/stale observations mean unknown,
    never absent. Constructing a record alone does not authorize its use.
    """
    grant_id: str
    scope: ContextScope
    source_id: str
    signal: str
    observed_at: datetime
    received_at: datetime
    stale_at: datetime

    def is_stale(self, now: datetime) -> bool:
        now = _timestamp(now)
        return not self.observed_at <= now < self.stale_at


_SIGNALS = {
    ContextScope.CAMERA: frozenset(("presence_present", "presence_absent")),
    ContextScope.SELECTED_DOCUMENT: frozenset(("selection_ready",)),
    ContextScope.SELECTED_WINDOW: frozenset(("selection_ready",)),
}


def _timestamp(value):
    if not isinstance(value, datetime) or value.tzinfo is None or value.utcoffset() is None:
        raise ValueError("timezone-aware source timestamp required")
    return value.astimezone(timezone.utc)


def _source(scope, source_id):
    if not isinstance(scope, ContextScope):
        raise ValueError("explicit ContextScope required")
    if not isinstance(source_id, str) or not re.fullmatch(r"[A-Za-z0-9_-]{1,64}", source_id):
        raise ValueError("opaque source identifier required; no paths or titles")


def _duration(value, maximum):
    if type(value) not in (int, float) or not math.isfinite(value) or not 0 < value <= maximum:
        raise ValueError("duration outside policy bounds")
    return value


class PermissionedContext:
    """Disabled by default; holds only latest coarse observation per source.

    All calls must be serialized by the owning local controller. Grant lifetime
    is at most one hour; observation lifetime at most one minute, measured from
    the source acquisition time, not ingestion time. At most 32 exact sources
    may be granted. Stale records are dropped on the next boundary operation;
    revocation clears them immediately. Clock rollback revokes everything.
    No grant is persisted. Tests use an injected UTC clock, never sensors.
    """
    def __init__(self, *, clock=None):
        self._clock = clock or (lambda: datetime.now(timezone.utc))
        self._grants = {}
        self._observations = {}
        self._last_observed = {}
        self._last_clock = None

    def _prune(self):
        now = _timestamp(self._clock())
        if self._last_clock is not None and now < self._last_clock:
            self.revoke_all()
        self._last_clock = now
        for key, grant in tuple(self._grants.items()):
            if not grant.granted_at <= now < grant.expires_at:
                del self._grants[key]
                self._last_observed.pop(key, None)
        for key, observation in tuple(self._observations.items()):
            grant = self._grants.get(key)
            if (grant is None or grant.grant_id != observation.grant_id
                    or observation.is_stale(now)):
                del self._observations[key]
        return now

    def grant(self, scope: ContextScope, source_id: str, *, confirmed=False,
              ttl_seconds=300) -> ContextGrant:
        """Call only after explicit consent for this exact source and scope."""
        if confirmed is not True:
            raise PermissionError("explicit local consent required")
        _source(scope, source_id)
        _duration(ttl_seconds, 3600)
        now = self._prune()
        key = (scope, source_id)
        if key not in self._grants and len(self._grants) >= 32:
            raise ValueError("active source capacity reached")
        grant = ContextGrant(uuid4().hex, scope, source_id, now,
                             now + timedelta(seconds=ttl_seconds))
        self._grants[key] = grant
        self._observations.pop(key, None)
        self._last_observed.pop(key, None)
        return grant

    def permission(self, scope: ContextScope, source_id: str) -> ContextGrant | None:
        _source(scope, source_id)
        self._prune()
        return self._grants.get((scope, source_id))

    def revoke(self, grant_id: str) -> bool:
        """Remove the exact grant and its observation immediately; idempotent."""
        for key, grant in tuple(self._grants.items()):
            if grant.grant_id == grant_id:
                del self._grants[key]
                self._observations.pop(key, None)
                self._last_observed.pop(key, None)
                return True
        return False

    def revoke_all(self) -> None:
        self._grants.clear()
        self._observations.clear()
        self._last_observed.clear()

    def observe(self, *, grant_id: str, scope: ContextScope, source_id: str,
                signal: str, observed_at: datetime, max_age_seconds=15) -> ContextObservation:
        """Accept a real adapter's coarse assertion, never acquire or infer one."""
        _source(scope, source_id)
        now = self._prune()
        key = (scope, source_id)
        grant = self._grants.get(key)
        if grant is None or grant.grant_id != grant_id:
            raise PermissionError("no active grant for exact source and scope")
        if not isinstance(signal, str) or signal not in _SIGNALS[scope]:
            raise ValueError("signal not allowed for source scope")
        observed_at = _timestamp(observed_at)
        _duration(max_age_seconds, 60)
        if not grant.granted_at <= observed_at <= now:
            raise ValueError("source timestamp outside current grant or in future")
        stale_at = min(observed_at + timedelta(seconds=max_age_seconds), grant.expires_at)
        if now >= stale_at:
            raise ValueError("observation already stale")
        previous = self._last_observed.get(key)
        if previous is not None and observed_at <= previous:
            raise ValueError("duplicate or out-of-order source timestamp")
        observation = ContextObservation(grant_id, scope, source_id, signal,
                                         observed_at, now, stale_at)
        self._observations[key] = observation
        self._last_observed[key] = observed_at
        return observation

    def snapshot(self) -> tuple[ContextObservation, ...]:
        """Only currently authorized, fresh records; empty means unknown."""
        self._prune()
        return tuple(self._observations.values())
