"""Semantic events — the ONLY thing that crosses the adapter boundary.

Spec rev1 §3/§5: typed, bounded, content-free. No raw args/results/commands.
"""
from __future__ import annotations

import re
import time
from dataclasses import dataclass, field
from enum import Enum


class EventKind(str, Enum):
    IDLE = "idle"
    TYPING_STARTED = "user.typing_started"
    TYPING_STOPPED = "user.typing_stopped"
    PROMPT_SUBMITTED = "user.prompt_submitted"
    AGENT_STARTED = "agent.started"
    TOOL_STARTED = "tool.started"
    TOOL_PROGRESS = "tool.progress"
    TOOL_FINISHED = "tool.finished"
    TOOL_FAILED = "tool.failed"
    APPROVAL_REQUIRED = "approval.required"
    APPROVAL_APPROVED = "approval.approved"
    APPROVAL_REJECTED = "approval.rejected"
    TASK_COMPLETE = "task.complete"
    AGENT_IDLE = "agent.idle"
    USER_RETURNED = "user.returned"
    SUBAGENT_STARTED = "agent.subagent_spawned"
    SUBAGENT_FINISHED = "agent.subagent_finished"
    SUBAGENT_FAILED = "agent.subagent_failed"


@dataclass
class SemanticEvent:
    kind: EventKind
    tool: str = ""
    category: str = ""
    session_id: str = ""
    task_id: str = ""
    ts: float = field(default_factory=time.time)
    importance: float = 0.5

    def __repr__(self) -> str:  # no content ever
        return f"<ev {self.kind.value}{' tool=' + self.tool if self.tool else ''}>"


# ---------------------------------------------------------------------------
# Adapter allow-list (spec rev1 §5.1). Raw hook fields are NEVER mapped here;
# only enum/bounded-scalar derivations are permitted.
TOOL_CATEGORY: dict[str, str] = {
    "web_search": "web", "web_extract": "web", "web_search/query": "web",
    "browser_*": "browser", "browser_exec": "browser", "open_preview": "browser",
    "read_preview": "browser", "drive_preview": "browser",
    "annotate_preview": "browser", "close_preview": "browser",
    "terminal": "terminal", "execute_code": "terminal", "process": "terminal",
    "read_terminal": "terminal",
    "read_file": "file", "write_file": "file", "patch": "file",
    "search_files": "file",
    "github_*": "development", "gh": "development", "github": "development",
    "image_generate": "design", "vision_analyze": "media",
    "text_to_speech": "audio", "local-audio-transcription": "audio",
    "songsee": "audio", "video_generate": "media", "video_analyze": "media",
    "memory": "memory", "fact_store": "memory", "session_search": "memory",
    "obsidian": "memory",
    "todo": "planning", "delegate_task": "delegation", "a2a_call": "delegation",
    "a2a_orchestrate": "delegation",
    "cronjob": "scheduling",
    "skill_*": "learning", "skills_list": "learning", "skill_view": "learning",
    "skill_manage": "learning",
    "computer_use": "desktop", "apply_layout": "desktop", "focus_pane": "desktop",
    "maps": "maps",
    "docx": "docs", "pdf": "docs", "powerpoint": "docs", "box": "docs",
    "notion": "docs", "google_workspace": "docs",
    "xlsx": "sheets", "excel_openpyxl": "sheets", "airtable": "sheets",
    "spreadsheet_verification_workflows": "sheets",
    "email": "communication", "gmail": "communication", "teams": "communication",
    "gmail-drive-delivery": "communication",
}


def classify_tool(tool_name: str) -> str:
    for prefix, cat in TOOL_CATEGORY.items():
        if prefix.endswith("*") and tool_name.startswith(prefix[:-1]):
            return cat
        if tool_name == prefix:
            return cat
    return "general"


# Delegated work runs in its own session id and marks its records with a
# subagent task id. Recognising it lets the visible companion keep showing the
# session the USER is in instead of being dragged to whichever worker spoke last.
_DELEGATED_TASK = re.compile(r"sa-\d{1,4}-[0-9a-fA-F]{4,64}\Z")


def is_delegated_task(task_id: object) -> bool:
    """True when a record came from a subagent rather than a top-level turn."""
    return isinstance(task_id, str) and _DELEGATED_TASK.fullmatch(task_id) is not None
