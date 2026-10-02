"""Per-pet sprite row order.

A sheet's rows are NOT a standard. v1 pets (the Alpha) and v2 pets (aeon-loom)
draw different animations on the same physical row, so the row that means
"jumping" on one is a crouch on the other. POSE_ROW maps a pose to a SEMANTIC
row name; this module maps that name onto the physical row for a given pet.

Because it is data (`rowmap.json` beside the spritesheet), a pet's author can
correct it without touching code. With no such file the v1 order is used, so
existing pets behave exactly as before.

Ordered by physical row: entry i is the name of the pet's row i.
"""

from __future__ import annotations

import json
from pathlib import Path

# The v1 order, and the fallback for every pet that does not declare one.
DEFAULT_ROW_ORDER: list[str] = [
    "idle", "running-right", "running-left", "waving", "jumping",
    "failed", "waiting", "running", "review",
]

ROWMAP_FILENAME = "rowmap.json"

# "idle" must always resolve: the renderer falls back to it for every unknown
# or missing row, so a map without it would break every pose at once.
REQUIRED_ROW = "idle"


def rowmap_path(spritesheet: str | Path) -> Path:
    """Path of the sidecar describing this sheet's rows."""
    return Path(spritesheet).with_name(ROWMAP_FILENAME)


def load_row_order(spritesheet: str | Path) -> list[str]:
    """Semantic row name per physical row, for this pet's sheet.

    Falls back to DEFAULT_ROW_ORDER whenever the sidecar is absent, unreadable,
    malformed, empty, not a list of strings, or missing the required "idle"
    row. Falling back is deliberate: a broken map must degrade to the known
    layout rather than crash the overlay or silently scramble every pose.
    """
    path = rowmap_path(spritesheet)
    if not path.is_file():
        return list(DEFAULT_ROW_ORDER)
    try:
        raw = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return list(DEFAULT_ROW_ORDER)

    order = raw.get("order") if isinstance(raw, dict) else raw
    if (not isinstance(order, list) or not order
            or not all(isinstance(name, str) and name for name in order)):
        return list(DEFAULT_ROW_ORDER)
    if REQUIRED_ROW not in order:
        return list(DEFAULT_ROW_ORDER)
    if len(set(order)) != len(order):
        # Duplicate names would collide in the frame table, silently dropping
        # whichever row lost the race.
        return list(DEFAULT_ROW_ORDER)
    return list(order)


def row_index(order: list[str], name: str) -> int | None:
    """Physical row for a semantic name, or None when this pet lacks it."""
    try:
        return order.index(name)
    except ValueError:
        return None