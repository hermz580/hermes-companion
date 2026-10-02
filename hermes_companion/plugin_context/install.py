"""Install the self-contained companion context hook plugin.

Usage:  python plugin_context/install.py
        python plugin_context/install.py --hermes-home <home> --config <config.yaml>
"""
from __future__ import annotations

import argparse
import os
import shutil
import sys

REPO_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
ADAPTER = os.path.join(REPO_ROOT, "plugin_context", "__init__.py")
MANIFEST = os.path.join(REPO_ROOT, "plugin_context", "plugin.yaml")
PKG_NAME = "hermes_companion"
DEFAULT_HERMES_HOME = os.environ.get("HERMES_HOME") or os.path.join(
    os.path.expanduser("~"), "AppData", "Local", "hermes")


def _insert_bootstrap(source: str) -> str:
    shim = (
        "# --- self-contained bootstrap: make the bundled package importable ---\n"
        "import os as _os, sys as _sys\n"
        "_PLUGIN_DIR = _os.path.dirname(_os.path.abspath(__file__))\n"
        "# The companion plugins each ship a top-level 'hermes_companion' package,\n"
        "# so whichever directory lands on sys.path first defines that name for the\n"
        "# whole process. Never let a partial bundle shadow a complete one: prefer\n"
        "# the sibling companion plugin's bundle when it has the behavior engine.\n"
        "_SIBLING_PKG = _os.path.join(_os.path.dirname(_PLUGIN_DIR),\n"
        "                             'hermes-companion', 'hermes_companion')\n"
        "_BUNDLE_DIR = (_os.path.dirname(_SIBLING_PKG)\n"
        "               if _os.path.isdir(_os.path.join(_SIBLING_PKG, 'behavior'))\n"
        "               else _PLUGIN_DIR)\n"
        "if _BUNDLE_DIR not in _sys.path:\n"
        "    _sys.path.insert(0, _BUNDLE_DIR)\n\n"
    )
    lines = source.split("\n")
    future_idx = next((i for i, line in enumerate(lines)
                       if line.startswith("from __future__")), None)
    if future_idx is None:
        raise RuntimeError("adapter has no from __future__ import line")
    return "\n".join(lines[:future_idx + 1]) + "\n" + shim + "\n".join(lines[future_idx + 1:])


def build(hermes_home: str) -> str:
    dest = os.path.join(hermes_home, "plugins", "hermes-companion-context")
    os.makedirs(dest, exist_ok=True)
    shutil.copy2(MANIFEST, os.path.join(dest, "plugin.yaml"))
    with open(ADAPTER, encoding="utf-8") as stream:
        adapter = _insert_bootstrap(stream.read())
    with open(os.path.join(dest, "__init__.py"), "w", encoding="utf-8") as stream:
        stream.write(adapter)

    package = os.path.join(dest, PKG_NAME)
    if os.path.isdir(package):
        shutil.rmtree(package)
    os.makedirs(package)
    # Bundle the COMPLETE package, not just core/ — a partial copy of this
    # top-level name can shadow the companion plugin's full bundle and silently
    # break its behavior-engine import.
    for name in ("core", "behavior", "movement", "animation", "renderer", "cli"):
        src = os.path.join(REPO_ROOT, name)
        if os.path.isdir(src):
            shutil.copytree(src, os.path.join(package, name))
    shutil.copy2(os.path.join(REPO_ROOT, "__init__.py"), os.path.join(package, "__init__.py"))
    main_mod = os.path.join(REPO_ROOT, "__main__.py")
    if os.path.isfile(main_mod):
        shutil.copy2(main_mod, os.path.join(package, "__main__.py"))
    return dest


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--hermes-home", default=DEFAULT_HERMES_HOME)
    parser.add_argument("--config", default=None,
                        help="Accepted for parity; enable with the Hermes CLI")
    args = parser.parse_args(argv)
    dest = build(args.hermes_home)
    print(f"[ok] plugin assembled at {dest}")
    print("Next: hermes plugins enable hermes-companion-context")
    print("      hermes plugins list --plain")
    return 0


if __name__ == "__main__":
    sys.exit(main())
