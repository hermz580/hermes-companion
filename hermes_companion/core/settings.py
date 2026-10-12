"""Saved preferences for `play`, edited from the tray or the settings window.

Stored in ``%LOCALAPPDATA%\\hermes-companion\\settings.json`` (or
``~/.hermes-companion``). Command-line flags always win over saved settings,
so scripts and shortcuts stay predictable.
"""
from __future__ import annotations

import json
import os
import sys
from pathlib import Path

DEFAULTS: dict = {
    "companion": "nyamekra",
    "palette": None,
    "size": "standard",
    "notice": "full",
    "sound": False,
    "bubbles": True,
    "speak": True,
    "memory": True,
    "perch": True,
    "reduced_motion": False,
    "high_contrast": False,
    "with": [],
}
COMPANIONS = ("nyamekra", "masque", "nia", "duet", "herald", "samurai", "astro")
SIZES = ("tiny", "standard", "large")
NOTICE = ("off", "ambient", "full")


def settings_path() -> Path:
    base = os.environ.get("LOCALAPPDATA")
    root = Path(base) / "hermes-companion" if base else Path.home() / ".hermes-companion"
    return root / "settings.json"


def load(path: Path | None = None) -> dict:
    out = dict(DEFAULTS)
    try:
        raw = json.loads((path or settings_path()).read_text(encoding="utf-8"))
        for key, default in DEFAULTS.items():
            if key in raw and (default is None or isinstance(raw[key], type(default))):
                out[key] = raw[key]
    except (OSError, ValueError):
        pass
    if out["companion"] not in COMPANIONS:
        out["companion"] = DEFAULTS["companion"]
    if out["size"] not in SIZES:
        out["size"] = DEFAULTS["size"]
    if out["notice"] not in NOTICE:
        out["notice"] = DEFAULTS["notice"]
    out["with"] = [c for c in out["with"] if c in COMPANIONS and c != out["companion"]][:3]
    return out


def save(values: dict, path: Path | None = None) -> None:
    path = path or settings_path()
    clean = {k: values.get(k, v) for k, v in DEFAULTS.items()}
    try:
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(clean, indent=2), encoding="utf-8")
    except OSError:
        pass


def play_command(values: dict, extra: list[str] | None = None) -> list[str]:
    """The exact command that starts `play` with these settings (also frozen .exe)."""
    base = [sys.executable] if getattr(sys, "frozen", False) else \
        [sys.executable, "-m", "hermes_companion"]
    cmd = base + ["play", "--companion", values["companion"], "--size", values["size"],
                  "--notice", values["notice"]]
    if values.get("palette"):
        cmd += ["--palette", values["palette"]]
    for flag, key, want in (("--sound", "sound", True), ("--no-bubbles", "bubbles", False),
                            ("--no-speak", "speak", False),
                            ("--no-memory", "memory", False), ("--no-perch", "perch", False),
                            ("--reduced-motion", "reduced_motion", True),
                            ("--high-contrast", "high_contrast", True)):
        if bool(values.get(key)) == want:
            cmd.append(flag)
    if values.get("with"):
        cmd += ["--with", ",".join(values["with"])]
    return cmd + list(extra or [])


def live_command(values: dict) -> list[str]:
    """The command that connects this companion to the real Hermes agent."""
    base = [sys.executable] if getattr(sys, "frozen", False) else \
        [sys.executable, "-m", "hermes_companion"]
    cmd = base + ["live", "--companion", values["companion"], "--follow",
                  "--notice", values["notice"]]
    if values.get("palette"):
        cmd += ["--palette", values["palette"]]
    for flag, key, want in (("--sound", "sound", True), ("--no-bubbles", "bubbles", False),
                            ("--no-speak", "speak", False), ("--no-perch", "perch", False)):
        if bool(values.get(key)) == want:
            cmd.append(flag)
    return cmd
