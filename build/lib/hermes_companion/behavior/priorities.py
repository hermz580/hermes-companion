"""Event priority table (spec rev1 §18). P0..P6, lower number wins."""
from __future__ import annotations

from hermes_companion.core.events import EventKind

P0 = 0   # critical
P1 = 1   # user attention required
P2 = 2   # failure
P3 = 3   # completion
P4 = 4   # active task
P5 = 5   # information
P6 = 6   # idle

EVENT_PRIORITY: dict[EventKind, int] = {
    EventKind.APPROVAL_REQUIRED: P1,
    EventKind.PROMPT_SUBMITTED: P1,
    EventKind.TOOL_FAILED: P2,
    EventKind.TASK_COMPLETE: P3,
    EventKind.TOOL_FINISHED: P3,
    EventKind.SUBAGENT_FINISHED: P3,
    EventKind.AGENT_STARTED: P4,
    EventKind.TOOL_STARTED: P4,
    EventKind.SUBAGENT_STARTED: P4,
    EventKind.APPROVAL_APPROVED: P4,
    EventKind.APPROVAL_REJECTED: P4,
    EventKind.TOOL_PROGRESS: P5,
    EventKind.TYPING_STARTED: P5,
    EventKind.TYPING_STOPPED: P6,
    EventKind.AGENT_IDLE: P6,
    EventKind.USER_RETURNED: P1,
    EventKind.IDLE: P6,
}

# Non-interruptible atomic steps: a chain already inside one of these must
# finish the step before yielding to an interrupt (spec rev1 §10.2).
NON_INTERRUPTIBLE_STEPS = {"land", "teleport_reappear", "stand_up", "fall", "wake"}
