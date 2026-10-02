"""The movement repertoire: shape, endpoints, and no regression in the old moves.

The renderer used to compute motion inline, so the first job here is proving the
refactor is motion-identical for every pre-existing move type — `_old_offset()`
below is a verbatim copy of that former dispatch.
"""

import math

import pytest

from hermes_companion.movement import easing
from hermes_companion.movement.paths import net_offset, offset
from hermes_companion.movement.paths import IN_PLACE_TYPES, is_moving

TS = [i / 40 for i in range(41)]
LEGACY = ["", "dash", "run", "walk", "creep", "sprint", "hop", "leap", "tip", "bounce", "fly"]


def _old_offset(move_type, dx, dy, ease, t):
    """The renderer's former inline dispatch, copied so it can be compared."""
    if move_type in ("hop", "leap", "tip"):
        return dx * easing.apply(ease, t), dy * 4 * t * (1 - t)
    if move_type == "bounce":
        return dx, dy * abs(math.sin(t * math.pi * 2))
    if move_type == "fly":
        return dx, dy * easing.apply(ease, t)
    # The old default branch called _place(x) only, i.e. y never moved.
    return dx * easing.apply(ease, t), 0.0


@pytest.mark.parametrize("move_type", LEGACY + ["mystery"])
@pytest.mark.parametrize("ease", ["easeOutCubic", "easeInOutQuad", "bounce", "easeInQuad"])
@pytest.mark.parametrize("dx,dy", [(120, 0), (0, -40), (80, -60), (-150, 0)])
def test_legacy_motion_is_unchanged(move_type, ease, dx, dy):
    for t in TS:
        got = offset(move_type, dx, dy, ease, t)
        want = _old_offset(move_type, dx, dy, ease, t)
        assert got == pytest.approx(want, abs=1e-9), f"{move_type} at t={t}"


# `bounce` and `fly` are excluded here on purpose: both are legacy types that
# put x on the target from the very first frame (see the legacy comparison
# above, which pins that behaviour). Every other move starts where it stands.
@pytest.mark.parametrize("move_type", [m for m in LEGACY if m not in ("bounce", "fly")] + [
    "pounce", "orbit", "figure8", "zigzag", "hover", "overshoot", "anticipate",
    "pop", "shimmer"])
def test_every_move_starts_at_its_origin(move_type):
    assert offset(move_type, 100, -50, "easeOutCubic", 0.0) == pytest.approx((0.0, 0.0), abs=1e-9)


@pytest.mark.parametrize("move_type", ["bounce", "fly"])
def test_legacy_target_first_moves_start_on_the_target(move_type):
    assert offset(move_type, 100, -50, "easeOutCubic", 0.0)[0] == pytest.approx(100.0)


@pytest.mark.parametrize("move_type", [
    "pounce", "orbit", "figure8", "zigzag", "hover", "overshoot", "anticipate",
    "pop", "shimmer"])
def test_every_move_ends_where_the_beat_leaves_it(move_type):
    assert offset(move_type, 100, -50, "easeOutCubic", 1.0) == pytest.approx(
        net_offset(move_type, 100, -50), abs=1e-6)


@pytest.mark.parametrize("move_type", LEGACY)
def test_legacy_types_end_where_the_beat_leaves_them(move_type):
    """Legacy moves are only ever given dy=0; with dy they still snap to it."""
    assert offset(move_type, 100, 0, "easeOutCubic", 1.0) == pytest.approx(
        net_offset(move_type, 100, 0), abs=1e-6)


def test_legacy_horizontal_move_ignores_dy_in_flight_but_snaps_to_it():
    """Preserved quirk, documented so it is a decision rather than a surprise."""
    assert offset("dash", 100, -50, "easeOutCubic", 1.0) == pytest.approx((100.0, 0.0))
    assert net_offset("dash", 100, -50) == (100.0, -50.0)


# --- shape of the new moves -------------------------------------------------

def test_hop_rises_and_lands_back_on_the_baseline():
    ys = [offset("hop", 200, -60, "easeOutCubic", t)[1] for t in TS]
    assert ys[0] == 0.0 and ys[-1] == pytest.approx(0.0)
    assert min(ys) < -40, "should lift well off the baseline mid-flight"


def test_overshoot_passes_the_target_then_settles_onto_it():
    xs = [offset("overshoot", 100, 0, "easeOutCubic", t)[0] for t in TS]
    assert max(xs) > 105, "should sail past the target"
    assert xs[-1] == pytest.approx(100.0, abs=1e-6)
    assert max(xs) > xs[-1], "and come back to it"


def test_anticipate_winds_up_behind_the_start_first():
    xs = [offset("anticipate", 100, 0, "easeOutCubic", t)[0] for t in TS]
    assert min(xs) < -10, "should pull back before setting off"
    assert xs.index(min(xs)) < xs.index(max(xs)), "wind-up must precede the travel"
    assert xs[-1] == pytest.approx(100.0, abs=1e-6)


def test_zigzag_weaves_but_still_makes_progress():
    ys = [offset("zigzag", 200, -30, "easeOutCubic", t)[1] for t in TS]
    xs = [offset("zigzag", 200, -30, "easeOutCubic", t)[0] for t in TS]
    turns = sum(1 for a, b in zip(ys, ys[1:]) if (a > 0) != (b > 0) and b != 0)
    assert turns >= 4, f"expected a visible weave, got {turns} direction changes"
    assert max(abs(y) for y in ys) <= 30 + 1e-9
    assert ys[-1] == pytest.approx(0.0)
    assert xs == sorted(xs), "progress along the run should not reverse"


def test_orbit_traces_an_ellipse_and_returns_home():
    xs = [offset("orbit", 100, -40, "easeOutCubic", t)[0] for t in TS]
    ys = [offset("orbit", 100, -40, "easeOutCubic", t)[1] for t in TS]
    assert max(xs) == pytest.approx(100.0, abs=1e-6), "reaches the far side of the loop"
    assert min(xs) == pytest.approx(0.0, abs=1e-6), "and comes back to the origin"
    assert min(ys) < 0 < max(ys), "and passes above and below"
    assert net_offset("orbit", 100, -40) == (0.0, 0.0)
    assert offset("orbit", 100, -40, "easeOutCubic", 1.0) == pytest.approx((0.0, 0.0), abs=1e-6)


def test_figure8_flourishes_in_place():
    xs = [offset("figure8", 60, 0, "easeOutCubic", t)[0] for t in TS]
    ys = [offset("figure8", 60, 0, "easeOutCubic", t)[1] for t in TS]
    assert min(xs) < 0 < max(xs) and min(ys) < 0 < max(ys)
    assert max(abs(x) for x in xs) <= 60 + 1e-9
    assert net_offset("figure8", 60, 0) == (0.0, 0.0)


def test_hover_bobs_without_sinking_below_the_baseline():
    """dy is signed in screen space: negative rises, positive sinks."""
    up = [offset("hover", 100, -40, "easeOutCubic", t)[1] for t in TS]
    assert min(up) < -5, "should visibly rise"
    assert max(up) <= 1e-9, "and never drop below the baseline"
    assert up[-1] == pytest.approx(0.0)

    down = [offset("hover", 100, 40, "easeOutCubic", t)[1] for t in TS]
    assert min(down) >= -1e-9 and max(down) > 5
    assert down[-1] == pytest.approx(0.0)


def test_weaving_moves_borrow_a_height_when_given_none():
    assert offset("zigzag", 100, 0, "easeOutCubic", 0.25)[1] != 0.0
    assert offset("hover", 100, 0, "easeOutCubic", 0.25)[1] != 0.0


def test_unknown_move_type_falls_back_to_a_level_slide():
    assert offset("nonsense", 100, 0, "easeOutCubic", 0.5)[1] == 0.0


# --- in-place flourishes ----------------------------------------------------

def test_in_place_flourishes_move_with_no_displacement_at_all():
    """dx=dy=0 must not mean 'no animation' for shape-driven moves.

    The renderer used to skip every beat without a displacement, which made
    ORBIT and SHIMMER (declared with dx=0, dy=0) inert no-ops.
    """
    for move_type in ("orbit", "figure8", "hover", "zigzag", "shimmer", "pop"):
        assert is_moving(move_type, 0, 0), f"{move_type} should animate"
        ys = [offset(move_type, 0, 0, "easeInOutSine", t)[1] for t in TS]
        assert max(abs(y) for y in ys) > 1.0, f"{move_type} produced no motion"


def test_a_still_beat_is_still_still():
    assert is_moving("", 0, 0) is False
    assert is_moving("walk", 0, 0) is False
    assert is_moving("dash", 100, 0) is True


def test_unimplemented_types_are_not_claimed_as_moving():
    """fold/unfold are declared in behaviour_rules but have no path."""
    assert "fold" not in IN_PLACE_TYPES
    assert "unfold" not in IN_PLACE_TYPES


def test_pop_lifts_straight_up_and_lands():
    ys = [offset("pop", 0, -200, "bounce", t)[1] for t in TS]
    assert ys[0] == 0.0 and ys[-1] == pytest.approx(0.0)
    assert min(ys) < -150


def test_shimmer_vibrates_in_place():
    ys = [offset("shimmer", 0, 0, "easeOutQuad", t)[1] for t in TS]
    assert min(ys) < -1 and max(ys) > 1
    assert ys[-1] == pytest.approx(0.0)


# --- easing curves ----------------------------------------------------------

@pytest.mark.parametrize("name", sorted(easing.EASING))
def test_curves_span_the_unit_interval(name):
    f = easing.EASING[name]
    assert f(0.0) == pytest.approx(0.0, abs=1e-9)
    assert f(1.0) == pytest.approx(1.0, abs=1e-9)


def test_overshoot_curves_really_overshoot():
    assert max(easing.EASING["easeOutBack"](t) for t in TS) > 1.05
    assert max(easing.EASING["easeOutElastic"](t) for t in TS) > 1.05
    assert max(easing.EASING["easeInOutBack"](t) for t in TS) > 1.0


def test_wind_up_curves_really_pull_back():
    assert min(easing.EASING["easeInBack"](t) for t in TS) < -0.02


def test_apply_clamps_input_and_falls_back_on_unknown_names():
    assert easing.apply("easeOutCubic", -5.0) == 0.0
    assert easing.apply("easeOutCubic", 5.0) == 1.0
    assert easing.apply("no-such-curve", 0.5) == easing.apply("easeOutQuad", 0.5)
