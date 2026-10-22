"""Keep a log when there is no console to show one.

The desktop icon, Companion Home's Start button and the one-file .exe all run
the companion with no console (``pythonw``). There, ``sys.stdout`` and
``sys.stderr`` are ``None``: every message and every crash vanished, so "it
opens and closes" left nothing to go on. This sends both streams, uncaught
exceptions and Tk callback errors to ``<settings dir>/logs/<command>.log``,
which Home reads to say *why* a companion closed.

Only lifecycle text and Python tracebacks go there - the same lines a
terminal run prints, never content from your desktop or Hermes.
"""
from __future__ import annotations

import sys
import time
import traceback
from pathlib import Path

KEEP_BYTES = 200_000          # a log never grows past this; old runs are trimmed


def log_dir() -> Path:
    from hermes_companion.core.settings import settings_path
    return settings_path().parent / "logs"


def log_path(command: str) -> Path:
    return log_dir() / f"{command or 'home'}.log"


def needs_log() -> bool:
    """True with no console to write to (pythonw, the windowed .exe)."""
    return sys.stdout is None or sys.stderr is None


def attach(command: str):
    """Send stdout, stderr and crashes to this command's log. Returns the file or None."""
    path = log_path(command)
    try:
        path.parent.mkdir(parents=True, exist_ok=True)
        if path.exists() and path.stat().st_size > KEEP_BYTES:
            path.write_bytes(path.read_bytes()[-KEEP_BYTES // 2:])
        out = open(path, "a", encoding="utf-8", buffering=1)
    except OSError:
        return None
    out.write(f"\n=== {time.strftime('%Y-%m-%d %H:%M:%S')} {command} {' '.join(sys.argv[1:])}\n")
    sys.stdout = sys.stdout or out
    sys.stderr = sys.stderr or out

    def hook(kind, value, tb):
        out.write("CRASH " + "".join(traceback.format_exception(kind, value, tb)))
        out.flush()

    sys.excepthook = hook
    try:
        import tkinter
        tkinter.Tk.report_callback_exception = lambda _self, k, v, t: hook(k, v, t)
    except Exception:
        pass
    return out


def last_error(command: str, max_lines: int = 400) -> str | None:
    """The last error line of this command's most recent run, if it crashed."""
    try:
        lines = log_path(command).read_text(encoding="utf-8", errors="replace").splitlines()[-max_lines:]
    except OSError:
        return None
    start = max((i for i, line in enumerate(lines) if line.startswith("=== ")), default=0)
    run = lines[start:]
    errors = [line.strip() for line in run
              if line.strip() and ("Error" in line or "Exception" in line) and not line.startswith(" ")]
    return errors[-1][:160] if errors else None
