"""Explicit companion -> session binding.

The visible companion refuses to display anything unless exactly one binding
maps it to a specific session, so this module is the sanctioned way to create
that record. Binding is always an explicit, user-invoked action:

  * ``resolve_current_session()`` reads the session Hermes is actually running
    *right now*, and is only ever called because the user asked for it
    (``bind --current``). It is never consulted at render time.
  * Rendering still re-reads ``bindings.json`` and fails closed, so a stale or
    ambiguous file stops the pet rather than guessing.

Nothing here grants the companion authority; a binding only says which real
session's evidence this body may display.
"""
from __future__ import annotations

import json
import os
import re
from datetime import datetime, timezone
from pathlib import Path

VERSION = 2
_SESSION_RE = re.compile(r"[0-9]{8}_[0-9]{6}_[0-9a-f]{4,}")
_VALID_ID = re.compile(r"[A-Za-z0-9][A-Za-z0-9_.-]*")

MODE_PINNED = "pinned"
MODE_FOLLOW = "follow"
_MODES = (MODE_PINNED, MODE_FOLLOW)


def companion_home() -> Path:
    override = os.environ.get("HERMES_COMPANION_HOME")
    if override:
        return Path(override)
    base = os.environ.get("LOCALAPPDATA") or str(Path.home())
    return Path(base) / "hermes" / "companion"


def hermes_home() -> Path:
    override = os.environ.get("HERMES_HOME")
    if override:
        return Path(override)
    base = os.environ.get("LOCALAPPDATA") or str(Path.home())
    return Path(base) / "hermes"


def default_bindings_path() -> Path:
    return companion_home() / "bindings.json"


def _bounded(value, name: str, limit: int) -> str:
    if not isinstance(value, str) or not value or value != value.strip():
        raise ValueError(f"{name} must be a non-empty trimmed string")
    if len(value) > limit or any(not c.isprintable() for c in value):
        raise ValueError(f"{name} is out of bounds")
    return value


def resolve_current_session(hermes_home_dir: Path | None = None) -> str | None:
    """Return the session Hermes is running now, or ``None`` if unclear.

    Only used by the explicit ``bind --current`` action. Prefers the most
    recent ``agent_session_id`` in the agent log, then the newest entry in
    ``sessions.json``. Returns ``None`` rather than inventing an answer when
    neither source yields exactly one plausible id.
    """
    home = hermes_home_dir or hermes_home()

    log = home / "logs" / "agent.log"
    try:
        text = log.read_text(encoding="utf-8", errors="replace")
    except OSError:
        text = ""
    if text:
        found = _SESSION_RE.findall(text[-200_000:])
        if found:
            return found[-1]

    sessions = home / "sessions" / "sessions.json"
    try:
        doc = json.loads(sessions.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return None
    if not isinstance(doc, dict):
        return None
    newest = None
    for value in doc.values():
        if not isinstance(value, dict):
            continue
        sid = value.get("session_id")
        updated = str(value.get("updated_at") or "")
        if isinstance(sid, str) and _SESSION_RE.fullmatch(sid):
            if newest is None or updated > newest[0]:
                newest = (updated, sid)
    return newest[1] if newest else None


def _empty() -> dict:
    return {"version": VERSION, "mode": MODE_PINNED,
            "companion_id": None, "bindings": []}


def _normalize(doc) -> dict:
    """Return the v2 shape for a v1 or v2 document, or an empty document.

    A follow document without a usable companion id degrades to pinned rather
    than following something arbitrary.
    """
    out = _empty()
    if not isinstance(doc, dict) or doc.get("version") not in (1, VERSION):
        return out
    if doc.get("mode") in _MODES:
        out["mode"] = doc["mode"]
    companion_id = doc.get("companion_id")
    if isinstance(companion_id, str) and _VALID_ID.fullmatch(companion_id):
        out["companion_id"] = companion_id
    rows = doc.get("bindings")
    if isinstance(rows, list):
        out["bindings"] = [r for r in rows if isinstance(r, dict)]
    if out["mode"] == MODE_FOLLOW and not out["companion_id"]:
        out["mode"] = MODE_PINNED
    return out


def load_bindings(path: Path | None = None) -> dict:
    target = Path(path) if path is not None else default_bindings_path()
    try:
        return _normalize(json.loads(target.read_text(encoding="utf-8")))
    except (OSError, ValueError):
        return _empty()


def _write(path: Path, doc: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(path.suffix + ".tmp")
    tmp.write_text(json.dumps(doc, indent=2) + "\n", encoding="utf-8")
    os.replace(tmp, path)


def bind(companion_id: str, session_id: str, *, task_id: str | None = None,
         project_id: str | None = None, path: Path | None = None) -> dict:
    """Create the single explicit binding for ``companion_id``.

    Any previous binding for this companion is replaced, because two rows for
    one companion make the reader treat the file as ambiguous and refuse.
    """
    companion_id = _bounded(companion_id, "companion_id", 64)
    if not _VALID_ID.fullmatch(companion_id):
        raise ValueError("invalid companion_id")
    session_id = _bounded(session_id, "session_id", 256)
    if task_id is not None:
        task_id = _bounded(task_id, "task_id", 256)
    if project_id is not None:
        project_id = _bounded(project_id, "project_id", 256)

    target = Path(path) if path is not None else default_bindings_path()
    doc = load_bindings(target)
    kept = [r for r in doc["bindings"] if r.get("companion_id") != companion_id]
    row = {"companion_id": companion_id, "session_id": session_id,
           "task_id": task_id, "project_id": project_id}
    doc["bindings"] = kept + [row]
    _write(target, doc)
    return row


def unbind(companion_id: str, *, path: Path | None = None) -> bool:
    companion_id = _bounded(companion_id, "companion_id", 64)
    target = Path(path) if path is not None else default_bindings_path()
    doc = load_bindings(target)
    kept = [r for r in doc["bindings"] if r.get("companion_id") != companion_id]
    if len(kept) == len(doc["bindings"]):
        return False
    doc["bindings"] = kept
    _write(target, doc)
    return True


def describe(*, path: Path | None = None) -> list[dict]:
    return load_bindings(path)["bindings"]


def set_mode(mode: str, companion_id: str | None = None, *,
             path: Path | None = None) -> dict:
    """Switch between pinned (one session) and follow (any session).

    Follow mode needs a companion to follow; without one it degrades back to
    pinned rather than following something arbitrary.
    """
    if mode not in _MODES:
        raise ValueError(f"mode must be one of {_MODES}")
    target = Path(path) if path is not None else default_bindings_path()
    doc = load_bindings(target)
    if mode == MODE_FOLLOW:
        # None means "reuse the one already remembered"; an explicitly blank id
        # is a mistake, so it fails closed rather than adopting a stale name.
        cid = companion_id if companion_id is not None else doc.get("companion_id")
        cid = _bounded(cid, "companion_id", 64)
        if not _VALID_ID.fullmatch(cid):
            raise ValueError("invalid companion_id")
        doc["companion_id"] = cid
    doc["mode"] = mode
    _write(target, doc)
    return doc


def current_mode(*, path: Path | None = None) -> str:
    return load_bindings(path)["mode"]


def following_companion(*, path: Path | None = None) -> str | None:
    """The companion in follow mode, or ``None`` when pinned."""
    doc = load_bindings(path)
    return doc["companion_id"] if doc["mode"] == MODE_FOLLOW else None


def _now_iso() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
