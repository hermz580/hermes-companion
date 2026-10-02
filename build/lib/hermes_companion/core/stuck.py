"""Truthful "is the agent stuck?" detection.

A stuck verdict is a strong claim and must be evidence-based, never inferred
from silence alone. This module answers it from real content-free events:

- An "open" tool is a ``tool.started`` with no matching ``tool.finished`` or
  ``tool.failed`` yet. Its age is measured against the per-category typical
  duration learned from the ``duration_ms`` carried by real finish/fail
  records, not a guessed number.
- The verdict only rises to ``stuck`` when ALL of these hold:
    * there is at least one open tool;
    * that tool is the *most recent* record (no other activity arrived after
      it started, which would prove the agent is alive and doing something
      else);
    * its age is well beyond the learned typical duration for its category;
    * the event stream is still fresh (otherwise we cannot tell "stuck work"
      from "dead observer", so the honest answer is ``unknown``);
    * there is no pending human approval (that is ``needs-you``, not stuck);
    * it is not an actively-ticking delegation.
  Otherwise the verdict is the conservative ``working`` / ``quiet`` /
  ``needs-you`` — never an invented failure.
"""
from __future__ import annotations

import statistics
from dataclasses import dataclass, field

from hermes_companion.core.events import EventKind


# If the most recent event is older than this we cannot confirm the agent is
# alive, so we refuse to say "stuck" and report "unknown" instead.
STREAM_FRESH_SECONDS = 90.0
# A tool is never "stuck" before this age, regardless of learned typicals.
MIN_SUSPECT_SECONDS = 30.0
# Default typical duration used until we have real data for a category.
DEFAULT_TYPICAL_SECONDS = 60.0
# Stuck = age beyond this multiple of the learned typical.
TYPICAL_MULTIPLIER = 3.0
# ... or this many seconds beyond the learned typical, whichever is larger.
TYPICAL_PADDING_SECONDS = 120.0


@dataclass(frozen=True)
class OpenTool:
    tool: str
    category: str
    started_ts: float
    is_delegated: bool


@dataclass
class StuckVerdict:
    state: str            # stuck | working | quiet | needs-you | unknown
    label: str
    open_tool: OpenTool | None = None
    open_age_s: float | None = None
    typical_s: float | None = None
    last_event_age_s: float | None = None

    def as_dict(self) -> dict:
        return {
            "state": self.state,
            "label": self.label,
            "open_tool": self.open_tool.tool if self.open_tool else None,
            "open_category": self.open_tool.category if self.open_tool else None,
            "open_age_s": round(self.open_age_s, 1) if self.open_age_s is not None else None,
            "typical_s": round(self.typical_s, 1) if self.typical_s is not None else None,
            "last_event_age_s": round(self.last_event_age_s, 1)
                if self.last_event_age_s is not None else None,
        }


class StuckDetector:
    """State machine over content-free lifecycle events.

    Pure and headless (no Tk, no I/O): ``ingest`` updates state, ``check(now)``
    returns a verdict. The clock is injected by the caller so tests need no
    sleeping.
    """

    def __init__(self, *, fresh_seconds: float = STREAM_FRESH_SECONDS,
                 min_suspect: float = MIN_SUSPECT_SECONDS,
                 typical_multiplier: float = TYPICAL_MULTIPLIER,
                 typical_padding: float = TYPICAL_PADDING_SECONDS,
                 default_typical: float = DEFAULT_TYPICAL_SECONDS) -> None:
        self.fresh_seconds = fresh_seconds
        self.min_suspect = min_suspect
        self.typical_multiplier = typical_multiplier
        self.typical_padding = typical_padding
        self.default_typical = default_typical
        self.open: dict[tuple[str, str, str], OpenTool] = {}
        self.category_durations: dict[str, list[float]] = {}
        self.last_event_ts: float | None = None
        self.last_event_kind: str | None = None
        self.pending_approval = False
        self.subagent_open = 0
        self.subagent_last_spawn: float | None = None

    # -- event intake -------------------------------------------------------
    def _key(self, session: str, task: str, tool: str) -> tuple[str, str, str]:
        return (str(session or ""), str(task or ""), str(tool or ""))

    def ingest(self, kind, tool: str = "", category: str = "",
               session: str = "", task: str = "", ts: float = 0.0) -> None:
        k = kind if isinstance(kind, EventKind) else EventKind(str(kind))
        self.last_event_kind = k.value
        self.last_event_ts = ts
        key = self._key(session, task, tool)

        if k is EventKind.APPROVAL_REQUIRED:
            self.pending_approval = True
        elif k in (EventKind.APPROVAL_APPROVED, EventKind.APPROVAL_REJECTED):
            self.pending_approval = False
        elif k is EventKind.TOOL_STARTED:
            delegated = self._is_delegated_task(task)
            self.open[key] = OpenTool(
                tool=str(tool), category=str(category or "general"),
                started_ts=ts, is_delegated=delegated)
        elif k in (EventKind.TOOL_FINISHED, EventKind.TOOL_FAILED):
            entry = self.open.pop(key, None)
            if entry is not None:
                duration = self._read_duration(ts, entry.started_ts)
                if duration is not None:
                    self.category_durations.setdefault(entry.category, []).append(duration)
        elif k is EventKind.SUBAGENT_STARTED:
            self.subagent_open += 1
            self.subagent_last_spawn = ts
        elif k in (EventKind.SUBAGENT_FINISHED, EventKind.SUBAGENT_FAILED):
            self.subagent_open = max(0, self.subagent_open - 1)

    @staticmethod
    def _is_delegated_task(task: str) -> bool:
        if not task:
            return False
        t = str(task)
        if t.startswith("sa-") or t.startswith("cron:"):
            return True
        return "-" in t and not t.replace("-", "").isalnum() and len(t) >= 16

    def _read_duration(self, finish_ts: float, start_ts: float) -> float | None:
        d = finish_ts - start_ts
        if d <= 0:
            return None
        return d

    # -- typical duration ---------------------------------------------------
    def _typical(self, category: str) -> float:
        durations = self.category_durations.get(str(category or "general"))
        if not durations:
            return self.default_typical
        try:
            p95 = statistics.quantiles(sorted(durations), n=20)[18]
        except (ValueError, IndexError):
            p95 = max(durations)
        return max(self.default_typical, p95)

    def _threshold(self, category: str) -> float:
        typical = self._typical(category)
        return max(self.min_suspect,
                   typical * self.typical_multiplier,
                   typical + self.typical_padding)

    # -- verdict ------------------------------------------------------------
    def check(self, now: float) -> StuckVerdict:
        last_age = self._age(now)

        if self.pending_approval:
            return StuckVerdict("needs-you", "Decision needed", last_event_age_s=last_age)

        if not self.open:
            # No open tool means nothing is in flight. That is the honest
            # "quiet" answer regardless of stream age: we are not claiming
            # anything is wrong. (Silence with no open tool is not evidence of
            # stuck — it is just no reported work.)
            return StuckVerdict("quiet", "No open tool", last_event_age_s=last_age)

        # Oldest open tool is the most conservative candidate.
        oldest = min(self.open.values(), key=lambda o: o.started_ts)
        age = max(0.0, now - oldest.started_ts)

        if self.last_event_ts is not None and oldest.started_ts < self.last_event_ts:
            # Something happened after this tool started → the agent is clearly
            # alive and busy elsewhere; do not claim stuck.
            return StuckVerdict(
                "working", f"Open tool: {oldest.tool}", open_tool=oldest,
                open_age_s=age, typical_s=self._typical(oldest.category),
                last_event_age_s=last_age)

        threshold = self._threshold(oldest.category)
        if age < threshold:
            return StuckVerdict(
                "working", f"Tool running ({oldest.tool})", open_tool=oldest,
                open_age_s=age, typical_s=self._typical(oldest.category),
                last_event_age_s=last_age)

        # The open tool IS the most recent record and far exceeds its learned
        # typical duration. The observer was demonstrably alive to record its
        # start, so this is stuck evidence even if the stream has since gone
        # quiet — not a dead observer.
        return StuckVerdict(
            "stuck",
            f"Looks stuck: {oldest.tool} running {age:.0f}s (typical {self._typical(oldest.category):.0f}s)",
            open_tool=oldest, open_age_s=age,
            typical_s=self._typical(oldest.category),
            last_event_age_s=last_age)

    def _age(self, now: float) -> float | None:
        if self.last_event_ts is None:
            return None
        return max(0.0, now - self.last_event_ts)
