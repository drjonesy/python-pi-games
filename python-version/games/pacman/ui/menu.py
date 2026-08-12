"""Title screen with the top-three leaderboard.

Ports the markup of Game.jsx:61-67 and Leaderboard.jsx, styled from
`src/styles/leaderboard.css`: a black panel with a 4px #2121ff border, an amber
title, cyan rank labels, white names and amber scores.
"""

from .. import constants as C
from cabinet.controls import KEYBOARD, SCHEMES
from cabinet.ui.hints import control_hints, draw_hint

LOGO_Y = 26
PROMPT_Y = 84
PROMPT_PADDING_X = 7
PROMPT_PADDING_Y = 5
PROMPT_BORDER = 2
PROMPT_SHADOW = 2

PANEL_X = 16
PANEL_Y = 116
PANEL_WIDTH = C.LOGICAL_WIDTH - (PANEL_X * 2)      # 192
PANEL_HEIGHT = 92
PANEL_BORDER = 2

TITLE_Y = PANEL_Y + 10
ROWS_Y = PANEL_Y + 34
ROW_SPACING = 16

RANK_X = PANEL_X + 12
NAME_X = PANEL_X + 44
SCORE_RIGHT = PANEL_X + PANEL_WIDTH - 12

HINT_Y = C.LOGICAL_HEIGHT - 20
# The way back to the game picker, above the pause/sound line. Drawn only under
# a scheme that has a control for it: the mat has not got a spare panel, so
# there the route back is the CHANGE GAME row in the operator menu and a hint
# naming a control that does not exist would be worse than none.
BACK_HINT_Y = C.LOGICAL_HEIGHT - 34


class Menu:
    def __init__(self, renderer, font, leaderboard, controls=None,
                 sound_manager=None):
        self.renderer = renderer
        self.font = font
        self.leaderboard = leaderboard
        # Only read for the speaker icon's mute state; the title screen plays
        # nothing itself.
        self.sound_manager = sound_manager
        # Held by reference, not copied: the operator menu can switch scheme
        # while this object lives, and the next frame must say the new thing.
        self.controls = controls
        self.scores = []
        self.refresh()

    @property
    def scheme(self):
        return self.controls.scheme if self.controls else SCHEMES[KEYBOARD]

    def refresh(self):
        """Re-reads the board - the `leaderboardUpdated` listener's job
        (Leaderboard.jsx:23)."""
        self.scores = self.leaderboard.get_top_scores()

    def draw(self, blink_ms=0):
        surface = self.renderer.surface

        self.renderer.draw_image_at('backdrop', 0, 0)
        self.renderer.draw_image_at(
            'pacman_logo', (C.LOGICAL_WIDTH - 175) / 2, LOGO_Y,
        )

        self.draw_start_button(surface)
        self.draw_panel(surface)
        # Dark on the amber backdrop - grey would disappear into it.
        scheme = self.scheme
        muted = (self.sound_manager is not None
                 and self.sound_manager.master_volume == 0)
        if scheme.back:
            self.font.draw(
                surface, f'{scheme.back} = GAMES', C.LOGICAL_WIDTH / 2,
                BACK_HINT_Y, C.ARCADE_DARK, align='center',
            )
        draw_hint(
            surface, self.font, control_hints(scheme),
            C.LOGICAL_WIDTH / 2, HINT_Y, C.ARCADE_DARK, align='center',
            muted=muted,
        )

    def draw_start_button(self, surface):
        """The PLAY button from game.css:.game-start, scaled down.

        Amber fill, dark border, red drop shadow. The reference started a game
        on click or on Enter (Game.jsx:36-53); with no mouse there is only the
        key, so the label names it - or the mat panel, under the pad scheme.
        The box is measured from the label, so both widths lay out correctly.
        """
        label = f'PRESS {self.scheme.start}'
        text_width = self.font.measure(label)[0]

        width = text_width + PROMPT_PADDING_X * 2
        height = 7 + PROMPT_PADDING_Y * 2
        x = (C.LOGICAL_WIDTH - width) / 2

        # box-shadow: 5px 5px #ee2a29
        self.renderer.fill_rect_at(
            x + PROMPT_SHADOW, PROMPT_Y + PROMPT_SHADOW, width, height,
            C.ARCADE_RED,
        )
        # border: 5px solid #231f20
        self.renderer.fill_rect_at(x, PROMPT_Y, width, height, C.ARCADE_DARK)
        # background-color: #fcc73f
        self.renderer.fill_rect_at(
            x + PROMPT_BORDER, PROMPT_Y + PROMPT_BORDER,
            width - PROMPT_BORDER * 2, height - PROMPT_BORDER * 2,
            C.ARCADE_YELLOW,
        )

        self.font.draw(
            surface, label, C.LOGICAL_WIDTH / 2, PROMPT_Y + PROMPT_PADDING_Y,
            C.ARCADE_DARK, align='center',
        )

    def draw_panel(self, surface):
        self.renderer.fill_rect_at(
            PANEL_X - PANEL_BORDER, PANEL_Y - PANEL_BORDER,
            PANEL_WIDTH + PANEL_BORDER * 2, PANEL_HEIGHT + PANEL_BORDER * 2,
            C.MAZE_BLUE,
        )
        self.renderer.fill_rect_at(
            PANEL_X, PANEL_Y, PANEL_WIDTH, PANEL_HEIGHT, C.BLACK,
        )

        self.font.draw(
            surface, 'HIGH SCORES', PANEL_X + PANEL_WIDTH / 2, TITLE_Y,
            C.ARCADE_YELLOW, align='center',
        )

        # Leaderboard.jsx:4. The cabinet's, not this screen's - the picker
        # labels its rows the same way and both must say the same thing.
        for index, label in enumerate(C.RANK_LABELS):
            y = ROWS_Y + index * ROW_SPACING
            entry = self.scores[index] if index < len(self.scores) else None

            self.font.draw(surface, label, RANK_X, y, C.ARCADE_CYAN)
            self.font.draw(
                surface, entry['name'] if entry else '---', NAME_X, y, C.WHITE,
            )
            self.font.draw(
                surface,
                str(int(entry['score'])) if entry else '00',
                SCORE_RIGHT, y, C.ARCADE_YELLOW, align='right',
            )
