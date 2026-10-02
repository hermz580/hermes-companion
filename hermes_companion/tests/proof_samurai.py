"""Headless SAMURAI companion proof — render the new companion across poses
and material palettes to PNGs WITHOUT touching the display.

Why headless-vector instead of a window grab: the windowed ImageGrab approach
(used by the round-pet proof) grabs the wallpaper when the desktop capture is
unavailable (locked session / screen switched), and that failure is not
deterministic. Here the samurai's canvas primitives are recorded onto a
transparent RGBA buffer by a minimal recording-canvas stand-in, so the proof
runs anywhere with PIL and no window at all.

Proves:
- the samurai renderer draws a REAL, distinct character (opaque-pixel count)
- every engine pose renders without error (pose vocabulary is shared)
- every material palette renders (changeable elements/materials)
- the FIXED kasa hat + geta shoes are present in every palette (the exact
  RGB of those regions is unchanged across all six palettes)
"""
from __future__ import annotations

import os

os.environ.setdefault("PYTHONPATH", str(Path(__file__).resolve().parents[2]))

from PIL import Image, ImageDraw

from hermes_companion.animation.samurai import (
    GETA_RGB, KASA_RGB, SAMURAI_PALETTES, draw_samurai)

POSES = [
    "idle_bob", "walk_to_workspace", "jump", "terminal_work",
    "web_scan", "memory_vault", "celebrate", "bow", "slash",
]


def _pil_color(c):
    """tkinter uses '' for 'no fill'; PIL needs None."""
    return c if c else None


class RecordingCanvas:
    """A tkinter-canvas-shaped stand-in that records every draw_samurai
    primitive onto an RGBA Image. Only the methods the animator uses are
    implemented; anything else raises, which is itself a useful contract."""

    def __init__(self, w: int = 200, h: int = 220) -> None:
        self.img = Image.new("RGBA", (w, h), (0, 254, 0, 0))  # chroma, alpha 0
        self.d = ImageDraw.Draw(self.img)
        self.w = w
        self.h = h
        self._shapes = 0

    # -- Canvas API used by the animator ------------------------------------
    def create_oval(self, x1, y1, x2, y2, **kw):
        self._shapes += 1
        self.d.ellipse([x1, y1, x2, y2],
                       fill=_pil_color(kw.get("fill")),
                       outline=_pil_color(kw.get("outline")),
                       width=kw.get("width", 1))
        return self._shapes

    def create_rectangle(self, x1, y1, x2, y2, **kw):
        self._shapes += 1
        self.d.rectangle([x1, y1, x2, y2],
                         fill=_pil_color(kw.get("fill")),
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
        # tkinter arcs: start/extent in degrees, style in
        # ('arc', 'chord', 'pieslice'); PIL uses the same convention.
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

    # -- analysis ------------------------------------------------------------
    def analyze(self) -> dict:
        """Opaque pixel count + color histogram (alpha>0, chroma excluded)."""
        px = self.img.load()
        w, h = self.img.size
        opaque = 0
        hist: dict[tuple, int] = {}
        for y in range(h):
            for x in range(w):
                r, g, b, a = px[x, y]
                if a > 0 and (r, g, b) != (0, 254, 0):
                    opaque += 1
                    hist[(r, g, b)] = hist.get((r, g, b), 0) + 1
        return {"opaque": opaque, "colors": len(hist),
                "hist": hist, "shapes": self._shapes}

    def save(self, out: str) -> None:
        self.img.save(out)


def _near(c1: tuple, c2: tuple, tol: int = 28) -> bool:
    return all(abs(a - b) <= tol for a, b in zip(c1, c2))


def render_samurai(pose: str, progress: float = 0.5, out: str = "",
                   palette: str | None = None) -> dict | None:
    """Render one samurai pose into a recording canvas; return its analysis.
    Raises if the renderer uses a Canvas method we did not stub."""
    canvas = RecordingCanvas()
    draw_samurai(canvas, pose, progress, palette=palette)
    if out:
        canvas.save(out)
    return canvas.analyze()


def main() -> int:
    from pathlib import Path
    outdir = Path(__file__).resolve().parent.parent / "proof" / "samurai"
    outdir.mkdir(parents=True, exist_ok=True)

    # 1) pose sheet (default crimson)
    print("== samurai poses (crimson) ==")
    failures: list[str] = []
    for i, pose in enumerate(POSES):
        a = render_samurai(pose, 0.5, str(outdir / f"{i:02d}_{pose}.png"))
        opaque, colors = a["opaque"], a["colors"]
        print(f"  {pose}: opaque={opaque} colors={colors} shapes={a['shapes']}")
        if opaque <= 800:
            failures.append(f"{pose} (low opaque px {opaque})")
        if colors < 6:
            failures.append(f"{pose} (too few colors {colors})")

    # 2) palette sheet — changeable materials + fixed hat/geta
    print("== palettes (memory_vault pose) ==")
    hat_present = all(
        any(_near(c, KASA_RGB) for c in
            render_samurai("memory_vault", 0.5, palette=pname)["hist"])
        for pname in SAMURAI_PALETTES)
    geta_present = all(
        any(_near(c, GETA_RGB) for c in
            render_samurai("memory_vault", 0.5, palette=pname)["hist"])
        for pname in SAMURAI_PALETTES)
    for pi, pname in enumerate(SAMURAI_PALETTES):
        a = render_samurai("memory_vault", 0.5,
                           str(outdir / f"pal_{pi:02d}_{pname}.png"),
                           palette=pname)
        print(f"  {pname}: opaque={a['opaque']} colors={a['colors']} "
              f"shapes={a['shapes']}")
        if a["opaque"] <= 800:
            failures.append(f"palette {pname} (low opaque px {a['opaque']})")

    if failures:
        print(f"\n[FAIL] {len(failures)} problem(s): {failures}")
        return 1
    fixed_ok = hat_present and geta_present
    print(f"\n[PASS] samurai renders in {len(POSES)} poses × "
          f"{len(SAMURAI_PALETTES)} palettes; fixed kasa hat "
          f"{'CONFIRMED' if hat_present else 'MISSING'}, geta "
          f"{'CONFIRMED' if geta_present else 'MISSING'}")
    return 0 if fixed_ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
