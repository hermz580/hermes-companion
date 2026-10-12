"""System-tray icon and settings window for `play`.

The tray menu changes the saved settings and restarts the companion with
them (character, energy, size, curiosity, sound, bubbles, memory, perching,
accessibility, extra companions). "Open Home..." (also a left-click on the
icon) opens Companion Home, the full window for every option. Everything
degrades quietly: without `pystray` there is no tray icon, and Home still
opens from `hermes-companion` or `hermes-companion settings`.
"""
from __future__ import annotations

import subprocess
import threading

from hermes_companion.core import settings as S

ENERGIES = {
    "nyamekra": ("cosmic", "earth", "fire", "water", "air", "shadow", "light",
                 "neon", "natural", "robotic"),
    "masque": ("eerie", "cute", "monster"),
    "nia": ("kente", "indigo", "ochre", "emerald", "royal"),
    "duet": ("classic", "evening", "carnival"),
    "master": ("midnight", "jade", "dawn"),
    "herald": ("olympus", "midnight", "ember", "verdant", "nebula"),
}


def relaunch(values: dict, on_quit=None) -> None:
    """Save, start a fresh companion with these settings, then quit this one."""
    S.save(values)
    subprocess.Popen(S.play_command(values), close_fds=True)
    if on_quit is not None:
        on_quit()


def menu_model(values: dict) -> list:
    """Pure description of the tray menu: [(label, kind, payload)], testable."""
    items: list = [("Open Home…", "action", "home"), ("", "separator", None)]
    items.append(("Character", "submenu",
                  [(c.title(), "radio", ("companion", c)) for c in S.COMPANIONS]))
    energies = ENERGIES.get(values["companion"])
    if energies:
        items.append(("Energy" if values["companion"] == "nyamekra" else "Palette", "submenu",
                      [(e.title(), "radio", ("palette", e)) for e in energies]))
    items.append(("Size", "submenu", [(s.title(), "radio", ("size", s)) for s in S.SIZES]))
    items.append(("Curiosity", "submenu",
                  [(n.title(), "radio", ("notice", n)) for n in S.NOTICE]))
    for label, key in (("Speech bubbles", "bubbles"), ("Speak aloud", "speak"), ("Sound", "sound"),
                       ("Learn my rhythm", "memory"), ("Live on my windows", "perch"),
                       ("Reduced motion", "reduced_motion"), ("High contrast", "high_contrast")):
        items.append((label, "toggle", key))
    items.append(("Companions on screen", "submenu",
                  [(c.title(), "toggle_with", c) for c in S.COMPANIONS
                   if c != values["companion"]]))
    items.append(("", "separator", None))
    items.append(("Quit", "action", "quit"))
    return items


def apply_choice(values: dict, kind: str, payload) -> dict:
    """New settings after a menu click (pure)."""
    out = dict(values, **{"with": list(values.get("with", []))})
    if kind == "radio":
        key, val = payload
        out[key] = val
        if key == "companion":
            out["palette"] = None
            out["with"] = [c for c in out["with"] if c != val]
    elif kind == "toggle":
        out[payload] = not bool(values.get(payload))
    elif kind == "toggle_with":
        if payload in out["with"]:
            out["with"].remove(payload)
        elif len(out["with"]) < 3:
            out["with"].append(payload)
    return out


def _checked_fn(values: dict, kind: str, payload):
    def checked(_item):
        if kind == "radio":
            return values.get(payload[0]) == payload[1]
        if kind == "toggle":
            return bool(values.get(payload))
        return payload in values.get("with", [])
    return checked


def _clicked_fn(values: dict, kind: str, payload, quit_all):
    # pystray only accepts callables taking 0-2 positional arguments, so each
    # handler is built by a factory instead of capturing via default args.
    def clicked(_icon, _item):
        relaunch(apply_choice(values, kind, payload), on_quit=quit_all)
    return clicked


def build_menu(pystray, values: dict, quit_all, show_settings):
    """The real pystray menu for `values` (also used by the tests)."""
    def build(items):
        entries = []
        for label, kind, payload in items:
            if kind == "separator":
                entries.append(pystray.Menu.SEPARATOR)
            elif kind == "submenu":
                entries.append(pystray.MenuItem(label, pystray.Menu(*build(payload))))
            elif kind == "action":
                handler = quit_all if payload == "quit" else show_settings
                entries.append(pystray.MenuItem(label, _action_fn(handler),
                                                default=(payload == "home")))
            else:
                entries.append(pystray.MenuItem(
                    label, _clicked_fn(values, kind, payload, quit_all),
                    checked=_checked_fn(values, kind, payload), radio=(kind == "radio")))
        return entries
    return pystray.Menu(*build(menu_model(values)))


def _action_fn(handler):
    def action(_icon, _item):
        handler()
    return action


def start_tray(overlay, values: dict):
    """Run the tray icon in a background thread. Returns the icon or None."""
    try:
        import pystray
    except Exception:
        return None
    from hermes_companion.renderer.smooth import FrameRenderer

    icon_img = FrameRenderer(values["companion"], values.get("palette")) \
        .frame("idle_bob", 0.0).crop((40, 0, 160, 120)).resize((64, 64))
    holder: dict = {}

    def quit_all():
        if "icon" in holder:
            holder["icon"].stop()
        overlay.root.after(0, overlay.close)

    def show_settings():
        overlay.root.after(0, lambda: open_home_window(overlay, values))

    icon = pystray.Icon("hermes-companion", icon_img, "Hermes Companion",
                        build_menu(pystray, values, quit_all, show_settings))
    holder["icon"] = icon
    threading.Thread(target=icon.run, daemon=True).start()
    return icon


def open_home_window(overlay, values: dict, page: str = "home"):
    from hermes_companion.renderer.home import open_home
    return open_home(overlay, values, page=page)


def open_settings(overlay, values: dict) -> None:
    """Kept for old callers: settings now live in Companion Home."""
    open_home_window(overlay, values, page="look")
