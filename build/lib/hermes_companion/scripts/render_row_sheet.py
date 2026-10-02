"""Render a labelled contact sheet of a pet atlas, one tile per physical row.

Purpose: confirm or correct a pet's `rowmap.json`. The row order is data
because it is not standardised, and the only reliable way to learn what a
given sheet puts on row 4 is to look at row 4.

    python scripts/render_row_sheet.py <spritesheet.webp> [out.png] [--col N]

Writes the sheet next to the spritesheet by default (<pet>-rows.png) and prints
the resolved name for each row, so a wrong mapping is visible at a glance.
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from PIL import Image, ImageDraw  # noqa: E402

from hermes_companion.renderer.petdex_overlay import FRAME_H, FRAME_W  # noqa: E402
from hermes_companion.renderer.pet_rows import load_row_order  # noqa: E402

TILE_W, TILE_H = 130, 141
GUTTER, PAD = 170, 8
PER_ROW = 4


def render_row_sheet(sheet: Path, out: Path, column: int = 0) -> Path:
    with Image.open(sheet) as raw:
        im = raw.convert("RGBA")
        cols = im.width // FRAME_W
        rows = im.height // FRAME_H
        if column >= cols:
            raise SystemExit(f"column {column} out of range (sheet has {cols})")
        order = load_row_order(sheet)

        grid_rows = (rows + PER_ROW - 1) // PER_ROW
        canvas = Image.new(
            "RGB",
            (PER_ROW * (TILE_W + GUTTER) + PAD, grid_rows * (TILE_H + 26) + PAD),
            (16, 26, 44),
        )
        draw = ImageDraw.Draw(canvas)
        for r in range(rows):
            cell = im.crop((column * FRAME_W, r * FRAME_H,
                            (column + 1) * FRAME_W, (r + 1) * FRAME_H))
            cell = cell.resize((TILE_W, TILE_H))
            gx, gy = r % PER_ROW, r // PER_ROW
            x, y = PAD + gx * (TILE_W + GUTTER), PAD + gy * (TILE_H + 26)
            canvas.paste(cell, (x, y), cell)
            name = order[r] if r < len(order) else "(unmapped)"
            draw.text((x, y + TILE_H + 4), f"row {r}: {name}", fill=(230, 240, 252))
        canvas.save(out)

    for r in range(rows):
        name = order[r] if r < len(order) else "(unmapped - no name in rowmap.json)"
        print(f"  row {r:>2} -> {name}")
    return out


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("spritesheet", type=Path)
    ap.add_argument("out", type=Path, nargs="?")
    ap.add_argument("--col", type=int, default=0, help="which frame column to show")
    args = ap.parse_args()

    if not args.spritesheet.is_file():
        raise SystemExit(f"no such spritesheet: {args.spritesheet}")
    out = args.out or args.spritesheet.with_name(f"{args.spritesheet.parent.name}-rows.png")
    print(f"{args.spritesheet}\nresolved rows:")
    written = render_row_sheet(args.spritesheet, out, args.col)
    print(f"\ncontact sheet: {written}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
