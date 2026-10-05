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
    ("user.prompt_submitted", "", "Hermes is thinking"),
    ("tool.started", "terminal", "Runs a terminal command"),
    ("tool.finished", "terminal", "Command finished"),
    ("tool.started", "web_search", "Searches the web"),
    ("tool.failed", "web_search", "A search failed"),
    ("approval.required", "", "Needs your OK"),
    ("approval.approved", "", "You approved"),
    ("tool.started", "github", "Works on code"),
    ("agent.subagent_spawned", "", "Sends out a helper"),
    ("agent.subagent_finished", "", "The helper is back"),
    ("task.complete", "", "Task complete"),
]


def build(out: Path, companion: str = "nyamekra", palette: str | None = "cosmic") -> Path:
    from hermes_companion.animation.characters import traits
    clock = [0.0]
    t = traits(companion)
    engine = BehaviorEngine(seed=11, variety=True, clock=lambda: clock[0], travel=t["travel"])
    r = FrameRenderer(companion, palette)
    observe = t.get("observe")
    live_state = None
    if observe is not None:                    # run the companion's live state on the GIF's clock
        from hermes_companion.animation import masque
        if t["observe"] is masque.observe:
            live_state = masque.STATE
            saved = dict(live_state.__dict__)
            live_state.__dict__.update(masque.MasqueState(clock=lambda: clock[0]).__dict__)
    W, H = max(360, r.fw + 40), r.fh + 80
    frames: list[Image.Image] = []
    bg = Image.new("RGBA", (W, H), "#0b0912")
    d0 = ImageDraw.Draw(bg)
    for i in range(0, H, 3):                     # soft vertical gradient
        d0.line([(0, i), (W, i)], fill=(14 + i // 30, 10 + i // 40, 26 + i // 18, 255))
    caption_font, small = _font(15, True), _font(11, False)
    for kind, tool, caption in SESSION:
        clock[0] += 10.0          # events spaced out, as in a real session
        ev = SemanticEvent(EventKind(kind), tool=tool, category=classify_tool(tool))
        if observe:
            observe(ev)                # live state (Masque: colour, tendrils, cracks, eyes)
        chain = engine.handle(ev)
        # Signature moves only: the demo shows what each Hermes action looks like.
        poses = [st["pose"] for st in chain.steps if st.get("role") != "flourish"][:6] \
            if chain else ["idle_bob"]
        for pose in poses:
            for step in range(3):
                f = bg.copy()
                f.alpha_composite(r.frame(pose, step / 4), ((W - r.fw) // 2, 18))
                d = ImageDraw.Draw(f)
                d.text((W / 2, H - 34), caption, fill="#ffe39a", font=caption_font, anchor="mm")
                d.text((W / 2, H - 14), f"{mood_label(pose)} · {pose.replace('_', ' ')}",
                       fill="#c4b5fd", font=small, anchor="mm")
                if r.fw > 200:                 # big companions: keep the GIF a sensible size
                    f = f.resize((int(W * 0.8), int(H * 0.8)), Image.LANCZOS)
                frames.append(f.convert("P", palette=Image.ADAPTIVE, colors=96))
                clock[0] += 0.14               # one GIF frame of time
    if live_state is not None:
        live_state.__dict__.update(saved)
    out.parent.mkdir(parents=True, exist_ok=True)
    frames[0].save(out, save_all=True, append_images=frames[1:], duration=140, loop=0,
                   optimize=True, disposal=2)
    return out


if __name__ == "__main__":
    import sys
    if len(sys.argv) > 1:                       # e.g. masque docs/masque-demo.gif
        p = build(Path(sys.argv[2] if len(sys.argv) > 2 else f"docs/{sys.argv[1]}-demo.gif"),
                  sys.argv[1], None)
        print(p, p.stat().st_size // 1024, "KB")
        sys.exit(0)
    p = build(Path("docs/demo.gif"))
    print(p, p.stat().st_size // 1024, "KB")
