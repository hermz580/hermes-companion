"""Install the Hermes Companion hook plugin (spec rev1 §2/§6/§39).

Assembles a SELF-CONTAINED plugin at <hermes-home>/plugins/hermes-companion/:
  plugin.yaml            manifest (hook subscriptions)
  __init__.py            adapter (real-hook -> semantic events)
  hermes_companion/      bundled copy of the behavior-engine package

Then adds "hermes-companion" to plugins.enabled in config.yaml (opt-in).

Usage:  python plugin/install.py
        python plugin/install.py --config %LOCALAPPDATA%/hermes/config.yaml
"""
from __future__ import annotations

import argparse
import os
import re
import shutil
import sys

REPO_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))  # .../hermes_companion
ADAPTER = os.path.join(REPO_ROOT, "plugin", "__init__.py")
MANIFEST = os.path.join(REPO_ROOT, "plugin", "plugin.yaml")
PKG_SRC = os.path.join(REPO_ROOT)  # the hermes_companion package root
PKG_NAME = "hermes_companion"

DEFAULT_HERMES_HOME = os.path.join(
    os.path.expanduser("~"), "AppData", "Local", "hermes")


def _bundled_subdirs() -> list[str]:
    """Package subpackages to bundle (exclude plugin/ and proof/)."""
    keep = {"core", "behavior", "movement", "animation", "renderer", "cli"}
    out = []
    for name in keep:
        p = os.path.join(PKG_SRC, name)
        if os.path.isdir(p):
            out.append(name)
    return out


def build(hermes_home: str) -> str:
    plugins_dir = os.path.join(hermes_home, "plugins")
    dest = os.path.join(plugins_dir, "hermes-companion")
    os.makedirs(dest, exist_ok=True)

    # 1. manifest
    shutil.copy2(MANIFEST, os.path.join(dest, "plugin.yaml"))

    # 2. adapter __init__.py with a sys.path shim so the bundled package
    #    resolves regardless of cwd / PYTHONPATH (self-contained plugin).
    #    CRITICAL: insert the shim AFTER any `from __future__` import —
    #    Python requires future imports to be the first statement.
    with open(ADAPTER, encoding="utf-8") as f:
        adapter_src = f.read()
    shim = (
        "# --- self-contained bootstrap: make the bundled package importable ---\n"
        "import os as _os, sys as _sys\n"
        "_PLUGIN_DIR = _os.path.dirname(_os.path.abspath(__file__))\n"
        "if _PLUGIN_DIR not in _sys.path:\n"
        "    _sys.path.insert(0, _PLUGIN_DIR)\n"
        "\n"
    )
    lines = adapter_src.split("\n")
    # find the `from __future__` line and insert the shim right after it
    future_idx = next((i for i, ln in enumerate(lines)
                       if ln.startswith("from __future__")), None)
    if future_idx is None:
        raise RuntimeError("adapter has no from __future__ import line")
    head = "\n".join(lines[: future_idx + 1]) + "\n"
    body = "\n".join(lines[future_idx + 1:])
    with open(os.path.join(dest, "__init__.py"), "w", encoding="utf-8") as f:
        f.write(head + shim + body)

    # 3. bundled package (fresh copy each install -> no drift)
    pkg_dest = os.path.join(dest, PKG_NAME)
    if os.path.isdir(pkg_dest):
        shutil.rmtree(pkg_dest)
    os.makedirs(pkg_dest)
    for name in _bundled_subdirs():
        shutil.copytree(os.path.join(PKG_SRC, name), os.path.join(pkg_dest, name))
    for fn in ("__init__.py", "__main__.py"):
        src = os.path.join(PKG_SRC, fn)
        if os.path.isfile(src):
            shutil.copy2(src, os.path.join(pkg_dest, fn))

    return dest


def enable(config_path: str, key: str = "hermes-companion") -> None:
    with open(config_path, encoding="utf-8") as f:
        cfg = f.read()
    # find plugins.enabled block and insert key if missing
    m = re.search(r"(plugins:\s*\n\s*enabled:\s*\n)((?:\s*-\s*.*\n)*)", cfg)
    if not m:
        raise RuntimeError("plugins.enabled block not found in config")
    header, body = m.group(1), m.group(2)
    if re.search(rf"^\s*-\s*{re.escape(key)}\s*$", body, re.M):
        print(f"  [ok] {key} already enabled")
        return
    indent = " " * 4
    new_body = body + f"{indent}- {key}\n"
    cfg = cfg[: m.start(2)] + new_body + cfg[m.end(2):]
    with open(config_path, "w", encoding="utf-8") as f:
        f.write(cfg)
    print(f"  [ok] enabled {key} in {config_path}")


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--config", default=os.path.join(DEFAULT_HERMES_HOME, "config.yaml"))
    p.add_argument("--hermes-home", default=DEFAULT_HERMES_HOME)
    args = p.parse_args(argv)

    dest = build(args.hermes_home)
    print(f"[ok] plugin assembled at {dest}")
    print(f"[ok] bundled subpackages: {', '.join(_bundled_subdirs())}")
    enable(args.config)
    print("\nNext: hermes plugins list  (confirm loaded)")
    print("      hermes chat -q '...'   (real session emits events)")
    print("      tail ~/.hermes/companion/events.jsonl")
    return 0


if __name__ == "__main__":
    sys.exit(main())
