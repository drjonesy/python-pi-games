#!/usr/bin/env python3
"""Build-time preview art for the game picker. Run this on a desktop.

Every game shows a still picture on the picker
(`cabinet/ui/game_select.py`), loaded from `games/<id>/preview.png`. A game may
just ship one drawn by hand; Pac-Man's is generated instead, because it is
assembled from art the game already owns, and drawing it by hand would mean a
second copy of the board to keep in step with the first.

Note that a preview is a *composed scene*, not a screenshot - Pac-Man's happens
to be its maze at exactly half scale, which is the whole board.

The output is committed, exactly like `assets/sprites/`, so the Pi never runs
this. Re-run it if the art changes::

    python tools/make_preview.py                # every game
    python tools/make_preview.py --game pacman

It renders at the panel's native size, so the picker blits it 1:1 with no
resampling. Pixel art survives an integer downscale and not much else, and this
is the only picture on that screen.
"""

import argparse
import os
import sys

REPO_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, REPO_ROOT)

# No display is opened, and none is needed: everything is blitted onto an
# offscreen surface and written straight out.
os.environ.setdefault('SDL_VIDEODRIVER', 'dummy')

import pygame                                            # noqa: E402

from cabinet.ui.game_select import PREVIEW_INNER         # noqa: E402
from games.pacman import constants as C                  # noqa: E402
from games.pacman.maze import MAZE_ROWS_RAW              # noqa: E402


def output_path(game_id):
    return os.path.join(REPO_ROOT, 'games', game_id, 'preview.png')

# The frame of the chase to freeze. Pac-Man runs row 5 - the upper of the two
# rows with no wall in them - with the ghosts strung out behind him. He is
# two-thirds across so the whole train is on the board and the eaten stretch of
# dots behind him is long enough to read as motion.
CHASE_ROW = 5
PACMAN_X_TILES = 19.5
# Two tiles apart. At 1.6 the 16px sprites overlapped, and at the picker's half
# scale four ghosts merged into one orange-to-red smear.
GHOST_GAP_TILES = 2.0
GHOST_KEYS = ('blinky_right', 'pinky_right', 'inky_right', 'clyde_right')

# Mid-chomp. Frame 0 is a closed mouth, which reads as a plain circle at 8px.
PACMAN_FRAME = 1
GHOST_FRAME = 0


def render_pacman(width, height):
    """The board at half scale, mid-chase. See the module docstring."""
    from cabinet.renderer import AssetStore
    from games.pacman.game import SPEC

    # This game's own pack, exactly as the cabinet loads it at play time. A
    # preview is drawn from the art the game ships, so it can only ever read
    # from the game's own asset root.
    assets = AssetStore().pack(SPEC.id, SPEC.asset_root)

    maze = assets.scaled('maze_blue', width, height)
    if maze is None:
        raise SystemExit('maze_blue is missing - run tools/convert_assets.py')

    board = maze.copy()
    scale_x = width / C.MAZE_WIDTH
    scale_y = height / C.MAZE_HEIGHT

    tile = C.SCALED_TILE_SIZE
    dot = max(1, round(tile * scale_x / 4))
    pellet = max(2, round(tile * scale_x))
    sprite = max(2, round(tile * 2 * scale_x))          # 16px at 1:1

    def stamp(column, row, size, color):
        x = (column * tile + tile / 2) * scale_x
        y = (row * tile + tile / 2) * scale_y
        board.fill(color, (round(x - size / 2), round(y - size / 2),
                           size, size))

    for row, line in enumerate(MAZE_ROWS_RAW):
        for column, char in enumerate(line):
            if char == 'o':
                stamp(column, row, dot, C.ARCADE_PALE)
            elif char == 'O':
                stamp(column, row, pellet, C.ARCADE_PALE)

    lead_x = PACMAN_X_TILES * tile
    centre_y = CHASE_ROW * tile + tile / 2
    top = round(centre_y * scale_y) - sprite // 2

    # The dots behind him are gone, as they would be mid-run. This row has no
    # wall in it, so the band can only ever cover dots and black.
    band = max(1, round(tile * scale_y / 2))
    board.fill(C.BLACK, (0, round(centre_y * scale_y) - band // 2,
                         round(lead_x * scale_x), band))

    for index, key in enumerate(GHOST_KEYS):
        x = lead_x - (index + 1) * GHOST_GAP_TILES * tile
        frames = assets.frames(key, sprite)
        if frames:
            board.blit(frames[GHOST_FRAME], (round(x * scale_x), top))

    frames = assets.frames('pacman_right', sprite)
    if frames:
        board.blit(frames[min(PACMAN_FRAME, len(frames) - 1)],
                   (round(lead_x * scale_x), top))

    return board


RENDERERS = {
    'pacman': render_pacman,
}


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--game', default=None, metavar='ID',
                        choices=sorted(RENDERERS),
                        help='render one game (default: all)')
    parser.add_argument('--output', default=None, metavar='PATH',
                        help='override the output path (implies --game)')
    parser.add_argument('--width', type=int, default=PREVIEW_INNER.width)
    parser.add_argument('--height', type=int, default=PREVIEW_INNER.height)
    args = parser.parse_args(argv)

    if args.output and not args.game:
        parser.error('--output needs --game')

    pygame.init()
    pygame.display.set_mode((1, 1))      # convert_alpha needs a video mode

    targets = [args.game] if args.game else sorted(RENDERERS)
    for game_id in targets:
        surface = RENDERERS[game_id](args.width, args.height)
        path = args.output or output_path(game_id)
        os.makedirs(os.path.dirname(path) or '.', exist_ok=True)
        pygame.image.save(surface, path)
        print(f'wrote {path} ({args.width}x{args.height})')

    pygame.quit()
    return 0


if __name__ == '__main__':
    sys.exit(main())
