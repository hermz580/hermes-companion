"""Entry point for the one-file HermesCompanion.exe.

Double-click: the first time, installs itself (Desktop and Start menu
icons, see `hermes_companion.core.install`) and opens Companion Home so you
can choose and start a companion; after that, starts `play` with your saved settings (tray
icon included, and Home is one click on it).
With arguments it behaves exactly like the `hermes-companion` command, e.g.
`HermesCompanion.exe live`, `HermesCompanion.exe doctor`.

A windowed .exe has no console, so output and any error go to
%LOCALAPPDATA%\\hermes-companion\\last-run.log instead of vanishing.
"""
import os
import sys
import traceback
from pathlib import Path


def _log_file():
    base = os.environ.get("LOCALAPPDATA")
    root = Path(base) / "hermes-companion" if base else Path.home() / ".hermes-companion"
    root.mkdir(parents=True, exist_ok=True)
    return open(root / "last-run.log", "w", encoding="utf-8", buffering=1)


def _first_run_install():
    """Copy the exe to Programs and add Desktop + Start menu icons. Never fatal."""
    try:
        from hermes_companion.core.install import apply
        for line in apply():
            print(line)
    except Exception as exc:
        print(f"install skipped: {exc}")


def run(argv):
    from hermes_companion.cli.emit import main
    args = list(argv)
    if not args:
        from hermes_companion.core.settings import settings_path
        if settings_path().exists():
            args = ["play"]
        else:                     # first double-click: install like a normal app
            _first_run_install()
            args = ["home"]
    elif args[0] == "live" and "--companion" not in args:
        args = ["live", "--companion", "nyamekra", "--follow"] + args[1:]
    return main(args)


if __name__ == "__main__":
    if sys.stdout is None or sys.stderr is None:      # windowed build
        log = _log_file()
        sys.stdout = sys.stdout or log
        sys.stderr = sys.stderr or log
    try:
        code = run(sys.argv[1:])
    except SystemExit as exc:
        code = exc.code if isinstance(exc.code, int) else 0
    except BaseException:
        traceback.print_exc()
        code = 1
    sys.stdout.flush()
    os._exit(int(code or 0))      # don't wait on leftover tray/GUI threads
