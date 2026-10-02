"""High-quality frames for procedural companions.

The classic overlay draws straight onto a Tk canvas and keys out one colour,
so every edge is a hard staircase and glows can't fade. Here the same
character code draws onto ``PILCanvas`` at 3x size, which is then
downsampled (anti-aliasing), given a soft mood-coloured glow and a little
squash-and-stretch, and returned as a straight-alpha RGBA image ready for a
per-pixel-alpha window (``renderer.layered``).

The character renderers are unchanged: they still speak the Tk canvas API.
"""
from __future__ import annotations

import math
from collections import OrderedDict
from functools import lru_cache

from PIL import Image, ImageChops, ImageDraw, ImageFilter, ImageFont

from hermes_companion.animation.animator import pose_params

FRAME_W, FRAME_H = 200, 220
SUPERSAMPLE = 3
PROGRESS_STEPS = 24          # frames per pose cycle kept in the cache
CACHE_FRAMES = 600


def _color(c):
    return c if c else None


def _chaikin(points: list[tuple[float, float]], closed: bool, rounds: int = 3):
    """Corner-cutting smoothing, a close match for Tk's ``smooth=True``."""
    for _ in range(rounds):
        out = []
        n = len(points)
        last = n if closed else n - 1
        if not closed:
            out.append(points[0])
        for i in range(last):
            (x0, y0), (x1, y1) = points[i], points[(i + 1) % n]
            out += [(0.75 * x0 + 0.25 * x1, 0.75 * y0 + 0.25 * y1),
                    (0.25 * x0 + 0.75 * x1, 0.25 * y0 + 0.75 * y1)]
        if not closed:
            out.append(points[-1])
        points = out
    return points


@lru_cache(maxsize=16)
def _font(size: int, bold: bool):
    for name in (("segoeuib.ttf", "arialbd.ttf", "DejaVuSans-Bold.ttf") if bold
                 else ("segoeui.ttf", "arial.ttf", "DejaVuSans.ttf")):
        try:
            return ImageFont.truetype(name, size)
        except OSError:
            continue
    try:
        return ImageFont.load_default(size)
    except TypeError:          # Pillow < 10.1
        return ImageFont.load_default()


class PILCanvas:
    """Enough of tkinter.Canvas for the companion renderers, drawn with PIL."""

    def __init__(self, w: int = FRAME_W, h: int = FRAME_H, scale: int = SUPERSAMPLE):
        self.w, self.h, self.s = w, h, scale
        self.delete()

    def delete(self, *_):
        self.img = Image.new("RGBA", (self.w * self.s, self.h * self.s), (0, 0, 0, 0))
        self.d = ImageDraw.Draw(self.img)

    def _pts(self, coords):
        flat = list(coords[0]) if len(coords) == 1 and isinstance(coords[0], (list, tuple)) \
            else list(coords)
        return [(flat[i] * self.s, flat[i + 1] * self.s) for i in range(0, len(flat) - 1, 2)]

    def _w(self, kw, default=1):
        return max(1, int(round(kw.get("width", default) * self.s)))

    def create_oval(self, x1, y1, x2, y2, **kw):
        box = [min(x1, x2) * self.s, min(y1, y2) * self.s, max(x1, x2) * self.s,
               max(y1, y2) * self.s]
        self.d.ellipse(box, fill=_color(kw.get("fill")),
                       outline=_color(kw.get("outline")), width=self._w(kw))

    def create_rectangle(self, x1, y1, x2, y2, **kw):
        box = [min(x1, x2) * self.s, min(y1, y2) * self.s, max(x1, x2) * self.s,
               max(y1, y2) * self.s]
        self.d.rectangle(box, fill=_color(kw.get("fill")),
                         outline=_color(kw.get("outline")), width=self._w(kw))

    def create_line(self, *coords, **kw):
        pts = self._pts(coords)
        if kw.get("smooth") and len(pts) > 2:
            pts = _chaikin(pts, closed=False)
        width = self._w(kw)
        fill = _color(kw.get("fill")) or "#000000"
        self.d.line(pts, fill=fill, width=width, joint="curve")
        if kw.get("capstyle") == "round" and width > 2:
            r = width / 2
            for x, y in (pts[0], pts[-1]):
                self.d.ellipse([x - r, y - r, x + r, y + r], fill=fill)

    def create_polygon(self, *coords, **kw):
        pts = self._pts(coords)
        if kw.get("smooth") and len(pts) > 2:
            pts = _chaikin(pts, closed=True)
        self.d.polygon(pts, fill=_color(kw.get("fill")), outline=_color(kw.get("outline")))

    def create_arc(self, x1, y1, x2, y2, **kw):
        box = [min(x1, x2) * self.s, min(y1, y2) * self.s, max(x1, x2) * self.s,
               max(y1, y2) * self.s]
        # Tk measures arcs counter-clockwise from 3 o'clock; PIL clockwise.
        start = kw.get("start", 0.0)
        extent = kw.get("extent", 90.0)
        a0, a1 = -(start + extent), -start
        style = kw.get("style", "pieslice")
        if style == "arc":
            self.d.arc(box, a0, a1, fill=_color(kw.get("outline")) or "#000000",
                       width=self._w(kw))
        elif style == "chord":
            self.d.chord(box, a0, a1, fill=_color(kw.get("fill")),
                         outline=_color(kw.get("outline")))
        else:
            self.d.pieslice(box, a0, a1, fill=_color(kw.get("fill")),
                            outline=_color(kw.get("outline")))

    def create_text(self, x, y, text="", **kw):
        font = kw.get("font") or ("Segoe UI", 9)
        size = int(font[1]) if len(font) > 1 else 9
        bold = len(font) > 2 and "bold" in str(font[2])
        f = _font(max(6, int(size * 1.33 * self.s)), bold)
        self.d.text((x * self.s, y * self.s), str(text), fill=_color(kw.get("fill")),
                    font=f, anchor="mm")


def _glow(frame: Image.Image, color: str, radius: float = 7.0, strength: float = 0.55):
    alpha = frame.getchannel("A")
    halo = alpha.filter(ImageFilter.GaussianBlur(radius))
    halo = halo.point(lambda v: int(v * strength))
    layer = Image.new("RGBA", frame.size, color)
    layer.putalpha(halo)
    return Image.alpha_composite(layer, frame)


def _squash(frame: Image.Image, pose: str, progress: float) -> Image.Image:
    """Stretch on take-off, squash on landing, anchored at the feet."""
    body = pose_params(pose, progress)["body"]
    p = progress % 1.0
    if body == "jump":
        sy = 1.0 + 0.10 * math.sin(p * math.pi)
    elif pose in ("land", "fall", "sit_back", "huff"):
        sy = 1.0 - 0.08 * math.sin(p * math.pi)
    elif body == "walk" or pose.endswith("_to_workspace"):
        sy = 1.0 + 0.03 * math.sin(p * 4 * math.pi)
    else:
        sy = 1.0 + 0.015 * math.sin(p * 2 * math.pi)   # breathing
    if abs(sy - 1.0) < 0.004:
        return frame
    sx = 1.0 / math.sqrt(sy)                           # keep the volume
    w, h = frame.size
    nw, nh = max(1, int(w * sx)), max(1, int(h * sy))
    scaled = frame.resize((nw, nh), Image.LANCZOS)
    out = Image.new("RGBA", (w, h), (0, 0, 0, 0))
    feet = int(h * 0.80)                               # ground line in the frame
    out.paste(scaled, ((w - nw) // 2, feet - int(feet * sy)), scaled)  # clips at edges
    return out


class FrameRenderer:
    """Renders and caches high-quality frames for one companion + palette."""

    def __init__(self, companion: str, palette: str | None = None,
                 glow: bool = True, squash: bool = True, scale: float = 1.0):
        from hermes_companion.animation.characters import COMPANIONS
        self.draw = COMPANIONS[companion]["draw"]
        self.companion, self.palette = companion, palette
        self.glow, self.squash, self.scale = glow, squash, scale
        self._cache: OrderedDict[tuple, Image.Image] = OrderedDict()

    def mood_color(self, pose: str) -> str:
        if self.companion == "herald":
            from hermes_companion.animation.herald import MOOD_COLORS, mood_of
            return MOOD_COLORS[mood_of(pose)]
        return "#93c5fd"

    def frame(self, pose: str, progress: float) -> Image.Image:
        step = int((progress % 1.0) * PROGRESS_STEPS)
        key = (pose, step)
        hit = self._cache.get(key)
        if hit is not None:
            self._cache.move_to_end(key)
            return hit
        p = step / PROGRESS_STEPS
        canvas = PILCanvas()
        self.draw(canvas, pose, p, palette=self.palette)
        out_w, out_h = int(FRAME_W * self.scale), int(FRAME_H * self.scale)
        img = canvas.img.resize((out_w, out_h), Image.LANCZOS)
        if self.squash:
            img = _squash(img, pose, p)
        if self.glow:
            img = _glow(img, self.mood_color(pose), radius=6.0 * self.scale)
        self._cache[key] = img
        if len(self._cache) > CACHE_FRAMES:
            self._cache.popitem(last=False)
        return img


def premultiplied_bgra(img: Image.Image) -> bytes:
    """Bytes for UpdateLayeredWindow: premultiplied BGRA, top-down rows."""
    r, g, b, a = img.split()
    r, g, b = (ImageChops.multiply(ch, a) for ch in (r, g, b))
    return Image.merge("RGBA", (b, g, r, a)).tobytes()


def chroma_fallback(img: Image.Image, key=(0, 254, 0)) -> Image.Image:
    """For a colour-keyed window: matte soft edges onto a dark rim so they
    don't fringe green, then hard-key what is left."""
    rim = Image.new("RGBA", img.size, (15, 23, 42, 255))
    bg = Image.new("RGBA", img.size, key + (255,))
    alpha = img.getchannel("A")
    solid = alpha.point(lambda v: 255 if v >= 96 else 0)
    matted = Image.alpha_composite(rim, img)
    return Image.composite(matted, bg, solid)
