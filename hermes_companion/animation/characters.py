"""Companion registry — the set of pet characters the engine can render.

Each companion is a procedural renderer with the same Canvas contract
`(canvas, pose, progress, **kw)`. The round pet (`animator.draw_pet`) is the
original; the samurai (`samurai.draw_samurai`) is the first new companion, a
tall/lanky ronin with two swords, a yellow accent, changeable material
palettes, and FIXED traditional kasa hat + geta shoes.
The astro boy (`astro_boy.draw_astro`) is a sleek black character
with LED eyes, chrome limbs, and futuristic HUD elements.

Adding a companion = one entry here + a draw function that honors
`pose_params` (so the whole behavior-engine movement vocabulary works).
"""
from __future__ import annotations

from hermes_companion.animation import animator, astro_boy, herald, samurai

# name -> (draw_fn, default_palette, palette_names, description)
COMPANIONS: dict[str, dict] = {
    "pet": {
        "draw": lambda canvas, pose, progress=0.0, **kw: animator.draw_pet(
            canvas, pose, progress),
        "palettes": [],
        "default": None,
        "desc": "the original round pet",
    },
    "samurai": {
        "draw": samurai.draw_samurai,
        "palettes": list(samurai.SAMURAI_PALETTES.keys()),
        "default": samurai.SAMURAI_DEFAULT_PALETTE,
        "desc": "tall lanky ronin · two swords · yellow accent · "
                "changeable materials · fixed kasa hat + geta shoes",
    },
    "astro": {
        "draw": astro_boy.draw_astro,
        "palettes": list(astro_boy.ASTRO_PALETTES.keys()),
        "default": astro_boy.ASTRO_DEFAULT_PALETTE,
        "desc": "black astro boy · LED eyes · chrome limbs · "
                "HUD visor · changeable accent colors · "
                "crimson | arctic | neon | plasma | mono | void",
    },
    "herald": {
        "draw": herald.draw_herald,
        "palettes": list(herald.HERALD_PALETTES.keys()),
        "default": herald.HERALD_DEFAULT_PALETTE,
        "desc": "winged messenger · mood aura + glowing staff orb · "
                "flapping helmet/sandal wings · streaming scarf · "
                "curiosity marks · olympus | midnight | ember | verdant | nebula",
    },
}

DEFAULT_COMPANION = "astro"


def list_companions() -> list[str]:
    return list(COMPANIONS.keys())


def get_companion(name: str | None) -> dict:
    if not name:
        name = DEFAULT_COMPANION
    if name not in COMPANIONS:
        raise KeyError(
            f"unknown companion '{name}' — known: {', '.join(COMPANIONS)}")
    return COMPANIONS[name]


def draw_companion(canvas, companion: str | None, pose: str,
                   progress: float = 0.0, palette: str | None = None) -> None:
    """Dispatch a pose to the named companion's renderer."""
    spec = get_companion(companion)
    spec["draw"](canvas, pose, progress, palette=palette)
