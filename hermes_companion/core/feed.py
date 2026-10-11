"""What Hermes is doing right now, for Companion Home: a read-only event feed.

Same truth rules as the status panel: only records that carry a valid
signature from the local Hermes plugin count, the feed shows lifecycle kinds
and safe categories only (never tool arguments, text or paths), and silence is
reported as silence, never as "nothing is running".

The feed never creates the signing key or the log: if they don't exist,
Hermes simply isn't connected yet.
"""
from __future__ import annotations

import json
import time
from collections import deque
from dataclasses import dataclass
from pathlib import Path

from hermes_companion.core.attention import SAFE_CATEGORIES, AttentionModel
from hermes_companion.core.event_auth import KEY_BYTES, verify_record
from hermes_companion.core.events import EventKind, SemanticEvent, classify_tool

SEED_BYTES = 64 * 1024        # how much history to read when the feed opens
READ_LIMIT = 256 * 1024       # most bytes read per poll
HISTORY = 6

# Attention state -> the glow colour key the companion would show (herald.MOOD_COLORS).
STATE_MOOD = {
    "quiet": "rest", "starting": "work", "working": "work", "reviewing": "work",
    "delegating": "delegate", "needs-you": "approve", "paused": "approve",
    "issue": "fail", "complete": "joy",
}

_PHRASES = {
    EventKind.AGENT_STARTED: ("Started a task", "work"),
    EventKind.PROMPT_SUBMITTED: ("Started a task", "work"),
    EventKind.TOOL_STARTED: ("Using {where}", "work"),
    EventKind.TOOL_FINISHED: ("Finished {a} {noun} step", "work"),
    EventKind.TOOL_FAILED: ("{A} {noun} step failed", "fail"),
    EventKind.APPROVAL_REQUIRED: ("Asked for your approval", "approve"),
    EventKind.APPROVAL_APPROVED: ("You approved", "work"),
    EventKind.APPROVAL_REJECTED: ("You declined", "approve"),
    EventKind.TASK_COMPLETE: ("Finished the task", "joy"),
    EventKind.SUBAGENT_STARTED: ("Handed work to a helper", "delegate"),
    EventKind.SUBAGENT_FINISHED: ("A helper finished", "delegate"),
    EventKind.SUBAGENT_FAILED: ("A helper failed", "fail"),
    EventKind.AGENT_IDLE: ("Went quiet", "rest"),
}

# category -> (where it happens, noun for one step)
_CATEGORY_WORDS = {
    "terminal": ("the terminal", "terminal"), "web": ("the web", "web"),
    "browser": ("the browser", "browser"), "file": ("files", "file"),
    "development": ("code", "code"), "dev": ("code", "code"), "media": ("media", "media"),
    "memory": ("memory", "memory"), "planning": ("a plan", "planning"),
    "delegation": ("helpers", "delegation"), "desktop": ("the desktop", "desktop"),
    "learning": ("learning", "learning"), "general": ("a tool", "tool"),
}


@dataclass(frozen=True)
class FeedItem:
    ts: float
    text: str
    mood: str


def describe(kind: EventKind, category: str) -> tuple[str, str] | None:
    """(sentence, mood) for one event, or None for events the feed skips."""
    phrase = _PHRASES.get(kind)
    if phrase is None:
        return None
    cat = category if category in SAFE_CATEGORIES or category == "browser" else "general"
    where, noun = _CATEGORY_WORDS.get(cat, _CATEGORY_WORDS["general"])
    a = "an" if noun[0] in "aeiou" else "a"
    return phrase[0].format(where=where, noun=noun, a=a, A=a.title()), phrase[1]


def age_text(seconds: float | None) -> str:
    if seconds is None:
        return "no events yet"
    s = max(0, int(seconds))
    if s < 5:
        return "just now"
    if s < 60:
        return f"{s}s ago"
    if s < 3600:
        return f"{s // 60} min ago"
    return f"{s // 3600} h ago"


def default_paths() -> tuple[Path, Path]:
    from hermes_companion.core.binding import hermes_home
    base = hermes_home() / "companion"
    return base / "events.jsonl", base / "event-auth.key"


class HermesFeed:
    """Tail the companion event log; feed verified records to an AttentionModel."""

    def __init__(self, events: Path | None = None, key: Path | None = None) -> None:
        d_events, d_key = default_paths() if events is None or key is None else (None, None)
        self.events = Path(events or d_events)
        self.key_path = Path(key or d_key)
        self.model = AttentionModel()
        self.items: deque[FeedItem] = deque(maxlen=HISTORY)
        self.last_ts: float | None = None
        self.rejected = 0
        self._key: bytes | None = None
        self._offset: int | None = None
        self._buf = b""

    @property
    def connected(self) -> bool:
        """True once the plugin has created its key and log on this PC."""
        return self.key_path.is_file() and self.events.is_file()

    def _load_key(self) -> bytes | None:
        if self._key is None:
            try:
                key = self.key_path.read_bytes()
            except OSError:
                return None
            if len(key) == KEY_BYTES:
                self._key = key
        return self._key

    def poll(self) -> bool:
        """Read anything new. Returns True when the feed changed."""
        key = self._load_key()
        if key is None:
            return False
        try:
            size = self.events.stat().st_size
        except OSError:
            return False
        if self._offset is None or size < self._offset:     # first open, or log rotated
            self._offset = max(0, size - SEED_BYTES)
            self._buf = b""
            skip_partial = self._offset > 0
        else:
            skip_partial = False
        if size == self._offset:
            return False
        try:
            with self.events.open("rb") as f:
                f.seek(self._offset)
                chunk = f.read(min(READ_LIMIT, size - self._offset))
        except OSError:
            return False
        self._offset += len(chunk)
        data = self._buf + chunk
        lines = data.split(b"\n")
        self._buf = lines.pop()
        if skip_partial and lines:
            lines = lines[1:]                 # seeking mid-file lands mid-line
        changed = False
        for raw in lines:
            changed |= self._ingest(raw, key)
        return changed

    def _ingest(self, raw: bytes, key: bytes) -> bool:
        try:
            rec = json.loads(raw.decode("utf-8"))
        except (ValueError, UnicodeDecodeError):
            return False
        rec = verify_record(rec, key)
        if rec is None:
            self.rejected += 1
            return False
        try:
            kind = EventKind(str(rec.get("event") or ""))
        except ValueError:
            return False
        tool = str(rec.get("tool") or "")
        category = str(rec.get("category") or "") or classify_tool(tool)
        try:
            ts = float(rec.get("ts") or 0.0) or time.time()
        except (TypeError, ValueError):
            ts = time.time()
        self.model.ingest(SemanticEvent(kind=kind, category=category,
                                        session_id=str(rec.get("session_id") or ""), ts=ts))
        said = describe(kind, category)
        if said is None:
            return False
        self.items.appendleft(FeedItem(ts, *said))
        self.last_ts = ts
        return True

    def headline(self) -> tuple[str, str]:
        """(sentence, mood) summarising Hermes right now."""
        sig = self.model.signal
        return sig.label, STATE_MOOD.get(sig.state, "calm")
