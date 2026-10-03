"""Entry point for the one-file HermesCompanion.exe.

Double-click: starts `play` with your saved settings (tray icon included).
With arguments it behaves exactly like the `hermes-companion` command, e.g.
`HermesCompanion.exe live`, `HermesCompanion.exe doctor`.
"""
import sys

from hermes_companion.cli.emit import main

if __name__ == "__main__":
    args = sys.argv[1:]
    if not args:
        args = ["play"]
    elif args[0] == "live" and "--companion" not in args:
        args = ["live", "--companion", "nyamekra", "--follow"] + args[1:]
    sys.exit(main(args))
