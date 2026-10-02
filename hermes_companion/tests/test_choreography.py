"""Choreography contracts: spectacle is compiled from routed evidence."""
from __future__ import annotations

import pytest

from hermes_companion.behavior.behavior_engine import BehaviorEngine
from hermes_companion.core.companion_routing import CompanionDelivery
from hermes_companion.core.events import EventKind, SemanticEvent


def _chain(kind, category="terminal"):
    return BehaviorEngine(seed=7).handle(SemanticEvent(kind, "terminal", category))


def test_real_started_event_gets_airborne_work_flourish_without_success_claim():
    from hermes_companion.behavior.choreography import compile_delivery

    event = SemanticEvent(EventKind.TOOL_STARTED, "terminal", "terminal", "s")
    plan = compile_delivery(CompanionDelivery("alpha", event), _chain(EventKind.TOOL_STARTED))
    assert plan.semantic_class == "activity"
    assert plan.evidence_kind == EventKind.TOOL_STARTED.value
    assert plan.participants == ("alpha",)
    assert "fly_up" in plan.poses and "fly_down" in plan.poses
    assert not ({"celebrate", "excited", "spin", "full_bounce"} & set(plan.poses))


def test_failure_plan_contains_reaction_only_and_no_success_or_repair_claim():
    from hermes_companion.behavior.choreography import compile_delivery

    event = SemanticEvent(EventKind.TOOL_FAILED, "terminal", "terminal", "s")
    plan = compile_delivery(CompanionDelivery("alpha", event), _chain(EventKind.TOOL_FAILED))
    assert plan.semantic_class == "failure"
    assert not ({"repair", "retry", "work", "celebrate", "excited"} & set(plan.poses))


def test_handoff_compiles_correlated_source_and_target_roles():
    from hermes_companion.behavior.choreography import compile_delivery

    event = SemanticEvent(EventKind.SUBAGENT_STARTED, session_id="parent")
    source = compile_delivery(
        CompanionDelivery("alpha", event, "handoff_source", "beta"),
        _chain(EventKind.SUBAGENT_STARTED, ""),
    )
    target = compile_delivery(
        CompanionDelivery("beta", event, "handoff_target", "alpha"),
        _chain(EventKind.SUBAGENT_STARTED, ""),
    )
    assert source.participants == target.participants == ("alpha", "beta")
    assert source.relation == "handoff_source"
    assert target.relation == "handoff_target"
    assert source.correlation_key == target.correlation_key
    assert source.poses != target.poses
    assert "orb_exits" in source.poses
    assert "orb_returns" in target.poses


def test_compiler_is_deterministic_and_rejects_untrusted_relation_shape():
    from hermes_companion.behavior.choreography import compile_delivery

    event = SemanticEvent(EventKind.TOOL_FINISHED, "terminal", "terminal", "s", "task")
    delivery = CompanionDelivery("alpha", event)
    assert compile_delivery(delivery, _chain(EventKind.TOOL_FINISHED)) == compile_delivery(
        delivery, _chain(EventKind.TOOL_FINISHED)
    )
    with pytest.raises(ValueError):
        compile_delivery(CompanionDelivery("alpha", event, "broadcast", "beta"),
                         _chain(EventKind.TOOL_FINISHED))


def test_missing_peer_never_invents_two_pet_choreography():
    from hermes_companion.behavior.choreography import compile_delivery

    event = SemanticEvent(EventKind.SUBAGENT_STARTED, session_id="parent")
    with pytest.raises(ValueError):
        compile_delivery(CompanionDelivery("alpha", event, "handoff_source", ""),
                         _chain(EventKind.SUBAGENT_STARTED, ""))


def test_live_alpha_executes_compiled_airborne_plan_from_signed_event():
    from pathlib import Path
    from tempfile import TemporaryDirectory

    from hermes_companion.core.event_auth import sign_record
    from hermes_companion.renderer.live import EventTail

    class Overlay:
        def __init__(self):
            self.played = []

        def play_chain(self, chain, category):
            self.played.append((chain, category))

    key = b"k" * 32
    with TemporaryDirectory() as d:
        overlay = Overlay()
        tail = EventTail(Path(d) / "events.jsonl", overlay,
                         bound_session_id="s", companion_id="alpha",
                         idle=False, auth_key=key)
        tail._handle_record(sign_record({
            "event": "tool.started", "tool": "terminal",
            "category": "terminal", "session_id": "s",
        }, key))
    assert len(overlay.played) == 1
    chain, category = overlay.played[0]
    assert category == "terminal"
    assert "fly_up" in chain.poses and "fly_down" in chain.poses


def test_multi_pet_model_preserves_handoff_roles_in_compiled_plans():
    from hermes_companion.renderer.multi_pet import FleetModel, PetBinding

    model = FleetModel([PetBinding("Alpha", "parent"), PetBinding("Beta", "child")])
    plans = model.accept({
        "event": "agent.subagent_spawned",
        "session_id": "parent",
        "target_session_id": "child",
        "target_agent_id": "",
        "ts": 1.0,
    }, now=1.0)
    assert set(plans) == {0, 1}
    assert plans[0].relation == "handoff_source"
    assert plans[1].relation == "handoff_target"
    assert plans[0].correlation_key == plans[1].correlation_key
    assert "orb_exits" in plans[0].poses
    assert "orb_returns" in plans[1].poses
