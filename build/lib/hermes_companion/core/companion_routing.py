"""Content-free, fail-closed routing of actual adapter records to companions.

No timers, inferred work, default broadcast, tool execution, or engine state.
Use one BehaviorEngine per companion in the renderer. Supply records from a
trusted adapter: an ID is a routing key, NOT proof of authentication. Unknown
payload fields are discarded, never retained in decisions or exceptions.
"""
from __future__ import annotations

import math
from dataclasses import dataclass, replace
from typing import Mapping

from .companion_registry import CompanionRegistry, bounded_text
from .events import EventKind, SemanticEvent, classify_tool


@dataclass(frozen=True)
class CompanionDelivery:
    companion_id: str
    event: SemanticEvent
    relation: str = 'activity'
    peer_companion_id: str = ''


@dataclass(frozen=True)
class RoutingDecision:
    deliveries: tuple[CompanionDelivery, ...] = ()
    reason: str = 'unbound_or_ambiguous'


class CompanionEventRouter:
    def __init__(self, registry: CompanionRegistry) -> None:
        self.registry = registry

    def route_record(self, record: Mapping[str, object]) -> RoutingDecision:
        try:
            if not isinstance(record, Mapping):
                raise ValueError('invalid record')
            kind = EventKind(record.get('event'))
            session = bounded_text(record.get('session_id', ''), 'session_id', empty=True)
            agent = bounded_text(record.get('agent_id', ''), 'agent_id', empty=True)
            task = bounded_text(record.get('task_id', ''), 'task_id', empty=True)
            tool = bounded_text(record.get('tool', ''), 'tool', empty=True)
            has_target = 'target_session_id' in record or 'target_agent_id' in record
            target_session, target_agent = '', ''
            if has_target:
                if kind not in (EventKind.SUBAGENT_STARTED, EventKind.SUBAGENT_FINISHED):
                    raise ValueError('unexpected target')
                target_session = bounded_text(record.get('target_session_id'), 'target_session_id')
                target_agent = bounded_text(record.get('target_agent_id'), 'target_agent_id', empty=True)
            ts = record.get('ts', 0.0)
            if type(ts) not in (int, float) or not math.isfinite(ts) or ts < 0:
                raise ValueError('invalid timestamp')
        except (TypeError, ValueError, OverflowError):
            return RoutingDecision(reason='invalid_record')
        companion = self.registry.resolve(session, agent)
        if companion is None:
            return RoutingDecision()
        # Timestamp 0 means absent, not a fabricated observation at parse time.
        event = SemanticEvent(kind, tool, classify_tool(tool), session, task, float(ts))
        if has_target:
            target = self.registry.resolve(target_session, target_agent)
            if target is None:
                return RoutingDecision(reason='unbound_handoff_target')
            if target.companion_id == companion.companion_id:
                return RoutingDecision(reason='invalid_handoff')
            return RoutingDecision((
                CompanionDelivery(companion.companion_id, event, 'handoff_source', target.companion_id),
                CompanionDelivery(target.companion_id, replace(event), 'handoff_target', companion.companion_id),
            ), 'handoff')
        return RoutingDecision((CompanionDelivery(companion.companion_id, event),), 'routed')
