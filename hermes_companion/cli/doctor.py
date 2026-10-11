"""``hermes-companion doctor``: can this PC run the companion, and if not, why.

Each check prints PASS / WARN / FAIL with a plain-language fix. FAIL means
``play`` will not work; WARN means it works with something reduced (for
example no true transparency, or no Hermes install for ``live``).
"""
from __future__ import annotations

import os
import platform
import sys
import time
from pathlib import Path

PASS, WARN, FAIL = "PASS", "WARN", "FAIL"


def _check(results, status, name, detail=""):
    results.append((status, name, detail))
    if _ECHO:
        print(f"  [{status}] {name}" + (f" - {detail}" if detail else ""), flush=True)


_ECHO = True


def run_doctor(open_window: bool = True) -> int:
    print("Hermes Companion doctor", flush=True)
    results = collect_checks(open_window)
    fails = sum(1 for r in results if r[0] == FAIL)
    warns = sum(1 for r in results if r[0] == WARN)
    print(f"\n{'READY' if not fails else 'NOT READY'}: {fails} problem(s), {warns} warning(s)",
          flush=True)
    return 1 if fails else 0


def collect_checks(open_window: bool = False, echo: bool = True) -> list[tuple[str, str, str]]:
    """Every check as (status, name, detail); the Home window shows these."""
    global _ECHO
    _ECHO = echo
    try:
        return _collect(open_window)
    finally:
        _ECHO = True


def _collect(open_window: bool) -> list[tuple[str, str, str]]:
    results: list[tuple[str, str, str]] = []

    v = sys.version_info
    _check(results, PASS if v >= (3, 10) else FAIL, "Python",
           f"{v.major}.{v.minor}.{v.micro}" + ("" if v >= (3, 10) else " - install 3.10+ from python.org"))

    on_windows = sys.platform == "win32"
    _check(results, PASS if on_windows else WARN, "Operating system",
           platform.platform() + ("" if on_windows else
                                  " - the desktop overlay is built for Windows 10/11"))

    try:
        from PIL import Image  # noqa: F401
        import PIL
        _check(results, PASS, "Pillow", PIL.__version__)
    except Exception as exc:  # pragma: no cover - environment specific
        _check(results, FAIL, "Pillow", f"{exc} - run: pip install pillow")

    try:
        import tkinter
        _check(results, PASS, "Tk", f"{tkinter.TkVersion}")
    except Exception as exc:
        _check(results, FAIL, "Tk", f"{exc} - reinstall Python with 'tcl/tk' ticked")

    try:
        from hermes_companion.animation.characters import list_companions
        from hermes_companion.renderer.smooth import FrameRenderer
        t0 = time.perf_counter()
        names = [n for n in list_companions() if n != "pet"]
        for n in names:
            FrameRenderer(n).frame("idle_bob", 0.3)
        ms = (time.perf_counter() - t0) * 1000 / max(1, len(names))
        _check(results, PASS if ms < 400 else WARN, "Characters render",
               f"{', '.join(names)} ({ms:.0f} ms/frame first draw)")
    except Exception as exc:
        _check(results, FAIL, "Characters render", repr(exc))

    if on_windows:
        try:
            from hermes_companion.renderer.desktop_sensors import DesktopSensors
            s = DesktopSensors.for_platform("full")
            if s is not None:
                s.sample(0.0)
            _check(results, PASS if s is not None else WARN, "Desktop sensors",
                   "cursor, windows, typing rhythm" if s is not None else "unavailable - curiosity off")
        except Exception as exc:
            _check(results, WARN, "Desktop sensors", f"{exc} - curiosity off")

    if open_window:
        try:
            from hermes_companion.renderer.layered import SmoothLiveOverlay
            overlay = SmoothLiveOverlay(companion="nyamekra")
            try:
                overlay.set_pose("wave", 0.5)
                overlay.root.update()
                mode = overlay.mode
            finally:
                overlay.close()
            _check(results, PASS if mode == "layered" else WARN, "Desktop window",
                   "true transparency" if mode == "layered" else
                   "colour-key fallback (works, edges less smooth)")
        except Exception as exc:
            _check(results, FAIL, "Desktop window", f"{exc}")

    home = Path(os.environ.get("HERMES_HOME") or
                Path(os.environ.get("LOCALAPPDATA", Path.home())) / "hermes")
    _check(results, PASS if home.exists() else WARN, "Hermes (for live mode)",
           str(home) if home.exists() else "not found - 'play' works; 'live' needs Hermes")
    return results
