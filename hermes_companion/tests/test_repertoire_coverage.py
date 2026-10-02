"""The repertoire must be reachable, distinct, and complete.

Adding moves is only worth anything if a chain can ask for them and the art
can show them. These tests catch the two silent failures: a move type no chain
requests (drawn but unreachable), and a pose with no sprite row (the move plays
underneath an idle body, so nobody sees it).
"""

import pytest

from hermes_companion.behavior import behavior_rules as br
from hermes_companion.core.events import EventKind
from hermes_companion.movement import paths
from hermes_companion.renderer.petdex_overlay import POSE_ROW, STATE_ROWS

# Types the renderer knows how to draw - taken from the paths module so this
# cannot drift out of step with the code that actually computes the motion.
DRAWABLE = paths.ALL_TYPES


def _all_chains():
    """Every (kind, category-or-None) chain the engine can select."""
    for kind, spec in br.CHAINS.items():
        yield kind.name, None, spec
    for (kind, category), spec in br.CHAINS_BY_CATEGORY.items():
        yield kind.name, category, spec


def _steps():
    for kind, category, (_state, steps) in _all_chains():
        for step in steps:
            yield kind, category, step


def test_every_chain_step_has_a_pose_and_a_duration():
    for kind, category, step in _steps():
        assert step.get("pose"), f"{kind}/{category}: step with no pose"
        assert isinstance(step.get("duration_ms"), int), f"{kind}/{category}: bad duration"


def test_every_pose_used_by_a_chain_maps_to_a_sprite_row():
    """An unmapped pose renders as idle: invisible motion, the worst outcome."""
    offenders = sorted({s["pose"] for _k, _c, s in _steps() if s["pose"] not in POSE_ROW})
    assert not offenders, f"poses with no sprite row: {offenders}"


def test_every_mapped_row_exists_in_the_atlas_layout():
    stray = sorted(set(POSE_ROW.values()) - set(STATE_ROWS))
    assert not stray, f"poses mapped to rows that do not exist: {stray}"


def test_every_move_type_a_chain_requests_is_drawable():
    offenders = sorted({
        s["move"]["type"] for _k, _c, s in _steps()
        if s.get("move") and s["move"].get("type") not in DRAWABLE
    })
    assert not offenders, f"chains request undrawable move types: {offenders}"


def test_the_previously_unreachable_move_types_now_have_a_caller():
    """These six were drawable but no chain ever asked for them."""
    requested = {s["move"]["type"] for _k, _c, s in _steps() if s.get("move")}
    missing = sorted({"creep", "sprint", "hop", "shimmer", "pounce", "zigzag"} - requested)
    assert not missing, f"still unreachable: {missing}"


def test_every_tool_category_can_show_start_finish_and_failure():
    categories = set(br.CATEGORY_TOOL_STARTED) | set(br.CATEGORY_TOOL_FINISHED)
    for table, label in ((br.CATEGORY_TOOL_STARTED, "started"),
                         (br.CATEGORY_TOOL_FINISHED, "finished"),
                         (br.CATEGORY_TOOL_FAILED, "failed")):
        missing = sorted(categories - set(table))
        assert not missing, f"no {label} animation for: {missing}"


def test_categories_that_did_different_work_do_not_animate_identically():
    """Duplicate flavours hide real differences between tool categories."""
    def shape(spec):
        return tuple((s.get("pose"), (s.get("move") or {}).get("type")) for s in spec[1])

    for table, label in ((br.CATEGORY_TOOL_STARTED, "started"),
                         (br.CATEGORY_TOOL_FINISHED, "finished")):
        seen = {}
        dupes = []
        for category, spec in sorted(table.items()):
            key = shape(spec)
            if key in seen:
                dupes.append(f"{label}: {seen[key]} == {category}")
            seen[key] = category
        assert not dupes, "; ".join(dupes)


def test_idle_has_a_chain_and_it_claims_nothing():
    """Idle is the only event that evidences 'nothing is happening'."""
    assert EventKind.IDLE in br.CHAINS
    _state, steps = br.CHAINS[EventKind.IDLE]
    words = " ".join(str(s.get("pose")) for s in steps).lower()
    for claim in ("work", "finish", "done", "verify", "success", "celebrat"):
        assert claim not in words, f"idle must not claim '{claim}'"


@pytest.mark.parametrize("name", ["POUNCE", "ZIGZAG", "PACE"])
def test_new_primitives_are_real_motion(name):
    mv = getattr(br, name)
    assert paths.is_moving(mv["type"], mv["dx"], mv["dy"]), f"{name} would never animate"
