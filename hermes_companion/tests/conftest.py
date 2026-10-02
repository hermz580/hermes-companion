"""Shared pytest configuration for the companion test suite.

Two Windows-only robustness measures, both test-process concerns rather than
product behaviour:

1. **Tcl library path.** `tkinter` locates the Tcl/Tk script library by
   searching relative to the interpreter. In a long pytest session with several
   Tk-using modules that search intermittently fails to read files that do
   exist ("couldn't read file .../init.tcl: No error"), surfacing as an
   order-dependent `_tkinter.TclError`. Pinning TCL_LIBRARY/TK_LIBRARY makes the
   lookup deterministic. Only set when the directory really exists, so a
   genuine misinstallation still raises a real error instead of being masked.

2. **Handle pressure.** Earlier tests leave sqlite connections and file handles
   awaiting finalization; Tk creation is the first thing to notice when the
   process runs short, and it reports it as a confusing "No error" read
   failure. Collecting before each test releases those cycles. A real failure
   still fails — this only stops unrelated work from poisoning the next test.
"""
from __future__ import annotations

import gc
import os
import sys
from pathlib import Path

import pytest


def _pin_tcl_library() -> None:
    if os.name != "nt":
        return
    base = Path(sys.base_prefix) / "tcl"
    if not base.is_dir():
        return
    for env_var, pattern in (("TCL_LIBRARY", "tcl8.*"), ("TK_LIBRARY", "tk8.*")):
        if os.environ.get(env_var):
            continue
        # Prefer the versioned dir that actually contains a library script.
        candidates = sorted(
            (p for p in base.glob(pattern) if (p / "init.tcl").is_file()
             or (p / "tk.tcl").is_file()),
            key=lambda p: p.name,
            reverse=True,
        )
        if candidates:
            os.environ[env_var] = str(candidates[0])


_pin_tcl_library()


_SHARED_ROOT = None


def shared_tk_root():
    """One Tcl interpreter for the whole test process.

    Creating and destroying Tk interpreters repeatedly in a single process
    fails order-dependently on Windows once several Tk-using modules have run
    ("couldn't read file init.tcl: No error" / "Can't find a usable tk.tcl"),
    which looks like a product defect but is harness churn. Reusing one hidden
    interpreter removes the churn. Product code still creates its own root in
    normal use; only tests inject this one.
    """
    global _SHARED_ROOT
    if _SHARED_ROOT is None:
        import tkinter as tk
        _SHARED_ROOT = tk.Tk()
        _SHARED_ROOT.attributes("-alpha", 0.0)
        _SHARED_ROOT.geometry("+10000+10000")
    return _SHARED_ROOT


def pytest_sessionfinish(session, exitstatus):
    global _SHARED_ROOT
    root, _SHARED_ROOT = _SHARED_ROOT, None
    if root is not None:
        try:
            root.destroy()
        except Exception:
            pass


@pytest.fixture(autouse=True)
def _release_handles():
    """Finalize leaked file/sqlite handles before each test runs."""
    gc.collect()
    yield
    gc.collect()
