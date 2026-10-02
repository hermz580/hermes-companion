"""Authenticated social gestures are decorative, content-free, and isolated."""
from __future__ import annotations

import copy

import pytest


KEYS = {"alpha": b"a" * 32, "beta": b"b" * 32}
IDS = frozenset(KEYS)


def _signal(now=1_000, sequence=1, kind="social.wave", signal_id=None):
    from hermes_companion.core.social_signals import create_signal

    return create_signal(
        kind=kind,
        source_companion_id="alpha",
        target_companion_id="beta",
        sequence=sequence,
        now_ms=now,
        ttl_ms=5_000,
        key=KEYS["alpha"],
        signal_id=signal_id or ("0" * 31 + f"{sequence:x}"),
    )


def test_signed_round_trip_is_exact_and_content_free():
    from hermes_companion.core.social_signals import verify_signal

    record = _signal()
    verified = verify_signal(record, keys=KEYS, companion_ids=IDS, now_ms=2_000)
    assert verified is not None
    assert verified.kind == "social.wave"
    assert verified.source_companion_id == "alpha"
    assert verified.target_companion_id == "beta"
    serialized = repr(record)
    for forbidden in ("session", "task", "agent", "tool", "prompt", "command", "result", "message"):
        assert forbidden not in serialized.lower()


def test_tampering_unknown_fields_and_wrong_source_key_fail_closed():
    from hermes_companion.core.social_signals import verify_signal

    original = _signal()
    for field, value in (
        ("kind", "social.boop"),
        ("target_companion_id", "alpha"),
        ("sequence", 2),
        ("expires_at_ms", 9_999),
    ):
        altered = copy.deepcopy(original)
        altered[field] = value
        assert verify_signal(altered, keys=KEYS, companion_ids=IDS, now_ms=2_000) is None
    extra = copy.deepcopy(original)
    extra["payload"] = "hello"
    assert verify_signal(extra, keys=KEYS, companion_ids=IDS, now_ms=2_000) is None
    assert verify_signal(original, keys={"alpha": KEYS["beta"]},
                         companion_ids=IDS, now_ms=2_000) is None


def test_unknown_self_missing_and_expired_targets_fail_closed():
    from hermes_companion.core.social_signals import create_signal, verify_signal

    with pytest.raises(ValueError):
        create_signal(kind="social.wave", source_companion_id="alpha",
                      target_companion_id="alpha", sequence=1, now_ms=0,
                      ttl_ms=1000, key=KEYS["alpha"])
    assert verify_signal(_signal(), keys=KEYS, companion_ids={"alpha"}, now_ms=2_000) is None
    assert verify_signal(_signal(), keys=KEYS, companion_ids=IDS, now_ms=7_000) is None


def test_gate_blocks_replay_sequence_rollback_and_pair_cooldown():
    from hermes_companion.core.social_signals import SocialSignalGate

    gate = SocialSignalGate(keys=KEYS, companion_ids=IDS)
    first = _signal(now=1_000, sequence=1)
    assert gate.accept(first, now_ms=1_100).decision == "accepted"
    assert gate.accept(first, now_ms=1_200).decision == "replayed"
    second = _signal(now=1_300, sequence=2)
    assert gate.accept(second, now_ms=1_400).decision == "cooldown"
    third = _signal(now=3_200, sequence=3)
    assert gate.accept(third, now_ms=3_300).decision == "accepted"
    old = _signal(now=3_400, sequence=2, signal_id="f" * 32)
    assert gate.accept(old, now_ms=3_500).decision == "sequence_replay"


def test_social_signal_is_not_a_work_event_or_intent():
    from hermes_companion.core.events import EventKind
    from hermes_companion.core.intents import IntentKind

    with pytest.raises(ValueError):
        EventKind("social.wave")
    with pytest.raises(ValueError):
        IntentKind("social.wave")
