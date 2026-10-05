"""System-tray icon and settings window for `play`.

The tray menu changes the saved settings and restarts the companion with
them (character, energy, size, curiosity, sound, bubbles, memory, perching,
accessibility, extra companions). "Settings..." opens a small window with the
same options. Everything degrades quietly: without `pystray` there is no tray
icon, and the settings window still opens from `hermes-companion settings`.
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
    items: list = []
    items.append(("Character", "submenu",
                  [(c.title(), "radio", ("companion", c)) for c in S.COMPANIONS]))
    energies = ENERGIES.get(values["companion"])
    if energies:
        items.append(("Energy" if values["companion"] == "nyamekra" else "Palette", "submenu",
                      [(e.title(), "radio", ("palette", e)) for e in energies]))
    items.append(("Size", "submenu", [(s.title(), "radio", ("size", s)) for s in S.SIZES]))
    items.append(("Curiosity", "submenu",
                  [(n.title(), "radio", ("notice", n)) for n in S.NOTICE]))
    for label, key in (("Speech bubbles", "bubbles"), ("Sound", "sound"),
                       ("Learn my rhythm", "memory"), ("Live on my windows", "perch"),
                       ("Reduced motion", "reduced_motion"), ("High contrast", "high_contrast")):
        items.append((label, "toggle", key))
    items.append(("Companions on screen", "submenu",
                  [(c.title(), "toggle_with", c) for c in S.COMPANIONS
                   if c != values["companion"]]))
    items.append(("Settings…", "action", "settings"))
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
            if kind == "submenu":
                entries.append(pystray.MenuItem(label, pystray.Menu(*build(payload))))
            elif kind == "action":
                handler = quit_all if payload == "quit" else show_settings
                entries.append(pystray.MenuItem(label, _action_fn(handler)))
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
        overlay.root.after(0, lambda: open_settings(overlay, values))

    icon = pystray.Icon("hermes-companion", icon_img, "Hermes Companion",
                        build_menu(pystray, values, quit_all, show_settings))
    holder["icon"] = icon
    threading.Thread(target=icon.run, daemon=True).start()
    return icon


def open_settings(overlay, values: dict) -> None:
    """A small settings window (Tk), opened from the tray or the CLI."""
    import tkinter as tk
    from tkinter import ttk

    root = overlay.root if overlay is not None else tk.Tk()
    win = tk.Toplevel(root) if overlay is not None else root
    win.title("Hermes Companion - Settings")
    win.configure(bg="#0b0912")
    win.resizable(False, False)
    style = ttk.Style(win)
    style.configure("TLabel", background="#0b0912", foreground="#ffe39a")
    style.configure("TCheckbutton", background="#0b0912", foreground="#f4e9d8")

    vars_: dict = {}
    row = 0

    def add_choice(label, key, options):
        nonlocal row
        ttk.Label(win, text=label).grid(row=row, column=0, sticky="w", padx=12, pady=4)
        v = tk.StringVar(value=values.get(key) or options[0])
        ttk.Combobox(win, textvariable=v, values=list(options), state="readonly",
                     width=16).grid(row=row, column=1, padx=12, pady=4)
        vars_[key] = v
        row += 1

    add_choice("Character", "companion", S.COMPANIONS)
    add_choice("Energy / palette", "palette",
               ENERGIES.get(values["companion"], ("default",)))
    add_choice("Size", "size", S.SIZES)
    add_choice("Curiosity", "notice", S.NOTICE)
    for label, key in (("Speech bubbles", "bubbles"), ("Sound", "sound"),
                       ("Learn my rhythm", "memory"), ("Live on my windows", "perch"),
                       ("Reduced motion", "reduced_motion"), ("High contrast", "high_contrast")):
        v = tk.BooleanVar(value=bool(values.get(key)))
        ttk.Checkbutton(win, text=label, variable=v).grid(row=row, column=0, columnspan=2,
                                                         sticky="w", padx=12)
        vars_[key] = v
        row += 1

    def save_and_restart():
        new = dict(values)
        for key, v in vars_.items():
            new[key] = v.get()
        if new.get("palette") == "default":
            new["palette"] = None
        if overlay is None:
            S.save(new)
            win.destroy()
            return
        relaunch(new, on_quit=lambda: overlay.root.after(0, overlay.close))

    ttk.Button(win, text="Save & restart" if overlay is not None else "Save",
               command=save_and_restart).grid(row=row, column=0, columnspan=2, pady=10)
    if overlay is None:
        win.mainloop()
