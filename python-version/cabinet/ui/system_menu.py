"""The SELECT operator menu (Pi-only; no reference counterpart).

A cabinet has no keyboard, so clearing the high scores, turning the sound off or
shutting the machine down used to mean SSHing in. This is that: the SELECT panel
on a title screen opens a short list - SOUND, CHANGE GAME, CONTROLLER, RESET
SCORES, EXIT GAME, CANCEL - navigated with the arrow panels and chosen with
SELECT.

SELECT is free to take on a title screen because it drives the `pause` action,
and there is nothing to pause there. An earlier version needed SELECT+START
together, which meant holding both panels' actions back for 250ms to see whether
a combo was forming - too tight a window to hit with two feet on a mat, and it
put a delay on starting a game. One panel needs none of that.

**RESET SCORES clears one game's board, not the machine's.** Each game keeps its
own top three (`cabinet/leaderboard.py`), so the board this menu resets is
whichever one it was opened over - the running game's, or the highlighted game's
on the picker. Which one that is is printed above the passcode slots, because
"RESET HIGH SCORES" on a machine with several boards is otherwise ambiguous at
exactly the moment it must not be.

RESET SCORES is the destructive one, so it is gated behind a passcode entered on
the four shape panels. EXIT GAME just exits; there is nothing to undo. CHANGE
GAME is the mat's only route back to the picker - there is no spare panel for
it, which is why it is a row here (see `cabinet/controls.py`).

The passcode is treated as a secret, which drives two things that would
otherwise look like missing polish:

* **Entry is masked.** The slots fill in but never show which panel was pressed,
  so the code cannot be read over a player's shoulder.
* **Nothing is checked until START.** A wrong panel is accepted silently and the
  whole sequence is compared at the end. Rejecting each panel as it was pressed
  would leak the code one position at a time - with four panels that is ~16
  guesses instead of the 256 sequences a blind search needs.

The code is read as *physical panels* rather than the eight actions the rest of
the game sees, which is the whole reason `gamepad.PANELS` exists. On this mat
the shapes are already aliased to mute/pause/delete/select, so reading actions
instead would toggle mute and pause the game while the code was being entered.

`main.py` only offers this on the menu screen, so it can never interrupt a run.
That is also why SOUND lives here rather than on a panel: the mat's square panel
used to mute, but it is a corner that a foot moving between the arrows clips, so
it was unbound. A row in a menu you can only reach while standing still cannot
be hit by accident.
"""

import json
import os

from .. import constants as C
from ..controls import SCHEME_ORDER, SCHEMES, Controls

# The alphabet the passcode is drawn from: the four shape panels. The arrows are
# deliberately excluded - they are how the menu is navigated, and a code that
# overlapped them would be harder to enter than to guess.
CODE_PANELS = ('cross', 'square', 'triangle', 'circle')

DATA_DIR = os.path.join(
    os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))),
    'data',
)
PASSCODE_FILE = os.path.join(DATA_DIR, 'passcode.json')

# Used when there is no passcode file. This one is in the repository, so it is
# public knowledge - `data/passcode.json` is gitignored precisely so a real
# secret can be set without committing it. See the README.
DEFAULT_CODE = ('cross', 'square', 'triangle', 'circle')

# A hand-written file should not be able to make the menu unusable, in either
# direction: an empty code would reset the board on a bare START press, and an
# absurdly long one could not be entered before the idle timeout.
MIN_CODE_LENGTH = 3
MAX_CODE_LENGTH = 10


def load_code(path=PASSCODE_FILE):
    """The configured passcode, or `DEFAULT_CODE` if there is not a usable one.

    Same rule as the leaderboard and the pad mapping: a missing or corrupt file
    is a fallback, never an error. A cabinet must always boot.
    """
    if not path or not os.path.exists(path):
        return DEFAULT_CODE

    try:
        with open(path, encoding='utf-8') as handle:
            parsed = json.load(handle)
    except (OSError, ValueError):
        return DEFAULT_CODE

    code = parsed.get('code') if isinstance(parsed, dict) else parsed
    if not isinstance(code, list):
        return DEFAULT_CODE
    if not MIN_CODE_LENGTH <= len(code) <= MAX_CODE_LENGTH:
        return DEFAULT_CODE
    if any(panel not in CODE_PANELS for panel in code):
        return DEFAULT_CODE

    return tuple(code)


OPTION_SOUND = 'sound'
OPTION_CHANGE_GAME = 'change_game'
OPTION_CONTROLS = 'controls'
OPTION_RESET = 'reset'
OPTION_EXIT = 'exit'
OPTION_CANCEL = 'cancel'

# CANCEL is not in the original sketch of this menu, but without it the popup is
# a trap: every other row either wipes the board or kills the game.
#
# SOUND leads the list. It is the only row anyone touches routinely, it is the
# most harmless - one more press puts it back - and the cursor starts on
# whatever is first. It is here at all because the mat has no sound panel: the
# square panel used to mute, but it is a corner a moving foot clips, so it was
# unbound (see `gamepad.DEFAULT_MAPPING`). This popup is the replacement, and it
# is a good home for it - reachable from the mat with no keyboard, and only from
# the main menu, so it can never fire mid-run.
#
# CHANGE GAME sits second and is present only when there is a game to leave -
# on the picker itself the row would do nothing, and a dead row is worse than a
# missing one.
OPTIONS = (
    (OPTION_SOUND, 'SOUND'),
    (OPTION_CHANGE_GAME, 'CHANGE GAME'),
    (OPTION_CONTROLS, 'CONTROLLER'),
    (OPTION_RESET, 'RESET SCORES'),
    (OPTION_EXIT, 'EXIT GAME'),
    (OPTION_CANCEL, 'CANCEL'),
)

STAGE_OPTIONS = 'options'
STAGE_CONTROLS = 'controls'
STAGE_CODE = 'code'
STAGE_CONFIRM = 'confirm'
STAGE_DONE = 'done'

RESULT_CLEARED = 'cleared'
RESULT_INCORRECT = 'incorrect'

# An unattended cabinet should not sit on this screen forever.
IDLE_TIMEOUT_MS = 20000
# How long the closing message stays up before the menu closes itself.
DONE_MS = 1600

PANEL_WIDTH = 132
PANEL_HEIGHT = 18
PANEL_GAP = 4

SLOT_SIZE = 24
SLOT_GAP = 10
SLOT_DOT = 10

HEADING_Y = 74
# Names the board the reset gate is pointed at, between the heading and the
# instruction.
TARGET_Y = 88
BODY_Y = 100
# Raised from 128 when CHANGE GAME made this a six-row list: at the old origin
# the last row landed exactly on the nav hint. `test_the_rows_still_fit_above
# _the_nav_hint` pins the relationship.
OPTIONS_Y = 114
HINT_Y = C.LOGICAL_HEIGHT - 40


class SystemMenu:
    """Modal state plus its own input handling, like `ScoreEntry`.

    While this is open `main.py` routes every key and panel here instead of to
    the game, so nothing behind it can be reached by the code being entered.
    """

    def __init__(self, renderer, font, leaderboard=None, code=None,
                 controls=None, sound_manager=None):
        self.renderer = renderer
        self.font = font
        # The board RESET SCORES clears. Rebound on every open to whichever
        # game the menu was opened over - see `open_menu`.
        self.leaderboard = leaderboard
        # What to call that board on the confirmation screen.
        self.target_label = None
        self.controls = controls if controls is not None else Controls()
        self.sound_manager = sound_manager
        # Read once at construction: re-reading per press would put a file stat
        # in the input path for no benefit, and the file is not hot-edited.
        self.code = tuple(code) if code else load_code()

        self.on_change_game = None
        self.options = self._build_options()

        self.open = False
        self.stage = STAGE_OPTIONS
        self.index = 0
        self.entered = []        # panels pressed so far, unvalidated
        self.result = None
        self.idle_ms = 0
        self.done_ms = 0

        self.on_reset = None
        self.on_exit = None

    # -- lifecycle -----------------------------------------------------------

    def _build_options(self):
        """The rows for this open. Every one of them has to do something.

        SOUND is dropped when there is nothing to toggle, CHANGE GAME when
        there is no game to leave. A row that did nothing would be worse than a
        missing one on a machine with no keyboard to escape with.
        """
        skip = set()
        if self.sound_manager is None:
            skip.add(OPTION_SOUND)
        if self.on_change_game is None:
            skip.add(OPTION_CHANGE_GAME)

        return tuple(option for option in OPTIONS if option[0] not in skip)

    def open_menu(self, on_reset=None, on_exit=None, on_change_game=None,
                  leaderboard=None, target_label=None):
        """Opens over whatever screen is up.

        `leaderboard` and `target_label` say whose high scores RESET SCORES
        would clear. They are passed per open rather than held for the life of
        the menu because the answer changes with the screen behind it: the
        running game's board, or the highlighted game's on the picker.
        """
        self.open = True
        self.stage = STAGE_OPTIONS
        self.index = 0
        self.entered = []
        self.result = None
        self.idle_ms = 0
        self.done_ms = 0
        self.on_reset = on_reset
        self.on_exit = on_exit
        self.on_change_game = on_change_game

        if leaderboard is not None:
            self.leaderboard = leaderboard
        self.target_label = target_label

        self.options = self._build_options()

    def close(self):
        self.open = False
        self.stage = STAGE_OPTIONS
        self.entered = []

    @property
    def awaiting_confirm(self):
        """True once the code is fully entered and only START is left.

        Says nothing about whether the code is *right* - that is not known until
        START is pressed. `main.py` reads this to decide what its Enter key
        stands in for when testing on a desktop.
        """
        return self.stage == STAGE_CONFIRM

    def tick(self, frame_ms):
        """Wall-clock bookkeeping. The game is not simulating behind this."""
        if not self.open:
            return

        if self.stage == STAGE_DONE:
            self.done_ms += frame_ms
            if self.done_ms >= DONE_MS:
                self.close()
            return

        self.idle_ms += frame_ms
        if self.idle_ms >= IDLE_TIMEOUT_MS:
            self.close()

    # -- input ---------------------------------------------------------------

    def feed(self, panels=(), actions=()):
        """Routes one input event. `panels` is physical, `actions` semantic.

        Navigation comes in as actions because the arrow panels genuinely mean
        up/down; the code comes in as panels because the shapes do not mean what
        they are bound to. See the module docstring.
        """
        if not self.open or self.stage == STAGE_DONE:
            return

        self.idle_ms = 0

        if self.stage == STAGE_OPTIONS:
            if 'up' in actions:
                self.index = (self.index - 1) % len(self.options)
            elif 'down' in actions:
                self.index = (self.index + 1) % len(self.options)
            elif 'select' in panels:
                self._choose()
            return

        if self.stage == STAGE_CONTROLS:
            if 'up' in actions:
                self.index = (self.index - 1) % len(SCHEME_ORDER)
            elif 'down' in actions:
                self.index = (self.index + 1) % len(SCHEME_ORDER)
            elif 'select' in panels:
                self.controls.select(SCHEME_ORDER[self.index])
                # Closes rather than stepping back, so the new labels on the
                # attract screen are the confirmation.
                self.close()
            return

        # Both remaining stages are part of the reset gate. SELECT backs out of
        # them rather than choosing anything, so a half-entered code is never a
        # dead end.
        if 'select' in panels:
            self.close()
            return

        if self.stage == STAGE_CONFIRM:
            if 'start' in panels:
                self._submit_code()
            return

        for panel in CODE_PANELS:
            if panel in panels:
                # Accepted without comment, right or wrong. See the module
                # docstring on why this must not give feedback per press.
                self.entered.append(panel)
                if len(self.entered) == len(self.code):
                    self.stage = STAGE_CONFIRM
                return

    @property
    def muted(self):
        return (self.sound_manager is not None
                and self.sound_manager.master_volume == 0)

    def option_label(self, key, label):
        """The row's text. SOUND carries its own state, the rest are static.

        The label *is* the readout - `SOUND  ON` / `SOUND  OFF` - which is the
        same trick the in-game speaker glyph uses. There is no separate
        indicator to keep in step with it, and no sub-list to step into.
        """
        if key != OPTION_SOUND:
            return label
        return f'{label}  {"OFF" if self.muted else "ON"}'

    def _choose(self):
        option = self.options[self.index][0]
        if option == OPTION_SOUND:
            # Stays open, unlike every other row: the label flips under the
            # cursor, which is both the confirmation and the way back if a foot
            # landed on the wrong panel. `toggle_mute` persists it to
            # `data/settings.json`, so it survives a restart.
            self.sound_manager.toggle_mute()
        elif option == OPTION_CANCEL:
            self.close()
        elif option == OPTION_CHANGE_GAME:
            self.close()
            self.on_change_game()
        elif option == OPTION_EXIT:
            self.close()
            if self.on_exit:
                self.on_exit()
        elif option == OPTION_CONTROLS:
            self.stage = STAGE_CONTROLS
            # Start on the active scheme, so the list doubles as a readout of
            # which one is in force.
            self.index = SCHEME_ORDER.index(self.controls.name)
        else:
            self.stage = STAGE_CODE
            self.entered = []

    def _submit_code(self):
        if tuple(self.entered) != tuple(self.code):
            self._finish(RESULT_INCORRECT)
            return
        self._commit_reset()

    def _commit_reset(self):
        """Clears the board. A failed write still closes the menu.

        Same rule as `ScoreEntry.close_and_save`: a bad disk must not trap
        anyone in a modal on a machine with no keyboard. A missing board is
        treated the same way - there is nothing to clear, and refusing to close
        would be the worse failure.
        """
        try:
            if self.leaderboard is not None:
                self.leaderboard.reset()
        except OSError:
            pass
        finally:
            if self.on_reset:
                self.on_reset()
            self._finish(RESULT_CLEARED)

    def _finish(self, result):
        self.result = result
        self.stage = STAGE_DONE
        self.done_ms = 0
        # Dropped so a wrong code cannot be re-submitted, and so it is not
        # sitting in memory while the closing message is up.
        self.entered = []

    # -- drawing -------------------------------------------------------------

    def draw(self, blink_ms=0):
        surface = self.renderer.surface

        # Heavier than the ScoreEntry scrim (217). That one only ever covers the
        # maze, which is mostly black anyway; this covers the attract screen,
        # and at 217 the leaderboard rows stayed legible behind a dialog about
        # erasing them.
        dim = surface.copy()
        dim.fill((0, 0, 0))
        dim.set_alpha(243)
        surface.blit(dim, (0, 0))

        if self.stage == STAGE_DONE:
            self._draw_done(surface)
        elif self.stage == STAGE_OPTIONS:
            self._draw_options(surface)
        elif self.stage == STAGE_CONTROLS:
            self._draw_controls(surface)
        else:
            self._draw_code(surface, blink_ms)

    def _draw_rows(self, surface, labels):
        """The highlighted list both list stages share."""
        center = C.LOGICAL_WIDTH / 2
        x = (C.LOGICAL_WIDTH - PANEL_WIDTH) / 2

        for row, label in enumerate(labels):
            y = OPTIONS_Y + row * (PANEL_HEIGHT + PANEL_GAP)
            selected = row == self.index

            self.renderer.fill_rect_at(
                x, y, PANEL_WIDTH, PANEL_HEIGHT,
                C.ARCADE_YELLOW if selected else C.ARCADE_DARK,
            )
            self.font.draw(
                surface, label, center, y + (PANEL_HEIGHT - 7) / 2,
                C.ARCADE_DARK if selected else C.WHITE, align='center',
            )

    def _draw_nav_hint(self, surface):
        self.font.draw(
            surface, f'UP DOWN MOVE  {self.controls.scheme.menu_pick} PICKS',
            C.LOGICAL_WIDTH / 2, HINT_Y, C.ARCADE_GREY, align='center',
        )

    def _draw_options(self, surface):
        self.font.draw(surface, 'SYSTEM MENU', C.LOGICAL_WIDTH / 2, HEADING_Y,
                       C.ARCADE_YELLOW, align='center')
        self._draw_rows(surface, [
            self.option_label(key, label) for key, label in self.options
        ])
        self._draw_nav_hint(surface)

    def _draw_controls(self, surface):
        center = C.LOGICAL_WIDTH / 2

        self.font.draw(surface, 'SELECT CONTROLLER', center, HEADING_Y,
                       C.ARCADE_YELLOW, align='center')
        self.font.draw(surface, 'CHANGES ON-SCREEN LABELS', center, BODY_Y,
                       C.ARCADE_GREY, align='center')

        # A dot marks the scheme in force, so the list reads as a setting rather
        # than as four unrelated buttons.
        self._draw_rows(surface, [
            f'{SCHEMES[name].label} *' if name == self.controls.name
            else SCHEMES[name].label
            for name in SCHEME_ORDER
        ])
        self._draw_nav_hint(surface)

    def _draw_code(self, surface, blink_ms):
        center = C.LOGICAL_WIDTH / 2

        self.font.draw(surface, 'RESET HIGH SCORES', center, HEADING_Y,
                       C.ARCADE_RED, align='center')
        # Which board. Every game has its own, and this clears exactly one of
        # them, so leaving it unnamed would make the destructive screen the
        # only ambiguous one on the machine.
        if self.target_label:
            self.font.draw(surface, self.target_label, center, TARGET_Y,
                           C.ARCADE_YELLOW, align='center')
        self.font.draw(surface, 'ENTER PASSCODE', center, BODY_Y,
                       C.WHITE, align='center')

        self._draw_slots()

        if self.stage == STAGE_CONFIRM:
            # Blinking, because this is the last press before the board is gone.
            color = (C.ARCADE_YELLOW if (blink_ms % 1000) < 500
                     else C.ARCADE_DARK)
            self.font.draw(
                surface, f'PRESS {self.controls.scheme.confirm} TO CONFIRM',
                center, OPTIONS_Y + 40, color, align='center',
            )

        self.font.draw(surface, f'{self.controls.scheme.cancel} CANCELS',
                       center, HINT_Y, C.ARCADE_GREY, align='center')

    def _draw_slots(self):
        """One masked slot per code position - never which panel was pressed."""
        count = len(self.code)
        total = count * SLOT_SIZE + (count - 1) * SLOT_GAP
        start_x = (C.LOGICAL_WIDTH - total) / 2
        inset = (SLOT_SIZE - SLOT_DOT) / 2

        for index in range(count):
            x = start_x + index * (SLOT_SIZE + SLOT_GAP)
            self.renderer.fill_rect_at(
                x, OPTIONS_Y, SLOT_SIZE, SLOT_SIZE, C.ARCADE_DARK,
            )
            if index < len(self.entered):
                self.renderer.fill_rect_at(
                    x + inset, OPTIONS_Y + inset, SLOT_DOT, SLOT_DOT,
                    C.ARCADE_YELLOW,
                )

    def _draw_done(self, surface):
        center = C.LOGICAL_WIDTH / 2
        if self.result == RESULT_CLEARED:
            self.font.draw(surface, 'SCORES CLEARED', center, BODY_Y,
                           C.ARCADE_YELLOW, align='center')
        else:
            # Says the sequence was wrong, not which part of it was.
            self.font.draw(surface, 'INCORRECT', center, BODY_Y,
                           C.ARCADE_RED, align='center')
