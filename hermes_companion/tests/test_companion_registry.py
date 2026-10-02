from __future__ import annotations

import pytest


def test_registry_round_trip_preserves_identity_and_binding():
    from hermes_companion.core.companion_registry import CompanionConfig, CompanionRegistry, AgentBinding

    config = CompanionConfig('builder', 'Builder', 'implementation', 'petdex:astro',
                             AgentBinding('session-1', 'agent-1'))
    registry = CompanionRegistry((config,))
    restored = CompanionRegistry.from_record(registry.to_record())
    assert restored.get('builder') == config
    assert restored.resolve('session-1', 'agent-1') == config
    assert restored.resolve('session-1', 'wrong-agent') is None
    assert restored.resolve('different-session', 'agent-1') is None
    assert restored.resolve('', '') is None
    assert config.context_permissions == ()


@pytest.mark.parametrize('field,value', [
    ('companion_id', ''), ('companion_id', 'bad id'), ('companion_id', 3),
    ('role', ''), ('display_name', 'bad\nname'), ('sprite_asset', ''),
    ('binding', {'session_id': 's'}), ('context_permissions', ['screen']),
    ('context_permissions', ('unknown',)),
])
def test_invalid_config_rejected(field, value):
    from hermes_companion.core.companion_registry import CompanionConfig
    fields = dict(companion_id='one', display_name='One', role='builder', sprite_asset='petdex:astro')
    fields[field] = value
    with pytest.raises(ValueError):
        CompanionConfig(**fields)


def test_duplicate_identity_or_binding_rejected_and_ambiguous_session_unrouted():
    from hermes_companion.core.companion_registry import CompanionConfig, CompanionRegistry, AgentBinding
    a = CompanionConfig('a', 'A', 'build', 'petdex:a', AgentBinding('s', 'a'))
    b = CompanionConfig('b', 'B', 'review', 'petdex:b', AgentBinding('s', 'b'))
    assert CompanionRegistry((a, b)).resolve('s') is None
    assert CompanionRegistry((a, b)).resolve('s', 'b') == b
    with pytest.raises(ValueError):
        CompanionRegistry((a, a))
    with pytest.raises(ValueError):
        CompanionRegistry((a, CompanionConfig('c', 'C', 'review', 'petdex:c', a.binding)))
    with pytest.raises(ValueError):
        AgentBinding('')


@pytest.mark.parametrize('record', [
    {}, {'version': True, 'companions': []}, {'version': 2, 'companions': []},
    {'version': 1, 'companions': [], 'extra': 1},
    {'version': 1, 'companions': {}},
    {'version': 1, 'companions': [{'companion_id': 'a'}]},
])
def test_config_schema_fail_closed(record):
    from hermes_companion.core.companion_registry import CompanionRegistry
    with pytest.raises(ValueError):
        CompanionRegistry.from_record(record)
