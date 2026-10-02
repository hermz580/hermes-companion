"""Render the FULL pose vocabulary of a procedural companion to proof sheets.

Why this exists: the rigged (procedural) companions have no art ceiling — every
pose is drawn from `pose_params`, so the number of distinct moves is a property
of the code, not of a spritesheet. This script makes that property visible and
testable:

  * renders every pose the behavior engine can actually emit (+ every pose the
    overlay can map) at several progress points,
  * counts DISTINCT renders (pixel signatures), i.e. how many looks the
    companion really has,
  * flags any pose that renders identically to the unknown-pose fallback — a
    "dead pose" that silently shows a neutral body instead of its intended move,
  * writes one labelled contact sheet per companion so a human can review the
    whole vocabulary at a glance,
  * exits nonzero when a dead pose exists, so the condition cannot ship.

Headless-vector (a recording canvas), not a window grab: no desktop window is
opened, and it cannot photograph the wallpaper on a locked session.

Usage:
    python scripts/render_pose_sheet.py                     # every companion
    python scripts/render_pose_sheet.py --companion astro
    python scripts/render_pose_sheet.py --companion samurai --palette jade
"""
from __future__ import annotations

import argparse
import hashlib
import os
import sys
from pathlib import Path

os.environ.setdefault("PYTHONPATH", str(Path(__file__).resolve().parents[2]))

from PIL import Image, ImageDraw  # noqa: E402

from hermes_companion.animation.characters import (  # noqa: E402
    COMPANIONS, draw_companion, list_companions)
from hermes_companion.animation.animator import pose_params  # noqa: E402

FRAME_W, FRAME_H = 200, 220
PROGRESS_SAMPLES = (0.2, 0.5, 0.8)
FALLBACK_PROBE = "__no_such_pose__"
LABEL_H = 14
SHEET_COLUMNS = 12


def _pil_color(c):
    """tkinter uses '' for 'no fill'; PIL needs None."""
    return c if c else None


class RecordingCanvas:
    """tkinter-canvas-shaped stand-in recording primitives onto an RGBA image.

    Only the methods the animators use are implemented; anything else raises,
    which is itself a useful contract for a new renderer.
    """

    def __init__(self, w: int = FRAME_W, h: int = FRAME_H) -> None:
        self.w, self.h = w, h
        self.img = Image.new("RGBA", (w, h), (0, 254, 0, 0))
        self.d = ImageDraw.Draw(self.img)
        self._shapes = 0

    def create_oval(self, x1, y1, x2, y2, **kw):
        self._shapes += 1
        self.d.ellipse([x1, y1, x2, y2], fill=_pil_color(kw.get("fill")),
                       outline=_pil_color(kw.get("outline")),
                       width=kw.get("width", 1))
        return self._shapes

    def create_rectangle(self, x1, y1, x2, y2, **kw):
        self._shapes += 1
        self.d.rectangle([x1, y1, x2, y2], fill=_pil_color(kw.get("fill")),
                         outline=_pil_color(kw.get("outline")),
                         width=kw.get("width", 1))
        return self._shapes

    def create_line(self, x1, y1, x2, y2, **kw):
        self._shapes += 1
        self.d.line([x1, y1, x2, y2], fill=_pil_color(kw.get("fill")),
                    width=kw.get("width", 1))
        return self._shapes

    def create_polygon(self, *coords, **kw):
        self._shapes += 1
        self.d.polygon(list(coords), fill=_pil_color(kw.get("fill")),
                       outline=_pil_color(kw.get("outline")))
        return self._shapes

    def create_text(self, x, y, text="", **kw):
        self._shapes += 1
        self.d.text((x, y), text, fill=_pil_color(kw.get("fill")))
        return self._shapes

    def create_arc(self, x1, y1, x2, y2, **kw):
        self._shapes += 1
        if kw.get("style") == "arc":
            self.d.arc([x1, y1, x2, y2], start=kw.get("start", 0),
                       end=kw.get("start", 0) + kw.get("extent", 360),
                       fill=_pil_color(kw.get("outline")),
                       width=kw.get("width", 1))
        else:
            self.d.pieslice([x1, y1, x2, y2], start=kw.get("start", 0),
                            end=kw.get("start", 0) + kw.get("extent", 360),
                            fill=_pil_color(kw.get("fill")),
                            outline=_pil_color(kw.get("outline")))
        return self._shapes

    def delete(self, *args):  # noqa: ARG002
        self.img = Image.new("RGBA", (self.w, self.h), (0, 254, 0, 0))
        self.d = ImageDraw.Draw(self.img)

    def signature(self) -> str:
        return hashlib.blake2s(self.img.tobytes(), digest_size=12).hexdigest()

    def opaque(self) -> int:
        """Opaque pixel count, excluding the chroma key."""
        px = self.img.load()
        return sum(1 for y in range(self.h) for x in range(self.w)
                   if px[x, y][3] > 0 and px[x, y][:3] != (0, 254, 0))


def engine_poses() -> list[str]:
    """Every pose the behavior engine or the overlay can reach.

    Read from the rules + overlay mapping so this cannot drift from the real
    vocabulary: chains/arcs/idle-progression supply the emitted names, and
    POSE_ROW supplies any name the overlay can map.
    """
    from hermes_companion.behavior import behavior_rules as br
    from hermes_companion.renderer.petdex_overlay import POSE_ROW

    def steps_of(chain):
        if hasattr(chain, "steps"):
            return chain.steps
        if isinstance(chain, tuple):
            for part in chain:
                if isinstance(part, list):
                    return part
        return []

    names: set[str] = set()
    for table in (br.CHAINS, br.CHAINS_BY_CATEGORY, br.EMOTIONAL_ARCS):
        for _key, value in table.items():
            if isinstance(value, dict) and "pose" in value:
                names.add(str(value["pose"]))
                continue
            for step in steps_of(value):
                if isinstance(step, dict) and step.get("pose"):
                    names.add(str(step["pose"]))
    for _timeout, pose, _dur in br.IDLE_PROGRESSION:
        names.add(str(pose))
    names.update(POSE_ROW)
    return sorted(names)


def render(companion: str, pose: str, progress: float,
           palette: str | None = None) -> RecordingCanvas:
    canvas = RecordingCanvas()
    draw_companion(canvas, companion, pose, progress, palette=palette)
    return canvas


def signatures(companion: str, pose: str, palette: str | None = None) -> tuple[str, ...]:
    """Signature across several progress points: two poses that differ only in
    animation phase are still different moves."""
    return tuple(render(companion, pose, p, palette).signature()
                 for p in PROGRESS_SAMPLES)


def build_sheet(companion: str, poses: list[str], out: Path,
                palette: str | None = None) -> None:
    renders = [render(companion, pose, 0.5, palette) for pose in poses]
    cols = min(SHEET_COLUMNS, max(1, len(renders)))
    rows = (len(renders) + cols - 1) // cols
    cell_h = FRAME_H + LABEL_H
    sheet = Image.new("RGBA", (cols * FRAME_W, rows * cell_h), (24, 24, 32, 255))
    d = ImageDraw.Draw(sheet)
    for i, (pose, canvas) in enumerate(zip(poses, renders)):
        cx, cy = (i % cols) * FRAME_W, (i // cols) * cell_h
        d.rectangle([cx, cy, cx + FRAME_W - 1, cy + LABEL_H - 1], fill=(40, 40, 54, 255))
        d.text((cx + 3, cy + 3), pose[:26], fill=(235, 235, 245, 255))
        # White backing so transparent glyphs stay readable in the review image.
        tile = Image.new("RGBA", (FRAME_W, FRAME_H), (255, 255, 255, 255))
        tile.alpha_composite(canvas.img)
        sheet.paste(tile, (cx, cy + LABEL_H))
    sheet.save(out)


def check(companion: str, palette: str | None = None, outdir: Path | None = None) -> int:
    """Render + report one companion's whole vocabulary."""
    poses = engine_poses()
    outdir = outdir or Path(__file__).resolve().parent.parent / "proof" / "poses" / companion
    outdir.mkdir(parents=True, exist_ok=True)

    fallback = signatures(companion, FALLBACK_PROBE, palette)
    dead: list[str] = []
    low_ink: list[str] = []
    seen: dict[tuple[str, ...], str] = {}

    for pose in poses:
        sig = signatures(companion, pose, palette)
        render(companion, pose, 0.5, palette).img.save(outdir / f"{pose}.png")
        if sig == fallback:
            dead.append(pose)
        ink = render(companion, pose, 0.5, palette).opaque()
        if ink < 400:
            low_ink.append(f"{pose}({ink})")
        seen.setdefault(sig, pose)

    sheet = outdir / f"sheet_{companion}.png"
    build_sheet(companion, poses, sheet, palette)

    print(f"== {companion} ==")
    print(f"  poses checked        : {len(poses)}")
    print(f"  distinct looks       : {len(seen)}")
    print(f"  dead (neutral body)  : {len(dead)} {dead if dead else ''}")
    print(f"  low ink (<400 px)    : {len(low_ink)} {low_ink[:8] if low_ink else ''}")
    print(f"  contact sheet        : {sheet}")
    return 1 if dead else 0


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--companion", choices=list_companions(), default=None,
                    help="which companion (default: all of them)")
    ap.add_argument("--palette", default=None,
                    help="material palette name (companion-specific)")
    ap.add_argument("--outdir", default=None)
    args = ap.parse_args(argv)

    targets = [args.companion] if args.companion else list_companions()
    outdir = Path(args.outdir) if args.outdir else None
    failed = 0
    for name in targets:
        palettes = COMPANIONS[name]["palettes"]
        palette = args.palette if args.palette in palettes else None
        if args.palette and palette is None:
            print(f"  (palette {args.palette!r} not offered by {name}; using default)")
        failed |= check(name, palette, outdir)
    print("\n[PASS] every pose renders a distinct move" if not failed
          else "\n[FAIL] dead poses found — they render as a neutral body")
    return 1 if failed else 0


if __name__ == "__main__":
    raise SystemExit(main())
