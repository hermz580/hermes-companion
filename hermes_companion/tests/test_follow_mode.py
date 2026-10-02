"""Follow mode: one companion across every session, with one switch to stop.

Pinned mode (the previous default) displays exactly one session and ignores
everything else. Follow mode adopts whichever session is producing activity,
announces the switch, and lets the previous session's animation be replaced
rather than overlap. Both are explicit user choices; neither is inferred.
"""
import json
import unittest
from pathlib import Path
from tempfile import TemporaryDirectory

from hermes_companion.core import binding as b
from hermes_companion.core.event_auth import sign_record

KEY = b"k" * 32


class Overlay:
    def __init__(self):
        self.played = []
        self.enqueued = []

    def play_chain(self, chain, category=""):
        self.played.append((chain, category))

    def enqueue(self, beats, replace=False):
        self.enqueued.append((beats, replace))


class Engine:
    def __init__(self):
        self.events = []

    def handle(self, event):
        self.events.append(event)
        return None

    def idle_tick(self, _dt):
        return None


def _tail(tmp, **kwargs):
    from hermes_companion.renderer.live import EventTail
    tail = EventTail(Path(tmp) / "events.jsonl", Overlay(), from_end=False,
                     auth_key=KEY, idle=False, **kwargs)
    tail.engine = Engine()
    return tail


_UNSET = object()


def _signed(session, event="tool.started", tool="terminal", task=_UNSET):
    """A signed record. ``task`` defaults to the session (a top-level turn).

    Pass ``task=None`` to omit the field entirely - which is how a subagent's
    own lifecycle events (``agent.started`` / ``agent.idle``) actually arrive.
    """
    payload = {"event": event, "tool": tool, "session_id": session}
    task_id = session if task is _UNSET else task
    if task_id is not None:
        payload["task_id"] = task_id
    return sign_record(payload, KEY)


class DelegatedWorkNeverOwnsTheDisplayTests(unittest.TestCase):
    """Subagent chatter must not pull the companion off your own session.

    A delegated turn runs in its own session id, so an activity-based follower
    treats it as a peer and hands the display over - which is how the pet ended
    up thrashing between three workers while the user sat in one chat. Delegated
    records self-identify via task_id ``sa-N-<hex>``, so they may animate only
    the session already on screen and may never claim the display.
    """

    def _tail(self, tmp, **kw):
        from hermes_companion.renderer.live import EventTail
        tail = EventTail(Path(tmp) / "events.jsonl", Overlay(), from_end=False,
                         auth_key=KEY, idle=False,
                         companion_id="the-alpha-and", **kw)
        tail.engine = Engine()
        return tail

    def test_delegated_record_cannot_claim_the_display(self):
        with TemporaryDirectory() as d:
            tail = self._tail(d, follow=True)
            tail._handle_record(_signed("20260912_140237_caa343", task="sa-0-6ca7a8df"))
            self.assertIsNone(tail.following_session,
                              "a subagent session claimed the display")
            self.assertEqual(tail.engine.events, [])

    def test_user_session_keeps_the_display_while_workers_chatter(self):
        with TemporaryDirectory() as d:
            tail = self._tail(d, follow=True)
            tail._handle_record(_signed("chat", task="chat"))
            self.assertEqual(tail.following_session, "chat")
            for worker, task in (("w1", "sa-0-aaaa1111"), ("w2", "sa-1-bbbb2222"),
                                 ("w3", "sa-2-cccc3333")):
                tail._handle_record(_signed(worker, task=task))
            self.assertEqual(tail.following_session, "chat",
                             "delegated work stole the display")

    def test_delegated_work_still_animates_the_displayed_session(self):
        with TemporaryDirectory() as d:
            tail = self._tail(d, follow=True)
            tail._handle_record(_signed("chat", task="chat"))
            before = len(tail.engine.events)
            tail._handle_record(_signed("chat", task="sa-0-aaaa1111"))
            self.assertEqual(len(tail.engine.events), before + 1)

    def test_quiet_chat_does_not_hand_over_to_a_worker(self):
        class Clock:
            now = 1000.0

            def __call__(self):
                return self.now

        clock = Clock()
        with TemporaryDirectory() as d:
            tail = self._tail(d, follow=True, clock=clock)
            tail._handle_record(_signed("chat", task="chat"))
            clock.now += 600.0            # the user's chat has been quiet a while
            tail._handle_record(_signed("w1", task="sa-0-aaaa1111"))
            self.assertEqual(tail.following_session, "chat",
                             "a worker took over a merely-quiet chat")

    def test_a_real_other_chat_still_takes_over_after_the_dwell(self):
        class Clock:
            now = 1000.0

            def __call__(self):
                return self.now

        clock = Clock()
        with TemporaryDirectory() as d:
            tail = self._tail(d, follow=True, clock=clock)
            tail._handle_record(_signed("chat-a", task="chat-a"))
            clock.now += 30.0
            tail._handle_record(_signed("chat-b", task="chat-b"))
            self.assertEqual(tail.following_session, "chat-b")

    def test_a_worker_cannot_reclaim_via_its_own_unmarked_lifecycle_event(self):
        """The real leak: a worker's agent.idle carries no task id at all."""
        class Clock:
            now = 1000.0

            def __call__(self):
                return self.now

        clock = Clock()
        with TemporaryDirectory() as d:
            tail = self._tail(d, follow=True, clock=clock)
            tail._handle_record(_signed("chat", task="chat"))
            # The worker reveals itself by doing delegated work...
            tail._handle_record(_signed("w1", task="sa-0-aaaa1111"))
            clock.now += 600.0
            # ...so its own unmarked idle event must not take the display.
            tail._handle_record(_signed("w1", event="agent.idle", task=None))
            self.assertEqual(tail.following_session, "chat",
                             "a worker reclaimed the display with agent.idle")

    def test_a_session_is_never_permanently_labelled_a_worker(self):
        """A real top-level turn from that session clears the mark."""
        class Clock:
            now = 1000.0

            def __call__(self):
                return self.now

        clock = Clock()
        with TemporaryDirectory() as d:
            tail = self._tail(d, follow=True, clock=clock)
            tail._handle_record(_signed("chat", task="chat"))
            tail._handle_record(_signed("s1", task="sa-0-aaaa1111"))
            self.assertIn("s1", tail._worker_sessions)
            tail._handle_record(_signed("s1", task="s1"))   # a genuine own turn
            self.assertNotIn("s1", tail._worker_sessions)



class BindingModeTests(unittest.TestCase):
    def test_follow_names_the_companion_to_carry_across_sessions(self):
        with TemporaryDirectory() as d:
            p = Path(d) / "bindings.json"
            b.set_mode(b.MODE_FOLLOW, "the-alpha-and", path=p)
            self.assertEqual(b.current_mode(path=p), b.MODE_FOLLOW)
            self.assertEqual(b.following_companion(path=p), "the-alpha-and")

    def test_pinned_switch_turns_follow_back_off(self):
        with TemporaryDirectory() as d:
            p = Path(d) / "bindings.json"
            b.set_mode(b.MODE_FOLLOW, "the-alpha-and", path=p)
            b.set_mode(b.MODE_PINNED, path=p)
            self.assertIsNone(b.following_companion(path=p))
            self.assertEqual(b.current_mode(path=p), b.MODE_PINNED)

    def test_follow_without_a_companion_is_refused(self):
        with TemporaryDirectory() as d:
            p = Path(d) / "bindings.json"
            with self.assertRaises(ValueError):
                b.set_mode(b.MODE_FOLLOW, "", path=p)
            with self.assertRaises(ValueError):
                b.set_mode("nonsense", path=p)

    def test_unknown_mode_in_the_file_degrades_to_pinned(self):
        with TemporaryDirectory() as d:
            p = Path(d) / "bindings.json"
            p.write_text(json.dumps({"version": 2, "mode": "follow",
                                     "companion_id": "ok", "bindings": []}),
                         encoding="utf-8")
            self.assertEqual(b.following_companion(path=p), "ok")
            p.write_text(json.dumps({"version": 2, "mode": "follow",
                                     "companion_id": "", "bindings": []}),
                         encoding="utf-8")
            self.assertIsNone(b.following_companion(path=p))
            self.assertEqual(b.current_mode(path=p), b.MODE_PINNED)

    def test_version_one_files_still_read_as_pinned(self):
        with TemporaryDirectory() as d:
            p = Path(d) / "bindings.json"
            p.write_text(json.dumps({"version": 1, "bindings": [
                {"companion_id": "the-alpha-and", "session_id": "session-a"}]}),
                encoding="utf-8")
            self.assertEqual(b.current_mode(path=p), b.MODE_PINNED)
            self.assertIsNone(b.following_companion(path=p))
            self.assertEqual(len(b.describe(path=p)), 1)

    def test_pinned_bindings_survive_switching_mode(self):
        with TemporaryDirectory() as d:
            p = Path(d) / "bindings.json"
            b.bind("the-alpha-and", "session-a", path=p)
            b.set_mode(b.MODE_FOLLOW, "the-alpha-and", path=p)
            b.set_mode(b.MODE_PINNED, path=p)
            self.assertEqual(b.describe(path=p)[0]["session_id"], "session-a")


class FollowRenderingTests(unittest.TestCase):
    def test_follow_requires_no_exact_session_but_still_needs_one_of_them(self):
        with TemporaryDirectory() as d:
            from hermes_companion.renderer.live import EventTail
            with self.assertRaises(ValueError):
                EventTail(Path(d) / "e.jsonl", Overlay(), auth_key=KEY)
            with self.assertRaises(ValueError):
                EventTail(Path(d) / "e.jsonl", Overlay(), follow=True,
                          bound_session_id="session-a", auth_key=KEY)

    def test_follow_adopts_and_switches_between_sessions(self):
        class Clock:
            now = 1000.0

            def __call__(self):
                return self.now

        clock = Clock()
        with TemporaryDirectory() as d:
            # Switching is hysteretic: the displayed session is held until it
            # goes quiet, so drive a controlled clock rather than wall time.
            tail = _tail(d, follow=True, clock=clock)
            tail._handle_record(_signed("session-a"))
            self.assertEqual(tail.following_session, "session-a")
            clock.now += 30.0
            tail._handle_record(_signed("session-b"))
            self.assertEqual(tail.following_session, "session-b")
            self.assertEqual([e.session_id for e in tail.engine.events],
                             ["session-a", "session-b"])
            self.assertFalse(tail.bound_session_id)

    def test_follow_ignores_unattributable_and_unsigned_records(self):
        with TemporaryDirectory() as d:
            tail = _tail(d, follow=True)
            tail._handle_record({"event": "tool.started", "tool": "terminal"})
            tail._handle_record({"event": "tool.started", "tool": "terminal",
                                 "session_id": "session-a"})  # unsigned
            self.assertEqual(tail.engine.events, [])
            self.assertIsNone(tail.following_session)

    def test_pinned_still_refuses_another_session(self):
        with TemporaryDirectory() as d:
            tail = _tail(d, bound_session_id="session-a")
            tail._handle_record(_signed("session-b"))
            self.assertEqual(tail.engine.events, [])
            tail._handle_record(_signed("session-a"))
            self.assertEqual(len(tail.engine.events), 1)


class FollowHysteresisTests(unittest.TestCase):
    """Following must not thrash when several sessions are active at once.

    Subagents and background turns each get their own session, so an
    activity-based follower that switches on every new session id flaps
    constantly — dozens of switches a second — which is exactly the "looks
    wild when I have many things running" failure. Stay on the displayed
    session while it is still active; move only once it has gone quiet.
    """

    def _tail(self, tmp, clock):
        from hermes_companion.renderer.live import EventTail
        tail = EventTail(Path(tmp) / "events.jsonl", Overlay(), from_end=False,
                         auth_key=KEY, idle=False, follow=True, clock=clock)
        tail.engine = Engine()
        return tail

    def test_interleaved_sessions_do_not_flap(self):
        class Clock:
            now = 1000.0

            def __call__(self):
                return self.now

        clock = Clock()
        with TemporaryDirectory() as d:
            tail = self._tail(d, clock)
            tail._handle_record(_signed("session-a"))
            self.assertEqual(tail.following_session, "session-a")
            played = len(tail.engine.events)

            # session-b chatters while session-a is still live (within dwell).
            for _ in range(6):
                clock.now += 0.2
                tail._handle_record(_signed("session-b"))
                clock.now += 0.2
                tail._handle_record(_signed("session-a"))
            self.assertEqual(tail.following_session, "session-a",
                             "follower flapped to another still-competing session")
            self.assertEqual(len(tail.engine.events), played + 6,
                             "records from the other session were rendered anyway")

        # Count the announcements: exactly one follow start, no switches.
        # (asserted via the absence of extra engine events above)

    def test_switches_once_the_displayed_session_goes_quiet(self):
        class Clock:
            now = 1000.0

            def __call__(self):
                return self.now

        clock = Clock()
        with TemporaryDirectory() as d:
            tail = self._tail(d, clock)
            tail._handle_record(_signed("session-a"))
            clock.now += 30.0                     # session-a goes quiet
            tail._handle_record(_signed("session-b"))
            self.assertEqual(tail.following_session, "session-b")
            self.assertEqual([e.session_id for e in tail.engine.events],
                             ["session-a", "session-b"])

    def test_pinned_mode_is_unaffected_by_the_dwell(self):
        class Clock:
            now = 1000.0

            def __call__(self):
                return self.now

        clock = Clock()
        with TemporaryDirectory() as d:
            from hermes_companion.renderer.live import EventTail
            tail = EventTail(Path(d) / "events.jsonl", Overlay(), from_end=False,
                             auth_key=KEY, idle=False, bound_session_id="session-a",
                             clock=clock)
            tail.engine = Engine()
            tail._handle_record(_signed("session-a"))
            tail._handle_record(_signed("session-b"))
            self.assertEqual([e.session_id for e in tail.engine.events], ["session-a"])


class FollowBrainTests(unittest.TestCase):
    def _store(self, path):
        from hermes_companion.core.companion_memory import CompanionMemoryStore
        store = CompanionMemoryStore(path)
        store.create_companion("the-alpha-and", "The Alpha And", "guide")
        store.add_memory("the-alpha-and", "Prefers concise replies.",
                         source="user", approved=True, scope="companion")
        return store

    def test_follow_injects_for_a_session_with_no_binding(self):
        from hermes_companion.core.companion_execution import build_context_block
        with TemporaryDirectory() as d:
            home = Path(d)
            store = self._store(home / "library.sqlite3")
            try:
                b.set_mode(b.MODE_FOLLOW, "the-alpha-and", path=home / "bindings.json")
                audit = home / "injection_audit.jsonl"
                block = build_context_block("some-new-session", "some-new-task",
                                            store=store,
                                            bindings_path=home / "bindings.json",
                                            audit_path=audit)
                self.assertTrue(block)
                self.assertIn("the-alpha-and", block)
                record = json.loads(audit.read_text(encoding="utf-8").splitlines()[-1])
                self.assertEqual(record["decision"], "injected_follow")
                self.assertFalse(record.get("content"))
            finally:
                store.close()

    def test_pinned_mode_still_refuses_an_unbound_session(self):
        from hermes_companion.core.companion_execution import build_context_block
        with TemporaryDirectory() as d:
            home = Path(d)
            store = self._store(home / "library.sqlite3")
            try:
                audit = home / "injection_audit.jsonl"
                block = build_context_block("some-new-session", "some-new-task",
                                            store=store,
                                            bindings_path=home / "bindings.json",
                                            audit_path=audit)
                self.assertEqual(block, "")
                record = json.loads(audit.read_text(encoding="utf-8").splitlines()[-1])
                self.assertEqual(record["decision"], "unbound")
            finally:
                store.close()

    def test_exact_binding_still_wins_over_follow(self):
        from hermes_companion.core.companion_execution import build_context_block
        with TemporaryDirectory() as d:
            home = Path(d)
            store = self._store(home / "library.sqlite3")
            try:
                store.create_companion("other-pet", "Other")
                store.add_memory("other-pet", "Other pet's own note.",
                                 source="user", approved=True, scope="companion")
                path = home / "bindings.json"
                b.bind("other-pet", "session-x", path=path)
                b.set_mode(b.MODE_FOLLOW, "the-alpha-and", path=path)
                block = build_context_block("session-x", "task-x", store=store,
                                            bindings_path=path,
                                            audit_path=home / "a.jsonl")
                self.assertIn("Other", block)
                self.assertNotIn("The Alpha And", block)
            finally:
                store.close()


if __name__ == "__main__":
    unittest.main()
