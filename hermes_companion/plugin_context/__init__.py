"""Hermes hook plugin: inject validated companion memory into real LLM calls.

Standalone plugin (its own directory; it never touches core files). It
subscribes to exactly one real hook, ``pre_llm_call`` (see ``VALID_HOOKS`` in
``hermes_cli/plugins.py``). The host joins every callback's returned ``context``
string and appends it to the USER MESSAGE -- never the system prompt, which must
stay byte-stable for prompt caching (``agent/turn_context.py::
_collect_pre_llm_call_context``).

The callback is a thin, fail-open adapter. It imports
``hermes_companion.core.companion_execution`` (the fail-closed bridge that maps
an explicit, user-authored ``(session_id, task_id)`` binding to a validated,
character-bounded companion-memory block) and returns that block as
``{"context": block}``. Every other path -- adapter import failure, missing
store, adapter exception, empty/whitespace/non-string block -- returns ``None``
so a broken companion can never break a user's LLM call.

Privacy: the callback never reads ``user_message`` (or any prompt content) into
a log or an audit. Only ``session_id``/``task_id`` cross the boundary, and the
adapter's own audit whitelists counts and IDs only.

Install and enable:
  1. ``python plugin_context/install.py``
  2. ``hermes plugins enable hermes-companion-context``
See ``docs/companion-context-plugin.md`` for the full steps.
"""
from __future__ import annotations

import logging
import os
import sys
from pathlib import Path
from typing import Any, Callable, Optional

log = logging.getLogger(__name__)

# The one hook this plugin subscribes to (must be in hermes_cli.plugins.VALID_HOOKS).
HOOK_NAME = "pre_llm_call"

# The only key the callback returns when it has a block to inject.
CONTEXT_KEY = "context"


def _ensure_package_on_path() -> None:
    """Resolve the shared ``hermes_companion`` package deterministically.

    This plugin and ``hermes-companion`` both bundle a top-level package of the
    same name, and both live in sibling directories. Whichever directory is
    first on ``sys.path`` owns that name process-wide, so a *partial* bundle
    (this plugin ships only ``core/``) can shadow the complete one and break the
    companion's ``hermes_companion.behavior`` import. Prefer the sibling's
    complete bundle when it is present; fall back to our own otherwise.
    """
    plugin_dir = Path(__file__).resolve().parent
    sibling = plugin_dir.parent / "hermes-companion" / "hermes_companion"
    target = plugin_dir.parent / "hermes-companion" if (sibling / "behavior").is_dir() else plugin_dir
    target_str = str(target)
    if target_str not in sys.path:
        sys.path.insert(0, target_str)


def _default_companion_dir() -> Path:
    """Resolve profile-local companion state from the active Hermes home."""
    override = os.environ.get("HERMES_COMPANION_HOME")
    if override:
        return Path(override)
    try:
        from hermes_constants import get_hermes_home
        return Path(get_hermes_home()) / "companion"
    except Exception:
        active_home = os.environ.get("HERMES_HOME")
        if active_home:
            return Path(active_home) / "companion"
        base = (os.environ.get("LOCALAPPDATA") or os.environ.get("XDG_STATE_HOME")
                or str(Path.home()))
        return Path(base) / "hermes" / "companion"


def _memory_db_path() -> Path:
    return _default_companion_dir() / "library.sqlite3"


def _load_adapter() -> Callable[..., str]:
    """Import the fail-closed companion execution bridge (raises if unavailable)."""
    _ensure_package_on_path()
    from hermes_companion.core.companion_execution import build_context_block
    return build_context_block


def _open_store() -> Any:
    """Open the local companion memory store (raises if unavailable)."""
    _ensure_package_on_path()
    from hermes_companion.core.companion_memory import CompanionMemoryStore
    return CompanionMemoryStore(_memory_db_path())


def _build_block(session_id: Any, task_id: Any) -> str:
    adapter = _load_adapter()
    store = _open_store()
    try:
        return adapter(session_id, task_id, store=store)
    finally:
        try:
            store.close()
        except Exception:
            pass


def provide_companion_context(*, session_id: Any = "", task_id: Any = "",
                              **_ignored: Any) -> Optional[dict]:
    """``pre_llm_call`` callback: return ``{"context": block}`` or ``None``.

    Never raises. ``user_message`` (and every other hook kwarg) is swallowed
    unread: nothing about the user's prompt is inspected, logged, or audited.
    """
    try:
        block = _build_block(session_id, task_id)
    except Exception:
        log.debug("companion context: adapter unavailable or failed", exc_info=True)
        return None
    if not isinstance(block, str) or not block.strip():
        return None
    return {CONTEXT_KEY: block}


def register(ctx) -> None:
    ctx.register_hook(HOOK_NAME, provide_companion_context)
