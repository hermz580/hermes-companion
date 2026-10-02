"""Immutable companion identity/config snapshots, independent of any renderer.

IDs are explicit, stable configuration keys, never inferred from sprite names.
Bindings represent observed/assigned runtime identities, not spawned agents.
Context permissions are declarations for a future broker, NOT authorization to
capture context; this module performs no I/O, context capture, or agent actions.
"""
from __future__ import annotations

import re
from dataclasses import asdict, dataclass
from typing import Mapping


def bounded_text(value: object, name: str, limit: int = 128, *, empty: bool = False) -> str:
    if not isinstance(value, str) or len(value) > limit or (not value and not empty):
        raise ValueError(f'invalid {name}')
    if value != value.strip() or any(not c.isprintable() for c in value):
        raise ValueError(f'invalid {name}')
    return value


@dataclass(frozen=True)
class AgentBinding:
    session_id: str
    agent_id: str = ''

    def __post_init__(self) -> None:
        bounded_text(self.session_id, 'session_id')
        bounded_text(self.agent_id, 'agent_id', empty=True)


@dataclass(frozen=True)
class CompanionConfig:
    companion_id: str
    display_name: str
    role: str
    sprite_asset: str
    binding: AgentBinding | None = None
    context_permissions: tuple[str, ...] = ()

    def __post_init__(self) -> None:
        bounded_text(self.companion_id, 'companion_id', 64)
        if not re.fullmatch(r'[A-Za-z0-9][A-Za-z0-9_.-]*', self.companion_id):
            raise ValueError('invalid companion_id')
        bounded_text(self.display_name, 'display_name', 80)
        bounded_text(self.role, 'role', 80)
        # Opaque local asset reference: resolving/loading is the renderer's job.
        bounded_text(self.sprite_asset, 'sprite_asset', 512)
        if self.binding is not None and not isinstance(self.binding, AgentBinding):
            raise ValueError('invalid binding')
        if not isinstance(self.context_permissions, tuple) or any(
            p not in ('active_window', 'screen', 'microphone', 'camera')
            for p in self.context_permissions
        ) or len(set(self.context_permissions)) != len(self.context_permissions):
            raise ValueError('invalid context_permissions')


class CompanionRegistry:
    """Snapshot registry; replace the snapshot when runtime bindings change.

    Session-only records route only when exactly one companion owns the session.
    Records with an agent ID require an exact session AND agent binding.
    """

    def __init__(self, companions: tuple[CompanionConfig, ...] = ()) -> None:
        self._companions = tuple(companions)
        ids, bindings = set(), set()
        for c in self._companions:
            if not isinstance(c, CompanionConfig):
                raise ValueError('invalid companion')
            if c.companion_id in ids or (c.binding is not None and c.binding in bindings):
                raise ValueError('duplicate companion identity or binding')
            ids.add(c.companion_id)
            if c.binding is not None:
                bindings.add(c.binding)

    def get(self, companion_id: str) -> CompanionConfig | None:
        return next((c for c in self._companions if c.companion_id == companion_id), None)

    def resolve(self, session_id: str, agent_id: str = '') -> CompanionConfig | None:
        if not session_id:
            return None
        matches = [c for c in self._companions if c.binding is not None
                   and c.binding.session_id == session_id
                   and (not agent_id or c.binding.agent_id == agent_id)]
        return matches[0] if len(matches) == 1 else None

    @property
    def companions(self) -> tuple[CompanionConfig, ...]:
        return self._companions

    def to_record(self) -> dict:
        records = []
        for companion in self._companions:
            record = asdict(companion)
            record['context_permissions'] = list(companion.context_permissions)
            records.append(record)
        return {'version': 1, 'companions': records}

    @classmethod
    def from_record(cls, record: Mapping) -> CompanionRegistry:
        if (not isinstance(record, Mapping) or set(record) != {'version', 'companions'}
                or type(record['version']) is not int or record['version'] != 1
                or not isinstance(record['companions'], list)):
            raise ValueError('invalid registry schema')
        companions = []
        for item in record['companions']:
            required = {'companion_id', 'display_name', 'role', 'sprite_asset'}
            if (not isinstance(item, Mapping) or not required <= set(item)
                    or set(item) - required - {'binding', 'context_permissions'}):
                raise ValueError('invalid companion schema')
            binding = item.get('binding')
            if binding is not None and (not isinstance(binding, Mapping)
                    or 'session_id' not in binding
                    or set(binding) - {'session_id', 'agent_id'}):
                raise ValueError('invalid binding schema')
            if not isinstance(item.get('context_permissions', []), list):
                raise ValueError('invalid permissions schema')
            fields = dict(item)
            binding = fields.get('binding')
            fields['binding'] = AgentBinding(**binding) if binding is not None else None
            fields['context_permissions'] = tuple(fields.get('context_permissions', ()))
            companions.append(CompanionConfig(**fields))
        return cls(tuple(companions))
