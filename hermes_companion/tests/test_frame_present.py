"""Presenting frames: one redraw per tick, none when nothing changed, conversions reused."""
from PIL import Image

from hermes_companion.renderer import overlay as O
from hermes_companion.renderer.layered import SmoothLiveOverlay


class Root:
    def __init__(self):
        self.idle, self.later = [], []

    def after_idle(self, fn):
        self.idle.append(fn)

    def after(self, ms, fn):
        self.later.append((ms, fn))

    def run_idle(self):
        jobs, self.idle = self.idle, []
        for fn in jobs:
            fn()


class Renderer:
    def __init__(self):
        self.cache = {}

    def frame(self, pose, progress):
        key = (pose, int(progress * 4))
        if key not in self.cache:
            self.cache[key] = Image.new("RGBA", (8, 8), (len(pose), key[1], 0, 255))
        return self.cache[key]


class Blitter:
    def __init__(self):
        self.calls = []

    def blit(self, img, x, y, data=None):
        self.calls.append((img, x, y, data))


def _overlay():
    o = SmoothLiveOverlay.__new__(SmoothLiveOverlay)     # no window: test the logic only
    o.root, o.renderer, o.blitter = Root(), Renderer(), Blitter()
    o._pose, o.x, o._y, o.w, o.h = ("idle_bob", 0.0), 10, 20, 8, 8
    o._bubble_text = None
    conversions = []
    import hermes_companion.renderer.layered as L
    real = L.premultiplied_bgra
    L.premultiplied_bgra = lambda img: conversions.append(img) or real(img)
    return o, conversions, (L, real)


def test_pose_and_move_in_one_tick_draw_once():
    o, _conv, (L, real) = _overlay()
    try:
        o.set_pose("walk", 0.5)
        o._place(30, 20)
        o.set_pose("walk", 0.75)
        assert len(o.root.idle) == 1                     # three requests, one redraw queued
        o.root.run_idle()
        assert len(o.blitter.calls) == 1
        img, x, y, _ = o.blitter.calls[0]
        assert (x, y) == (30, 20) and img is o.renderer.frame("walk", 0.75)
    finally:
        L.premultiplied_bgra = real


def test_nothing_changed_means_no_redraw():
    o, _conv, (L, real) = _overlay()
    try:
        o._present(); o.root.run_idle()
        o._present(); o.root.run_idle()                 # same frame, same place
        assert len(o.blitter.calls) == 1
        o._place(11, 20); o.root.run_idle()             # moved: draw again
        assert len(o.blitter.calls) == 2
    finally:
        L.premultiplied_bgra = real


def test_each_frame_is_converted_once_and_reused():
    o, conv, (L, real) = _overlay()
    try:
        for x in range(5):                               # walking in place on one frame
            o._place(x, 20); o.root.run_idle()
        o.set_pose("wave", 0.0); o.root.run_idle()
        o.set_pose("idle_bob", 0.0); o.root.run_idle()   # back to a frame seen before
        assert len(o.blitter.calls) == 7
        assert len(conv) == 2                            # idle_bob once, wave once
        datas = {id(c[3]) for c in o.blitter.calls if c[0] is o.renderer.frame("idle_bob", 0)}
        assert len(datas) == 1
    finally:
        L.premultiplied_bgra = real


def test_bubble_text_is_drawn_and_counts_as_a_change():
    o, _conv, (L, real) = _overlay()
    try:
        o._present(); o.root.run_idle()
        o.w = o.h = 120
        o._show_bubble_inline("Need your OK"); o.root.run_idle()
        assert len(o.blitter.calls) == 2
        assert o.blitter.calls[1][0] is not o.renderer.frame("idle_bob", 0)
    finally:
        L.premultiplied_bgra = real


class Director:
    def __init__(self):
        self.steps = []

    def step(self, dt):
        self.steps.append(dt)


def test_ticks_advance_by_real_time_and_clamp_stalls(monkeypatch):
    o = O.ProceduralLiveOverlay.__new__(O.ProceduralLiveOverlay)
    o.root, o._director = Root(), Director()
    clock = iter([0.0, 0.0, 0.05, 0.05, 2.05, 2.05])
    monkeypatch.setattr(O.time, "monotonic", lambda: next(clock))
    o._tick(); o._tick(); o._tick()
    assert o._director.steps[0] == O.TICK_S              # first tick: nominal step
    assert abs(o._director.steps[1] - 0.05) < 1e-9       # a slow tick moves further
    assert o._director.steps[2] == O.MAX_STEP_S          # a 2 s stall doesn't teleport
    assert all(ms >= 1 for ms, _fn in o.root.later)
