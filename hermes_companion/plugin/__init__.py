"""Hermes Companion plugin — real-hook adapter (spec rev1 §5/§6).

Maps Hermes lifecycle hooks to SemanticEvents through an allow-list, runs them
through the behavior engine, and appends the decision trace to a JSONL log
(`~/.hermes/companion/events.jsonl` by default).

Trust boundary (spec §5): raw payloads (args, result, command) are NEVER
forwarded. Only enum/session/task fields cross the adapter. Nothing is
rendered as text by this plugin — the Tk overlay is driven separately by the
companion CLI reading the same event log.

Fail-open: any exception inside a callback is swallowed and logged at debug
level, exactly like the Langfuse reference plugin — a broken companion can
never break Hermes.
"""
from __future__ import annotations

import json
import logging
import os
import time
from typing import Any

log = logging.getLogger("hermes_companion")


def _hermes_home_dir() -> str:
    """Resolve the ACTIVE Hermes home (HERMES_HOME or platform default) so the
    companion log lives next to the install — not in a stray ~/.hermes that the
    CLI may or may not be reading. Matches how the plugin loader resolves home."""
    try:
        from hermes_constants import get_hermes_home  # authoritative
        return get_hermes_home()
    except Exception:
        pass
    env = os.environ.get("HERMES_HOME")
    if env:
        return env
    return os.path.join(os.path.expanduser("~"), "AppData", "Local", "hermes")


_COMPANION_DIR = os.path.join(_hermes_home_dir(), "companion")
_EVENTS_LOG = os.path.join(_COMPANION_DIR, "events.jsonl")
_EVENT_KEY_PATH = os.path.join(_COMPANION_DIR, "event-auth.key")
_seed = int(os.environ.get("HERMES_COMPANION_SEED", "0") or "0")
_EVENT_KEY = None


def _event_key() -> bytes:
    global _EVENT_KEY
    if _EVENT_KEY is None:
        from hermes_companion.core.event_auth import load_or_create_event_key
        _EVENT_KEY = load_or_create_event_key(_EVENT_KEY_PATH)
    return _EVENT_KEY


def _log_event(record: dict[str, Any]) -> None:
    """Append one semantic-event record to the JSONL log (thread-safe-ish:
    single-line appends are atomic enough on local FS for a pet logger)."""
    try:
        os.makedirs(_COMPANION_DIR, exist_ok=True)
        record.setdefault("ts", time.time())
        record.setdefault("seed", _seed)
        from hermes_companion.core.event_auth import sign_record
        signed = sign_record(record, _event_key())
        with open(_EVENTS_LOG, "a", encoding="utf-8") as f:
            f.write(json.dumps(signed, ensure_ascii=False) + "\n")
    except Exception:
        log.debug("companion: failed to append event log", exc_info=True)


def _engine() -> Any:
    """Lazily import the behavior engine (kept optional so the plugin never
    becomes a hard dependency of Hermes core)."""
    from hermes_companion.behavior.behavior_engine import BehaviorEngine
    return BehaviorEngine(seed=_seed or None)


_ENGINE_CACHE = None


def _get_engine() -> Any:
    global _ENGINE_CACHE
    if _ENGINE_CACHE is None:
        _ENGINE_CACHE = _engine()
    return _ENGINE_CACHE


# ---------------------------------------------------------------------------
# Tool hooks (spec §6.1)
# ---------------------------------------------------------------------------
def on_pre_tool_call(*, tool_name: str = "", args: Any = None, task_id: str = "",
                     session_id: str = "", tool_call_id: str = "",
                     turn_id: str = "", api_request_id: str = "",
                     **_: Any) -> None:
    """tool.started — content-free: only tool name/category/ids cross."""
    try:
        from hermes_companion.core.events import EventKind, SemanticEvent
        from hermes_companion.core.events import classify_tool
        engine = _get_engine()
        ev = SemanticEvent(
            kind=EventKind.TOOL_STARTED,
            tool=tool_name,
            category=classify_tool(tool_name),
            session_id=session_id,
            task_id=task_id,
        )
        chain = engine.handle(ev)
        _log_event({
            "event": ev.kind.value,
            "tool": tool_name,
            "category": ev.category,
            "session_id": session_id,
            "task_id": task_id,
            "state": chain.state.value if chain else engine.state.value,
            "steps": chain.poses if chain else [],
        })
    except Exception:
        log.debug("companion on_pre_tool_call failed", exc_info=True)


def on_post_tool_call(*, tool_name: str = "", args: Any = None, result: Any = None,
                      task_id: str = "", session_id: str = "", tool_call_id: str = "",
                      turn_id: str = "", api_request_id: str = "",
                      duration_ms: int = 0, status: str | None = None,
                      error_type: str | None = None, error_message: str | None = None,
                      **_: Any) -> None:
    """tool.finished / tool.failed / tool.blocked — status enum only, never
    result content (spec §5.2)."""
    try:
        from hermes_companion.core.events import EventKind, SemanticEvent
        from hermes_companion.core.events import classify_tool
        engine = _get_engine()
        if status == "blocked":
            kind = EventKind.APPROVAL_REQUIRED
        elif status == "error" or error_type:
            kind = EventKind.TOOL_FAILED
        else:
            kind = EventKind.TOOL_FINISHED
        ev = SemanticEvent(
            kind=kind,
            tool=tool_name,
            category=classify_tool(tool_name),
            session_id=session_id,
            task_id=task_id,
        )
        chain = engine.handle(ev)
        _log_event({
            "event": ev.kind.value,
            "tool": tool_name,
            "category": ev.category,
            "status": status or "",
            "duration_ms": int(duration_ms or 0),
            "session_id": session_id,
            "task_id": task_id,
            "state": chain.state.value if chain else engine.state.value,
            "steps": chain.poses if chain else [],
        })
    except Exception:
        log.debug("companion on_post_tool_call failed", exc_info=True)


# ---------------------------------------------------------------------------
# Approval hooks (spec §6.3 — the `command` kwarg is DROPPED, never forwarded)
# ---------------------------------------------------------------------------
def on_pre_approval_request(*, command: str = "", description: str = "",
                            pattern_key: str = "", pattern_keys: list[str] | None = None,
                            session_key: str = "", surface: str = "",
                            **_: Any) -> None:
    try:
        from hermes_companion.core.events import EventKind, SemanticEvent
        engine = _get_engine()
        ev = SemanticEvent(kind=EventKind.APPROVAL_REQUIRED, session_id=session_key)
        chain = engine.handle(ev)
        _log_event({
            "event": ev.kind.value,
            "surface": surface,          # enum only
            "session_key": session_key,
            "state": chain.state.value if chain else engine.state.value,
            "steps": chain.poses if chain else [],
            # NOTE: `command` is intentionally never logged or forwarded.
        })
    except Exception:
        log.debug("companion on_pre_approval_request failed", exc_info=True)


def on_post_approval_response(*, command: str = "", description: str = "",
                              pattern_key: str = "", pattern_keys: list[str] | None = None,
                              session_key: str = "", surface: str = "",
                              choice: str = "", decided_by: str = "",
                              **_: Any) -> None:
    try:
        from hermes_companion.core.events import EventKind, SemanticEvent
        engine = _get_engine()
        kind = EventKind.APPROVAL_APPROVED if choice in ("once", "session", "always", "smart_approve") \
            else EventKind.APPROVAL_REJECTED
        ev = SemanticEvent(kind=kind, session_id=session_key)
        chain = engine.handle(ev)
        _log_event({
            "event": ev.kind.value,
            "surface": surface,
            "choice": choice,            # enum only
            "session_key": session_key,
            "state": chain.state.value if chain else engine.state.value,
            "steps": chain.poses if chain else [],
        })
    except Exception:
        log.debug("companion on_post_approval_response failed", exc_info=True)


# ---------------------------------------------------------------------------
# Session / subagent hooks (spec §6.2)
# ---------------------------------------------------------------------------
def on_session_start(*, session_id: str = "", **_: Any) -> None:
    try:
        from hermes_companion.core.events import EventKind, SemanticEvent
        engine = _get_engine()
        ev = SemanticEvent(kind=EventKind.AGENT_STARTED, session_id=session_id)
        chain = engine.handle(ev)
        _log_event({"event": ev.kind.value, "session_id": session_id,
                    "state": chain.state.value if chain else engine.state.value,
                    "steps": chain.poses if chain else []})
    except Exception:
        log.debug("companion on_session_start failed", exc_info=True)


def on_session_end(*, session_id: str = "", reason: str = "", **_: Any) -> None:
    try:
        from hermes_companion.core.events import EventKind, SemanticEvent
        engine = _get_engine()
        ev = SemanticEvent(kind=EventKind.AGENT_IDLE, session_id=session_id)
        chain = engine.handle(ev)
        _log_event({"event": ev.kind.value, "session_id": session_id, "reason": reason,
                    "state": chain.state.value if chain else engine.state.value,
                    "steps": chain.poses if chain else []})
    except Exception:
        log.debug("companion on_session_end failed", exc_info=True)


def on_subagent_start(*, parent_session_id: Any = None, parent_turn_id: str = "",
                      subagent_id: str = "", **_: Any) -> None:
    try:
        from hermes_companion.core.events import EventKind, SemanticEvent
        engine = _get_engine()
        ev = SemanticEvent(kind=EventKind.SUBAGENT_STARTED, session_id=str(parent_session_id or ""))
        chain = engine.handle(ev)
        _log_event({"event": ev.kind.value, "session_id": str(parent_session_id or ""),
                    "subagent_id": subagent_id,
                    "state": chain.state.value if chain else engine.state.value,
                    "steps": chain.poses if chain else []})
    except Exception:
        log.debug("companion on_subagent_start failed", exc_info=True)


def on_subagent_stop(*, parent_session_id: Any = None, parent_turn_id: str = "",
                     subagent_id: str = "", success: bool = True,
                     **_: Any) -> None:
    try:
        from hermes_companion.core.events import EventKind, SemanticEvent
        engine = _get_engine()
        kind = EventKind.SUBAGENT_FINISHED if success else EventKind.SUBAGENT_FAILED
        ev = SemanticEvent(kind=kind, session_id=str(parent_session_id or ""))
        chain = engine.handle(ev)
        _log_event({"event": ev.kind.value, "session_id": str(parent_session_id or ""),
                    "subagent_id": subagent_id, "success": bool(success),
                    "state": chain.state.value if chain else engine.state.value,
                    "steps": chain.poses if chain else []})
    except Exception:
        log.debug("companion on_subagent_stop failed", exc_info=True)


# ---------------------------------------------------------------------------
# Registration (spec §2 / §6 — the bus IS the hook system)
# ---------------------------------------------------------------------------
def register(ctx) -> None:
    ctx.register_hook("pre_tool_call", on_pre_tool_call)
    ctx.register_hook("post_tool_call", on_post_tool_call)
    ctx.register_hook("pre_approval_request", on_pre_approval_request)
    ctx.register_hook("post_approval_response", on_post_approval_response)
    ctx.register_hook("on_session_start", on_session_start)
    ctx.register_hook("on_session_end", on_session_end)
    ctx.register_hook("subagent_start", on_subagent_start)
    ctx.register_hook("subagent_stop", on_subagent_stop)
