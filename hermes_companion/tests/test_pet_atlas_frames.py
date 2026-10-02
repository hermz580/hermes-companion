"""Per-row frame counts for pet atlases.

A fixed column count is wrong in both directions: it discards real frames from
rows that have more, or animates into fully-transparent cells, which reads as
the pet flickering out of existence. Frames per row differ *within* one sheet
(the Alpha's idle row holds 6, its walk rows 8), so the count must be measured
per row rather than assumed from the sheet width.
"""

import os
from pathlib import Path

import pytest
from PIL import Image

from hermes_companion.renderer.petdex_overlay import (
    FRAME_H,
    FRAME_W,
    usable_frame_count,
)

PETS = Path(os.environ.get("LOCALAPPDATA", ""), "hermes", "pets")


def _sheet(rows: int, cols: int, blank: set[tuple[int, int]] = frozenset()):
    """Synthetic atlas; `blank` lists (row, col) cells that are transparent."""
    im = Image.new("RGBA", (cols * FRAME_W, rows * FRAME_H), (0, 0, 0, 0))
    for r in range(rows):
        for c in range(cols):
            if (r, c) in blank:
                continue
            im.paste(Image.new("RGBA", (FRAME_W, FRAME_H), (200, 40, 40, 255)),
                     (c * FRAME_W, r * FRAME_H))
    return im


def _row(im: Image.Image, r: int) -> Image.Image:
    return im.crop((0, r * FRAME_H, im.width, (r + 1) * FRAME_H))


def test_counts_leading_art_frames():
    im = _sheet(3, 8, blank={(0, 6), (0, 7), (1, 7)})
    assert usable_frame_count(_row(im, 0), cols=8) == 6
    assert usable_frame_count(_row(im, 1), cols=8) == 7
    assert usable_frame_count(_row(im, 2), cols=8) == 8


def test_fully_blank_row_counts_zero():
    im = _sheet(1, 8, blank={(0, c) for c in range(8)})
    assert usable_frame_count(im, cols=8) == 0


def test_stops_at_first_blank_not_the_last():
    """A blank frame ends the row; art after it is not silently skipped over."""
    im = _sheet(1, 8, blank={(0, 3)})
    assert usable_frame_count(im, cols=8) == 3


def test_defaults_to_sheet_width():
    assert usable_frame_count(_sheet(1, 6)) == 6


@pytest.mark.parametrize("slug", ["the-alpha-and", "aeon-loom"])
def test_installed_sheets_give_every_row_at_least_one_frame(slug: str):
    """Every row must yield a frame, because the renderer indexes [0]."""
    path = PETS / slug / "spritesheet.webp"
    if not path.is_file():
        pytest.skip(f"{slug} not installed on this machine")
    with Image.open(path) as raw:
        im = raw.convert("RGBA")
        cols = im.width // FRAME_W
        rows = im.height // FRAME_H
        assert cols >= 6 and rows >= 9, f"{slug}: {im.size}"
        counts = [usable_frame_count(_row(im, r), cols=cols) for r in range(rows)]
        assert min(counts) >= 1, f"{slug}: empty rows {counts}"
        assert max(counts) <= cols, f"{slug}: over-counted {counts}"
