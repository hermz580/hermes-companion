from __future__ import annotations

import pytest


def test_delivery_drives_only_its_real_engine():
    from hermes_companion.behavior.behavior_engine import BehaviorEngine
    from hermes_companion.core.companion_routing import CompanionEventRouter
    engines = {c.companion_id: BehaviorEngine(seed=42) for c in registry().companions}
    lead_state = engines['lead'].state
    result = CompanionEventRouter(registry()).route_record(dict(
        event='tool.started', session_id='child', agent_id='b', tool='terminal'))
    for delivery in result.deliveries:
        chain = engines[delivery.companion_id].handle(delivery.event)
        assert chain is not None
        assert chain.poses
    assert engines['lead'].state == lead_state
    assert engines['lead'].active is None
    assert engines['worker'].active is not None


def test_self_handoff_and_invalid_top_level_rejected():
    from hermes_companion.core.companion_routing import CompanionEventRouter
    router = CompanionEventRouter(registry())
    assert router.route_record(None).reason == 'invalid_record'
    assert router.route_record(dict(event='agent.subagent_spawned', session_id='s', agent_id='a',
        target_session_id='s', target_agent_id='a')).reason == 'invalid_handoff'


@pytest.mark.parametrize('kind', ['agent.subagent_spawned', 'agent.subagent_finished'])
def test_explicit_observed_handoff_routes_both_ends(kind):
    from hermes_companion.core.companion_routing import CompanionEventRouter
    router = CompanionEventRouter(registry())
    record = dict(event=kind, session_id='s', agent_id='a', task_id='task-1',
                  target_session_id='child', target_agent_id='b', ts=1)
    result = router.route_record(record)
    assert result.reason == 'handoff'
    assert [(d.companion_id, d.peer_companion_id, d.relation) for d in result.deliveries] == [
        ('lead', 'worker', 'handoff_source'), ('worker', 'lead', 'handoff_target')]
    assert all(d.event.kind.value == kind for d in result.deliveries)
    assert all(d.event.session_id == 's' for d in result.deliveries)  # original evidence, not invented child work
    assert result.deliveries[0].event is not result.deliveries[1].event
    record['target_agent_id'] = 'unknown'
    assert router.route_record(record).reason == 'unbound_handoff_target'
    assert not router.route_record(record).deliveries


@pytest.mark.parametrize('patch', [
    {'ts': float('nan')}, {'ts': float('inf')}, {'ts': True}, {'ts': -1},
    {'tool': {}}, {'session_id': 's\n'}, {'agent_id': 'x' * 129},
    {'target_session_id': 'child'}, {'target_agent_id': 'b'},
    {'target_session_id': 'child', 'target_agent_id': 'b'},
])
def test_malformed_or_non_handoff_targets_fail_closed(patch):
    from hermes_companion.core.companion_routing import CompanionEventRouter
    record = dict(event='tool.started', session_id='s', agent_id='a')
    record.update(patch)
    assert CompanionEventRouter(registry()).route_record(record).reason == 'invalid_record'


def test_missing_handoff_peer_does_not_invent_one():
    from hermes_companion.core.companion_routing import CompanionEventRouter
    result = CompanionEventRouter(registry()).route_record(dict(event='agent.subagent_spawned', session_id='s'))
    assert result.reason == 'routed'
    assert [d.companion_id for d in result.deliveries] == ['lead']


from hermes_companion.core.companion_registry import AgentBinding, CompanionConfig, CompanionRegistry


def registry():
    return CompanionRegistry((
        CompanionConfig('lead', 'Lead', 'coordination', 'petdex:astro', AgentBinding('s', 'a')),
        CompanionConfig('worker', 'Worker', 'implementation', 'petdex:samurai', AgentBinding('child', 'b')),
    ))


def test_real_event_routes_only_to_bound_companion_without_payload():
    from hermes_companion.core.companion_routing import CompanionEventRouter
    router = CompanionEventRouter(registry())
    result = router.route_record(dict(event='tool.started', tool='terminal', session_id='child',
                                      agent_id='b', ts=123.0, prompt='SECRET', category='fake'))
    assert result.reason == 'routed'
    assert len(result.deliveries) == 1
    delivery = result.deliveries[0]
    assert delivery.companion_id == 'worker'
    assert delivery.event.category == 'terminal'
    assert delivery.event.ts == 123.0
    assert 'SECRET' not in repr(result)
    assert not router.route_record(dict(event='tool.started', session_id='unknown')).deliveries
    assert not router.route_record(dict(event='tool.started')).deliveries
    assert not router.route_record(dict(event='tool.started', session_id='s', agent_id='b')).deliveries
    assert router.route_record(dict(event='not-real', session_id='s')).reason == 'invalid_record'
