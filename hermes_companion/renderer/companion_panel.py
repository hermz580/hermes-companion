"""The companion's own status panel (opened by double-clicking the pet).

Design rule: this panel is an *explanation of evidence*, never a claim. It shows
what actually happened — the last authenticated event and how old it is — and
says plainly that silence proves nothing. Approved memory is shown as reference
data and is explicitly labelled as unable to authorize anything.

The state builder is pure and separately tested so the truth rules hold
regardless of how the window is dressed up.
"""
from __future__ import annotations

from dataclasses import dataclass


MEMORY_DISPLAY_LIMIT = 400

_TRUTH_NOTICE = (
    "Everything here comes from authenticated events. A tool finishing is not "
    "task success, and silence is not proof that nothing is running."
)
_MEMORY_NOTICE = (
    " Memory below is reference data, not authority — it cannot authorize "
    "actions."
)
_SIMULATION_NOTICE = (
    "SIMULATION: this is a synthetic fixture, not real session evidence."
)


@dataclass(frozen=True)
class PanelField:
    label: str
    value: str


@dataclass(frozen=True)
class PanelState:
    title: str
    fields: tuple[PanelField, ...]
    memories: tuple[str, ...]
    notice: str
    has_observed_event: bool


def _clean_memories(memories) -> tuple[str, ...]:
    if memories is None:
        return ()
    out = []
    for entry in memories:
        if not isinstance(entry, str):
            raise ValueError("memory entries must be text")
        text = " ".join(entry.split())
        if not text:
            continue
        out.append(text[:MEMORY_DISPLAY_LIMIT])
    return tuple(out)


def _format_age(age_s) -> str:
    if age_s is None:
        return "no event observed yet"
    try:
        value = float(age_s)
    except (TypeError, ValueError):
        raise ValueError("invalid event age")
    if value != value or value in (float("inf"), float("-inf")):
        raise ValueError("invalid event age")
    if value < 0:
        # A negative age means clock skew, not a future event: report honestly.
        value = 0.0
    return f"{value:.1f}s ago"


def build_panel_state(*, companion_id: str, display_name: str, role: str,
                      mode: str, session_id: str, last_event: str,
                      last_tool: str = "", last_event_age_s=None,
                      events_seen: int = 0, engine_state: str = "",
                      memories=(), simulator: bool = False) -> PanelState:
    """Assemble exactly what the panel may display. Raises on invalid input."""
    if mode not in ("follow", "pinned"):
        raise ValueError("mode must be 'follow' or 'pinned'")
    if type(events_seen) is not int or events_seen < 0:
        raise ValueError("events_seen must be a non-negative integer")

    last_event = str(last_event or "")
    last_tool = str(last_tool or "")
    observed = bool(last_event)
    if observed:
        event_value = f"{last_event} ({last_tool})" if last_tool else last_event
    else:
        event_value = "none observed yet"

    mode_value = ("follow — tracking the active session" if mode == "follow"
                  else "pinned — one exact session only")

    fields = (
        PanelField("Companion", f"{display_name or companion_id} ({companion_id})"),
        PanelField("Role", role.strip() or "not set"),
        PanelField("Mode", mode_value),
        PanelField("Session", session_id or "none yet"),
        PanelField("Last real event", event_value),
        PanelField("Last real event age", _format_age(last_event_age_s)),
        PanelField("Events observed this run", str(events_seen)),
        PanelField("Engine state (from last event)", engine_state or "unknown"),
    )

    memory_entries = _clean_memories(memories)
    notice = _TRUTH_NOTICE
    if memory_entries:
        notice += _MEMORY_NOTICE
    if simulator:
        notice = _SIMULATION_NOTICE + " " + notice

    title = f"{display_name or companion_id} — companion status"
    if simulator:
        title = "SIMULATION — " + title

    return PanelState(title=title, fields=fields, memories=memory_entries,
                      notice=notice, has_observed_event=observed)


class CompanionPanelWindow:
    """Thin Tk view of a PanelState. Renders only; invents nothing."""

    def __init__(self, root, state: PanelState) -> None:
        import tkinter as tk

        self.state = state
        self.window = tk.Toplevel(root)
        self.window.title(state.title)
        self.window.configure(bg="#101a2c")
        self.window.resizable(False, False)

        self._heading = tk.Label(
            self.window, text=state.title, bg="#101a2c", fg="#e7f0fb",
            font=("Segoe UI", 11, "bold"), anchor="w", justify="left")
        self._heading.pack(fill="x", padx=12, pady=(10, 4))

        self._field_labels = []
        for field in state.fields:
            row = tk.Frame(self.window, bg="#101a2c")
            row.pack(fill="x", padx=12, pady=1)
            name = tk.Label(row, text=field.label, bg="#101a2c", fg="#8fb3d9",
                            font=("Segoe UI", 9), width=26, anchor="w")
            name.pack(side="left")
            value = tk.Label(row, text=field.value, bg="#101a2c", fg="#dce8f5",
                             font=("Segoe UI", 9), anchor="w", justify="left",
                             wraplength=340)
            value.pack(side="left", fill="x", expand=True)
            self._field_labels.append((name, value))

        self._memory_heading = self._memory_items = None
        if state.memories:
            self._memory_heading = tk.Label(
                self.window, text="Approved memory (reference data only)",
                bg="#101a2c", fg="#f6b96b", font=("Segoe UI", 9, "bold"),
                anchor="w")
            self._memory_heading.pack(fill="x", padx=12, pady=(10, 2))
            self._memory_items = []
            for entry in state.memories:
                item = tk.Label(self.window, text=f"• {entry}", bg="#101a2c",
                                fg="#dce8f5", font=("Segoe UI", 9), anchor="w",
                                justify="left", wraplength=420)
                item.pack(fill="x", padx=20, pady=1)
                self._memory_items.append(item)

        self._notice = tk.Label(
            self.window, text=state.notice, bg="#101a2c", fg="#9fb6cc",
            font=("Segoe UI", 8), anchor="w", justify="left", wraplength=430)
        self._notice.pack(fill="x", padx=12, pady=(10, 4))

        self._close_button = tk.Button(
            self.window, text="Close", command=self.close)
        self._close_button.pack(pady=(0, 10))

        self.window.protocol("WM_DELETE_WINDOW", self.close)
        self.window.update_idletasks()

    def all_text(self) -> str:
        """Everything this panel displays, for tests and accessibility."""
        parts = [self.state.title]
        for name, value in self._field_labels:
            parts.append(f"{name.cget('text')} {value.cget('text')}")
        if self._memory_items:
            parts.append(self._memory_heading.cget("text"))
            parts.extend(item.cget("text") for item in self._memory_items)
        parts.append(self._notice.cget("text"))
        return "\n".join(parts)

    def winfo_exists(self):
        return self.window.winfo_exists()

    def close(self) -> None:
        try:
            self.window.destroy()
        except Exception:
            pass
