"""Row order is per-pet data, and a broken map must never scramble the sprite.

The failure this guards against is silent: if the map is wrong, poses still
render - just as the wrong animation. So the loader falls back to the v1 order
on anything it cannot trust, and these tests pin that.
"""

import json
import os
from pathlib import Path

import pytest

from hermes_companion.renderer.pet_rows import (
    DEFAULT_ROW_ORDER,
    REQUIRED_ROW,
    load_row_order,
    row_index,
    rowmap_path,
)


@pytest.fixture
def sheet(tmp_path: Path) -> Path:
    """A stand-in spritesheet path; only its name is used to find the sidecar."""
    path = tmp_path / "spritesheet.webp"
    path.write_bytes(b"not really an image")
    return path


def _write_map(sheet: Path, payload) -> None:
    text = payload if isinstance(payload, str) else json.dumps(payload)
    rowmap_path(sheet).write_text(text, encoding="utf-8")


def test_no_sidecar_uses_the_v1_order(sheet: Path):
    assert load_row_order(sheet) == DEFAULT_ROW_ORDER


def test_sidecar_with_an_order_list_is_honoured(sheet: Path):
    order = ["idle", "waving", "failed", "review", "waiting"]
    _write_map(sheet, {"order": order})
    assert load_row_order(sheet) == order


def test_bare_list_sidecar_is_honoured(sheet: Path):
    order = ["idle", "review"]
    _write_map(sheet, order)
    assert load_row_order(sheet) == order


@pytest.mark.parametrize("payload, why", [
    ("{not json", "unparseable"),
    ({"order": "idle"}, "order is not a list"),
    ({"order": []}, "empty order"),
    ({"order": ["idle", 7]}, "non-string entry"),
    ({"order": ["", "idle"]}, "blank entry"),
    ({"order": ["running-left", "running-right"]}, "no idle row"),
    ({"order": ["idle", "idle"]}, "duplicate names collide"),
    ({"nothing": "useful"}, "no order key"),
])
def test_untrustworthy_maps_fall_back_to_the_v1_order(sheet: Path, payload, why):
    _write_map(sheet, payload)
    assert load_row_order(sheet) == DEFAULT_ROW_ORDER, why


def test_a_missing_or_unreadable_sidecar_never_raises(sheet: Path, monkeypatch):
    _write_map(sheet, {"order": ["idle"]})

    def boom(*_a, **_k):
        raise OSError("drive went away")

    monkeypatch.setattr(Path, "read_text", boom)
    assert load_row_order(sheet) == DEFAULT_ROW_ORDER


def test_the_default_order_always_contains_the_required_row():
    assert REQUIRED_ROW in DEFAULT_ROW_ORDER
    assert DEFAULT_ROW_ORDER[0] == REQUIRED_ROW


def test_row_index_finds_names_and_reports_the_missing_ones():
    order = ["idle", "running-left", "review"]
    assert row_index(order, "running-left") == 1
    assert row_index(order, "jumping") is None


def test_overlay_exposes_the_default_order_as_its_row_list():
    """STATE_ROWS must stay the single source of truth, not a second copy."""
    from hermes_companion.renderer.petdex_overlay import STATE_ROWS

    assert STATE_ROWS == DEFAULT_ROW_ORDER


def test_installed_v2_pet_swaps_the_running_pair():
    """aeon-loom's sheet runs the opposite way to the v1 default.

    Guarded because it reads the machine's installed pets; the point is that a
    real v2 sidecar is parsed and actually changes the mapping.
    """
    sheet = Path(os.environ.get("LOCALAPPDATA", ""), "hermes", "pets", "aeon-loom", "spritesheet.webp")
    if not sheet.is_file():
        pytest.skip("aeon-loom is not installed on this machine")
    order = load_row_order(sheet)
    assert order != DEFAULT_ROW_ORDER, "the sidecar was not applied"
    assert order[0] == "idle"
    assert order.index("running-left") < order.index("running-right"), \
        "this pet runs left on the earlier row"
