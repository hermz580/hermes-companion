"""Renderer-side intent bridge.

Small adapter used by the visible pet body. It turns UI gestures into bounded
CompanionIntent records and routes them through the audited core intent layer.
"""
from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from hermes_companion.core.intents import CompanionIntent, IntentDecision, IntentKind, route_intent


@dataclass(frozen=True)
class CompanionIntentEmitter:
    audit_path: Path
    session_id: str = ""

    def show_status(self, *, source: str = "pet") -> IntentDecision:
        return route_intent(
            CompanionIntent(
                kind=IntentKind.SHOW_STATUS,
                source=source,
                confidence=1.0,
                session_id=self.session_id,
            ),
            audit_path=self.audit_path,
        )
