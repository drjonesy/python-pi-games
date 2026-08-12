"""Arcade name entry (ports ScoreEntry.jsx).

Opens on game over when the score earns a top-three place. Driven purely by
direction + select + delete, which is what makes it work identically on a
keyboard and on a gamepad or arcade encoder - the same reason the reference
built it as a key grid rather than a text input (ScoreEntry.jsx:8-11).
"""

from .. import constants as C
from ..controls import KEYBOARD, SCHEMES

LETTERS = 'ABCDEFGHIJKLMNOPQRSTUVWXYZ'

# ScoreEntry.jsx:12-23. Every cell is a key object so one set of arrow-key
# navigation rules covers letters and actions alike.
KEY_ROWS = [
    [{'label': ch, 'type': 'char'} for ch in LETTERS[0:9]],
    [{'label': ch, 'type': 'char'} for ch in LETTERS[9:18]],
    ([{'label': ch, 'type': 'char'} for ch in LETTERS[18:26]]
     + [{'label': 'SPACE', 'type': 'space'}]),
    [{'label': 'DEL', 'type': 'del'}, {'label': 'CONFIRM', 'type': 'confirm'}],
]

KEY_WIDTH = 20
KEY_HEIGHT = 14
KEY_GAP = 2
WIDE_KEYS = {'space': 40, 'confirm': 84, 'del': 44}

HEADING_Y = 30
SCORE_Y = 44
LABEL_Y = 64
SLOTS_Y = 78
KEYBOARD_Y = 104
HINT_Y = C.LOGICAL_HEIGHT - 26

SLOT_WIDTH = 16
SLOT_GAP = 2


def key_width(key):
    return WIDE_KEYS.get(key['type'], KEY_WIDTH)


def row_width(row):
    return sum(key_width(key) for key in row) + KEY_GAP * (len(row) - 1)


class ScoreEntry:
    """Modal state plus its own input handling.

    While this is open it consumes every key. The reference achieved that by
    registering its listener in the capture phase so arrows could not steer
    Pacman and Enter could not start a new game (ScoreEntry.jsx:102-110); here
    `main.py` simply routes input to this object instead of the game.
    """

    def __init__(self, renderer, font, leaderboard, controls=None):
        self.renderer = renderer
        self.font = font
        self.leaderboard = leaderboard
        # By reference - see the note in `ui/menu.py`.
        self.controls = controls

        self.open = False
        self.pending_score = None
        self.name = ''
        self.row = 0
        self.col = 0
        self.on_close = None

    def try_open(self, score, on_close=None):
        """Opens the modal if `score` earns a place (ScoreEntry.jsx:53)."""
        if score > 0 and self.leaderboard.qualifies(score):
            self.name = ''
            self.row = 0
            self.col = 0
            self.pending_score = score
            self.open = True
            self.on_close = on_close
            return True
        return False

    def close_and_save(self):
        """Saves the entry and closes (ScoreEntry.jsx:65).

        A failed save still closes, so a bad disk cannot trap the player in the
        modal.
        """
        try:
            self.leaderboard.submit_score(self.name, self.pending_score)
        except OSError:
            pass
        finally:
            self.open = False
            self.pending_score = None
            if self.on_close:
                self.on_close()

    # -- input ---------------------------------------------------------------

    def move(self, direction):
        """ScoreEntry.jsx:112."""
        row, col = self.row, self.col

        if direction == 'up':
            row = max(0, row - 1)
        elif direction == 'down':
            row = min(len(KEY_ROWS) - 1, row + 1)
        elif direction == 'left':
            col = max(0, col - 1)
        elif direction == 'right':
            col = min(len(KEY_ROWS[row]) - 1, col + 1)

        # Clamp the column so it stays valid on a shorter row.
        self.row = row
        self.col = min(col, len(KEY_ROWS[row]) - 1)

    def activate_key(self, key):
        """ScoreEntry.jsx:80."""
        if key['type'] == 'char':
            if len(self.name) < C.ENTRY_NAME_LENGTH:
                self.name += key['label']
        elif key['type'] == 'space':
            if len(self.name) < C.ENTRY_NAME_LENGTH:
                self.name += ' '
        elif key['type'] == 'del':
            self.name = self.name[:-1]
        elif key['type'] == 'confirm':
            self.close_and_save()

    def select(self):
        self.activate_key(KEY_ROWS[self.row][self.col])

    def backspace(self):
        self.name = self.name[:-1]

    # -- drawing -------------------------------------------------------------

    def draw(self, blink_ms=0):
        surface = self.renderer.surface

        # rgba(0, 0, 0, 0.85) - leaderboard.css's overlay.
        overlay_color = (0, 0, 0, 217)
        dim = surface.copy()
        dim.fill(overlay_color[:3])
        dim.set_alpha(overlay_color[3])
        surface.blit(dim, (0, 0))

        self.font.draw(surface, 'NEW HIGH SCORE!', C.LOGICAL_WIDTH / 2, HEADING_Y,
                       C.ARCADE_YELLOW, align='center')
        self.font.draw(surface, str(self.pending_score), C.LOGICAL_WIDTH / 2,
                       SCORE_Y, C.ARCADE_RED, scale=2, align='center')
        self.font.draw(surface, 'ENTER YOUR NAME', C.LOGICAL_WIDTH / 2, LABEL_Y,
                       C.WHITE, align='center')

        self.draw_slots(surface, blink_ms)
        self.draw_keyboard(surface)

        scheme = self.controls.scheme if self.controls else SCHEMES[KEYBOARD]
        self.font.draw(surface, f'{scheme.move} MOVE  {scheme.pick} PICK',
                       C.LOGICAL_WIDTH / 2, HINT_Y, C.ARCADE_GREY,
                       align='center')

    def draw_slots(self, surface, blink_ms):
        """Ten underlined character slots with a blinking caret."""
        total = C.ENTRY_NAME_LENGTH * SLOT_WIDTH + (C.ENTRY_NAME_LENGTH - 1) * SLOT_GAP
        start_x = (C.LOGICAL_WIDTH - total) / 2

        for index in range(C.ENTRY_NAME_LENGTH):
            x = start_x + index * (SLOT_WIDTH + SLOT_GAP)
            is_caret = (index == len(self.name)
                        and len(self.name) < C.ENTRY_NAME_LENGTH)

            underline = C.ARCADE_YELLOW if is_caret else C.MAZE_BLUE
            # The caret blinks on a 1s step, matching `caret-blink`.
            if is_caret and (blink_ms % 1000) < 500:
                underline = C.MAZE_BLUE
            self.renderer.fill_rect_at(x, SLOTS_Y + 10, SLOT_WIDTH, 2, underline)

            if index < len(self.name):
                char = self.name[index]
                # A typed space would be invisible, so show it as a low bar.
                self.font.draw(
                    surface, '_' if char == ' ' else char,
                    x + SLOT_WIDTH / 2, SLOTS_Y + 2, C.ARCADE_YELLOW,
                    align='center',
                )

    def draw_keyboard(self, surface):
        for row_index, row in enumerate(KEY_ROWS):
            y = KEYBOARD_Y + row_index * (KEY_HEIGHT + KEY_GAP)
            x = (C.LOGICAL_WIDTH - row_width(row)) / 2

            for col_index, key in enumerate(row):
                width = key_width(key)
                selected = (row_index == self.row and col_index == self.col)

                self.renderer.fill_rect_at(
                    x, y, width, KEY_HEIGHT,
                    C.ARCADE_YELLOW if selected else C.ARCADE_DARK,
                )
                self.font.draw(
                    surface, key['label'], x + width / 2,
                    y + (KEY_HEIGHT - 7) / 2,
                    C.ARCADE_DARK if selected else C.WHITE,
                    align='center',
                )
                x += width + KEY_GAP
