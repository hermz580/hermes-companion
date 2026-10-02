from __future__ import annotations

import argparse
import json
from pathlib import Path
from unittest.mock import patch

import pytest

from hermes_companion.cli import emit
from hermes_companion.core.intents import CompanionIntent, IntentKind, route_intent


def test_hindsight_prints_only_bounded_identifier_labels(capsys):
    private = "PRIVATE recall content must never be printed"

    class FakeHindsight:
        url = "http://user:password@localhost/private"

        def ping(self):
            return True

        def list_banks(self):
            return [
                {"bank_id": "bank-1", "name": private, "fact_count": 4},
                {"bank_id": "bank-2", "name": "safe_label", "fact_count": private},
            ]

        def memory_count(self):
            return 4

        def recall(self, query, limit):
            assert query == private
            assert limit == 3
            return [
                {"label": "release-tag", "summary": private, "content": private},
                {"label": private, "bank_id": "hit-2", "summary": private},
                {"summary": private, "content": private},
            ]

    with patch("hermes_companion.core.hindsight.HindsightClient", FakeHindsight):
        rc = emit.cmd_hindsight(argparse.Namespace(query=private, limit=3))

    output = capsys.readouterr().out
    assert rc == 0
    assert private not in output
    assert "password" not in output
    assert "recall hits: 3" in output
    assert "release-tag" in output
    assert "hit-2" in output
    assert "bank-1" in output
    assert "safe_label" in output


def test_direct_intent_rejects_unbounded_or_content_like_identifiers(tmp_path):
    audit = tmp_path / "audit.jsonl"
    bad_values = [" private sentence ", "line\nbreak", "x" * 129, "a/b", object()]
    for value in bad_values:
        with pytest.raises(ValueError):
            CompanionIntent(
                kind=IntentKind.SHOW_STATUS,
                source=value,
                confidence=1,
                session_id="session-1",
            )
    assert not audit.exists()

    with pytest.raises(ValueError):
        CompanionIntent(
            kind=IntentKind.SHOW_STATUS,
            source="cli",
            confidence=1,
            session_id="private session sentence",
        )


def test_direct_intent_confidence_is_finite_and_clamped():
    def confidence(value):
        return CompanionIntent(
            kind=IntentKind.SHOW_STATUS,
            source="cli",
            confidence=value,
            session_id="session-1",
        ).confidence

    assert confidence(-2) == 0.0
    assert confidence(2) == 1.0
    assert confidence(float("nan")) == 0.0
    assert confidence(float("inf")) == 0.0
    assert confidence("not-a-number") == 0.0


def test_record_constructor_drops_bad_metadata_and_audit_has_fixed_schema(tmp_path):
    private = "raw private text with spaces"
    intent = CompanionIntent.from_record({
        "intent": "show_status",
        "source": private,
        "session_id": private,
        "confidence": float("nan"),
        "prompt": private,
        "command": private,
    })
    audit = tmp_path / "audit.jsonl"
    route_intent(intent, audit_path=audit)
    record = json.loads(audit.read_text(encoding="utf-8"))
    assert record == {
        "type": "companion.intent",
        "intent": "show_status",
        "source": "",
        "confidence": 0.0,
        "session_id": "",
        "allowed": True,
        "command": "show_status",
        "requires_confirmation": False,
        "reason": "safe_local_status",
    }
    assert private not in audit.read_text(encoding="utf-8")


def test_live_parser_supports_validated_companion_without_token_argument(monkeypatch):
    seen = {}

    def fake_live(args):
        seen.update(vars(args))
        return 0

    monkeypatch.setattr(emit, "cmd_live", fake_live)
    assert emit.main(["live", "--companion", "astro"]) == 0
    assert seen["companion"] == "astro"
    assert "token" not in seen
    with pytest.raises(SystemExit):
        emit.main(["live", "--companion", "not-a-companion"])
    with pytest.raises(SystemExit):
        emit.main(["live", "--token", "secret-on-command-line"])


def test_launchers_never_put_relay_tokens_on_process_command_lines():
    launch = Path(__file__).parents[1] / "launch"
    for path in launch.glob("*.cmd"):
        text = path.read_text(encoding="utf-8")
        assert "--token" not in text, path.name
    for name in ("companion-pet.cmd", "companion-relay.cmd", "companion-astro.cmd", "companion-choose.cmd"):
        text = (launch / name).read_text(encoding="utf-8")
        assert "HERMES_COMPANION_TOKEN" in text, name
    local = (launch / "companion-astro-local.cmd").read_text(encoding="utf-8")
    assert 'set "COMPANION=%DEFAULT_COMPANION%"' in local
    assert 'set "SCALE=%DEFAULT_SCALE%"' in local
