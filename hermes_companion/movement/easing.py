"""Easing curves (spec §10). All take t in [0,1], return eased t."""
from __future__ import annotations

import math


def ease_in_quad(t: float) -> float:
    return t * t


def ease_out_quad(t: float) -> float:
    return t * (2 - t)


def ease_in_out_cubic(t: float) -> float:
    return 4 * t * t * t if t < 0.5 else 1 - ((-2 * t + 2) ** 3) / 2


def ease_out_cubic(t: float) -> float:
    return 1 - (1 - t) ** 3


def ease_in_out_quad(t: float) -> float:
    return 2 * t * t if t < 0.5 else 1 - ((-2 * t + 2) ** 2) / 2


def bounce(t: float) -> float:
    n1, d1 = 7.5625, 2.75
    if t < 1 / d1:
        return n1 * t * t
    if t < 2 / d1:
        t -= 1.5 / d1
        return n1 * t * t + 0.75
    if t < 2.5 / d1:
        t -= 2.25 / d1
        return n1 * t * t + 0.9375
    t -= 2.625 / d1
    return n1 * t * t + 0.984375


def ease_in_cubic(t: float) -> float:
    return t * t * t


def ease_in_out_sine(t: float) -> float:
    return -(math.cos(math.pi * t) - 1) / 2


def ease_out_expo(t: float) -> float:
    return 1.0 if t >= 1 else 1 - 2 ** (-10 * t)


def ease_in_back(t: float) -> float:
    """Anticipation: pulls behind the start before setting off."""
    c1 = 1.70158
    return (c1 + 1) * t * t * t - c1 * t * t


def ease_out_back(t: float) -> float:
    """Follow-through: sails past the target, then settles onto it.

    Deliberately exceeds 1 part-way through, which is what makes a move read
    as having weight instead of sliding to a stop.
    """
    c1 = 1.70158
    return 1 + (c1 + 1) * (t - 1) ** 3 + c1 * (t - 1) ** 2


def ease_in_out_back(t: float) -> float:
    c2 = 1.70158 * 1.525
    if t < 0.5:
        return ((2 * t) ** 2 * ((c2 + 1) * 2 * t - c2)) / 2
    return (((2 * t - 2) ** 2 * ((c2 + 1) * (2 * t - 2) + c2)) + 2) / 2


def ease_out_elastic(t: float) -> float:
    """Springy settle: overshoots and rings down, for delighted reactions."""
    if t <= 0:
        return 0.0
    if t >= 1:
        return 1.0
    c4 = (2 * math.pi) / 3
    return 2 ** (-10 * t) * math.sin((t * 10 - 0.75) * c4) + 1


def teleport(t: float) -> float:
    """Stay put, then be there: the jump happens at the halfway point."""
    return 0.0 if t < 0.5 else 1.0


EASING = {
    "teleport": teleport,
    "easeInQuad": ease_in_quad,
    "easeOutQuad": ease_out_quad,
    "easeInOutCubic": ease_in_out_cubic,
    "easeOutCubic": ease_out_cubic,
    "easeInOutQuad": ease_in_out_quad,
    "easeInCubic": ease_in_cubic,
    "easeOutExpo": ease_out_expo,
    "easeInOutSine": ease_in_out_sine,
    "easeInBack": ease_in_back,
    "easeOutBack": ease_out_back,
    "easeInOutBack": ease_in_out_back,
    "easeOutElastic": ease_out_elastic,
    "bounce": bounce,
}


def apply(easing_name: str, t: float) -> float:
    return EASING.get(easing_name, ease_out_quad)(max(0.0, min(1.0, t)))
