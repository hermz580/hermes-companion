from __future__ import annotations

import json

from hermes_companion.renderer.intent_bridge import CompanionIntentEmitter
from hermes_companion.renderer.petdex_overlay import PetdexOverlay


def test_pet_double_click_emits_show_status_intent(tmp_path):
    calls = []

    class FakeEmitter:
        def show_status(self, *, source):
            calls.append(source)

    class FakeOverlay:
        intent_emitter = FakeEmitter()

    PetdexOverlay._emit_show_status_intent(FakeOverlay())

    assert calls == ["double_click"]


def test_pet_emitter_records_double_click_show_status_intent(tmp_path):
    audit_path = tmp_path / "intents.jsonl"
    emitter = CompanionIntentEmitter(audit_path=audit_path, session_id="s-pet")

    decision = emitter.show_status(source="double_click")

    assert decision.allowed is True
    assert decision.command == "show_status"
    record = json.loads(audit_path.read_text(encoding="utf-8"))
    assert record["type"] == "companion.intent"
    assert record["intent"] == "show_status"
    assert record["source"] == "double_click"
    assert record["session_id"] == "s-pet"
    assert record["requires_confirmation"] is False
