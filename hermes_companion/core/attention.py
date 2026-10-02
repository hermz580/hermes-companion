"""Privacy-safe attention signal for the visible companion.

The model answers one bounded question: does Hermes need the user right now?
It only consumes content-free lifecycle fields from ``SemanticEvent`` and never
stores prompts, tool arguments, command text, results, paths, or private payloads.
"""
from __future__ import annotations

from dataclasses import dataclass

from hermes_companion.core.events import EventKind, SemanticEvent


@dataclass(frozen=True)
class AttentionSignal:
    state: str
    urgency: int
    label: str
    needs_user: bool = False


# Public movement vocabulary: observable activity, never hidden reasoning.
MOVEMENT_LANGUAGE = {
    "quiet": ("idle", "Resting: no active work reported"),
    "starting": ("waving", "Waking and stretching: starting a task"),
    "working": ("waiting", "Steady small motions: using a tool"),
    "delegating": ("review", "Orbiting helpers: work delegated"),
    "reviewing": ("review", "Leaning and inspecting: a tool returned"),
    "needs-you": ("waving", "Repeated gentle wave: approval remains unresolved"),
    "issue": ("failed", "Recoil and pause: a tool reported failure"),
    "complete": ("jumping", "Celebration then rest: completion reported"),
    "paused": ("waiting", "Still and waiting: approval was declined"),
}

SAFE_CATEGORIES = {
    "terminal", "web", "file", "development", "dev", "media", "memory",
    "planning", "delegation", "desktop", "learning", "general",
}


class AttentionModel:
    """Turn content-free events into an ambient trust signal.

    Approval remains sticky until an explicit approval result arrives; failures
    remain visible until real recovery/progress arrives. That prevents quiet,
    unrelated background activity, or idle events from pretending a human
    decision or failure has been resolved.
    """

    def __init__(self) -> None:
        self.signal = AttentionSignal("quiet", 0, "Hermes is ready")
        self.active_tools = 0
        self.subagents = 0
        self.pending_approval = False

    def _safe_category(self, category: str | None) -> str:
        value = str(category or "").strip().lower()
        return value if value in SAFE_CATEGORIES else "general"

    def ingest(self, event: SemanticEvent) -> AttentionSignal:
        k = event.kind

        if k is EventKind.APPROVAL_REQUIRED:
            self.pending_approval = True
            self.signal = AttentionSignal("needs-you", 3, "Decision needed", True)
            return self.signal

        if k in (EventKind.APPROVAL_APPROVED, EventKind.APPROVAL_REJECTED):
            self.pending_approval = False
            if k is EventKind.APPROVAL_APPROVED:
                self.signal = AttentionSignal("starting", 1, "Approved; ready to continue")
            else:
                self.signal = AttentionSignal("paused", 1, "Approval declined")
            return self.signal

        if self.pending_approval:
            # Background tool churn does not clear a human decision request.
            return self.signal

        if k is EventKind.TOOL_FAILED:
            self.active_tools = max(0, self.active_tools - 1)
            self.signal = AttentionSignal("issue", 2, "Tool failed; recovery not confirmed")
        elif k in (EventKind.AGENT_STARTED, EventKind.PROMPT_SUBMITTED):
            self.signal = AttentionSignal("starting", 1, "Starting the task")
        elif k is EventKind.SUBAGENT_STARTED:
            self.subagents += 1
            plural = "s" if self.subagents != 1 else ""
            self.signal = AttentionSignal("delegating", 1, f"Coordinating {self.subagents} helper{plural}")
        elif k in (EventKind.SUBAGENT_FINISHED, EventKind.SUBAGENT_FAILED):
            self.subagents = max(0, self.subagents - 1)
            self.signal = AttentionSignal("working", 1, "Integrating helper work")
        elif k is EventKind.TOOL_STARTED:
            self.active_tools += 1
            category = self._safe_category(event.category)
            self.signal = AttentionSignal("working", 1, f"Working with {category}")
        elif k is EventKind.TOOL_FINISHED:
            self.active_tools = max(0, self.active_tools - 1)
            self.signal = AttentionSignal(
                "working" if self.active_tools else "reviewing",
                1,
                "Continuing the task" if self.active_tools else "Reviewing progress",
            )
        elif k is EventKind.TASK_COMPLETE:
            self.active_tools = 0
            self.subagents = 0
            self.signal = AttentionSignal("complete", 0, "Task complete")
        elif k in (EventKind.AGENT_IDLE, EventKind.IDLE):
            if self.signal.state not in ("issue", "complete", "paused"):
                self.signal = AttentionSignal("quiet", 0, "Hermes is ready")
        return self.signal
