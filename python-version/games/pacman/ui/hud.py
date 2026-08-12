"""Score row, lives and fruit row, FPS readout, pause overlay.

These were DOM elements in the reference (Game.jsx:86-112) laid out with CSS.
The proportions are ported from `src/styles/game.css`: the score row is three
tiles tall with a 1.5-tile line height, and the lives/fruit row is two tiles.
Everything is drawn in absolute screen coordinates, not maze coordinates.
"""

import pygame

from .. import constants as C
from cabinet.controls import KEYBOARD, SCHEMES
from cabinet.ui.hints import control_hints, draw_hint

TILE = C.SCALED_TILE_SIZE

# Score row: two lines of text inside a 3-tile row, at a 1.5-tile line height.
LINE_HEIGHT = TILE * (C.SCORE_ROW_TILES / 2)     # 12
LINE_ONE_Y = round((LINE_HEIGHT - 7) / 2)        # vertically centred glyph
LINE_TWO_Y = round(LINE_HEIGHT + (LINE_HEIGHT - 7) / 2)

# game.css splits the row into a 25% column (1UP) and a 50% column (HIGH SCORE),
# with the values right-aligned at `calc(50% - 3em)` inside each.
COLUMN_25_WIDTH = C.LOGICAL_WIDTH * 0.25         # 56
COLUMN_50_WIDTH = C.LOGICAL_WIDTH * 0.5          # 112
ONE_UP_CENTER = COLUMN_25_WIDTH / 2              # 28
POINTS_RIGHT = COLUMN_25_WIDTH - (COLUMN_25_WIDTH / 2 - 3 * TILE)   # 52
HIGH_SCORE_CENTER = COLUMN_25_WIDTH + COLUMN_50_WIDTH / 2           # 112
HIGH_SCORE_RIGHT = (COLUMN_25_WIDTH + COLUMN_50_WIDTH
                    - (COLUMN_50_WIDTH / 2 - 3 * TILE))              # 136

BOTTOM_ROW_Y = C.MAZE_ORIGIN_Y + C.MAZE_HEIGHT   # 280
ICON_SIZE = TILE * 2                             # 16, engine.js:1878
MAX_FRUIT_ICONS = 7                              # engine.js:1888

# The control reminder sits in the one-tile gap between the score row and the
# maze (y=24..31), which is the only *full-width* empty band on the screen and
# the only place `PAUSE = [SELECT]` fits at all: the score row's spare corner
# has 80px, and that line alone is 95px. The bottom row is no good either -
# with a full complement of lives on the left and seven fruit on the right, the
# gap between them narrows to about 48px.
#
# Being clear of the top-right corner also means the FPS counter no longer
# contends with it, so the hint is drawn unconditionally.
HINT_Y = C.MAZE_ORIGIN_Y - TILE                  # 24
HINT_CENTER = C.LOGICAL_WIDTH / 2


class Hud:
    def __init__(self, renderer, font, controls=None):
        self.renderer = renderer
        self.font = font
        # By reference - see the note in `ui/menu.py`.
        self.controls = controls

    @property
    def scheme(self):
        return self.controls.scheme if self.controls else SCHEMES[KEYBOARD]

    def draw(self, coordinator, fps):
        """Draws the chrome around the board."""
        self.draw_score_row(coordinator)
        self.draw_bottom_row(coordinator)
        self.draw_control_hint(coordinator)

        # The reference showed a volume_up / volume_off icon in its header
        # (engine.js:1342). The struck-through speaker in the hint below is
        # that icon, so the separate MUTE readout this used to carry would now
        # be saying the same thing twice.

        if coordinator.show_fps:
            self.draw_fps(fps)

    def draw_score_row(self, coordinator):
        surface = self.renderer.surface

        # '1UP' blinks on a 600ms cycle - game.css's `blink` keyframes hold it
        # invisible for the first half of the cycle.
        blink_on = (coordinator.pellet_blink_ms % C.ONE_UP_BLINK_PERIOD_MS) >= (
            C.ONE_UP_BLINK_PERIOD_MS / 2
        )
        if blink_on:
            self.font.draw(surface, '1UP', ONE_UP_CENTER, LINE_ONE_Y,
                           C.WHITE, align='center')

        self.font.draw(surface, 'HIGH SCORE', HIGH_SCORE_CENTER, LINE_ONE_Y,
                       C.WHITE, align='center')

        points = str(coordinator.points) if coordinator.points else '00'
        self.font.draw(surface, points, POINTS_RIGHT, LINE_TWO_Y,
                       C.WHITE, align='right')

        high_score = str(coordinator.high_score) if coordinator.high_score else '00'
        self.font.draw(surface, high_score, HIGH_SCORE_RIGHT, LINE_TWO_Y,
                       C.WHITE, align='right')

    def draw_bottom_row(self, coordinator):
        """Remaining lives on the left, eaten fruit on the right (engine.js:1872)."""
        for index in range(coordinator.lives):
            self.renderer.draw_image_at(
                'extra_life', index * ICON_SIZE, BOTTOM_ROW_Y,
                ICON_SIZE, ICON_SIZE,
            )

        icons = coordinator.fruit_display[-MAX_FRUIT_ICONS:]
        for index, key in enumerate(icons):
            x = C.LOGICAL_WIDTH - (len(icons) - index) * ICON_SIZE
            self.renderer.draw_image_at(key, x, BOTTOM_ROW_Y, ICON_SIZE, ICON_SIZE)

    def draw_control_hint(self, coordinator):
        """Names the pause and sound controls, so neither has to be memorised.

        Grey rather than white so it reads as chrome and does not compete with
        the score above or the maze below.
        """
        draw_hint(
            self.renderer.surface, self.font, control_hints(self.scheme),
            HINT_CENTER, HINT_Y, C.ARCADE_GREY, align='center',
            muted=coordinator.sound_manager.master_volume == 0,
        )

    def draw_fps(self, fps):
        """The debug FPS counter (engine.js:2550) - kept, per §11, as a toggle."""
        self.font.draw(
            self.renderer.surface, f'{round(fps)} FPS',
            C.LOGICAL_WIDTH - 2, 1, C.ARCADE_CYAN, align='right',
        )

    def draw_pause_overlay(self, muted=False):
        """Blurs the board and prints PAUSED (engine.js:2015).

        The web build applied `filter: blur(5px)`. Downscaling and scaling back
        up is the cheap equivalent, and it only runs while paused.
        """
        surface = self.renderer.surface
        width, height = surface.get_size()

        small = pygame.transform.smoothscale(
            surface, (max(1, width // 5), max(1, height // 5)),
        )
        surface.blit(pygame.transform.smoothscale(small, (width, height)), (0, 0))

        self.font.draw(
            surface, 'PAUSED', width / 2, height / 2 - 7, C.WHITE,
            scale=2, align='center',
        )

        # The score row's hint is blurred out along with the board, and a
        # stopped player is the one most likely to be looking for the control.
        draw_hint(
            surface, self.font, control_hints(self.scheme, verb='RESUME'),
            width / 2, height / 2 + 14, C.ARCADE_GREY, align='center',
            muted=muted,
        )
