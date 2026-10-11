"""'Hermes right now' on Companion Home: signed events only, plain words, honest silence."""
import json

from hermes_companion.core.event_auth import sign_record
from hermes_companion.core.feed import HermesFeed, age_text, describe
from hermes_companion.core.events import EventKind
from hermes_companion.renderer.home import feed_view

KEY = bytes(range(32))


def _setup(tmp_path):
    events, key = tmp_path / "events.jsonl", tmp_path / "event-auth.key"
    key.write_bytes(KEY)
    events.write_text("")
    return HermesFeed(events, key), events


def _write(path, *records, key=KEY):
    with path.open("a", encoding="utf-8") as f:
        for rec in records:
            f.write(json.dumps(sign_record(rec, key) if key else rec) + "\n")


def test_not_connected_without_key_and_never_creates_one(tmp_path):
    feed = HermesFeed(tmp_path / "events.jsonl", tmp_path / "event-auth.key")
    assert not feed.poll() and not feed.connected
    assert not (tmp_path / "event-auth.key").exists()
    view = feed_view(feed)
    assert view["headline"] == "Not connected" and "Connect to Hermes" in view["sub"]
    assert feed_view(None)["headline"] == "Not connected"


def test_connected_but_quiet_says_so(tmp_path):
    feed, _ = _setup(tmp_path)
    feed.poll()
    assert feed_view(feed)["headline"] == "Waiting for Hermes"


def test_signed_events_drive_the_headline_and_history(tmp_path):
    feed, events = _setup(tmp_path)
    _write(events,
           {"event": "agent.started", "ts": 100.0},
           {"event": "tool.started", "tool": "terminal", "category": "terminal", "ts": 101.0},
           {"event": "approval.required", "ts": 102.0})
    assert feed.poll()
    view = feed_view(feed, now=112.0)
    assert view["headline"] == "Decision needed" and view["mood"] == "approve"
    assert view["sub"] == "Last event 10s ago."
    assert [i[0] for i in view["items"]] == [
        "Asked for your approval", "Using the terminal", "Started a task"]


def test_forged_or_unsigned_records_are_ignored(tmp_path):
    feed, events = _setup(tmp_path)
    _write(events, {"event": "task.complete", "ts": 5.0}, key=None)
    _write(events, {"event": "task.complete", "ts": 5.0}, key=bytes(32))
    feed.poll()
    assert feed.last_ts is None and feed.rejected == 2


def test_content_never_reaches_the_feed(tmp_path):
    feed, events = _setup(tmp_path)
    _write(events, {"event": "tool.started", "tool": "rm -rf secret", "category": "s3cr3t",
                    "args": "password", "ts": 1.0})
    feed.poll()
    text = " ".join(i.text for i in feed.items) + feed.headline()[0]
    assert "secret" not in text and "s3cr3t" not in text and "password" not in text
    assert feed.items[0].text == "Using a tool"


def test_partial_lines_and_rotation(tmp_path):
    feed, events = _setup(tmp_path)
    line = json.dumps(sign_record({"event": "task.complete", "ts": 1.0}, KEY))
    with events.open("a") as f:
        f.write(line[:20])
    assert not feed.poll()
    with events.open("a") as f:
        f.write(line[20:] + "\n")
    assert feed.poll() and feed.items[0].text == "Finished the task"
    events.write_text("")                                   # log rotated
    _write(events, {"event": "agent.idle", "ts": 2.0})
    assert feed.poll() and feed.items[0].text == "Went quiet"


def test_opening_mid_file_skips_the_broken_first_line(tmp_path):
    feed, events = _setup(tmp_path)
    for i in range(1500):
        _write(events, {"event": "tool.finished", "category": "web", "ts": float(i)})
    _write(events, {"event": "task.complete", "ts": 9999.0})
    feed.poll()
    assert feed.rejected == 0 and feed.items[0].text == "Finished the task"


def test_wording_helpers():
    assert describe(EventKind.TOOL_PROGRESS, "web") is None
    assert describe(EventKind.TOOL_FAILED, "web") == ("A web step failed", "fail")
    assert describe(EventKind.TOOL_FINISHED, "memory") == ("Finished a memory step", "work")
    assert describe(EventKind.TOOL_STARTED, "file") == ("Using files", "work")
    assert age_text(None) == "no events yet" and age_text(2) == "just now"
    assert age_text(75) == "1 min ago" and age_text(7200) == "2 h ago"
