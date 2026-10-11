"""Companion Home: the one place to start, choose, tune and check the companion.

Before this, the experience was split across a tray menu, a bare settings
dialog, a status panel and a dozen CLI commands. Home pulls them into a single
window with a sidebar, like a small OS for the companion:

* **Home** - what's running, one big Start button, what Hermes is doing right
  now (signed events only), and what every colour means.
* **Companions** - pick who lives on your desktop, see them, invite others.
* **Look** - energy style and size, with a live preview.
* **Behavior** - talking, awareness and comfort, each in plain words.
* **System check** - the ``doctor`` checks, shown as cards with fixes.
* **Help** - how it works, privacy promises, handy commands.

Changes are staged, shown in an "unsaved changes" bar, and applied in one go.
Everything the window shows comes from the pure functions below, which are
tested without a display.
"""
from __future__ import annotations

import subprocess
import threading
import time

from hermes_companion.core import settings as S

# --------------------------------------------------------------------------- tokens
# One palette for every window, so the companion's surfaces read as one system.
THEME = {
    "bg": "#0e0b16",          # window
    "side": "#15111f",        # sidebar
    "card": "#1c1729",        # raised surfaces
    "card_hi": "#272038",     # hover / selected
    "line": "#2f2742",
    "text": "#f4ecdf",
    "muted": "#a89cba",
    "accent": "#e9b949",      # Nyamekra gold
    "accent_text": "#1a1205",
    "ok": "#4ade80",
    "warn": "#fbbf24",
    "bad": "#fb7185",
}
FONT = "Segoe UI"

ENERGIES = {
    "nyamekra": ("cosmic", "earth", "fire", "water", "air", "shadow", "light",
                 "neon", "natural", "robotic"),
    "masque": ("eerie", "cute", "monster"),
    "nia": ("kente", "indigo", "ochre", "emerald", "royal"),
    "herald": ("olympus", "midnight", "ember", "verdant", "nebula"),
}

# --------------------------------------------------------------------------- model
NAV = (
    ("home", "Home", "Start your companion and see what it's telling you."),
    ("companions", "Companions", "Choose who lives on your desktop."),
    ("look", "Look", "Energy style and size. The meaning of a move never changes."),
    ("behavior", "Behavior", "How your companion talks, notices and moves."),
    ("check", "System check", "Make sure this PC can run everything."),
    ("help", "Help", "How it works, what it never looks at, handy commands."),
)

COMPANION_INFO = {
    "nyamekra": ("Nyamekra", "The All-Doing Crow. Channels a symbol for every kind of work."),
    "masque": ("Masque", "The many behind the mask. Eyes and tendrils follow live work."),
    "nia": ("Nia", "The storyteller. Drum, dance and a heart that glows when it waits."),
    "herald": ("Herald", "A winged messenger. Its staff orb shows what a move means."),
    "samurai": ("Samurai", "A rigged warrior with martial moves."),
    "astro": ("Astro", "A small astronaut, light and quick."),
}

SIZE_HELP = {"tiny": "Out of the way", "standard": "Balanced", "large": "Easy to see"}
NOTICE_HELP = {
    "off": "Only reacts to Hermes. Ignores your desktop.",
    "ambient": "Also notices your cursor, windows and when you step away.",
    "full": "Also notices clicks and typing rhythm. Never what you type.",
}

BEHAVIOR_GROUPS = (
    ("Talking", (
        ("bubbles", "Speech bubbles", "Short status lines like “Need your OK”."),
        ("speak", "Speak aloud", "Says those lines with your system voice."),
        ("sound", "Sound", "Soft wing and chime cues per mood."),
    )),
    ("Awareness", (
        ("memory", "Learn my rhythm", "Greets and rests in step with your work hours. Counts only."),
        ("perch", "Live on my windows", "Perches on window edges instead of the taskbar."),
    )),
    ("Comfort", (
        ("reduced_motion", "Reduced motion", "Minimal movement, no squash or hopping."),
        ("high_contrast", "High contrast", "Thick mood ring plus a word label."),
    )),
)

# What the companion's glow means, in the user's words (colours from herald.MOOD_COLORS).
MEANINGS = (
    ("work", "#2dd4bf", "Working", "Hermes is running a tool: terminal, web, files."),
    ("approve", "#fbbf24", "Needs you", "Hermes is waiting on your approval."),
    ("fail", "#fb7185", "Hit a snag", "A step failed. It's retrying or recovering."),
    ("delegate", "#a78bfa", "Delegating", "Work handed to a helper agent."),
    ("joy", "#facc15", "Done", "The task finished."),
    ("curious", "#22d3ee", "Noticed you", "Reacting to something you did (“!” or “?”)."),
    ("rest", "#c4b5fd", "Resting", "Nothing is happening. It may fall asleep."),
)

PRIVACY = (
    "Senses positions, counters and on/off only.",
    "Never reads keys, window titles, clipboard text or screen pixels.",
    "What Hermes is really doing always wins over decoration.",
)

COMMANDS = (
    ("hermes-companion", "Open this Home window"),
    ("hermes-companion play", "Start with saved settings, no Hermes needed"),
    ("hermes-companion live", "Connect to your real Hermes agent"),
    ("hermes-companion doctor", "Check this PC in a terminal"),
)


def energies_for(companion: str) -> tuple[str, ...]:
    return ENERGIES.get(companion, ())


def companion_cards(values: dict) -> list[dict]:
    """One card per companion, in display order."""
    cards = []
    for name in S.COMPANIONS:
        title, tagline = COMPANION_INFO.get(name, (name.title(), ""))
        cards.append({
            "name": name, "title": title, "tagline": tagline,
            "selected": values["companion"] == name,
            "on_screen": name in values.get("with", []),
            "can_join": name != values["companion"],
        })
    return cards


def choose_companion(values: dict, name: str) -> dict:
    """Make `name` the main companion. Its old energy doesn't carry over."""
    if name not in S.COMPANIONS:
        raise ValueError(f"unknown companion {name!r}")
    out = dict(values, companion=name, palette=None)
    out["with"] = [c for c in values.get("with", []) if c != name]
    return out


def toggle_guest(values: dict, name: str) -> dict:
    """Invite or dismiss an extra companion (at most three, never the main one)."""
    guests = [c for c in values.get("with", []) if c != values["companion"]]
    if name == values["companion"]:
        return dict(values, **{"with": guests})
    if name in guests:
        guests.remove(name)
    elif len(guests) < 3:
        guests.append(name)
    return dict(values, **{"with": guests})


def _show(key: str, value) -> str:
    if key == "palette":
        return (value or "default").title()
    if key == "with":
        return ", ".join(v.title() for v in value) or "none"
    if isinstance(value, bool):
        return "on" if value else "off"
    return str(value).title()


LABELS = {"companion": "Companion", "palette": "Energy", "size": "Size",
          "notice": "Curiosity", "with": "Also on screen"}
LABELS.update({key: label for _g, items in BEHAVIOR_GROUPS for key, label, _h in items})


def pending_changes(saved: dict, staged: dict) -> list[str]:
    """Human-readable list of what Apply would change."""
    out = []
    for key in S.DEFAULTS:
        if saved.get(key) != staged.get(key):
            out.append(f"{LABELS.get(key, key)}: {_show(key, staged.get(key))}")
    return out


def readiness(checks: list[tuple[str, str, str]] | None) -> tuple[str, str]:
    """(level, sentence) summarising doctor results; level is ok|warn|bad|unknown."""
    if checks is None:
        return "unknown", "Not checked yet."
    fails = [n for s, n, _d in checks if s == "FAIL"]
    warns = [n for s, n, _d in checks if s == "WARN"]
    if fails:
        return "bad", f"Can't run yet: {', '.join(fails)}. See System check."
    if warns:
        return "warn", f"Ready, with {len(warns)} note{'s' if len(warns) > 1 else ''}."
    return "ok", "Ready. Everything checks out."


def status_line(values: dict, mode: str | None) -> tuple[str, str]:
    """(level, sentence) for the Home header: what's on screen right now."""
    title = COMPANION_INFO.get(values["companion"], (values["companion"].title(),))[0]
    if mode == "live":
        return "ok", f"{title} is live, acting out what Hermes really does."
    if mode == "play":
        return "ok", f"{title} is on your desktop in practice mode."
    return "idle", f"{title} is resting. Press Start to bring it to your desktop."


def crash_notice(companion: str) -> str:
    title = COMPANION_INFO.get(companion, (companion.title(),))[0]
    return f"{title} closed right after starting. Run System check to see why."


def fix_for(detail: str) -> tuple[str, str]:
    """Split a doctor detail into (what was found, how to fix it)."""
    if " - " in detail:
        found, fix = detail.split(" - ", 1)
        return found, fix[:1].upper() + fix[1:]
    return detail, ""


STALE_S = 10 * 60      # older than this, the headline is history, not "now"
MOOD_HEX = {key: color for key, color, _n, _m in MEANINGS}
FEED_NOTICE = ("Only signed events from your Hermes count. Quiet doesn't prove nothing "
               "is running.")


def feed_view(feed, now: float | None = None) -> dict:
    """What the 'Hermes right now' card shows, from a HermesFeed (or None)."""
    import time as _time
    now = _time.time() if now is None else now
    if feed is None or not feed.connected:
        return {"headline": "Not connected", "mood": "calm",
                "sub": "Press Connect to Hermes above and this card shows what your "
                       "agent is doing.", "items": []}
    from hermes_companion.core.feed import age_text
    if feed.last_ts is None:
        return {"headline": "Waiting for Hermes", "mood": "rest",
                "sub": "Connected. No events yet: start a task in Hermes.",
                "items": []}
    headline, mood = feed.headline()
    if now - feed.last_ts > STALE_S:
        headline, mood = f"Last known: {headline}", "calm"
    return {"headline": headline, "mood": mood,
            "sub": f"Last event {age_text(now - feed.last_ts)}.",
            "items": [(i.text, i.mood, age_text(now - i.ts)) for i in feed.items]}


# --------------------------------------------------------------------------- view
def _avatar(companion: str, palette: str | None, px: int):
    """A cropped, square idle frame of the companion as a PIL image."""
    from PIL import Image

    from hermes_companion.renderer.smooth import FrameRenderer
    im = FrameRenderer(companion, palette).frame("idle_bob", 0.0)
    box = im.getbbox() or (0, 0, im.width, im.height)
    im = im.crop(box)
    side = max(im.width, im.height)
    square = Image.new("RGBA", (side, side), (0, 0, 0, 0))
    square.paste(im, ((side - im.width) // 2, (side - im.height) // 2))
    return square.resize((px, px), Image.LANCZOS)


class HomeWindow:
    """Tk view of the model above. `overlay` is set when opened from a running pet."""

    def __init__(self, values: dict | None = None, overlay=None, page: str = "home",
                 runner=None, saver=None, feed=None, master=None,
                 presence=None, stopper=None) -> None:
        import tkinter as tk

        self.tk = tk
        self.overlay = overlay
        self.saved = dict(values or S.load())
        self.staged = dict(self.saved, **{"with": list(self.saved.get("with", []))})
        self._runner = runner or subprocess.Popen
        self._saver = saver or S.save
        self.proc = None
        self.mode = "play" if overlay is not None else None
        # What is really on the desktop, read from the running companion's heartbeat
        # (core.presence), so Home also sees companions it didn't start.
        from hermes_companion.core import presence as P
        self._presence = presence or P.current
        self._stopper = stopper or P.request_stop
        self.running_companion = None
        self.notice = None
        self._started_at = 0.0
        self.checks = None
        self._images: dict = {}
        self.feed = feed if feed is not None else _open_feed()
        self.feed_card = None

        if overlay is not None or master is not None:
            self.win = tk.Toplevel(master if master is not None else overlay.root)
        else:
            self.win = tk.Tk()
        self.win.title("Hermes Companion")
        self.win.configure(bg=THEME["bg"])
        self.win.geometry("920x660")
        self.win.minsize(820, 600)
        self.win.protocol("WM_DELETE_WINDOW", self.close)

        self.side = tk.Frame(self.win, bg=THEME["side"], width=210)
        self.side.pack(side="left", fill="y")
        self.side.pack_propagate(False)
        self.main = tk.Frame(self.win, bg=THEME["bg"])
        self.main.pack(side="left", fill="both", expand=True)

        self._build_sidebar()
        self.header = tk.Frame(self.main, bg=THEME["bg"])
        self.header.pack(fill="x", padx=28, pady=(22, 6))
        self.title_lbl = tk.Label(self.header, bg=THEME["bg"], fg=THEME["text"],
                                  font=(FONT, 18, "bold"), anchor="w")
        self.title_lbl.pack(fill="x")
        self.sub_lbl = tk.Label(self.header, bg=THEME["bg"], fg=THEME["muted"],
                                font=(FONT, 10), anchor="w")
        self.sub_lbl.pack(fill="x")

        self.bar = tk.Frame(self.main, bg=THEME["card_hi"])
        self.bar_lbl = tk.Label(self.bar, bg=THEME["card_hi"], fg=THEME["text"],
                                font=(FONT, 10), anchor="w", justify="left")
        self.bar_lbl.pack(side="left", fill="x", expand=True, padx=16, pady=10)
        self._button(self.bar, "Apply", self.apply, primary=True).pack(side="right", padx=(6, 16))
        self._button(self.bar, "Discard", self.discard).pack(side="right")

        self.body = tk.Frame(self.main, bg=THEME["bg"])
        self.body.pack(fill="both", expand=True, padx=28, pady=(8, 16))

        for i, (key, _l, _s) in enumerate(NAV, start=1):
            self.win.bind(f"<Control-Key-{i}>", lambda _e, k=key: self.show(k))
        self.win.bind("<Control-s>", lambda _e: self.apply())
        self.show(page if page in dict((k, 1) for k, _l, _s in NAV) else "home")
        self._tick()

    # ---- building blocks -------------------------------------------------------
    def _button(self, parent, text, command, primary=False, small=False):
        tk = self.tk
        bg = THEME["accent"] if primary else THEME["card_hi"]
        fg = THEME["accent_text"] if primary else THEME["text"]
        return tk.Button(parent, text=text, command=command, bg=bg, fg=fg,
                         activebackground=THEME["text"] if primary else THEME["line"],
                         activeforeground=THEME["accent_text"] if primary else THEME["text"],
                         relief="flat", bd=0, cursor="hand2", highlightthickness=0,
                         font=(FONT, 9 if small else 10, "bold" if primary else "normal"),
                         padx=10 if small else 16, pady=3 if small else 7)

    def _card(self, parent, **pack):
        f = self.tk.Frame(parent, bg=THEME["card"], highlightthickness=1,
                          highlightbackground=THEME["line"])
        f.pack(fill="x", pady=(0, 12), **pack)
        return f

    def _label(self, parent, text, size=10, color="text", bold=False, bg="card", **kw):
        return self.tk.Label(parent, text=text, bg=THEME[bg], fg=THEME[color],
                             font=(FONT, size, "bold" if bold else "normal"),
                             anchor="w", justify="left", **kw)

    @staticmethod
    def _wrapping(label):
        """Wrap a label's text to whatever width its container gives it."""
        label.configure(wraplength=150)
        label.bind("<Configure>", lambda e: e.widget.configure(wraplength=max(120, e.width - 4)))
        return label

    def _photo(self, key, companion, palette, px):
        from PIL import ImageTk
        cache_key = (key, companion, palette, px)
        if cache_key not in self._images:
            try:
                self._images[cache_key] = ImageTk.PhotoImage(_avatar(companion, palette, px),
                                                             master=self.win)
            except Exception:
                self._images[cache_key] = None
        return self._images[cache_key]

    def _build_sidebar(self):
        tk = self.tk
        brand = tk.Frame(self.side, bg=THEME["side"])
        brand.pack(fill="x", padx=16, pady=(20, 18))
        self.brand_img = tk.Label(brand, bg=THEME["side"])
        self.brand_img.pack(side="left")
        tk.Label(brand, text="Hermes\nCompanion", bg=THEME["side"], fg=THEME["text"],
                 font=(FONT, 11, "bold"), justify="left").pack(side="left", padx=8)

        self.nav_items = {}
        for i, (key, label, _sub) in enumerate(NAV, start=1):
            row = tk.Frame(self.side, bg=THEME["side"])
            row.pack(fill="x")
            mark = tk.Frame(row, bg=THEME["side"], width=4)
            mark.pack(side="left", fill="y")
            btn = tk.Button(row, text=label, anchor="w", relief="flat", bd=0,
                            bg=THEME["side"], fg=THEME["muted"], cursor="hand2",
                            activebackground=THEME["card_hi"], activeforeground=THEME["text"],
                            highlightthickness=0, font=(FONT, 10), padx=16, pady=8,
                            command=lambda k=key: self.show(k))
            btn.pack(side="left", fill="x", expand=True)
            self.nav_items[key] = (row, mark, btn)

        foot = tk.Frame(self.side, bg=THEME["side"])
        foot.pack(side="bottom", fill="x", padx=16, pady=16)
        self.dot = tk.Canvas(foot, width=10, height=10, bg=THEME["side"], highlightthickness=0)
        self.dot.pack(side="left")
        self.run_lbl = tk.Label(foot, bg=THEME["side"], fg=THEME["muted"], font=(FONT, 9))
        self.run_lbl.pack(side="left", padx=6)
        self._refresh_brand()

    def _refresh_brand(self):
        img = self._photo("brand", self.saved["companion"], self.saved.get("palette"), 40)
        if img is not None:
            self.brand_img.configure(image=img)

    # ---- navigation ------------------------------------------------------------
    def show(self, page: str) -> None:
        self.page = page
        for key, (row, mark, btn) in self.nav_items.items():
            on = key == page
            bg = THEME["card"] if on else THEME["side"]
            row.configure(bg=bg)
            mark.configure(bg=THEME["accent"] if on else THEME["side"])
            btn.configure(bg=bg, fg=THEME["text"] if on else THEME["muted"],
                          font=(FONT, 10, "bold" if on else "normal"))
        _k, title, sub = next(n for n in NAV if n[0] == page)
        self.title_lbl.configure(text=title if page != "home" else "Welcome back")
        self.sub_lbl.configure(text=sub)
        for child in self.body.winfo_children():
            child.destroy()
        self.feed_card = None
        getattr(self, f"_page_{page}")()
        self._refresh_bar()

    def _rerender(self):
        self.show(self.page)

    # ---- pages -----------------------------------------------------------------
    def _page_home(self):
        tk = self.tk
        hero = self._card(self.body)
        who = self.staged if self.mode is None else dict(
            self.saved, companion=self.running_companion or self.saved["companion"])
        if who["companion"] not in COMPANION_INFO:          # e.g. a Petdex pet in live mode
            who = dict(who, companion=self.saved["companion"])
        if who["companion"] != self.saved["companion"]:
            who["palette"] = None
        img = self._photo("hero", who["companion"], who.get("palette"), 110)
        tk.Label(hero, image=img, bg=THEME["card"]).pack(side="left", padx=18, pady=12)
        col = tk.Frame(hero, bg=THEME["card"])
        col.pack(side="left", fill="both", expand=True, pady=12)
        title, tagline = COMPANION_INFO.get(who["companion"], ("", ""))
        self._label(col, title, 16, bold=True).pack(fill="x")
        self._label(col, tagline, 10, "muted", wraplength=420).pack(fill="x", pady=(0, 8))
        level, line = status_line(who, self.mode)
        self._label(col, line, 10, "ok" if level == "ok" else "text", wraplength=420).pack(fill="x")
        if self.notice:
            self._label(col, self.notice, 9, "bad", wraplength=420).pack(fill="x", pady=(4, 0))
        row = tk.Frame(col, bg=THEME["card"])
        row.pack(fill="x", pady=(12, 0))
        if self.mode is None:
            self._button(row, "Start", lambda: self.start("play"), primary=True).pack(side="left")
            self._button(row, "Connect to Hermes", lambda: self.start("live")).pack(side="left", padx=8)
        else:
            self._button(row, "Stop", self.stop).pack(side="left")
            if self.mode == "play":
                self._button(row, "Switch to live", lambda: self.start("live")).pack(side="left", padx=8)
        self._button(row, "Change companion", lambda: self.show("companions"),
                     small=True).pack(side="right", padx=16)

        level, line = readiness(self.checks)
        ready = tk.Label(col, text="\u25cf  " + line + "  \u203a", bg=THEME["card"], cursor="hand2",
                         fg=THEME[{"ok": "ok", "warn": "warn", "bad": "bad"}.get(level, "muted")],
                         font=(FONT, 9), anchor="w")
        ready.pack(fill="x", pady=(10, 0))
        ready.bind("<Button-1>", lambda _e: self.show("check"))

        cols = tk.Frame(self.body, bg=THEME["bg"])
        cols.pack(fill="both", expand=True)
        legend = tk.Frame(cols, bg=THEME["card"], highlightthickness=1,
                          highlightbackground=THEME["line"], width=290)
        legend.pack(side="right", fill="y", padx=(12, 0))
        legend.pack_propagate(False)
        self._label(legend, "What its glow means", 11, bold=True).pack(fill="x", padx=16, pady=(12, 4))
        for _k, color, name, meaning in MEANINGS:
            item = tk.Frame(legend, bg=THEME["card"])
            item.pack(fill="x", padx=16, pady=2)
            dot = tk.Canvas(item, width=12, height=12, bg=THEME["card"], highlightthickness=0)
            dot.create_oval(1, 1, 11, 11, fill=color, outline="")
            dot.pack(side="left", anchor="n", pady=4)
            text = tk.Frame(item, bg=THEME["card"])
            text.pack(side="left", padx=(8, 0), fill="x")
            self._label(text, name, 9, bold=True).pack(fill="x")
            self._label(text, meaning, 8, "muted", wraplength=230).pack(fill="x")

        self.feed_card = tk.Frame(cols, bg=THEME["card"], highlightthickness=1,
                                  highlightbackground=THEME["line"])
        self.feed_card.pack(side="left", fill="both", expand=True)
        self._fill_feed()

    def _fill_feed(self):
        """The 'Hermes right now' card; rebuilt in place when new events arrive."""
        tk = self.tk
        card = self.feed_card
        for child in card.winfo_children():
            child.destroy()
        self._label(card, "Hermes right now", 11, bold=True).pack(fill="x", padx=16, pady=(12, 6))
        view = feed_view(self.feed)
        head = tk.Frame(card, bg=THEME["card"])
        head.pack(fill="x", padx=16)
        dot = tk.Canvas(head, width=14, height=14, bg=THEME["card"], highlightthickness=0)
        dot.create_oval(1, 1, 13, 13, fill=MOOD_HEX.get(view["mood"], THEME["line"]), outline="")
        dot.pack(side="left")
        self._label(head, view["headline"], 12, bold=True).pack(side="left", padx=8)
        self._wrapping(self._label(card, view["sub"], 9, "muted")).pack(
            fill="x", padx=16, pady=(2, 8))
        for text, mood, when in view["items"]:
            row = tk.Frame(card, bg=THEME["card"])
            row.pack(fill="x", padx=16, pady=1)
            c = tk.Canvas(row, width=8, height=8, bg=THEME["card"], highlightthickness=0)
            c.create_oval(0, 0, 7, 7, fill=MOOD_HEX.get(mood, THEME["line"]), outline="")
            c.pack(side="left")
            self._label(row, text, 9).pack(side="left", padx=8)
            self._label(row, when, 9, "muted").pack(side="right")
        self._wrapping(self._label(card, FEED_NOTICE, 8, "muted")).pack(
            side="bottom", fill="x", padx=16, pady=(4, 10))

    def _page_companions(self):
        tk = self.tk
        grid = tk.Frame(self.body, bg=THEME["bg"])
        grid.pack(fill="both", expand=True)
        for i, card in enumerate(companion_cards(self.staged)):
            border = THEME["accent"] if card["selected"] else THEME["line"]
            f = tk.Frame(grid, bg=THEME["card_hi"] if card["selected"] else THEME["card"],
                         highlightthickness=2, highlightbackground=border, cursor="hand2")
            f.grid(row=i // 3, column=i % 3, sticky="nsew", padx=6, pady=6)
            bg = f.cget("bg")
            img = self._photo("card", card["name"], None, 84)
            pic = tk.Label(f, image=img, bg=bg)
            pic.pack(pady=(12, 4))
            name = tk.Label(f, text=card["title"] + ("  ✓" if card["selected"] else ""),
                            bg=bg, fg=THEME["text"], font=(FONT, 11, "bold"))
            name.pack()
            tag = tk.Label(f, text=card["tagline"], bg=bg, fg=THEME["muted"], font=(FONT, 9),
                           wraplength=170, justify="center", height=3)
            tag.pack(padx=8)
            pick = (lambda _e, n=card["name"]: self._set(choose_companion(self.staged, n)))
            for w in (f, pic, name, tag):
                w.bind("<Button-1>", pick)
            # Keyboard: Tab reaches each card, Enter/Space chooses it, focus shows a gold ring.
            f.configure(takefocus=1, highlightcolor=THEME["accent"])
            f.bind("<Return>", pick)
            f.bind("<space>", pick)
            f.bind("<FocusIn>", lambda e: e.widget.configure(highlightbackground=THEME["accent"]))
            f.bind("<FocusOut>", lambda e, b=border: e.widget.configure(highlightbackground=b))
            if card["can_join"]:
                text = "− Remove from screen" if card["on_screen"] else "+ Also on screen"
                self._button(f, text, lambda n=card["name"]: self._set(toggle_guest(self.staged, n)),
                             small=True).pack(pady=(4, 12))
            else:
                tk.Label(f, text="Main companion", bg=bg, fg=THEME["accent"],
                         font=(FONT, 9, "bold")).pack(pady=(6, 14))
        for c in range(3):
            grid.columnconfigure(c, weight=1, uniform="cards")

    def _segmented(self, parent, key, options, helptext=None):
        tk = self.tk
        row = tk.Frame(parent, bg=THEME["card"])
        row.pack(fill="x", padx=16, pady=(0, 6))
        current = (self.staged.get(key) or "default") if key == "palette" else self.staged.get(key)
        for opt in options:
            on = current == opt
            b = tk.Button(row, text=opt.title(), relief="flat", bd=0, cursor="hand2",
                          bg=THEME["accent"] if on else THEME["card_hi"],
                          fg=THEME["accent_text"] if on else THEME["text"],
                          activebackground=THEME["line"], highlightthickness=0,
                          font=(FONT, 9, "bold" if on else "normal"), padx=10, pady=5,
                          command=lambda o=opt: self._set(dict(
                              self.staged, **{key: (None if o == "default" else o)})))
            b.pack(side="left", padx=(0, 6), pady=2)
        if helptext:
            self._label(parent, helptext.get(self.staged.get(key), ""), 9, "muted").pack(
                fill="x", padx=16, pady=(0, 12))

    def _page_look(self):
        tk = self.tk
        wrap = tk.Frame(self.body, bg=THEME["bg"])
        wrap.pack(fill="both", expand=True)
        preview = tk.Frame(wrap, bg=THEME["card"], highlightthickness=1,
                           highlightbackground=THEME["line"])
        preview.pack(side="right", fill="y", padx=(12, 0))
        img = self._photo("look", self.staged["companion"], self.staged.get("palette"), 180)
        tk.Label(preview, image=img, bg=THEME["card"]).pack(padx=16, pady=(16, 6))
        self._label(preview, "Preview", 9, "muted").pack()

        col = tk.Frame(wrap, bg=THEME["bg"])
        col.pack(side="left", fill="both", expand=True)
        energies = energies_for(self.staged["companion"])
        card = self._card(col)
        self._label(card, "Energy style", 11, bold=True).pack(fill="x", padx=16, pady=(12, 2))
        if energies:
            self._label(card, "Changes only the energy around the companion, never the being.",
                        9, "muted").pack(fill="x", padx=16, pady=(0, 8))
            options = ("default",) + energies
            for i in range(0, len(options), 6):
                self._segmented(card, "palette", options[i:i + 6])
        else:
            self._label(card, "This companion has one look.", 9, "muted").pack(
                fill="x", padx=16, pady=(0, 8))
        tk.Frame(card, bg=THEME["card"], height=6).pack()

        card = self._card(col)
        self._label(card, "Size", 11, bold=True).pack(fill="x", padx=16, pady=(12, 8))
        self._segmented(card, "size", S.SIZES, SIZE_HELP)

    def _page_behavior(self):
        tk = self.tk
        card = self._card(self.body)
        self._label(card, "Curiosity", 11, bold=True).pack(fill="x", padx=16, pady=(12, 8))
        self._segmented(card, "notice", S.NOTICE, NOTICE_HELP)

        cols = tk.Frame(self.body, bg=THEME["bg"])
        cols.pack(fill="both", expand=True)
        for i, (group, items) in enumerate(BEHAVIOR_GROUPS):
            f = tk.Frame(cols, bg=THEME["card"], highlightthickness=1,
                         highlightbackground=THEME["line"])
            f.grid(row=0, column=i, sticky="nsew", padx=(0 if i == 0 else 6, 0))
            cols.columnconfigure(i, weight=1, uniform="groups")
            self._label(f, group, 11, bold=True).pack(fill="x", padx=14, pady=(12, 6))
            for key, label, helptext in items:
                var = tk.BooleanVar(value=bool(self.staged.get(key)))
                tk.Checkbutton(f, text=label, variable=var, bg=THEME["card"], fg=THEME["text"],
                               selectcolor=THEME["bg"], activebackground=THEME["card"],
                               activeforeground=THEME["text"], highlightthickness=0,
                               font=(FONT, 10), anchor="w",
                               command=lambda k=key, v=var: self._set(
                                   dict(self.staged, **{k: v.get()}), rerender=False)
                               ).pack(fill="x", padx=10)
                self._wrapping(self._label(f, helptext, 9, "muted")).pack(
                    fill="x", padx=(34, 10), pady=(0, 8))

    def _page_check(self):
        tk = self.tk
        top = tk.Frame(self.body, bg=THEME["bg"])
        top.pack(fill="x", pady=(0, 10))
        level, line = readiness(self.checks)
        self._label(top, line, 11, {"ok": "ok", "warn": "warn", "bad": "bad"}.get(level, "muted"),
                    bold=True, bg="bg").pack(side="left")
        self._button(top, "Run check again" if self.checks else "Run check",
                     self.run_checks, primary=self.checks is None).pack(side="right")
        if self.checks is None:
            self._label(self.body, "Checks Python, drawing, the desktop window and your Hermes "
                        "install. Takes a few seconds.", 10, "muted", bg="bg").pack(fill="x")
            return
        badge = {"PASS": ("✓", "ok"), "WARN": ("!", "warn"), "FAIL": ("✕", "bad")}
        for status, name, detail in self.checks:
            mark, color = badge.get(status, ("?", "muted"))
            f = self._card(self.body)
            self._label(f, mark, 14, color, bold=True, width=2).pack(side="left", padx=(14, 4), pady=8)
            col = tk.Frame(f, bg=THEME["card"])
            col.pack(side="left", fill="x", expand=True, pady=6)
            found, fix = fix_for(detail)
            self._label(col, name, 10, bold=True).pack(fill="x")
            self._label(col, found, 9, "muted", wraplength=520).pack(fill="x")
            if fix:
                self._label(col, "→ " + fix, 9, color, wraplength=520).pack(fill="x")

    def _page_help(self):
        tk = self.tk
        card = self._card(self.body)
        self._label(card, "How it works", 11, bold=True).pack(fill="x", padx=16, pady=(12, 4))
        for n, step in enumerate((
                "Pick a companion and press Start. It lives on your desktop.",
                "Connect to Hermes and it acts out your agent's real work.",
                "Watch its glow: it runs to you when Hermes needs your OK."), start=1):
            self._label(card, f"{n}.  {step}", 10).pack(fill="x", padx=16, pady=2)
        tk.Frame(card, bg=THEME["card"], height=8).pack()

        card = self._card(self.body)
        self._label(card, "Privacy promises", 11, bold=True).pack(fill="x", padx=16, pady=(12, 4))
        for line in PRIVACY:
            self._label(card, "•  " + line, 10).pack(fill="x", padx=16, pady=1)
        tk.Frame(card, bg=THEME["card"], height=8).pack()

        card = self._card(self.body)
        self._label(card, "Handy commands", 11, bold=True).grid(
            row=0, column=0, columnspan=2, sticky="w", padx=16, pady=(12, 4))
        for i, (cmd, what) in enumerate(COMMANDS, start=1):
            tk.Label(card, text=cmd, bg=THEME["card"], fg=THEME["accent"],
                     font=("Consolas", 10), anchor="w").grid(row=i, column=0, sticky="w", padx=16)
            self._label(card, what, 10, "muted").grid(row=i, column=1, sticky="w", padx=8)
        tk.Frame(card, bg=THEME["card"], height=8).grid(row=99, column=0)
        self._label(self.body, "Shortcuts: Ctrl+1–6 switch pages, Ctrl+S applies changes.",
                    9, "muted", bg="bg").pack(fill="x")

    # ---- state -----------------------------------------------------------------
    def _set(self, new: dict, rerender: bool = True) -> None:
        self.staged = new
        if rerender:
            self._rerender()
        else:
            self._refresh_bar()

    def _refresh_bar(self) -> None:
        changes = pending_changes(self.saved, self.staged)
        if changes:
            restart = " — your companion will restart" if self.mode else ""
            self.bar_lbl.configure(text="Unsaved: " + " · ".join(changes) + restart,
                                   wraplength=520)
            self.bar.pack(fill="x", side="bottom", before=self.body)
        else:
            self.bar.pack_forget()

    def apply(self) -> None:
        if not pending_changes(self.saved, self.staged):
            return
        self._saver(self.staged)
        self.saved = dict(self.staged, **{"with": list(self.staged.get("with", []))})
        self._refresh_brand()
        if self.overlay is not None:
            from hermes_companion.renderer.tray import relaunch
            relaunch(self.saved, on_quit=lambda: self.overlay.root.after(0, self.overlay.close))
            return
        if self.mode is not None:
            self.start(self.mode)
        self._rerender()

    def discard(self) -> None:
        self.staged = dict(self.saved, **{"with": list(self.saved.get("with", []))})
        self._rerender()

    def start(self, mode: str) -> None:
        """Start (or restart) the companion in `play` or `live` mode."""
        # Always save: starting is a choice, and a first-run launch should remember it.
        self._saver(self.staged)
        self.saved = dict(self.staged, **{"with": list(self.staged.get("with", []))})
        if self.overlay is not None:
            # This Home lives inside a running pet: hand over to a fresh process.
            cmd = S.live_command(self.saved) if mode == "live" else S.play_command(self.saved)
            self._runner(cmd, close_fds=True)
            self.overlay.root.after(0, self.overlay.close)
            return
        # No need to stop what's running: the new companion claims the desktop and
        # the old one (ours or not) notices and closes itself gracefully.
        cmd = S.live_command(self.saved) if mode == "live" else S.play_command(self.saved)
        self.notice = None
        try:
            self.proc = self._runner(cmd)
            self.mode, self.running_companion = mode, self.saved["companion"]
            self._started_at = time.monotonic()
        except OSError:
            self.proc, self.mode = None, None
            self.notice = "Couldn't start the companion. Try System check."
        self._rerender()

    def stop(self, rerender: bool = True) -> None:
        if self.overlay is not None:
            self.overlay.root.after(0, self.overlay.close)
            return
        asked = self._stopper()               # closes any companion gracefully
        if not asked and self.proc is not None and self.proc.poll() is None:
            self.proc.terminate()             # ours, but not yet claimed the desktop
        self.proc, self.mode, self.running_companion = None, None, None
        if rerender:
            self._rerender()

    def run_checks(self) -> None:
        from hermes_companion.cli.doctor import collect_checks
        self.checks = None
        for child in self.body.winfo_children():
            child.destroy()
        self._label(self.body, "Checking…", 11, "muted", bg="bg").pack(fill="x")

        def work():
            try:
                result = collect_checks(open_window=False, echo=False)
            except Exception as exc:          # a broken check must not kill the window
                result = [("FAIL", "System check", repr(exc))]
            self._checks_result = result      # picked up by _tick on the Tk thread
        self._checks_result = None
        threading.Thread(target=work, daemon=True).start()

    def _tick(self) -> None:
        """Keep the sidebar's running light and the Hermes feed honest."""
        self._ticks = getattr(self, "_ticks", 0) + 1
        result, self._checks_result = getattr(self, "_checks_result", None), None
        if result is not None:
            self.checks = result
            if self.page in ("check", "home"):
                self._rerender()
        if self.feed is not None:
            try:
                changed = self.feed.poll()
            except Exception:
                changed = False
            if self.page == "home" and self.feed_card is not None and (
                    changed or self._ticks % 5 == 0):        # ages tick even when quiet
                try:
                    self._fill_feed()
                except Exception:
                    pass
        if self.overlay is None:
            self._sync_running()
        on = self.mode is not None
        self.dot.delete("all")
        self.dot.create_oval(1, 1, 9, 9, fill=THEME["ok"] if on else THEME["line"], outline="")
        self.run_lbl.configure(text={"live": "Live with Hermes", "play": "Running"}
                               .get(self.mode, "Not running"))
        try:
            self.win.after(1000, self._tick)
        except Exception:
            pass

    def _sync_running(self) -> None:
        """Running light = the heartbeat, or our own process while it starts up."""
        before = (self.mode, self.running_companion, self.notice)
        if self.proc is not None and self.proc.poll() is not None:
            code, quick = self.proc.returncode, time.monotonic() - self._started_at < 20
            if code and quick:
                self.notice = crash_notice(self.running_companion or self.saved["companion"])
            self.proc = None
        try:
            claim = self._presence()
        except Exception:
            claim = None
        if claim is not None:
            self.mode = claim.get("mode") if claim.get("mode") in ("play", "live") else "play"
            self.running_companion = claim.get("companion")
        elif self.proc is None:
            self.mode, self.running_companion = None, None
        if (self.mode, self.running_companion, self.notice) != before and self.page == "home":
            self._rerender()

    def close(self) -> None:
        # A companion started from here keeps running: Home is only a window onto it.
        try:
            self.win.destroy()
        except Exception:
            pass

    def run(self) -> None:
        self.win.mainloop()


def _open_feed():
    try:
        from hermes_companion.core.feed import HermesFeed
        return HermesFeed()
    except Exception:          # no feed is better than no Home
        return None


def open_home(overlay=None, values: dict | None = None, page: str = "home") -> HomeWindow:
    """Open Home. Without an overlay it owns the Tk loop until closed."""
    home = HomeWindow(values, overlay=overlay, page=page)
    if overlay is None:
        home.run()
    return home
