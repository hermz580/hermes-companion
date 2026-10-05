"""Render Masque's reference sheets (turnaround, movement, special moves, forms, faces).

    python -m hermes_companion.scripts.masque_sheets docs/
"""
from __future__ import annotations

import sys
import time
from pathlib import Path

from PIL import Image, ImageDraw

from hermes_companion.animation import masque as M
from hermes_companion.renderer.smooth import FrameRenderer, _font

BG = (22, 20, 30, 255)
RESET = dict(category="general", cracks=0, work=0, running=0, helpers=0, danger=False,
             think_until=0.0, beat_until=0.0, tools=[], swap_until=0.0, rest_until=0.0)

TURNAROUND = [("Front", "idle_bob", 0.2, {}), ("Turn right", "turn_right", 0.15, {}),
              ("Right side", "turn_right", 0.6, {}), ("Back", "turn_back", 0.3, {}),
              ("Left side", "turn_left", 0.6, {}), ("Spin", "celebrate", 0.18, {})]
MOVEMENT = [("Idle", "idle_bob", 0.2), ("Walk / float", "float_walk", 0.3), ("Run", "run_trail", 0.3),
            ("Jump", "jump_leap", 0.5), ("Hover", "hover", 0.3), ("Turn left", "turn_left", 0.6),
            ("Turn right", "turn_right", 0.6), ("Spin", "celebrate", 0.35), ("Crouch", "crouch", 0.3),
            ("Stretch", "stretch", 0.3), ("Look up", "look_up", 0.3), ("Look down", "look_down", 0.3)]
SPECIAL = [("Travel slide", "ink_slide", 0.3, {}), ("Enter crack", "enter_crack", 0.6, {}),
           ("Exit crack", "exit_crack", 0.8, {}), ("Window perch", "window_perch", 0.3, {}),
           ("Follow cursor", "follow_cursor", 0.2, {}), ("React to click", "react_click", 0.4, {}),
           ("Celebration", "celebrate", 0.05, {}), ("Curious peek", "curious_peek", 0.5, {}),
           ("Sleep", "sleep", 0.3, {}), ("Wake up", "wake_up", 0.8, {}),
           ("Angry / error", "angry", 0.3, {"cracks": 2}), ("Approval request", "approval_request", 0.3,
                                                             {"category": "approval"})]
FORMS = [("Terminal / code", "terminal_work", {"running": 2, "category": "terminal"}),
         ("Web search", "web_scan", {"running": 1, "category": "web"}),
         ("Reading files", "read", {"running": 1, "category": "file"}),
         ("Writing files", "design_draft", {"running": 1, "category": "design"}),
         ("Memory", "memory_vault", {"running": 1, "category": "memory"}),
         ("Browser", "work", {"running": 1, "category": "browser"}),
         ("Helpers", "open_portal", {"helpers": 3, "category": "delegation"}),
         ("Approval needed", "wait", {"category": "approval"}),
         ("Long tool", "work", {"running": 1, "category": "terminal", "beat_until": 1e12}),
         ("Mixed tools", "work", {"running": 3, "category": "memory",
                                  "tools": ["terminal", "web", "memory"]}),
         ("Mask swap", "work", {"running": 1, "category": "terminal", "tools": ["terminal"],
                                "swap_until": 1e12}),
         ("Session ends", "idle_bob", {"rest_until": 1e12}),
         ("Asleep", "sleep", {})]


def _cell(r, label, pose, t, state):
    M.STATE.__dict__.update(RESET)
    M.STATE.__dict__.update(state)
    if state.get("think"):
        M.STATE.think_until = time.monotonic() + 99
    f = r.frame(pose, t).copy()
    out = Image.new("RGBA", (f.width, f.height + 26), BG)
    out.alpha_composite(f, (0, 0))
    ImageDraw.Draw(out).text((f.width // 2, f.height + 12), label, fill=(240, 226, 196, 255),
                             font=_font(15, True), anchor="mm")
    return out


def sheet(title, cells, cols, path):
    w, h = cells[0].size
    rows = (len(cells) + cols - 1) // cols
    img = Image.new("RGBA", (w * cols, h * rows + 44), BG)
    ImageDraw.Draw(img).text((16, 22), title, fill=(243, 212, 138, 255), font=_font(22, True),
                             anchor="lm")
    for i, c in enumerate(cells):
        img.alpha_composite(c, ((i % cols) * w, 44 + (i // cols) * h))
    img.convert("RGB").quantize(256).save(path, optimize=True)


def main(out="docs"):
    out = Path(out)
    r = FrameRenderer("masque", None)
    saved = dict(M.STATE.__dict__)
    try:
        sheet("MASQUE - turnaround", [_cell(r, *c) for c in TURNAROUND], 6,
              out / "masque-turnaround.png")
        sheet("MASQUE - movement actions", [_cell(r, a, b, c, {}) for a, b, c in MOVEMENT], 6,
              out / "masque-movement.png")
        sheet("MASQUE - special moves", [_cell(r, *c) for c in SPECIAL], 6,
              out / "masque-special.png")
        sheet("MASQUE - body forms (driven by the kind of work)",
              [_cell(r, a, b, 0.3, s) for a, b, s in FORMS], 5, out / "masque-forms.png")
        faces = [_cell(r, f.title(), "idle_bob", 0.2, {}) for f in ()]
        del faces
    finally:
        M.STATE.__dict__.update(saved)
    return 0


if __name__ == "__main__":
    sys.exit(main(*sys.argv[1:]))
