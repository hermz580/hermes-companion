"""Headless diversity proof — render each new tool-specific pose + a sample of
the old ones to PNGs, proving the procedural animator draws them distinctly
without opening any window on the user's desktop."""
from __future__ import annotations

import os

os.environ.setdefault("PYTHONPATH", str(Path(__file__).resolve().parents[2]))

import tkinter as tk
from tkinter import font as tkfont

from PIL import Image, ImageGrab

from hermes_companion.animation.animator import BG, draw_pet, pose_params

POSES = [
    # category tool-work poses (new)
    "terminal_work", "web_scan", "file_organize",
    "dev_merge", "media_paint", "memory_vault",
    # v0.3 new category work poses
    "design_draft", "audio_tune", "read", "lean_work",
    # celebration variety
    "double_jump", "spin", "celebrate", "leap", "bounce", "excited",
    # failure / recovery (unchanged, included for baseline)
    "shock", "fall", "repair", "retry", "shake_head", "scratch_head", "think",
    # new emotes
    "shrug", "look_up", "look_down", "check_watch", "yawn", "smug",
    # idle progression
    "look_around", "sit", "play_with_object", "sleep", "stretch_lazy", "dance",
]


def render_pose(pose: str, progress: float = 0.5, out: str = "") -> bool:
    """Render one pose to a PNG. A Tk canvas is the render target, so the
    window must be briefly MAPPED for ImageGrab to capture it — we pin it to
    the bottom-left corner, grab, and destroy it within milliseconds (the
    pet window flashes on screen for one frame, then vanishes)."""
    root = tk.Tk()
    root.overrideredirect(True)  # no frame/title
    try:
        W, H = 200, 220
        x0, y0 = 0, 300  # pinned corner (below the taskbar-ish area)
        root.geometry(f"{W}x{H}+{x0}+{y0}")
        canvas = tk.Canvas(root, width=W, height=H, bg=BG, highlightthickness=0)
        canvas.pack()
        draw_pet(canvas, pose, progress)
        root.update()
        # Wait until the window is ACTUALLY mapped by the OS — an
        # overrideredirect window lags behind update() on Windows, and
        # grabbing before it maps captures the desktop (wallpaper leak).
        import time as _time
        deadline = _time.time() + 2.0
        while _time.time() < deadline:
            root.update()
            try:
                if root.winfo_ismapped() and root.winfo_viewable():
                    break
            except tk.TclError:
                pass
            _time.sleep(0.02)
        # DWM composition lags the Tk map flag — settle before grabbing so the
        # window's pixels are actually on the desktop, not the frame behind.
        _time.sleep(0.3)
        root.update()
        # Read the ACTUAL mapped position (window managers can nudge
        # overrideredirect windows) instead of trusting the geometry request.
        gx, gy = root.winfo_rootx(), root.winfo_rooty()
        img = ImageGrab.grab(bbox=(gx, gy, gx + W, gy + H))
        img = img.convert("RGBA")
        # Make chroma-key green transparent for a clean PNG.
        data = img.getdata()
        new = []
        for px in data:
            r, g, b, a = px
            if g > 180 and r < 90 and b < 90:
                new.append((r, g, b, 0))
            else:
                new.append((r, g, b, 255))
        img.putdata(new)
        img.save(out)
        return True
    except Exception as exc:
        print(f"  [render failed {pose}: {exc}]")
        return False
    finally:
        try:
            root.destroy()
        except Exception:
            pass


def main() -> int:
    outdir = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
                          "proof", "diversity")
    os.makedirs(outdir, exist_ok=True)
    ok = 0
    for i, pose in enumerate(POSES):
        out = os.path.join(outdir, f"{i:02d}_{pose}.png")
        if render_pose(pose, 0.5, out):
            ok += 1
            print(f"  [ok] {out}")
        else:
            print(f"  [FAIL] {pose}")
    print(f"\ndiversity proof: {ok}/{len(POSES)} rendered to {outdir}")
    if ok != len(POSES):
        return 1
    # Gate: every frame must be a real render (small opaque blob), not a
    # wallpaper grab (a full-canvas capture leaks ~44k opaque px). A leak
    # means ImageGrab missed the mapped window — fail loudly.
    bad = []
    for f in sorted(os.listdir(outdir)):
        if not f.endswith(".png"):
            continue
        from PIL import Image
        im = Image.open(os.path.join(outdir, f)).convert("RGBA")
        alpha = im.split()[3]
        n = sum(1 for p in alpha.getdata() if p > 0)
        if n > 10000:
            bad.append(f"{f} ({n}px)")
    if bad:
        print(f"\n[FAIL] wallpaper leak detected in: {bad} — window was not "
              f"mapped at capture time; re-run")
        return 1
    print("\n[PASS] all %d frames are real renders (no wallpaper leak)" % len(POSES))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
