"""Kai out on the desktop: roams, drops in, rides window edges, launches off kickers.

Every one of these is opt-in per character (traits), so the other companions
keep behaving exactly as before.
"""
from __future__ import annotations

import random

from hermes_companion.animation import kai as K
from hermes_companion.animation.characters import COMPANIONS, list_companions, traits
from hermes_companion.animation.director import ARC_BY_POSE, Director, arc_height
from hermes_companion.behavior.behavior_engine import BehaviorEngine, Chain
from hermes_companion.behavior.perch import FEET_Y, PerchDriver, make_driver, start_roaming
from hermes_companion.core.state import State
from hermes_companion.renderer.desktop_sensors import Snapshot

WIN = Snapshot(cursor=(0, 0), buttons_down=False, fg_handle=11,
               fg_rect=(400, 400, 1400, 1000), fg_minimized=False, fg_maximized=False,
               last_input_ms=0, clipboard_seq=0, displays=1, hour=12)


class Surface:
    def __init__(self, w=360, h=300, x=900, home_y=1200):
        self.x, self.home_x, self.home_y, self.w, self.h = x, x, home_y, w, h
        self.poses = []
        self.places = []

    def set_x(self, x):
        self.x = x

    def set_y(self, y):
        self.home_y = y

    def place_at(self, x, y):
        self.home_y, self.x = y, x
        self.places.append((x, y))

    def set_pose(self, pose, progress=0.0):
        self.poses.append(pose)

    def set_state(self, s):
        pass

    def lift(self, dy):
        pass

    def room(self):
        return self.x - 0, 3840 - (self.x + self.w)


class Sensors:
    prev = WIN


def _driver(surface=None, clock=None):
    surface = surface or Surface()
    clock = clock or [0.0]
    director = Director(BehaviorEngine(seed=1), surface, clock=lambda: clock[0])
    driver = make_driver(surface, director, Sensors(), traits("kai"), log=lambda *_: None)
    driver.planner.settle_s = 0.0
    return surface, director, driver


def test_only_kai_opts_in():
    for name in list_companions():
        t = traits(name)
        if name == "kai":
            assert t["roam"] and t["entrance"] and t["perch_ride"] and t["feet_y"] == K.FLOOR
        else:
            assert not t["roam"] and not t["entrance"] and t["perch_ride"] is None and t["feet_y"] is None


def test_he_stands_on_the_title_bar_not_in_it():
    _s, _d, driver = _driver()
    assert driver.planner.feet_y == K.FLOOR                  # not the round pet's 192/220 guess
    default = PerchDriver(Surface(200, 220), _d, Sensors(), log=lambda *_: None)
    assert default.planner.feet_y == FEET_Y


def test_he_rides_the_window_edge_back_and_forth_then_sits():
    surface, director, driver = _driver()
    xs, poses = [], []
    for i in range(400):                                      # 20 s at 20 Hz
        driver.tick(i * 0.05, "quiet")
        xs.append(surface.x)
        poses.append(director.idle_pose)
    assert driver.perched
    riding = [x for x, pose in zip(xs, poses) if pose == "edge_grind"]
    assert max(riding) - min(riding) > 300                    # really travels along the bar
    assert "edge_sit" in poses                                # then takes a seat on the edge
    left, top, right, _b = WIN.fg_rect
    assert all(left <= x and x + surface.w <= right for x in riding)   # never off the window


def test_he_drops_off_the_window_when_hermes_gets_busy():
    surface, director, driver = _driver()
    for i in range(80):
        driver.tick(i * 0.05, "quiet")
    assert driver.perched
    seen = []
    for i in range(80, 140):
        driver.tick(i * 0.05, "working")
        seen.append(director.idle_pose)
    assert "bomb_drop" in seen and surface.home_y == 1200
    assert director.idle_pose == "idle_bob"                   # riding stopped with the perch


def test_entrance_drops_in_from_the_top_of_the_screen():
    surface, director, driver = _driver()
    driver.enter(0.0, 0)
    ys = []
    for i in range(1, 60):
        driver.tick(i * 0.05, "working")
        ys.append(surface.home_y)
    assert ys[0] < 300 and ys[-1] == 1200                     # top of the screen to the floor
    assert ys == sorted(ys)                                   # always falling, never bouncing back up


def _finish(director, clock, chain):
    director.start_chain(chain)
    for _ in range(400):
        clock[0] += 0.033
        director.step(0.033)
        if director.chain is None and not director._returning:
            break


def test_a_roamer_lives_where_it_ends_up():
    surface = Surface(x=600)
    clock = [0.0]
    director = Director(BehaviorEngine(seed=1), surface, clock=lambda: clock[0])
    start_roaming(director, traits("kai"), 40.0)
    assert director.roam and director.wander_s == 18.0
    chain = Chain(name="go", state=State.WORKING, priority=5, steps=[
        {"pose": "skate_roll", "duration_ms": 300, "move": {"type": "run", "dx": 700, "easing": "linear"}}])
    _finish(director, clock, chain)
    assert surface.x == 1300 and surface.home_x == 1300       # no walk back to 600


def test_others_still_walk_home():
    surface = Surface(x=600)
    clock = [0.0]
    director = Director(BehaviorEngine(seed=1), surface, clock=lambda: clock[0])
    start_roaming(director, traits("master"), 40.0)
    assert not director.roam and director.wander_s == 40.0
    chain = Chain(name="go", state=State.WORKING, priority=5, steps=[
        {"pose": "run_to_workspace", "duration_ms": 300, "move": {"type": "run", "dx": 300, "easing": "linear"}}])
    _finish(director, clock, chain)
    assert surface.home_x == 600 and abs(surface.x - 600) <= 1


def test_wandering_heads_for_the_open_side_of_the_desktop():
    surface = Surface(x=200)                                  # near the left edge of two screens
    director = Director(BehaviorEngine(seed=1), surface)
    director.roam = True
    rights = sum(director._wander_chain().steps[0]["move"]["dx"] > 0 for _ in range(40))
    assert rights >= 24                                       # mostly toward all that room


def test_travel_is_skating_with_ollies_and_kicker_launches():
    rng = random.Random(3)
    names = set()
    for kind in ("run", "dash", "hop", "walk"):
        for dx in (120, -450, 900):
            step = {"pose": "run_to_workspace", "duration_ms": 900,
                    "move": {"type": kind, "dx": dx, "easing": "linear"}}
            out = K.travel(step, rng)
            names.add(out["pose"])
            assert out["move"]["dx"] == int(dx * K.ROAM)       # further, same direction
    assert names == {"skate_roll", "ollie_gap", "kicker_air"}
    still = {"pose": "work", "duration_ms": 900, "move": None}
    assert K.travel(still, rng) is still                      # standing work is left alone
    assert arc_height({"pose": "kicker_air", "move": {"type": "run", "dx": 900}}) == ARC_BY_POSE["kicker_air"] > 100


def test_window_moves_draw_no_street_and_no_plaque():
    for move in ("bomb_drop", "edge_grind", "edge_sit"):
        fx = K.MOVES[move](0.4)["fx"]
        assert {"bare", "perch"} <= fx
    for move in ("skate_roll", "ollie_gap", "kicker_air"):
        fx = K.MOVES[move](0.4)["fx"]
        assert "bare" in fx and "perch" not in fx               # status still shows on the move
    assert K.status_text("kicker_air", "calm")[0] == "On the move"
    assert "kicker_here" in K.MOVES["kicker_air"](0.05)["fx"] and "kicker_here" not in K.MOVES["kicker_air"](0.5)["fx"]
    assert COMPANIONS["kai"]["perch_poses"]["drop"] == "bomb_drop"
