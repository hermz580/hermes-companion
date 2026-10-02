"""Perching: live on the active window, but Hermes's work happens on the floor."""
from dataclasses import replace

from hermes_companion.animation.director import Director
from hermes_companion.behavior.behavior_engine import BehaviorEngine
from hermes_companion.behavior.perch import FEET_Y, PerchDriver, PerchMotion, PerchPlanner
from hermes_companion.renderer.desktop_sensors import Snapshot

WIN = Snapshot(cursor=(0, 0), buttons_down=False, fg_handle=11,
               fg_rect=(400, 400, 1400, 1000), fg_minimized=False, fg_maximized=False,
               last_input_ms=0, clipboard_seq=0, displays=1, hour=12)


def _planner():
    return PerchPlanner(200, 220, floor_y=1200, settle_s=0.0)


def test_perches_on_the_title_bar():
    a = _planner().plan(WIN, hermes_quiet=True, current_x=900, now=1.0)
    assert a.kind == "perch" and a.y == 400 - FEET_Y + 2
    assert 400 <= a.x <= 1400 - 200


def test_rides_a_dragged_window():
    p = _planner()
    first = p.plan(WIN, hermes_quiet=True, current_x=900, now=1.0)
    moved = p.plan(replace(WIN, fg_rect=(500, 350, 1500, 950)), hermes_quiet=True,
                   current_x=first.x, now=2.0)
    assert moved.reason == "ride"
    assert (moved.x - first.x, moved.y - first.y) == (100, -50)


def test_hops_to_a_newly_focused_window():
    p = _planner()
    p.plan(WIN, hermes_quiet=True, current_x=900, now=1.0)
    a = p.plan(replace(WIN, fg_handle=22, fg_rect=(0, 300, 900, 800)), hermes_quiet=True,
               current_x=900, now=2.0)
    assert a.kind == "perch" and a.reason == "hop" and a.handle == 22


def test_drops_when_window_cant_be_stood_on():
    for why, snap in (("minimized", replace(WIN, fg_minimized=True)),
                      ("maximized", replace(WIN, fg_maximized=True)),
                      ("too small", replace(WIN, fg_rect=(400, 400, 500, 450))),
                      ("no headroom", replace(WIN, fg_rect=(400, 50, 1400, 900))),
                      ("no window", replace(WIN, fg_handle=0))):
        p = _planner()
        p.plan(WIN, hermes_quiet=True, current_x=900, now=1.0)
        a = p.plan(snap, hermes_quiet=True, current_x=900, now=2.0)
        assert a.kind == "floor" and a.reason == why and a.y == 1200


def test_hermes_work_always_happens_on_the_floor():
    p = _planner()
    p.plan(WIN, hermes_quiet=True, current_x=900, now=1.0)
    a = p.plan(WIN, hermes_quiet=False, current_x=900, now=2.0)
    assert a.kind == "floor" and a.reason == "hermes busy"


def test_waits_before_climbing_back_up():
    p = PerchPlanner(200, 220, floor_y=1200, settle_s=3.0)
    assert p.plan(WIN, hermes_quiet=True, current_x=900, now=10.0).kind == "floor"
    assert p.plan(WIN, hermes_quiet=True, current_x=900, now=11.0).kind == "floor"
    assert p.plan(WIN, hermes_quiet=True, current_x=900, now=13.5).kind == "perch"


def test_motion_hits_both_ends_and_arcs_upward():
    m = PerchMotion(0, 1000, 300, 600, start=0.0, style="hop")
    assert m.at(0.0)[:2] == (0, 1000)
    assert m.at(m.duration)[:2] == (300, 600)
    mid_y = m.at(m.duration / 2)[1]
    assert mid_y < 800 - 30          # apex above the straight line
    d = PerchMotion(300, 600, 300, 1000, start=0.0, style="drop")
    ys = [d.at(t * d.duration / 4)[1] for t in range(5)]
    assert ys[-1] == 1000 and all(b >= a for a, b in zip(ys, ys[1:]))
    assert ys[2] - ys[1] > ys[1] - ys[0]   # accelerating


class Surface:
    w, h = 200, 220

    def __init__(self):
        self.x, self.home_x, self.home_y = 900, 900, 1200
        self.poses = []

    def set_x(self, x):
        self.x = x

    def set_y(self, y):
        self.home_y = y

    def place_at(self, x, y):
        self.home_y, self.x = y, x

    def set_pose(self, pose, progress=0.0):
        self.poses.append(pose)

    def set_state(self, s):
        pass


class Sensors:
    prev = WIN


def test_driver_hops_up_then_drops_for_hermes():
    surface = Surface()
    clock = [0.0]
    director = Director(BehaviorEngine(seed=1), surface, clock=lambda: clock[0])
    assert director._x == 900       # starts where the surface is, not at 0
    driver = PerchDriver(surface, director, Sensors(), log=lambda *_: None)
    driver.planner.settle_s = 0.0
    for i in range(80):
        driver.tick(i * 0.05, "quiet")
    assert driver.perched and surface.home_y == 400 - FEET_Y + 2
    for i in range(80, 160):
        driver.tick(i * 0.05, "working")
    assert not driver.perched and surface.home_y == 1200
