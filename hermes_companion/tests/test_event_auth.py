"""Authenticated local-event record contract."""
import json
import os
import stat
from pathlib import Path

from hermes_companion.core.event_auth import (
    load_or_create_event_key,
    sign_record,
    verify_record,
)


def test_signed_record_round_trip_is_content_free_and_tamper_evident():
    key = b'a' * 32
    payload = {
        'event': 'tool.started',
        'tool': 'terminal',
        'category': 'terminal',
        'session_id': 'session-a',
        'task_id': 'task-a',
        'state': 'working',
        'steps': ['run_right', 'terminal_work'],
        'ts': 123.5,
        'seed': 7,
    }
    signed = sign_record(payload, key)
    assert verify_record(signed, key) == payload
    assert set(signed['auth']) == {'v', 'alg', 'mac'}
    assert 'args' not in json.dumps(signed)
    forged = dict(signed)
    forged['tool'] = 'web_search'
    assert verify_record(forged, key) is None


def test_unsigned_and_wrong_key_records_fail_closed():
    payload = {'event': 'agent.started', 'session_id': 'session-a'}
    assert verify_record(payload, b'a' * 32) is None
    assert verify_record(sign_record(payload, b'a' * 32), b'b' * 32) is None


def test_key_is_persistent_and_private_on_posix(tmp_path: Path):
    path = tmp_path / 'event-auth.key'
    first = load_or_create_event_key(path)
    second = load_or_create_event_key(path)
    assert first == second
    assert len(first) == 32
    if os.name != 'nt':
        assert stat.S_IMODE(path.stat().st_mode) == 0o600
