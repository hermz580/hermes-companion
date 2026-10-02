"""Dedicated authenticated plane for decorative companion social gestures.

These records are not work evidence, agent messages, intents, or memory.  The
schema deliberately has no free-text or task/session fields.
"""
from __future__ import annotations

from collections import deque
from dataclasses import dataclass
import hashlib
import hmac
import json
import re
import secrets
from typing import Mapping


DOMAIN = b"hermes-companion-social-signal-v1\0"
TYPE = "companion.social_signal.v1"
KINDS = frozenset({
    "social.wave", "social.boop", "social.play_bow",
    "social.happy_hop", "social.sleepy_blink", "social.mirror_pose",
})
_FIELDS = frozenset({
    "type", "signal_id", "sequence", "kind", "source_companion_id",
    "target_companion_id", "created_at_ms", "expires_at_ms", "auth",
})
_AUTH_FIELDS = frozenset({"v", "alg", "signature"})
_ID = re.compile(r"[A-Za-z0-9][A-Za-z0-9_.-]{0,63}\Z")
_HEX32 = re.compile(r"[0-9a-f]{32}\Z")


@dataclass(frozen=True)
class SocialSignal:
    signal_id: str
    sequence: int
    kind: str
    source_companion_id: str
    target_companion_id: str
    created_at_ms: int
    expires_at_ms: int


@dataclass(frozen=True)
class SignalDecision:
    decision: str
    signal: SocialSignal | None = None


def _unsigned(record: Mapping[str, object]) -> dict:
    return {key: record[key] for key in sorted(_FIELDS - {"auth"})}


def _mac(record: Mapping[str, object], key: bytes) -> str:
    body = json.dumps(_unsigned(record), sort_keys=True, separators=(",", ":"),
                      ensure_ascii=True).encode("ascii")
    return hmac.new(key, DOMAIN + body, hashlib.sha256).hexdigest()


def _validate_shape(record: object) -> SocialSignal | None:
    if not isinstance(record, Mapping) or set(record) != _FIELDS:
        return None
    auth = record.get("auth")
    if not isinstance(auth, Mapping) or set(auth) != _AUTH_FIELDS:
        return None
    if auth.get("v") != 1 or auth.get("alg") != "hmac-sha256":
        return None
    if not isinstance(auth.get("signature"), str) or not re.fullmatch(r"[0-9a-f]{64}", auth["signature"]):
        return None
    if record.get("type") != TYPE:
        return None
    sid = record.get("signal_id")
    kind = record.get("kind")
    source = record.get("source_companion_id")
    target = record.get("target_companion_id")
    seq = record.get("sequence")
    created = record.get("created_at_ms")
    expires = record.get("expires_at_ms")
    if (not isinstance(sid, str) or not _HEX32.fullmatch(sid)
            or kind not in KINDS
            or not isinstance(source, str) or not _ID.fullmatch(source)
            or not isinstance(target, str) or not _ID.fullmatch(target)
            or source == target
            or type(seq) is not int or not 0 <= seq < 2**63
            or type(created) is not int or created < 0
            or type(expires) is not int or expires <= created
            or expires - created > 10_000):
        return None
    return SocialSignal(sid, seq, kind, source, target, created, expires)


def create_signal(*, kind: str, source_companion_id: str,
                  target_companion_id: str, sequence: int, now_ms: int,
                  ttl_ms: int, key: bytes, signal_id: str | None = None) -> dict:
    """Validate and sign one exact, content-free social signal."""
    record = {
        "type": TYPE,
        "signal_id": signal_id or secrets.token_hex(16),
        "sequence": sequence,
        "kind": kind,
        "source_companion_id": source_companion_id,
        "target_companion_id": target_companion_id,
        "created_at_ms": now_ms,
        "expires_at_ms": now_ms + ttl_ms if type(now_ms) is int and type(ttl_ms) is int else -1,
        "auth": {"v": 1, "alg": "hmac-sha256", "signature": "0" * 64},
    }
    if not isinstance(key, bytes) or len(key) < 32 or _validate_shape(record) is None:
        raise ValueError("invalid social signal")
    record["auth"]["signature"] = _mac(record, key)
    return record


def verify_signal(record: object, *, keys: Mapping[str, bytes],
                  companion_ids: set[str] | frozenset[str], now_ms: int) -> SocialSignal | None:
    """Verify source attribution, exact target, lifetime, and signature."""
    signal = _validate_shape(record)
    if signal is None or type(now_ms) is not int:
        return None
    if signal.source_companion_id not in companion_ids or signal.target_companion_id not in companion_ids:
        return None
    key = keys.get(signal.source_companion_id)
    if not isinstance(key, bytes) or len(key) < 32:
        return None
    supplied = record["auth"]["signature"]
    if not hmac.compare_digest(supplied, _mac(record, key)):
        return None
    if signal.created_at_ms > now_ms + 2_000 or now_ms >= signal.expires_at_ms:
        return None
    return signal


class SocialSignalGate:
    """Bounded replay/cooldown guard. Receipt never emits a reply."""

    def __init__(self, *, keys: Mapping[str, bytes], companion_ids,
                 pair_cooldown_ms: int = 2_000) -> None:
        self.keys = dict(keys)
        self.companion_ids = frozenset(companion_ids)
        self.pair_cooldown_ms = pair_cooldown_ms
        self._seen_ids: deque[tuple[int, str]] = deque(maxlen=512)
        self._highest_sequence: dict[str, int] = {}
        self._last_pair: dict[tuple[str, str, str], int] = {}

    def accept(self, record: object, *, now_ms: int) -> SignalDecision:
        signal = verify_signal(record, keys=self.keys,
                               companion_ids=self.companion_ids, now_ms=now_ms)
        if signal is None:
            return SignalDecision("invalid")
        self._prune(now_ms)
        if any(signal.signal_id == sid for _until, sid in self._seen_ids):
            return SignalDecision("replayed")
        if signal.sequence <= self._highest_sequence.get(signal.source_companion_id, -1):
            return SignalDecision("sequence_replay")
        self._seen_ids.append((now_ms + 600_000, signal.signal_id))
        self._highest_sequence[signal.source_companion_id] = signal.sequence
        pair = (signal.source_companion_id, signal.target_companion_id, signal.kind)
        if now_ms - self._last_pair.get(pair, -10**18) < self.pair_cooldown_ms:
            return SignalDecision("cooldown")
        self._last_pair[pair] = now_ms
        return SignalDecision("accepted", signal)

    def _prune(self, now_ms: int) -> None:
        while self._seen_ids and self._seen_ids[0][0] <= now_ms:
            self._seen_ids.popleft()
