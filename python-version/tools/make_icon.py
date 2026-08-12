#!/usr/bin/env python3
"""Draw the desktop launcher icon. Run this on a desktop, never on the Pi.

The output - `assets/icon.png` - is committed, so the Pi needs neither Pillow
nor this script; `install-desktop-shortcut.sh` just points the .desktop entry at
the finished file. Rerun this only to change how the icon looks.

The label is set in the game's own 5x7 bitmap font (`cabinet/font.py`) rather
than a system typeface, so the icon and the HUD it launches use identical
letterforms. That font has no lowercase glyphs, hence PACMAN rather than Pacman.

Requirements (desktop only)::

    pip install Pillow

Usage::

    python tools/make_icon.py
"""

import os
import sys

from PIL import Image, ImageDraw

REPO_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, REPO_ROOT)

from games.pacman import constants as C          # noqa: E402
from cabinet.font import CELL_WIDTH, GLYPHS  # noqa: E402

OUTPUT_PATH = os.path.join(REPO_ROOT, 'assets', 'icon.png')

SIZE = 256          # final edge length, in pixels
SUPERSAMPLE = 4     # draw this many times larger, then downsample to antialias

LABEL = 'PACMAN'

# Geometry, in final-image pixels. Pac-Man sits left of centre to leave room for
# the dot he is about to eat; the label occupies the bottom quarter.
BODY_CENTER = (104, 94)
BODY_RADIUS = 72
MOUTH_HALF_ANGLE = 32   # degrees above and below the horizontal
DOT_CENTER = (210, 94)
DOT_RADIUS = 15
LABEL_TOP = 190
LABEL_SCALE = 5         # one font pixel becomes this many image pixels

CORNER_RADIUS = 48
BACKGROUND = C.ARCADE_DARK + (255,)


def draw_text(draw, text, scale, top, color):
    """Stamps the bitmap font as rectangles, horizontally centred."""
    width = len(text) * CELL_WIDTH * scale
    x = (SIZE * SUPERSAMPLE - width) // 2
    for char in text:
        rows = GLYPHS.get(char)
        if rows is None:
            x += CELL_WIDTH * scale
            continue
        for row_index, row in enumerate(rows):
            for col_index, bit in enumerate(row):
                if bit != '1':
                    continue
                left = x + col_index * scale
                upper = top + row_index * scale
                draw.rectangle(
                    (left, upper, left + scale - 1, upper + scale - 1),
                    fill=color,
                )
        x += CELL_WIDTH * scale


def build():
    scale = SUPERSAMPLE
    canvas = SIZE * scale
    image = Image.new('RGBA', (canvas, canvas), (0, 0, 0, 0))
    draw = ImageDraw.Draw(image)

    draw.rounded_rectangle(
        (0, 0, canvas - 1, canvas - 1),
        radius=CORNER_RADIUS * scale,
        fill=BACKGROUND,
    )

    # pieslice omits the wedge between its end and start angles, so a mouth
    # opening to the right is everything *except* -32..32 degrees.
    cx, cy = BODY_CENTER[0] * scale, BODY_CENTER[1] * scale
    r = BODY_RADIUS * scale
    draw.pieslice(
        (cx - r, cy - r, cx + r, cy + r),
        start=MOUTH_HALF_ANGLE,
        end=360 - MOUTH_HALF_ANGLE,
        fill=C.PACMAN_YELLOW + (255,),
    )

    dx, dy = DOT_CENTER[0] * scale, DOT_CENTER[1] * scale
    dr = DOT_RADIUS * scale
    draw.ellipse(
        (dx - dr, dy - dr, dx + dr, dy + dr),
        fill=C.WHITE + (255,),
    )

    draw_text(
        draw, LABEL, LABEL_SCALE * scale, LABEL_TOP * scale,
        C.PACMAN_YELLOW + (255,),
    )

    return image.resize((SIZE, SIZE), Image.LANCZOS)


def main():
    image = build()
    os.makedirs(os.path.dirname(OUTPUT_PATH), exist_ok=True)
    image.save(OUTPUT_PATH)
    print(f'wrote {OUTPUT_PATH} ({SIZE}x{SIZE})')


if __name__ == '__main__':
    main()
