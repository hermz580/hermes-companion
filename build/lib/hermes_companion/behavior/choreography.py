"""Truth-aware choreography plans compiled from already-routed evidence.

This module does not authenticate records.  Its input is a CompanionDelivery,
which must only be created after the caller has verified the signed event
record and routed it to exact companion identities.
"""
from __future__ import annotations

from dataclasses import dataclass
import hashlib

from hermes_companion.behavior.behavior_engine import Chain
from hermes_companion.behavior.behavior_rules import FLY_DOWN, FLY_UP
from hermes_companion.core.companion_routing import CompanionDelivery
from hermes_companion.core.events import EventKind
from hermes_companion.core.state import State


_SUCCESS = {EventKind.TOOL_FINISHED, EventKind.TASK_COMPLETE, EventKind.SUBAGENT_FINISHED}
_FAILURE = {EventKind.TOOL_FAILED, EventKind.SUBAGENT_FAILED}
_ACTIVITY = {
    EventKind.TOOL_STARTED, EventKind.TOOL_PROGRESS, EventKind.AGENT_STARTED,
    EventKind.SUBAGENT_STARTED,
}
_APPROVAL = {
    EventKind.APPROVAL_REQUIRED, EventKind.APPROVAL_APPROVED,
    EventKind.APPROVAL_REJECTED,
}
_RELATIONS = {"activity", "handoff_source", "handoff_target"}


@dataclass(frozen=True)
class ChoreographyPlan:
    evidence_kind: str
    semantic_class: str
    participants: tuple[str, ...]
    relation: str
    correlation_key: str
    state: State
    priority: int
    steps: tuple[dict, ...]

    @property
    def poses(self) -> tuple[str, ...]:
        return tuple(str(step["pose"]) for step in self.steps)

    def to_chain(self) -> Chain:
        return Chain(self.evidence_kind, self.state, self.priority,
                     [dict(step) for step in self.steps])


def _semantic_class(kind: EventKind) -> str:
    if kind in _SUCCESS:
        return "success"
    if kind in _FAILURE:
        return "failure"
    if kind in _ACTIVITY:
        return "activity"
    if kind in _APPROVAL:
        return "approval"
    return "neutral"


def _step(pose: str, duration_ms: int, move: dict | None = None) -> dict:
    return {"pose": pose, "duration_ms": duration_ms, "move": dict(move) if move else None}


def _correlation(delivery: CompanionDelivery, participants: tuple[str, ...]) -> str:
    event = delivery.event
    material = "\0".join((
        event.kind.value, event.session_id, event.task_id,
        *participants,
    )).encode("utf-8")
    return hashlib.blake2s(material, digest_size=12).hexdigest()


def _handoff_steps(relation: str, kind: EventKind) -> tuple[dict, ...]:
    if relation == "handoff_source":
        return (
            _step("open_portal", 500),
            _step("orb_exits", 650),
            _step("fly_up", 700, FLY_UP),
        )
    # The target reacts to an observed handoff; it does not claim child work.
    finish_pose = "excited" if kind == EventKind.SUBAGENT_FINISHED else "head_tilt"
    return (
        _step("fly_down", 700, FLY_DOWN),
        _step("orb_returns", 650),
        _step("absorb", 450),
        _step(finish_pose, 500),
    )


def compile_delivery(delivery: CompanionDelivery, base_chain: Chain | None) -> ChoreographyPlan:
    """Compile deterministic spectacle without changing evidence semantics."""
    if not isinstance(delivery, CompanionDelivery) or base_chain is None:
        raise ValueError("routed delivery and evidence-backed chain required")
    if delivery.relation not in _RELATIONS:
        raise ValueError("unknown choreography relation")

    if delivery.relation == "activity":
        if delivery.peer_companion_id:
            raise ValueError("activity delivery cannot name a peer")
        participants = (delivery.companion_id,)
        steps = tuple(dict(step) for step in base_chain.steps)
        if delivery.event.kind in (EventKind.TOOL_STARTED, EventKind.TOOL_PROGRESS):
            # Airborne movement is decorative amplification of observed work.
            steps = (_step("fly_up", 520, FLY_UP),) + steps + (
                _step("fly_down", 520, FLY_DOWN),
            )
    else:
        if not delivery.peer_companion_id or delivery.peer_companion_id == delivery.companion_id:
            raise ValueError("handoff requires one distinct peer")
        participants = tuple(sorted((delivery.companion_id, delivery.peer_companion_id)))
        steps = _handoff_steps(delivery.relation, delivery.event.kind)

    return ChoreographyPlan(
        evidence_kind=delivery.event.kind.value,
        semantic_class=_semantic_class(delivery.event.kind),
        participants=participants,
        relation=delivery.relation,
        correlation_key=_correlation(delivery, participants),
        state=base_chain.state,
        priority=base_chain.priority,
        steps=steps,
    )
