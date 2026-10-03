"""Speech bubbles and (opt-in) sound for the companion.

Everything said comes from content-free sources only: the attention state and
its fixed label (``core.attention``), curiosity kinds, and personality
greetings. Never prompts, tool arguments, file names or results.

``Voice`` holds the decisions (what to say, when, how often) and is tested
without a GUI. ``BubbleWindow`` draws the bubble on Windows as its own
per-pixel-alpha window above the pet; elsewhere the text goes to the
overlay's fallback. ``Chimes`` synthesises short tones in memory and plays
them with ``winsound`` - no audio files, nothing on other platforms.
"""
from __future__ import annotations

import io
import math
import struct
import sys
import threading
import time
import wave

from PIL import Image, ImageDraw

# What the companion says for each Hermes attention state. `{label}` is the
# fixed, content-free label from AttentionModel.
SAY = {
    "starting": "On it!",
    "working": "{label}…",
    "delegating": "{label}…",
    "reviewing": "Checking the result…",
    "needs-you": "I need your OK!",
    "issue": "A tool failed - working on it",
    "stuck": "{label}",
    "complete": "All done!",
    "paused": "Okay, holding off.",
}
CURIOUS_SAY = {
    "user.back": "Welcome back!",
    "window.focus_flipping": "So many windows!",
    "time.late_night": "It's late - don't forget to rest.",
    "time.long_stretch": "Time for a stretch?",
    "display.changed": "Ooh, a new screen!",
    "clipboard.changed": "Copied something?",
    "cursor.circling": "Hi there!",
}
# Which sound plays for which state (curiosity uses "curious").
CHIME_FOR = {"starting": "start", "complete": "done", "needs-you": "attention",
             "issue": "problem", "stuck": "problem"}


class Voice:
    """Decides what to say and when; renders through `show` and `play`."""

    def __init__(self, show, play=None, clock=time.monotonic,
                 hold_s: float = 3.5, quiet_curiosity_s: float = 25.0) -> None:
        self.show, self.play, self.clock = show, play, clock
        self.hold_s, self.quiet_curiosity_s = hold_s, quiet_curiosity_s
        self._last_text = None
        self._last_state = None
        self._last_curious = -1e9
        self.hide_at: float | None = None
        self.said: list[str] = []

    def _say(self, text: str, hold: float | None = None) -> None:
        self._last_text = text
        self.said.append(text)
        self.hide_at = self.clock() + (hold or self.hold_s)
        self.show(text)

    def on_attention(self, state: str, label: str) -> None:
        if state == self._last_state and state not in ("working", "delegating"):
            return
        self._last_state = state
        template = SAY.get(state)
        if template:
            text = template.format(label=label)[:48]
            if text != self._last_text:
                self._say(text, hold=6.0 if state == "needs-you" else None)
        if self.play is not None and state in CHIME_FOR:
            self.play(CHIME_FOR[state])

    def on_curious(self, kind: str) -> None:
        text = CURIOUS_SAY.get(kind)
        now = self.clock()
        if text and now - self._last_curious >= self.quiet_curiosity_s:
            self._last_curious = now
            self._say(text)
            if self.play is not None:
                self.play("curious")

    def greet(self, text: str | None) -> None:
        if text:
            self._say(text, hold=5.0)

    def tick(self) -> None:
        if self.hide_at is not None and self.clock() >= self.hide_at:
            self.hide_at = None
            self._last_text = None
            self.show(None)


# ---- bubble art ------------------------------------------------------------
def bubble_image(text: str, accent: str = "#ffe39a", width: int = 220) -> Image.Image:
    from hermes_companion.renderer.smooth import _font
    f = _font(13, True)
    d = ImageDraw.Draw(Image.new("RGBA", (1, 1)))
    words, lines, cur = text.split(), [], ""
    for w in words:
        trial = (cur + " " + w).strip()
        if d.textlength(trial, font=f) > width - 28 and cur:
            lines.append(cur)
            cur = w
        else:
            cur = trial
    lines.append(cur)
    lines = lines[:3]
    tw = max(d.textlength(line, font=f) for line in lines)
    bw, bh = int(tw) + 28, 18 * len(lines) + 18
    img = Image.new("RGBA", (bw, bh + 12), (0, 0, 0, 0))
    g = ImageDraw.Draw(img)
    g.rounded_rectangle([1, 1, bw - 2, bh - 2], radius=12, fill=(14, 10, 24, 235),
                        outline=accent, width=2)
    g.polygon([(bw // 2 - 8, bh - 3), (bw // 2 + 8, bh - 3), (bw // 2, bh + 10)],
              fill=(14, 10, 24, 235), outline=accent)
    g.line([(bw // 2 - 7, bh - 3), (bw // 2 + 7, bh - 3)], fill=(14, 10, 24, 235), width=3)
    for i, line in enumerate(lines):
        g.text((bw / 2, 10 + 18 * i + 9), line, fill="#fdf6e3", font=f, anchor="mm")
    return img


class BubbleWindow:
    """A separate per-pixel-alpha window that floats above the pet (Windows)."""

    def __init__(self, overlay) -> None:
        import tkinter as tk
        from hermes_companion.renderer.layered import LayeredBlitter
        self.overlay = overlay
        self.top = tk.Toplevel(overlay.root)
        self.top.overrideredirect(True)
        self.top.wm_attributes("-topmost", True)
        self.top.geometry("1x1+0+0")
        self.top.update_idletasks()
        self.hwnd = __import__("ctypes").windll.user32.GetParent(self.top.winfo_id())
        self._blitter_cls = LayeredBlitter
        self.blitter = None
        self.size = (0, 0)
        self.top.withdraw()

    def show(self, text: str | None) -> None:
        if not text:
            self.top.withdraw()
            return
        img = bubble_image(text)
        if img.size != self.size:
            if self.blitter is not None:
                self.blitter.close()
            self.top.geometry(f"{img.width}x{img.height}")
            self.top.deiconify()
            self.top.update_idletasks()
            self.blitter = self._blitter_cls(self.hwnd, img.width, img.height)
            self.size = img.size
        else:
            self.top.deiconify()
        ov = self.overlay
        x = int(ov.x + ov.w / 2 - img.width / 2)
        y = int(getattr(ov, "_y", ov.home_y) - img.height + 18)
        self.blitter.blit(img, x, y)

    def close(self) -> None:
        if self.blitter is not None:
            self.blitter.close()


# ---- sound -----------------------------------------------------------------------
NOTES = {  # (frequency Hz, duration s) sequences
    "start": ((523, 0.08), (784, 0.12)),
    "done": ((523, 0.08), (659, 0.08), (784, 0.16)),
    "attention": ((880, 0.10), (0, 0.06), (880, 0.10)),
    "problem": ((392, 0.12), (311, 0.18)),
    "curious": ((988, 0.05),),
}


def synth(name: str, rate: int = 22050, volume: float = 0.25) -> bytes:
    """A short, soft chime as WAV bytes (sine with a gentle envelope)."""
    frames = bytearray()
    for freq, dur in NOTES[name]:
        n = int(rate * dur)
        for i in range(n):
            env = min(1.0, i / (rate * 0.01)) * (1 - i / n) ** 1.5
            v = math.sin(2 * math.pi * freq * i / rate) * env * volume if freq else 0.0
            frames += struct.pack("<h", int(v * 32767))
    buf = io.BytesIO()
    with wave.open(buf, "wb") as w:
        w.setnchannels(1)
        w.setsampwidth(2)
        w.setframerate(rate)
        w.writeframes(bytes(frames))
    return buf.getvalue()


class Chimes:
    """Opt-in sound cues. Silent off Windows and when rate-limited."""

    def __init__(self, min_gap_s: float = 1.5, clock=time.monotonic) -> None:
        self.min_gap_s, self.clock = min_gap_s, clock
        self._last = -1e9
        self._cache = {name: synth(name) for name in NOTES}
        self.enabled = sys.platform == "win32"
        self.played: list[str] = []

    def __call__(self, name: str) -> None:
        now = self.clock()
        if name not in self._cache or now - self._last < self.min_gap_s:
            return
        self._last = now
        self.played.append(name)
        if not self.enabled:
            return
        import winsound
        data = self._cache[name]
        threading.Thread(target=winsound.PlaySound,
                         args=(data, winsound.SND_MEMORY), daemon=True).start()
