"""Truth contract for the visible single-companion event bridge."""
import json
from pathlib import Path
from tempfile import TemporaryDirectory

from hermes_companion.core.event_auth import sign_record
from hermes_companion.renderer.live import EventTail, bound_session_for_companion


_EVENT_KEY = b'k' * 32


class Overlay:
    def __init__(self):
        self.played = []
        self.enqueued = []

    def play_chain(self, chain, category):
        self.played.append((chain, category))

    def enqueue(self, beats, replace=False):
        self.enqueued.append((beats, replace))


class Engine:
    def __init__(self):
        self.events = []
        self.active = None

    def handle(self, event):
        self.events.append(event)
        return None

    def idle_tick(self, _dt):
        raise AssertionError('semantic idle actions must never run in live truth mode')


def test_binding_resolver_requires_one_exact_active_identity():
    with TemporaryDirectory() as d:
        p = Path(d) / 'bindings.json'
        p.write_text(json.dumps({'version': 1, 'bindings': [
            {'companion_id': 'the-alpha-and', 'session_id': 'session-a', 'task_id': None},
        ]}), encoding='utf-8')
        assert bound_session_for_companion('the-alpha-and', p) == 'session-a'
        assert bound_session_for_companion('other', p) is None
        p.write_text(json.dumps({'version': 1, 'bindings': [
            {'companion_id': 'the-alpha-and', 'session_id': 'session-a'},
            {'companion_id': 'the-alpha-and', 'session_id': 'session-b'},
        ]}), encoding='utf-8')
        assert bound_session_for_companion('the-alpha-and', p) is None


def test_single_pet_rejects_missing_and_other_session_events():
    with TemporaryDirectory() as d:
        overlay = Overlay()
        tail = EventTail(Path(d) / 'events.jsonl', overlay,
                         bound_session_id='session-a', idle=False,
                         auth_key=_EVENT_KEY)
        tail.engine = Engine()
        tail._handle_record({'event': 'tool.started', 'tool': 'terminal'})
        tail._handle_record({'event': 'tool.started', 'tool': 'terminal',
                             'session_id': 'session-b'})
        assert tail.engine.events == []
        assert overlay.played == []


def test_single_pet_accepts_only_its_exact_bound_session():
    with TemporaryDirectory() as d:
        overlay = Overlay()
        tail = EventTail(Path(d) / 'events.jsonl', overlay,
                         bound_session_id='session-a', idle=False,
                         auth_key=_EVENT_KEY)
        tail.engine = Engine()
        tail._handle_record(sign_record(
            {'event': 'tool.started', 'tool': 'terminal', 'session_id': 'session-a'},
            _EVENT_KEY))
        assert len(tail.engine.events) == 1
        assert tail.engine.events[0].session_id == 'session-a'


def test_single_pet_rejects_unsigned_and_forged_local_events():
    with TemporaryDirectory() as d:
        overlay = Overlay()
        tail = EventTail(Path(d) / 'events.jsonl', overlay,
                         bound_session_id='session-a', idle=False,
                         auth_key=_EVENT_KEY)
        tail.engine = Engine()
        unsigned = {'event': 'tool.started', 'tool': 'terminal',
                    'session_id': 'session-a'}
        tail._handle_record(unsigned)
        tail._handle_record(sign_record(unsigned, b'x' * 32))
        assert tail.engine.events == []
        assert overlay.played == []


def test_relay_rejects_other_companion_session():
    class Relay:
        def drain(self):
            return [{'type': 'event', 'event': 'tool.started', 'tool': 'web_search',
                     'session_id': 'session-b', 'source': 'another-machine'}]

    with TemporaryDirectory() as d:
        overlay = Overlay()
        tail = EventTail(Path(d) / 'events.jsonl', overlay,
                         bound_session_id='session-a', relay=Relay(), idle=False,
                         auth_key=_EVENT_KEY)
        tail.engine = Engine()
        tail._poll_relay()
        assert tail.engine.events == []
        assert overlay.played == []


def test_live_truth_mode_never_generates_semantic_idle_actions():
    with TemporaryDirectory() as d:
        tail = EventTail(Path(d) / 'events.jsonl', Overlay(),
                         bound_session_id='session-a', idle=False,
                         auth_key=_EVENT_KEY)
        tail.engine = Engine()
        tail._poll_idle()
