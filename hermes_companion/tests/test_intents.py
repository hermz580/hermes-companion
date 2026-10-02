from __future__ import annotations

import json

import pytest

from hermes_companion.core.intents import (
    CompanionIntent,
    IntentDecision,
    IntentKind,
    route_intent,
)


def test_safe_status_intent_routes_to_audited_command(tmp_path):
    audit_path = tmp_path / "intents.jsonl"
    intent = CompanionIntent(
        kind=IntentKind.SHOW_STATUS,
        source="double_click",
        confidence=0.91,
        session_id="s1",
    )

    decision = route_intent(intent, audit_path=audit_path)

    assert decision == IntentDecision(
        allowed=True,
        command="show_status",
        requires_confirmation=False,
        reason="safe_local_status",
    )
    records = [json.loads(line) for line in audit_path.read_text(encoding="utf-8").splitlines()]
    assert records == [
        {
            "type": "companion.intent",
            "intent": "show_status",
            "source": "double_click",
            "confidence": 0.91,
            "session_id": "s1",
            "allowed": True,
            "command": "show_status",
            "requires_confirmation": False,
            "reason": "safe_local_status",
        }
    ]


def test_unknown_intent_is_rejected_and_audited_without_raw_payload(tmp_path):
    audit_path = tmp_path / "intents.jsonl"

    intent = CompanionIntent.from_record(
        {
            "intent": "delete_everything",
            "source": "webpage",
            "confidence": 1.7,
            "session_id": "s2",
            "prompt": "raw private content must not be stored",
            "command": "rm -rf C:/Users/me",
        }
    )
    decision = route_intent(intent, audit_path=audit_path)

    assert decision.allowed is False
    assert decision.command == ""
    assert decision.requires_confirmation is True
    assert decision.reason == "unknown_intent"

    record = json.loads(audit_path.read_text(encoding="utf-8"))
    assert record["intent"] == "unknown"
    assert record["source"] == "webpage"
    assert record["confidence"] == 1.0
    assert record["allowed"] is False
    assert "prompt" not in record
    assert "rm -rf" not in json.dumps(record)


def test_cli_intent_command_writes_audit_record(tmp_path, capsys):
    from hermes_companion.cli.emit import main

    audit_path = tmp_path / "intent-audit.jsonl"

    exit_code = main([
        "intent",
        "show_status",
        "--source",
        "pet_menu",
        "--confidence",
        "0.77",
        "--session-id",
        "s3",
        "--audit",
        str(audit_path),
    ])

    assert exit_code == 0
    assert "show_status -> allowed" in capsys.readouterr().out
    record = json.loads(audit_path.read_text(encoding="utf-8"))
    assert record["type"] == "companion.intent"
    assert record["intent"] == "show_status"
    assert record["source"] == "pet_menu"
    assert record["allowed"] is True


# ---------------------------------------------------------------------------
# Bounded agency: the pet may ASK for local UI actions, never for execution.
# ---------------------------------------------------------------------------

# Commands the companion is allowed to request. Every one is a local display
# action performed by the companion's own window — none touches a tool, the
# network, the filesystem, or another agent.
LOCAL_UI_COMMANDS = {
    "show_status", "show_memory", "show_session", "show_fleet", "quiet", "wake",
}

# Words that would mean the pet had acquired real authority. The vocabulary
# must never grow one of these without a deliberate, reviewed decision.
FORBIDDEN_IN_COMMANDS = (
    "exec", "shell", "run", "cmd", "system", "delete", "remove", "write",
    "create", "send", "message", "email", "http", "fetch", "download",
    "upload", "open_url", "browse", "install", "kill", "stop_process",
)


def test_every_declared_intent_has_an_explicit_decision():
    """A new intent kind must be given a decision on purpose, not by accident."""
    from hermes_companion.core.intents import _SAFE_DECISIONS

    declared = {k for k in IntentKind if k is not IntentKind.UNKNOWN}
    missing = sorted(k.value for k in declared if k not in _SAFE_DECISIONS)
    assert missing == [], f"intent kinds with no decision: {missing}"


def test_bounded_intents_stay_local_and_never_imply_execution():
    from hermes_companion.core.intents import _SAFE_DECISIONS

    for kind, decision in _SAFE_DECISIONS.items():
        assert decision.allowed is True, f"{kind.value} should be a local action"
        assert decision.requires_confirmation is False
        assert decision.command in LOCAL_UI_COMMANDS, (
            f"{kind.value} requests {decision.command!r}, which is not a known "
            f"local UI action"
        )
        blob = f"{kind.value} {decision.command} {decision.reason}".lower()
        for banned in FORBIDDEN_IN_COMMANDS:
            assert banned not in blob, (
                f"{kind.value.value} implies execution via {banned!r}"
            )


@pytest.mark.parametrize("kind", [
    IntentKind.SHOW_STATUS, IntentKind.SHOW_MEMORY, IntentKind.SHOW_SESSION,
    IntentKind.SHOW_FLEET, IntentKind.QUIET, IntentKind.WAKE,
])
def test_bounded_intents_route_allowed_and_audited(tmp_path, kind):
    audit_path = tmp_path / "intents.jsonl"
    intent = CompanionIntent(kind=kind, source="pet_panel", session_id="s9")

    decision = route_intent(intent, audit_path=audit_path)

    assert decision.allowed is True
    assert decision.command in LOCAL_UI_COMMANDS
    record = json.loads(audit_path.read_text(encoding="utf-8"))
    assert record["intent"] == kind.value
    assert record["allowed"] is True
    assert record["source"] == "pet_panel"


def test_intent_records_remain_content_free(tmp_path):
    audit_path = tmp_path / "intents.jsonl"
    intent = CompanionIntent(kind=IntentKind.SHOW_MEMORY, source="pet_panel",
                             session_id="s9")
    route_intent(intent, audit_path=audit_path)
    record = json.loads(audit_path.read_text(encoding="utf-8"))
    assert set(record) == {
        "type", "intent", "source", "confidence", "session_id",
        "allowed", "command", "requires_confirmation", "reason",
    }


def test_an_unknown_kind_string_is_still_denied(tmp_path):
    audit_path = tmp_path / "intents.jsonl"
    intent = CompanionIntent.from_record({"intent": "run_shell", "source": "x"})
    decision = route_intent(intent, audit_path=audit_path)
    assert decision.allowed is False
    assert decision.command == ""
    assert decision.requires_confirmation is True
