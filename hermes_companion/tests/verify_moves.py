"""Headless behavior/move verification; never creates windows or PNGs."""
from __future__ import annotations

from collections.abc import Iterable

from hermes_companion.animation import animator as A
from hermes_companion.animation.animator import pose_params
from hermes_companion.behavior.behavior_engine import BehaviorEngine
from hermes_companion.behavior.behavior_rules import (
    CATEGORY_TOOL_FAILED,
    CATEGORY_TOOL_FINISHED,
    CATEGORY_TOOL_STARTED,
    CHAINS,
    CHAINS_BY_CATEGORY,
    EMOTIONAL_ARCS,
    IDLE_PROGRESSION,
)
from hermes_companion.core.events import EventKind, SemanticEvent, classify_tool
from hermes_companion.core.state import State
from hermes_companion.renderer.petdex_overlay import POSE_PROP, POSE_ROW, STATE_ROWS


CATEGORY_FAMILIES = (
    (EventKind.TOOL_STARTED, CATEGORY_TOOL_STARTED),
    (EventKind.TOOL_FINISHED, CATEGORY_TOOL_FINISHED),
    (EventKind.TOOL_FAILED, CATEGORY_TOOL_FAILED),
)


class _HeadlessCanvas:
    """Minimal tkinter Canvas protocol used by ``draw_extra``."""

    def __init__(self) -> None:
        self.items = 0

    def __getattr__(self, name: str):
        if not name.startswith("create_"):
            raise AttributeError(name)

        def create(*_args, **_kwargs) -> int:
            self.items += 1
            return self.items

        return create


def _reachable_poses() -> set[str]:
    poses = {step["pose"] for _state, steps in CHAINS.values() for step in steps}
    for _kind, specs in CATEGORY_FAMILIES:
        poses.update(step["pose"] for _state, steps in specs.values() for step in steps)
    poses.update(pose for _threshold, pose, _duration in IDLE_PROGRESSION)

    # Combo shaping adds poses dynamically, so exercise every tier rather than
    # assuming the static chain dictionaries contain the complete vocabulary.
    for tier in range(1, 5):
        engine = BehaviorEngine(seed=100 + tier)
        for _ in range(tier - 1):
            engine.handle(SemanticEvent(kind=EventKind.APPROVAL_REQUIRED))
        for kind in CHAINS:
            chain = engine.handle(SemanticEvent(kind=kind, category="bogus"))
            if chain:
                poses.update(chain.poses)
            engine.end_chain()
    return poses


def run_checks() -> list[tuple[str, bool]]:
    checks: list[tuple[str, bool]] = []

    # Iterate the actual generic dictionary.  The previous ``for cat in ("")``
    # loop iterated zero times and silently skipped every generic chain.
    generic_bad: list[str] = []
    for kind, (_state, steps) in CHAINS.items():
        engine = BehaviorEngine(seed=7)
        chain = engine.handle(SemanticEvent(kind=kind, category="bogus"))
        expected = [step["pose"] for step in steps]
        if chain is None or chain.poses != expected:
            generic_bad.append(kind.value)
    checks.append((f"all {len(CHAINS)} generic chains resolve ({generic_bad=})", not generic_bad))

    expected_index = {
        (kind, category): spec
        for kind, specs in CATEGORY_FAMILIES
        for category, spec in specs.items()
    }
    checks.append(("category index uses final definitions", CHAINS_BY_CATEGORY == expected_index))

    category_bad: list[str] = []
    for kind, specs in CATEGORY_FAMILIES:
        for category, (_state, steps) in specs.items():
            chain = BehaviorEngine(seed=11).handle(
                SemanticEvent(kind=kind, category=category)
            )
            expected = [step["pose"] for step in steps]
            if chain is None or chain.poses != expected:
                category_bad.append(f"{kind.value}:{category}")
    checks.append((f"all {len(expected_index)} category chains resolve ({category_bad=})", not category_bad))

    poses = _reachable_poses()
    missing_rows = sorted(poses - set(POSE_ROW))
    invalid_rows = sorted(
        f"{pose}:{row}" for pose, row in POSE_ROW.items() if row not in STATE_ROWS
    )
    checks.append((f"all {len(poses)} reachable poses map to valid atlas rows "
                   f"({missing_rows=}, {invalid_rows=})",
                   not missing_rows and not invalid_rows))

    animator_bad: list[str] = []
    for pose in sorted(poses):
        try:
            pose_params(pose, 0.5)
        except Exception as exc:  # pragma: no cover - diagnostic detail
            animator_bad.append(f"{pose}: {exc}")
    checks.append((f"reachable poses are accepted by animator ({animator_bad=})", not animator_bad))

    idle_poses = [pose for _threshold, pose, _duration in IDLE_PROGRESSION]
    thresholds = [threshold for threshold, _pose, _duration in IDLE_PROGRESSION]
    idle_shape_ok = (
        thresholds == sorted(set(thresholds))
        and IDLE_PROGRESSION[-1] == (300.0, "sleep", 0)
        and not (set(idle_poses) & set(EMOTIONAL_ARCS))
        and set(idle_poses) <= set(POSE_ROW)
    )
    checks.append(("idle progression is concrete, ordered, mapped, and ends at 300s sleep",
                   idle_shape_ok))

    engine = BehaviorEngine(seed=13)
    elapsed = 0.0
    emitted: list[tuple[float, str | None]] = []
    for threshold, pose, _duration in IDLE_PROGRESSION:
        before = max(0.0, threshold - elapsed - 0.1)
        if before:
            engine.idle_tick(before)
            elapsed += before
        emitted.append((threshold, engine.idle_tick(threshold - elapsed)))
        elapsed = threshold
    timing_ok = (
        emitted == [(threshold, pose) for threshold, pose, _duration in IDLE_PROGRESSION]
        and engine.state == State.SLEEPING
        and engine.idle_tick(60.0) is None
    )
    checks.append((f"idle emissions match declared thresholds ({emitted=})", timing_ok))

    all_specs = list(CHAINS.values()) + [
        spec for _kind, specs in CATEGORY_FAMILIES for spec in specs.values()
    ]
    vertical = {
        step["move"]["type"]
        for _state, steps in all_specs
        for step in steps
        if step.get("move") and step["move"].get("dy", 0) != 0
    }
    checks.append((f"vertical move types are reachable ({sorted(vertical)})",
                   {"hop", "leap", "bounce", "tip", "fly"} <= vertical))

    dead_props: list[str] = []
    for pose, prop in sorted(POSE_PROP.items()):
        canvas = _HeadlessCanvas()
        try:
            A.draw_extra(canvas, prop, 0.3, 100, 150, s=1.0)
        except Exception as exc:  # pragma: no cover - diagnostic detail
            dead_props.append(f"{pose}:{prop} ({exc})")
    checks.append((f"all {len(POSE_PROP)} props draw headlessly ({dead_props=})", not dead_props))

    tool_expectations = [
        ("image_generate", "design"), ("text_to_speech", "audio"),
        ("cronjob", "scheduling"), ("skill_view", "learning"),
        ("computer_use", "desktop"), ("browser_exec", "browser"),
        ("open_preview", "browser"), ("read_preview", "browser"),
        ("docx", "docs"), ("pdf", "docs"), ("xlsx", "sheets"),
        ("excel_openpyxl", "sheets"), ("email", "communication"),
        ("teams", "communication"), ("maps", "maps"),
        ("terminal", "terminal"),
    ]
    bad_classifications = [
        f"{tool}:{classify_tool(tool)}!={expected}"
        for tool, expected in tool_expectations
        if classify_tool(tool) != expected
    ]
    checks.append((f"tool classifications are correct ({bad_classifications=})",
                   not bad_classifications))
    return checks


def main(checks: Iterable[tuple[str, bool]] | None = None) -> int:
    results = list(run_checks() if checks is None else checks)
    for name, passed in results:
        print(f"[{'PASS' if passed else 'FAIL'}] {name}")
    failures = sum(not passed for _name, passed in results)
    print(f"RESULT: {len(results) - failures}/{len(results)} checks passed")
    return 1 if failures else 0


if __name__ == "__main__":
    raise SystemExit(main())
