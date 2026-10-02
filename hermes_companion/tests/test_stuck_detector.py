import unittest

from hermes_companion.core.events import EventKind
from hermes_companion.core.stuck import StuckDetector


class StuckDetectorTests(unittest.TestCase):
    def _base(self, **kw):
        defaults = dict(fresh_seconds=90.0, min_suspect=30.0,
                        typical_multiplier=3.0, typical_padding=120.0,
                        default_typical=60.0)
        defaults.update(kw)
        return StuckDetector(**defaults)

    def test_no_open_tool_is_quiet_not_stuck(self):
        d = self._base()
        d.ingest(EventKind.AGENT_IDLE.value, "", "", "s", "s", 1000.0)
        v = d.check(now=1100.0)
        self.assertEqual(v.state, "quiet")

    def test_open_tool_under_threshold_is_working(self):
        d = self._base(min_suspect=30.0)
        d.ingest(EventKind.TOOL_STARTED.value, "terminal", "terminal", "s", "t", 1000.0)
        v = d.check(now=1010.0)  # only 10s
        self.assertEqual(v.state, "working")

    def test_open_tool_learns_typical_duration_from_real_finish(self):
        d = self._base(min_suspect=30.0, typical_multiplier=3.0, typical_padding=120.0)
        # learn typical: a tool that took 5s
        d.ingest(EventKind.TOOL_STARTED.value, "terminal", "terminal", "s", "t1", 1000.0)
        d.ingest(EventKind.TOOL_FINISHED.value, "terminal", "terminal", "s", "t1", 1005.0)
        # now an open tool that exceeds threshold (5*3=15, +120 => 135s, floor 30)
        d.ingest(EventKind.TOOL_STARTED.value, "terminal", "terminal", "s", "t2", 2000.0)
        # 300s later, still open, nothing after it
        v = d.check(now=2300.0)
        self.assertEqual(v.state, "stuck")
        self.assertEqual(v.open_tool.tool, "terminal")
        self.assertGreaterEqual(v.open_age_s, 300.0)

    def test_stuck_requires_the_open_tool_be_the_latest_record(self):
        d = self._base(min_suspect=30.0)
        d.ingest(EventKind.TOOL_STARTED.value, "terminal", "terminal", "s", "t", 1000.0)
        # a later event proves the agent is alive and doing something else
        d.ingest(EventKind.TOOL_STARTED.value, "web_search", "web", "s", "w", 2200.0)
        v = d.check(now=2300.0)
        self.assertEqual(v.state, "working")

    def test_quiet_stream_with_no_open_tool_is_quiet(self):
        d = self._base(fresh_seconds=90.0)
        # tool started then finished; no open tool now, and stream is stale
        d.ingest(EventKind.TOOL_STARTED.value, "terminal", "terminal", "s", "t", 1000.0)
        d.ingest(EventKind.TOOL_FINISHED.value, "terminal", "terminal", "s", "t", 1005.0)
        # no open tool = no work in flight = quiet, even on a stale stream
        v = d.check(now=2000.0)
        self.assertEqual(v.state, "quiet")

    def test_open_tool_past_threshold_with_quiet_stream_is_stuck(self):
        # An open tool far past its typical duration is stuck evidence even if
        # the stream has since gone quiet — the observer was alive to record
        # the start, so this is not a dead-observer false positive.
        d = self._base(min_suspect=30.0, fresh_seconds=90.0)
        d.ingest(EventKind.TOOL_STARTED.value, "terminal", "terminal", "s", "t", 1000.0)
        v = d.check(now=2000.0)
        self.assertEqual(v.state, "stuck")

    def test_pending_approval_is_needs_you_not_stuck(self):
        d = self._base(min_suspect=30.0)
        d.ingest(EventKind.APPROVAL_REQUIRED.value, "", "", "s", "", 1000.0)
        d.ingest(EventKind.TOOL_STARTED.value, "terminal", "terminal", "s", "t", 1000.0)
        v = d.check(now=2300.0)
        self.assertEqual(v.state, "needs-you")

    def test_approval_resolved_clears_need_and_can_go_stuck(self):
        d = self._base(min_suspect=30.0, fresh_seconds=90.0)
        d.ingest(EventKind.APPROVAL_REQUIRED.value, "", "", "s", "", 1000.0)
        d.ingest(EventKind.APPROVAL_APPROVED.value, "", "", "s", "", 1001.0)
        d.ingest(EventKind.TOOL_STARTED.value, "terminal", "terminal", "s", "t", 1001.0)
        v = d.check(now=2300.0)
        self.assertEqual(v.state, "stuck")

    def test_finished_tool_clears_open(self):
        d = self._base(min_suspect=30.0)
        d.ingest(EventKind.TOOL_STARTED.value, "terminal", "terminal", "s", "t", 1000.0)
        d.ingest(EventKind.TOOL_FINISHED.value, "terminal", "terminal", "s", "t", 1005.0)
        v = d.check(now=2300.0)
        self.assertEqual(v.state, "quiet")

    def test_verdict_serializes_without_raw_content(self):
        d = self._base(min_suspect=30.0)
        d.ingest(EventKind.TOOL_STARTED.value, "terminal", "terminal", "s", "t", 1000.0)
        v = d.check(now=2300.0)
        blob = v.as_dict()
        self.assertIn("state", blob)
        self.assertIn("open_tool", blob)
        # content-free: never carries paths, args, or results
        self.assertNotIn("command", blob)
        self.assertNotIn("args", blob)


if __name__ == "__main__":
    unittest.main()
