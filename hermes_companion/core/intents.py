"""Companion intents — audited, content-free requests from the pet to Hermes.

The visible companion should not receive direct tool power. It emits bounded
intents; Hermes or a bridge can decide how to execute them. This module is the
safe edge: unknown or unsafe records are rejected and every decision is logged
without raw payloads, prompts, commands, or tool results.
"""
from __future__ import annotations

import json
import math
import re
from dataclasses import dataclass
from enum import Enum
from pathlib import Path


class IntentKind(str, Enum):
    """Everything the companion may ASK for.

    Each value is a bounded request performed by the companion's own local UI.
    None of them reaches a tool, the network, the filesystem, or another agent;
    the pet has no authority, only a small vocabulary of display actions.
    """
    UNKNOWN = "unknown"
    SHOW_STATUS = "show_status"
    SHOW_MEMORY = "show_memory"
    SHOW_SESSION = "show_session"
    SHOW_FLEET = "show_fleet"
    QUIET = "quiet"
    WAKE = "wake"


@dataclass(frozen=True)
class CompanionIntent:
    kind: IntentKind
    source: str = ""
    confidence: float = 0.0
    session_id: str = ""

    def __post_init__(self) -> None:
        if not isinstance(self.kind, IntentKind):
            raise ValueError("invalid intent kind")
        object.__setattr__(self, "source", _bounded_identifier(
            self.source, "source", 64))
        object.__setattr__(self, "session_id", _bounded_identifier(
            self.session_id, "session_id", 128))
        object.__setattr__(self, "confidence", _clamp_confidence(self.confidence))

    @classmethod
    def from_record(cls, record: dict) -> "CompanionIntent":
        raw_kind = str(record.get("intent") or "")[:64]
        try:
            kind = IntentKind(raw_kind)
        except ValueError:
            kind = IntentKind.UNKNOWN
        confidence = _clamp_confidence(record.get("confidence", 0.0))
        return cls(
            kind=kind,
            source=_identifier_or_empty(record.get("source"), 64),
            confidence=confidence,
            session_id=_identifier_or_empty(record.get("session_id"), 128),
        )


@dataclass(frozen=True)
class IntentDecision:
    allowed: bool
    command: str
    requires_confirmation: bool
    reason: str


def _local(kind_reason: str, command: str) -> IntentDecision:
    return IntentDecision(allowed=True, command=command,
                          requires_confirmation=False,
                          reason=f"safe_local_{kind_reason}")


# Every allowed entry is a LOCAL UI action on the companion's own window. This
# table is the whole of the companion's authority; anything absent falls through
# to the deny-by-default decision below.
_SAFE_DECISIONS: dict[IntentKind, IntentDecision] = {
    IntentKind.SHOW_STATUS: _local("status", "show_status"),
    IntentKind.SHOW_MEMORY: _local("memory", "show_memory"),
    IntentKind.SHOW_SESSION: _local("session", "show_session"),
    IntentKind.SHOW_FLEET: _local("fleet", "show_fleet"),
    IntentKind.QUIET: _local("quiet", "quiet"),
    IntentKind.WAKE: _local("wake", "wake"),
}


_IDENTIFIER = re.compile(r"[A-Za-z0-9][A-Za-z0-9_.:-]*\Z")


def _bounded_identifier(value: object, name: str, limit: int) -> str:
    """Accept only an empty value or a compact, non-content identifier."""
    if value == "":
        return ""
    if (not isinstance(value, str) or len(value) > limit
            or _IDENTIFIER.fullmatch(value) is None):
        raise ValueError(f"invalid {name}")
    return value


def _identifier_or_empty(value: object, limit: int) -> str:
    try:
        return _bounded_identifier(value or "", "identifier", limit)
    except ValueError:
        return ""


def _clamp_confidence(value: object) -> float:
    try:
        conf = float(value)
    except (TypeError, ValueError):
        return 0.0
    if not math.isfinite(conf):
        return 0.0
    if conf < 0.0:
        return 0.0
    if conf > 1.0:
        return 1.0
    return round(conf, 4)


def route_intent(intent: CompanionIntent, *, audit_path: Path) -> IntentDecision:
    decision = _SAFE_DECISIONS.get(
        intent.kind,
        IntentDecision(
            allowed=False,
            command="",
            requires_confirmation=True,
            reason="unknown_intent",
        ),
    )
    _append_audit(intent, decision, audit_path)
    return decision


def _append_audit(intent: CompanionIntent, decision: IntentDecision, audit_path: Path) -> None:
    audit_path.parent.mkdir(parents=True, exist_ok=True)
    record = {
        "type": "companion.intent",
        "intent": intent.kind.value,
        "source": intent.source,
        "confidence": intent.confidence,
        "session_id": intent.session_id,
        "allowed": decision.allowed,
        "command": decision.command,
        "requires_confirmation": decision.requires_confirmation,
        "reason": decision.reason,
    }
    with audit_path.open("a", encoding="utf-8") as f:
        f.write(json.dumps(record, ensure_ascii=False) + "\n")
