"""No console (pythonw, desktop icon, .exe): output and crashes go to a log Home can read."""
import sys

from hermes_companion.core import runlog


def test_no_console_run_writes_a_log_and_home_reads_the_error(tmp_path, monkeypatch):
    monkeypatch.setattr(runlog, "log_dir", lambda: tmp_path)
    monkeypatch.setattr(sys, "stdout", None)
    monkeypatch.setattr(sys, "stderr", None)
    monkeypatch.setattr(sys, "excepthook", sys.excepthook)
    assert runlog.needs_log()
    out = runlog.attach("play")
    print("PLAY READY companion=kai")
    try:
        raise RuntimeError("Failed to open the overlay")
    except RuntimeError:
        sys.excepthook(*sys.exc_info())
    out.flush()
    text = (tmp_path / "play.log").read_text()
    assert "PLAY READY" in text and "CRASH" in text
    assert runlog.last_error("play") == "RuntimeError: Failed to open the overlay"


def test_only_the_latest_run_counts(tmp_path, monkeypatch):
    monkeypatch.setattr(runlog, "log_dir", lambda: tmp_path)
    (tmp_path / "play.log").write_text("=== old\nValueError: old problem\n=== new\nPLAY OK ran 6s\n")
    assert runlog.last_error("play") is None


def test_home_says_why_a_companion_closed():
    from hermes_companion.renderer.home import crash_notice
    msg = crash_notice("kai", "TclError: bad window path", "C:/Users/me/logs/play.log")
    assert "Kai closed right after starting: TclError: bad window path" in msg and "play.log" in msg
    assert "System check" in crash_notice("kai")            # nothing logged: old advice
