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

from hermes_companion.animation import animator, astro_boy, herald, nia, nyamekra, samurai

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
    "nia": {
        "draw": nia.draw_nia,
        "palettes": list(nia.NIA_PALETTES.keys()),
        "default": nia.NIA_DEFAULT_PALETTE,
        "extra_flourishes": nia.nia_flourishes(),
        "desc": "Afrocentric storyteller · afro, locs or headwrap · kente-inspired "
                "sash · beaded collar · mudcloth wrap · talking drum · "
                f"{len(nia.NIA_MOVES)} extra dance and storytelling moves · "
                "kente | indigo | ochre | emerald | royal",
    },
    "nyamekra": {
        "draw": nyamekra.draw_nyamekra,
        "palettes": list(nyamekra.NYAMEKRA_PALETTES.keys()),
        "default": nyamekra.NYAMEKRA_DEFAULT_PALETTE,
        "extra_flourishes": nyamekra.nyamekra_flourishes(),
        "flourish_hints": nyamekra.flourish_hints(),
        "curious_moves": nyamekra.CURIOUS_MOVES,
        "voice": nyamekra.VOICE,
        "greeting": nyamekra.GREETING,
        "desc": "the All-Doing Crow · one form · celestial halo · galaxy eyes · "
                "gold crown, ankh and neck rings · kente-woven feathered robe · "
                f"{len(nyamekra.NYAMEKRA_MOVES)} own moves channelling the ten "
                "Symbols of Essence",
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


def extra_flourishes(name: str | None) -> dict[str, tuple[str, ...]]:
    """A companion's own body-language moves, by mood (empty for most)."""
    if not name or name not in COMPANIONS:
        return {}
    return dict(COMPANIONS[name].get("extra_flourishes", {}))


def traits(name: str | None) -> dict:
    """Everything a companion brings beyond its drawing (all optional)."""
    spec = COMPANIONS.get(name or "", {})
    return {"extra_flourishes": dict(spec.get("extra_flourishes", {})),
            "flourish_hints": dict(spec.get("flourish_hints", {})),
            "curious_moves": tuple(spec.get("curious_moves", ())),
            "voice": dict(spec.get("voice", {})),
            "greeting": spec.get("greeting")}


def draw_companion(canvas, companion: str | None, pose: str,
                   progress: float = 0.0, palette: str | None = None) -> None:
    """Dispatch a pose to the named companion's renderer."""
    spec = get_companion(companion)
    spec["draw"](canvas, pose, progress, palette=palette)
