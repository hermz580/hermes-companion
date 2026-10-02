"""The double-click panel must describe real state and never invent any.

The panel is where the companion explains itself, so it is the easiest place to
accidentally lie: a pretty popup that says "working" or "done" without an event
behind it is exactly the failure the user called out. The state builder is pure
so these rules can be tested without a window.
"""
from __future__ import annotations

import unittest
from pathlib import Path

import pytest


class Overlay:
    """Stands in for the pet overlay, including its optional panel hook."""

    def __init__(self):
        self.played = []
        self.panel_state_provider = None

    def play_chain(self, chain, category=""):
        self.played.append((chain, category))

    def enqueue(self, beats, replace=False):
        pass


def _state(**overrides):
    from hermes_companion.renderer.companion_panel import build_panel_state

    kwargs = dict(
        companion_id="the-alpha-and",
        display_name="The Alpha And",
        role="Visible companion",
        mode="follow",
        session_id="20260912_140154_783aac",
        last_event="",
        last_tool="",
        last_event_age_s=None,
        events_seen=0,
        engine_state="idle",
        memories=(),
    )
    kwargs.update(overrides)
    return build_panel_state(**kwargs)


class PanelTruthTests(unittest.TestCase):
    def test_no_event_yet_is_reported_honestly(self):
        state = _state()
        values = {f.label: f.value for f in state.fields}
        self.assertEqual(values["Last real event"], "none observed yet")
        self.assertFalse(state.has_observed_event)
        notice = state.notice.lower()
        self.assertIn("silence", notice)
        self.assertIn("not proof", notice)

    def test_a_real_event_is_shown_verbatim_with_its_tool_and_age(self):
        state = _state(last_event="tool.started", last_tool="terminal",
                       last_event_age_s=2.5, events_seen=17)
        values = {f.label: f.value for f in state.fields}
        self.assertTrue(state.has_observed_event)
        self.assertEqual(values["Last real event"], "tool.started (terminal)")
        self.assertEqual(values["Last real event age"], "2.5s ago")
        self.assertEqual(values["Events observed this run"], "17")

    def test_a_started_event_never_reads_as_success(self):
        for event in ("tool.started", "tool.progress", "agent.started"):
            with self.subTest(event=event):
                state = _state(last_event=event, last_tool="terminal",
                               last_event_age_s=1.0)
                blob = " ".join(f"{f.label} {f.value}" for f in state.fields).lower()
                for claim in ("success", "complete", "finished", "verified"):
                    self.assertNotIn(claim, blob)

    def test_follow_and_pinned_modes_are_described_differently(self):
        follow = {f.label: f.value for f in _state(mode="follow").fields}["Mode"]
        pinned = {f.label: f.value for f in _state(mode="pinned").fields}["Mode"]
        self.assertIn("follow", follow.lower())
        self.assertIn("active session", follow.lower())
        self.assertIn("pinned", pinned.lower())
        self.assertNotEqual(follow, pinned)

    def test_missing_session_and_absent_role_degrade_without_inventing(self):
        values = {f.label: f.value for f in _state(session_id="", role="").fields}
        self.assertEqual(values["Session"], "none yet")
        self.assertEqual(values["Role"], "not set")

    def test_memory_is_shown_but_explicitly_non_authoritative(self):
        state = _state(memories=("Prefers concise replies.",))
        self.assertEqual(state.memories, ("Prefers concise replies.",))
        notice = state.notice.lower()
        self.assertIn("reference data", notice)
        self.assertIn("cannot authorize", notice)

    def test_memory_entries_are_bounded_and_blank_ones_dropped(self):
        state = _state(memories=("ok", "", "   ", "x" * 5000))
        self.assertEqual(len(state.memories), 2)
        self.assertTrue(all(len(m) <= 400 for m in state.memories))

    def test_invalid_counters_and_modes_fail_closed(self):
        for bad in (True, -1, None, "3", 1.5):
            with self.subTest(events_seen=bad), pytest.raises(ValueError):
                _state(events_seen=bad)
        for bad in ("", None, "following", "pinned-ish", 1):
            with self.subTest(mode=bad), pytest.raises(ValueError):
                _state(mode=bad)

    def test_negative_age_is_clamped_rather_than_reported_as_future(self):
        state = _state(last_event="tool.started", last_event_age_s=-4.0)
        values = {f.label: f.value for f in state.fields}
        self.assertEqual(values["Last real event age"], "0.0s ago")

    def test_simulation_state_is_labelled_as_not_real_evidence(self):
        state = _state(simulator=True)
        self.assertIn("SIMULATION", state.title)
        self.assertIn("not real", state.notice.lower())


class PanelWindowTests(unittest.TestCase):
    """The window is thin; it must render the state and claim nothing more."""

    def test_window_renders_real_state_and_closes_cleanly(self):
        from conftest import shared_tk_root
        from hermes_companion.renderer.companion_panel import (
            CompanionPanelWindow, build_panel_state)

        root = shared_tk_root()
        state = build_panel_state(
            companion_id="the-alpha-and", display_name="The Alpha And",
            role="Visible companion", mode="follow", session_id="session-a",
            last_event="tool.started", last_tool="terminal",
            last_event_age_s=1.0, events_seen=4, engine_state="working",
            memories=("Prefers concise replies.",))
        win = CompanionPanelWindow(root, state)
        try:
            text = win.all_text()
            self.assertIn("The Alpha And", text)
            self.assertIn("tool.started", text)
            self.assertIn("reference data", text.lower())
            self.assertIn("silence", text.lower())
        finally:
            win.close()
        self.assertFalse(win.winfo_exists())


class PanelWiringTests(unittest.TestCase):
    """The panel's content must come from the tail's real observations."""

    def _make(self, tmp, **kw):
        from hermes_companion.renderer.live import EventTail
        from hermes_companion.core.event_auth import sign_record

        overlay = Overlay()
        kw.setdefault("follow", True)
        # Mirrors production: the live CLI passes the active pet's slug, which is
        # the identity the library is keyed by.
        kw.setdefault("companion_id", "the-alpha-and")
        tail = EventTail(Path(tmp) / "events.jsonl", overlay, from_end=False,
                         auth_key=b"k" * 32, idle=False, **kw)
        return tail, overlay, sign_record

    def test_panel_reports_no_events_honestly_before_anything_happens(self):
        import tempfile
        from pathlib import Path
        with tempfile.TemporaryDirectory() as d:
            tail, _overlay, _sign = self._make(d)
            state = tail.panel_state()
            values = {f.label: f.value for f in state.fields}
            self.assertEqual(values["Last real event"], "none observed yet")
            self.assertFalse(state.has_observed_event)

    def test_panel_reflects_a_real_observed_event(self):
        import tempfile
        from pathlib import Path
        with tempfile.TemporaryDirectory() as d:
            tail, _overlay, sign = self._make(d)
            tail._handle_record(sign({
                "event": "tool.started", "tool": "terminal",
                "category": "terminal", "session_id": "session-a"}, b"k" * 32))
            state = tail.panel_state()
            values = {f.label: f.value for f in state.fields}
            self.assertTrue(state.has_observed_event)
            self.assertEqual(values["Last real event"], "tool.started (terminal)")
            self.assertEqual(values["Events observed this run"], "1")
            self.assertIn("follow", values["Mode"].lower())

    def test_panel_shows_only_approved_memory_from_the_library(self):
        import tempfile, os
        from pathlib import Path
        from hermes_companion.core.companion_memory import CompanionMemoryStore

        with tempfile.TemporaryDirectory() as d:
            home = Path(d)
            (home / "companion").mkdir(parents=True, exist_ok=True)
            store = CompanionMemoryStore(home / "companion" / "library.sqlite3")
            try:
                store.create_companion("the-alpha-and", "The Alpha And", "Guide")
                store.add_memory("the-alpha-and", "Approved note.",
                                 source="user", approved=True)
                store.add_memory("the-alpha-and", "Unapproved note.",
                                 source="user", approved=False)
            finally:
                store.close()

            old = os.environ.get("HERMES_HOME")
            os.environ["HERMES_HOME"] = str(home)
            try:
                tail, _overlay, _sign = self._make(d)
                state = tail.panel_state()
                self.assertIn("Approved note.", state.memories)
                self.assertNotIn("Unapproved note.", state.memories)
                values = {f.label: f.value for f in state.fields}
                self.assertIn("The Alpha And", values["Companion"])
            finally:
                if old is None:
                    os.environ.pop("HERMES_HOME", None)
                else:
                    os.environ["HERMES_HOME"] = old

    def test_double_click_opens_a_real_panel_window(self):
        from conftest import shared_tk_root
        from hermes_companion.renderer.petdex_overlay import PetdexOverlay

        root = shared_tk_root()
        state = _state(last_event="tool.finished", last_tool="terminal",
                       last_event_age_s=0.5, events_seen=3)

        class Holder:
            pass

        holder = Holder()
        holder.root = root
        holder.panel_state_provider = lambda: state
        holder._panel = None

        PetdexOverlay._open_status_panel(holder)      # the real method, no Tk pet
        try:
            self.assertIsNotNone(holder._panel)
            self.assertTrue(holder._panel.winfo_exists())
            self.assertIn("tool.finished", holder._panel.all_text())
        finally:
            holder._panel.close()

    def test_panel_is_optional_and_its_absence_never_breaks_the_pet(self):
        from hermes_companion.renderer.petdex_overlay import PetdexOverlay

        class Bare:
            root = None
            panel_state_provider = None
            _panel = None

        PetdexOverlay._open_status_panel(Bare())      # must simply do nothing

        class Broken:
            root = None
            _panel = None

            @staticmethod
            def panel_state_provider():
                raise RuntimeError("boom")

        PetdexOverlay._open_status_panel(Broken())    # must not raise


if __name__ == "__main__":
    unittest.main()
