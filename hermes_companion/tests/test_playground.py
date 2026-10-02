"""The no-Hermes playground: demo Hermes always outranks curiosity."""
from hermes_companion.animation.director import Director
from hermes_companion.core.curiosity import Observation, Seen
from hermes_companion.renderer.playground import (
    CURIOSITY_PRIORITY, DEMO_SESSION, PlaygroundBrain,
)


class Surface:
    x, w, h, home_x, home_y = 500, 200, 200, 500, 800

    def __init__(self):
        self.poses = []

    def set_pose(self, pose, progress=0.0):
        self.poses.append(pose)

    def set_x(self, x):
        self.x = x

    def set_state(self, state):
        pass


class Sensors:
    def __init__(self):
        self.queue = []

    def sample(self, now=None):
        out, self.queue = self.queue, []
        return out


def _brain(demo=True):
    clock = [0.0]
    surface, sensors = Surface(), Sensors()
    brain = PlaygroundBrain(None, surface, sensors=sensors, seed=1, demo=demo,
                            log=lambda *_: None)
    director = Director(brain.engine, surface, clock=lambda: clock[0])
    brain.bind(director)
    return brain, director, sensors, clock


def test_curiosity_plays_when_nothing_else_is():
    brain, director, sensors, _ = _brain(demo=False)
    sensors.queue = [Observation(Seen.USER_BACK, 1.0)]
    brain.tick(1.0)
    assert director.chain is not None and director.chain.name == "curious:user.back"
    assert director.chain.priority == CURIOSITY_PRIORITY


def test_hermes_interrupts_curiosity_and_curiosity_waits():
    brain, director, sensors, clock = _brain()
    sensors.queue = [Observation(Seen.USER_BACK, 1.0)]
    brain.tick(1.0)
    assert director.chain.name.startswith("curious:")
    first_event_at = DEMO_SESSION[0][0]
    clock[0] = first_event_at
    brain.tick(first_event_at)
    director.step(5.0)   # let the current atomic step finish
    clock[0] += 5.0
    director.step(0.1)
    assert not director.chain.name.startswith("curious:")
    # While Hermes's chain plays, nothing curious may start.
    sensors.queue = [Observation(Seen.CURSOR_CIRCLING, clock[0], 1, 1)]
    brain.tick(clock[0])
    assert not director.chain.name.startswith("curious:")


def test_demo_session_loops():
    brain, director, _sensors, _ = _brain()
    seen = []
    brain.log = seen.append
    for t in range(0, 200):
        brain.tick(float(t))
        director.chain = None
    assert sum("task.complete" in s for s in seen) == 2
