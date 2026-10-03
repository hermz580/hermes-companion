"""``hermes-companion play``: see the companion without installing Hermes.

A procedural character (samurai or astro) runs on the desktop with
curiosity and move variety on, while a scripted Hermes session loops in the
background so both halves are visible: Hermes's work (always wins) and the
pet noticing what you do (fills the gaps).

``PlaygroundBrain`` holds all the decisions and has no GUI, so it is tested
directly; ``run_playground`` only wires it to a window.
"""
from __future__ import annotations

import time

from hermes_companion.behavior.behavior_engine import BehaviorEngine, Chain
from hermes_companion.behavior.perch import PerchDriver
from hermes_companion.core.attention import AttentionModel
from hermes_companion.core.curiosity import CuriosityModel, Reaction
from hermes_companion.core.events import EventKind, SemanticEvent, classify_tool
from hermes_companion.core.state import State

CURIOSITY_PRIORITY = 9   # lower number wins; every Hermes chain outranks this

# (seconds into the loop, event, tool). Spaced out so curiosity gets turns.
DEMO_SESSION: tuple[tuple[float, str, str], ...] = (
    (4.0, "agent.started", ""),
    (6.0, "tool.started", "terminal"),
    (11.0, "tool.finished", "terminal"),
    (18.0, "tool.started", "web_search"),
    (23.0, "tool.failed", "web_search"),
    (28.0, "tool.started", "read_file"),
    (32.0, "tool.finished", "read_file"),
    (38.0, "approval.required", ""),
    (44.0, "approval.approved", ""),
    (46.0, "tool.started", "github"),
    (52.0, "tool.finished", "github"),
    (55.0, "task.complete", ""),
    (58.0, "agent.idle", ""),
)
DEMO_LOOP_S = 90.0


def reaction_chain(reaction: Reaction, current_x: int, width: int) -> Chain:
    steps: list[dict] = []
    if reaction.target is not None:
        dx = max(-400, min(400, reaction.target[0] - width // 2 - current_x))
        if abs(dx) > 40:
            steps.append({"pose": "walk_to_workspace", "duration_ms": 700,
                          "move": {"type": "walk", "dx": dx, "dy": 0,
                                   "duration_ms": 700, "easing": "easeInOutQuad"}})
    steps.extend(dict(s) for s in reaction.steps)
    return Chain(name=f"curious:{reaction.kind.value}", state=State.CURIOUS,
                 priority=CURIOSITY_PRIORITY, steps=steps)


class PlaygroundBrain:
    def __init__(self, director, surface, *, sensors=None, seed: int = 7,
                 variety: bool = True, demo: bool = True, start: float = 0.0,
                 perch: bool = False, log=print) -> None:
        from hermes_companion.animation.characters import extra_flourishes
        self.engine = BehaviorEngine(
            seed=seed, variety=variety,
            extra_flourishes=extra_flourishes(getattr(surface, "companion", None)))
        self.director = director
        self.surface = surface
        self.attention = AttentionModel()
        self.curiosity = CuriosityModel(seed=seed)
        self.sensors = sensors
        self.demo = demo
        self.start = start
        self._next = 0
        self._loop = 0
        self.log = log
        self.want_perch = perch
        self.perch: PerchDriver | None = None

    def bind(self, director) -> None:
        self.director = director
        if self.want_perch and self.sensors is not None and hasattr(self.surface, "set_y"):
            self.perch = PerchDriver(self.surface, director, self.sensors, log=self.log)

    def _hermes(self, now: float) -> None:
        if not self.demo:
            return
        t = now - self.start - self._loop * DEMO_LOOP_S
        if t >= DEMO_LOOP_S:
            self._loop += 1
            self._next = 0
            return
        while self._next < len(DEMO_SESSION) and DEMO_SESSION[self._next][0] <= t:
            _at, kind, tool = DEMO_SESSION[self._next]
            self._next += 1
            ev = SemanticEvent(EventKind(kind), tool=tool, category=classify_tool(tool))
            signal = self.attention.ingest(ev)
            chain = self.engine.handle(ev)
            self.log(f"HERMES {kind} {tool} -> {signal.label}")
            if chain is not None:
                self.director.start_chain(chain)

    def _curious(self, now: float) -> None:
        if self.sensors is None:
            return
        try:
            observations = self.sensors.sample(now)
        except Exception:
            return
        for obs in observations:
            reaction = self.curiosity.observe(obs, self.attention.signal.state)
            if reaction is None or self.director.chain is not None:
                continue   # never talk over a chain that is already playing
            if self.perch is not None and (self.perch.perched or self.perch.motion):
                reaction.target = None   # don't walk off the edge of a title bar
            chain = reaction_chain(reaction, int(self.surface.x), int(self.surface.w))
            self.log(f"CURIOUS {obs.kind.value} {chain.poses}")
            self.director.start_chain(chain)
            return

    def tick(self, now: float) -> None:
        self._hermes(now)
        self._curious(now)
        if self.perch is not None:
            self.perch.tick(now, self.attention.signal.state)


def run_playground(companion: str = "herald", notice: str = "full",
                   palette: str | None = None,
                   seed: int = 7, variety: bool = True, demo: bool = True,
                   render: str = "smooth", perch: bool = True) -> int:
    from hermes_companion.animation.director import Director
    from hermes_companion.renderer.desktop_sensors import DesktopSensors
    from hermes_companion.renderer.overlay import ProceduralLiveOverlay

    if render == "smooth":
        from hermes_companion.renderer.layered import SmoothLiveOverlay
        overlay = SmoothLiveOverlay(companion=companion, palette=palette)
        print(f"render: smooth ({overlay.mode})", flush=True)
    else:
        overlay = ProceduralLiveOverlay(companion=companion, palette=palette)
    sensors = DesktopSensors.for_platform(
        notice, pet_box=lambda: (overlay.x, overlay.home_y,
                                 overlay.x + overlay.w, overlay.home_y + overlay.h))
    if sensors is None and notice != "off":
        print("curiosity unavailable on this platform (needs Windows)", flush=True)
    brain = PlaygroundBrain(None, overlay, sensors=sensors, seed=seed,
                            variety=variety, demo=demo, start=time.monotonic(),
                            perch=perch)
    overlay._director = Director(brain.engine, overlay)
    brain.bind(overlay._director)

    def poll() -> None:
        brain.tick(time.monotonic())
        overlay.root.after(33, poll)    # 30 Hz so hops and drops look smooth

    def ready() -> None:
        print(f"PLAY READY companion={companion} notice={notice} "
              f"demo={'on' if demo else 'off'}  (Ctrl+C here to quit)", flush=True)
        overlay.root.after(100, poll)

    overlay.on_ready = ready
    try:
        overlay.run()
    except KeyboardInterrupt:
        overlay.close()
    return 0
