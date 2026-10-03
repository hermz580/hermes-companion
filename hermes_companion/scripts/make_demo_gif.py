"""Render docs/demo.gif: Nyamekra acting out a real Hermes session.

Uses the real behavior engine (same chains as live mode) and the smooth
renderer, so the GIF shows exactly what users see. Run from the repo root:

    python -m hermes_companion.scripts.make_demo_gif
"""
from __future__ import annotations

from pathlib import Path

from PIL import Image, ImageDraw

from hermes_companion.behavior.behavior_engine import BehaviorEngine
from hermes_companion.core.events import EventKind, SemanticEvent, classify_tool
from hermes_companion.renderer.smooth import FrameRenderer, _font, mood_label

SESSION = [
    ("agent.started", "", "Hermes starts a task"),
    ("tool.started", "terminal", "Runs a terminal command"),
    ("tool.finished", "terminal", "Command finished"),
    ("tool.started", "web_search", "Searches the web"),
    ("tool.failed", "web_search", "A search failed"),
    ("approval.required", "", "Needs your OK"),
    ("approval.approved", "", "You approved"),
    ("tool.started", "github", "Works on code"),
    ("task.complete", "", "Task complete"),
]
W, H = 360, 300


def build(out: Path, companion: str = "nyamekra", palette: str = "cosmic") -> Path:
    clock = [0.0]
    engine = BehaviorEngine(seed=11, variety=True, clock=lambda: clock[0])
    r = FrameRenderer(companion, palette)
    frames: list[Image.Image] = []
    bg = Image.new("RGBA", (W, H), "#0b0912")
    d0 = ImageDraw.Draw(bg)
    for i in range(0, H, 3):                     # soft vertical gradient
        d0.line([(0, i), (W, i)], fill=(14 + i // 30, 10 + i // 40, 26 + i // 18, 255))
    caption_font, small = _font(15, True), _font(11, False)
    for kind, tool, caption in SESSION:
        clock[0] += 10.0          # events spaced out, as in a real session
        chain = engine.handle(SemanticEvent(EventKind(kind), tool=tool, category=classify_tool(tool)))
        # Signature moves only: the demo shows what each Hermes action looks like.
        poses = [st["pose"] for st in chain.steps if st.get("role") != "flourish"][:6] \
            if chain else ["idle_bob"]
        for pose in poses:
            for step in range(3):
                f = bg.copy()
                f.alpha_composite(r.frame(pose, step / 4), ((W - 200) // 2, 18))
                d = ImageDraw.Draw(f)
                d.text((W / 2, H - 34), caption, fill="#ffe39a", font=caption_font, anchor="mm")
                d.text((W / 2, H - 14), f"{mood_label(pose)} · {pose.replace('_', ' ')}",
                       fill="#c4b5fd", font=small, anchor="mm")
                frames.append(f.convert("P", palette=Image.ADAPTIVE, colors=128))
    out.parent.mkdir(parents=True, exist_ok=True)
    frames[0].save(out, save_all=True, append_images=frames[1:], duration=140, loop=0,
                   optimize=True, disposal=2)
    return out


if __name__ == "__main__":
    p = build(Path("docs/demo.gif"))
    print(p, p.stat().st_size // 1024, "KB")
