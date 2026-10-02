"""Where a moving beat actually puts the sprite (spec §10).

This used to be computed inline in the renderer, so a move type was either a
hardcoded special case or a plain eased slide. Holding it here makes the whole
repertoire pure and testable, and lets behaviour chains reach for expressive
motion without touching the renderer.

Convention
----------
`offset()` is where the sprite sits at progress `t`, relative to the beat's
start (so it begins at (0, 0)).
`net_offset()` is where the beat LEAVES the sprite. Everything that arcs,
weaves, hovers, orbits or figure-eights returns to its baseline, so its net
vertical move is zero even though it travelled a long way getting there.

The pre-existing types reproduce the old inline formulas exactly; the tests
pin that against a copy of the old implementation.
"""

from __future__ import annotations

import math

from .easing import apply as ease_apply

# Types that lift off the baseline and come back down to it.
ARC_TYPES = ("hop", "leap", "tip", "pounce")

# Types that return to the exact spot they started from.
LOOP_TYPES = ("orbit", "figure8")

# Types that travel horizontally and end level with the baseline.
LEVEL_TYPES = ("hop", "leap", "tip", "pounce", "bounce", "zigzag", "hover",
               "pop", "shimmer", "drift")

# Types that keep moving even with dx=0 and dy=0, because their motion comes
# from the shape of the path rather than from a displacement. Without this the
# renderer's `if move_dx or move_dy` guard skips them entirely, which made
# ORBIT / FOLD / UNFOLD / SHIMMER inert no-ops.
IN_PLACE_TYPES = LOOP_TYPES + ("hover", "zigzag", "shimmer", "pop")

# NOTE: "fold" and "unfold" are declared in behaviour_rules but have no path
# implementation, so they are deliberately NOT listed above — claiming them
# would promise motion that never happens. They stay inert until defined.

# Every move type offset() actually understands. Chains and the renderer are
# checked against this, so a chain cannot request motion that never happens -
# "drift" was requested by a primitive while being no such path, and quietly
# degraded into a plain walk.
ALL_TYPES = tuple(sorted(
    set(ARC_TYPES) | set(LEVEL_TYPES) | set(LOOP_TYPES) | set(IN_PLACE_TYPES)
    | {"dash", "run", "walk", "creep", "sprint", "fly", "bounce",
       "overshoot", "anticipate"}
))

# Vertical lift used when a weaving or looping move carries no height of its own.
WEAVE_RATIO = 0.35
MIN_WEAVE = 28.0

# How far a wind-up pulls back behind the start, as a fraction of the distance.
ANTICIPATION_FRACTION = 0.15
ANTICIPATION_TIME = 0.25


def lift(dx: float, dy: float) -> float:
    """Vertical amplitude for a move that has no explicit height."""
    if dy:
        return float(dy)
    return max(MIN_WEAVE, abs(float(dx)) * WEAVE_RATIO)


def is_moving(move_type: str, dx: float, dy: float) -> bool:
    """Whether this beat animates at all.

    A displacement is the usual reason to move, but in-place flourishes move
    without one, so the caller must not decide purely on dx/dy.
    """
    return bool(dx or dy) or (move_type or "") in IN_PLACE_TYPES


def offset(move_type: str, dx: float, dy: float, ease: str, t: float) -> tuple[float, float]:
    """Sprite position at progress `t` in [0, 1], relative to the beat's start."""
    t = 0.0 if t < 0 else 1.0 if t > 1 else float(t)
    eased = ease_apply(ease, t)
    mt = move_type or ""

    if mt in ARC_TYPES:
        # Up and back down over the run, so the travel reads as a jump.
        return dx * eased, dy * 4 * t * (1 - t)

    if mt == "bounce":
        # Flat-out horizontal travel with a hard repeating bounce.
        return dx, dy * abs(math.sin(t * math.pi * 2))

    if mt == "fly":
        # Straight flight: no return, vertical eased all the way.
        return dx, dy * eased

    if mt == "orbit":
        # One full ellipse, leaving and returning to the origin.
        return (dx / 2) * (1 - math.cos(2 * math.pi * t)), lift(dx, dy) * math.sin(2 * math.pi * t)

    if mt == "figure8":
        # A flourish in place: two lateral passes, half the height each time.
        a = lift(dx, dy)
        return a * math.sin(2 * math.pi * t), (a / 2) * math.sin(4 * math.pi * t)

    if mt == "zigzag":
        # Scampering: makes progress while weaving, ending level. sin(6*pi) = 0.
        return dx * eased, lift(dx, dy) * math.sin(t * math.pi * 6)

    if mt == "hover":
        # Bobbing in place or on the way: two gentle rises, ending level.
        return dx * eased, lift(dx, dy) * (1 - math.cos(4 * math.pi * t)) / 2

    if mt == "pop":
        # A straight up-and-down startle: no travel, just lift and land. Uses
        # lift() rather than raw dy so a bar-0 pop still lands a visible hop.
        return dx * eased, lift(dx, dy) * 4 * t * (1 - t)

    if mt == "shimmer":
        # A fast, small vibration: energy with no displacement at all.
        return dx * eased, lift(dx, dy) * 0.25 * math.sin(t * math.pi * 8)

    if mt == "drift":
        # A slow glide carrying the faintest bob, so travel reads as floating.
        return dx * eased, lift(dx, dy) * 0.15 * math.sin(2 * math.pi * t)

    if mt == "overshoot":
        # Follow-through: passes the target, then settles onto it.
        return dx * ease_apply("easeOutBack", t), dy * eased

    if mt == "anticipate":
        # Wind-up first (behind the start), then travel. Deliberately ignores
        # the beat's ease: the shape is the point of the move.
        back = -abs(dx) * ANTICIPATION_FRACTION
        if t < ANTICIPATION_TIME:
            return back * (t / ANTICIPATION_TIME), dy * eased
        u = (t - ANTICIPATION_TIME) / (1 - ANTICIPATION_TIME)
        return back + (dx - back) * ease_apply("easeOutCubic", u), dy * eased

    # dash / run / walk / creep / sprint / "" and anything unrecognised keep the
    # original behaviour: a plain eased horizontal slide that never touches y.
    return dx * eased, 0.0


def net_offset(move_type: str, dx: float, dy: float) -> tuple[float, float]:
    """Where the beat leaves the sprite, relative to where it started."""
    mt = move_type or ""
    if mt in LOOP_TYPES:
        return 0.0, 0.0
    if mt in LEVEL_TYPES:
        return float(dx), 0.0
    return float(dx), float(dy)