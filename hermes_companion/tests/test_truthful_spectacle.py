"""RED/GREEN contract: spectacle may amplify evidence, never invent it."""
from __future__ import annotations

from pathlib import Path
from tempfile import TemporaryDirectory
from unittest.mock import patch

from hermes_companion.behavior.behavior_engine import BehaviorEngine, Chain
from hermes_companion.core.events import EventKind, SemanticEvent
from hermes_companion.core.state import State
from hermes_companion.plugin import on_subagent_stop
from hermes_companion.renderer.live import EventTail


SUCCESS_POSES = {
    "celebrate", "excited", "spin", "spin_joy", "full_bounce",
    "double_jump", "leap_double_joy", "eyebrow_raise",
}
UNPROVEN_ACTION_POSES = {"repair", "retry", "work", "terminal_work"}


class Clock:
    def __init__(self):
        self.now = 0.0

    def __call__(self):
        return self.now


class Overlay:
    def __init__(self):
        self.played = []

    def play_chain(self, chain, category):
        self.played.append((chain, category))


class Relay:
    def __init__(self, records):
        self.records = list(records)

    def drain(self):
        records, self.records = self.records, []
        return records


class SuppressingEngine:
    def __init__(self):
        self.active = Chain("stale", State.CELEBRATING, 5, [
            {"pose": "celebrate", "duration_ms": 500},
        ])

    def handle(self, _event):
        return None


def test_started_event_combo_never_adds_success_pose():
    clock = Clock()
    engine = BehaviorEngine(seed=1, clock=clock)
    chains = []
    for _ in range(4):
        chain = engine.handle(SemanticEvent(EventKind.TOOL_STARTED, "terminal", "terminal"))
        assert chain is not None
        chains.append(chain)
        clock.now += 0.81
    assert not (set(chains[-1].poses) & SUCCESS_POSES)


def test_failure_and_approval_do_not_claim_unobserved_action():
    failed = BehaviorEngine(seed=1).handle(
        SemanticEvent(EventKind.TOOL_FAILED, "terminal", "terminal")
    )
    approved = BehaviorEngine(seed=1).handle(
        SemanticEvent(EventKind.APPROVAL_APPROVED)
    )
    assert failed is not None and approved is not None
    assert not (set(failed.poses) & UNPROVEN_ACTION_POSES)
    assert not (set(approved.poses) & UNPROVEN_ACTION_POSES)


def test_failed_subagent_emits_failure_not_finished_success():
    records = []
    engine = BehaviorEngine(seed=1)
    with patch("hermes_companion.plugin._get_engine", return_value=engine), \
         patch("hermes_companion.plugin._log_event", side_effect=records.append):
        on_subagent_stop(parent_session_id="s", subagent_id="child", success=False)
    assert records[0]["event"] == EventKind.SUBAGENT_FAILED.value
    assert not (set(records[0]["steps"]) & SUCCESS_POSES)


def test_remote_suppression_never_replays_stale_active_chain():
    overlay = Overlay()
    relay = Relay([{
        "type": "event", "event": "tool.started", "tool": "terminal",
        "category": "terminal", "session_id": "s", "source": "peer",
    }])
    with TemporaryDirectory() as d:
        tail = EventTail(Path(d) / "events.jsonl", overlay,
                         bound_session_id="s", relay=relay, idle=False,
                         auth_key=b"k" * 32)
        tail.engine = SuppressingEngine()
        tail._poll_relay()
    assert overlay.played == []


def test_follow_switch_resets_behavior_context_before_accepting_new_session():
    with TemporaryDirectory() as d:
        tail = EventTail(Path(d) / "events.jsonl", Overlay(),
                         follow=True, idle=False, follow_dwell_s=0.0,
                         auth_key=b"k" * 32)
        tail.engine = BehaviorEngine(seed=1)
        tail.engine._recent_activity.append((0.0, EventKind.TOOL_FINISHED, "terminal"))
        tail.engine._cooldown_until[EventKind.TOOL_STARTED.value] = 999.0
        assert tail._claim_session("session-a")
        tail.engine._recent_activity.append((0.0, EventKind.TOOL_FINISHED, "terminal"))
        tail.engine._cooldown_until[EventKind.TOOL_STARTED.value] = 999.0
        assert tail._claim_session("session-b")
        assert list(tail.engine._recent_activity) == []
        assert tail.engine._cooldown_until == {}
        assert tail.engine.active is None
