"""Shared test fixtures.

Everything here runs headless - no display, no mixer - so the suite can check
simulation behaviour without a window.
"""

import os
import sys

import pytest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from games.pacman.character_util import CharacterUtil          # noqa: E402
from games.pacman.characters.ghost import Ghost                # noqa: E402
from games.pacman.characters.pacman import Pacman              # noqa: E402
from games.pacman.constants import SCALED_TILE_SIZE            # noqa: E402
from games.pacman.events import EventBus                       # noqa: E402
from games.pacman.maze import MAZE_ARRAY                       # noqa: E402

TILE = SCALED_TILE_SIZE


def grid_to_pixels(x, y):
    """Grid position -> the pixel position that produces it exactly.

    Inverse of CharacterUtil.determine_grid_position.
    """
    return {'top': (y - 0.5) * TILE, 'left': (x - 0.5) * TILE}


def pixels_to_grid(position):
    return {
        'x': position['left'] / TILE + 0.5,
        'y': position['top'] / TILE + 0.5,
    }


class Harness:
    """A Pacman plus the four ghosts, with no coordinator or renderer."""

    def __init__(self, level=1):
        self.events = EventBus()
        self.fired = []
        for name in ('eatGhost', 'deathSequence', 'restoreGhost',
                     'releaseGhost', 'dotEaten', 'powerUp', 'awardPoints'):
            self.events.on(name, self._recorder(name))

        self.pacman = Pacman(TILE, MAZE_ARRAY, CharacterUtil())
        self.blinky = Ghost(TILE, MAZE_ARRAY, self.pacman, 'blinky', level,
                            CharacterUtil(), self.events)
        self.pinky = Ghost(TILE, MAZE_ARRAY, self.pacman, 'pinky', level,
                           CharacterUtil(), self.events)
        self.inky = Ghost(TILE, MAZE_ARRAY, self.pacman, 'inky', level,
                          CharacterUtil(), self.events, self.blinky)
        self.clyde = Ghost(TILE, MAZE_ARRAY, self.pacman, 'clyde', level,
                           CharacterUtil(), self.events)
        self.ghosts = [self.blinky, self.pinky, self.inky, self.clyde]

    def _recorder(self, name):
        def record(**detail):
            self.fired.append((name, detail))
        return record

    def names_fired(self):
        return [name for name, _ in self.fired]

    def place_pacman(self, x, y, direction='left'):
        self.pacman.position = grid_to_pixels(x, y)
        self.pacman.old_position = dict(self.pacman.position)
        self.pacman.direction = direction
        self.pacman.desired_direction = direction

    def place_ghost(self, ghost, x, y, direction, mode=None):
        ghost.position = grid_to_pixels(x, y)
        ghost.old_position = dict(ghost.position)
        ghost.direction = direction
        ghost.idle_mode = None
        ghost.moving = True
        if mode is not None:
            ghost.mode = mode


@pytest.fixture
def harness():
    return Harness()
