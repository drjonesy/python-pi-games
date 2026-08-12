"""The contract between the cabinet and a game.

Adding a title to the machine means three things and no more:

1. a package under `games/<id>/` containing a `Game` subclass,
2. a `GameSpec` describing it - name, blurb, and a `preview.png` beside it,
3. one line adding that spec to `games/registry.py`.

Everything else is lent to it. The shell owns the window, the sprite cache, the
font, the mixer, the pad, the control-label scheme, the high-score file, the
name-entry modal and the operator menu, and hands them over in a
`GameContext`. A game is therefore never responsible for anything cabinet-wide,
which is what keeps two of them from disagreeing about it.

The split of responsibility for input is worth stating explicitly, because it
is the one place the boundary is not obvious. The shell resolves a keypress or
a mat panel into one of eight **actions** - the four directions plus `select`,
`delete`, `pause`, `mute` - and routes it. Modals it owns (name entry, operator
menu) get first refusal; only if none is up does the action reach
`Game.handle_action`. A game never sees a raw pygame event, never learns which
physical panel was pressed, and never has to know a modal is open.
"""

import os

from .leaderboard import data_file_for


class GameContext:
    """The shared services a game is lent, plus the few knobs it may turn.

    Held by reference and mutated in place: `show_fps` and the controller
    scheme can change from the operator menu while a game is loaded, and the
    next frame has to say the new thing.
    """

    def __init__(self, renderer, assets, font, sound_manager, controls,
                 leaderboard, submit_score=None, exit_to_picker=None,
                 quit_cabinet=None):
        self.renderer = renderer
        self.assets = assets
        self.font = font
        self.sound_manager = sound_manager
        self.controls = controls
        # This game's board, not the cabinet's - see `cabinet/leaderboard.py`.
        self.leaderboard = leaderboard

        # Offer a final score to the shared name-entry modal. It opens only if
        # the score earns a place; `on_close` fires either way, so a game can
        # repaint its own high-score readout without checking first.
        self.submit_score = submit_score or (lambda score, on_close=None: None)
        # Hand control back to the game picker.
        self.exit_to_picker = exit_to_picker or (lambda: None)
        # Shut the cabinet down. Deliberately not reachable from a mat panel.
        self.quit_cabinet = quit_cabinet or (lambda: None)

        # Cabinet-wide, not per game: F1 means the same thing on every screen.
        self.show_fps = False
        # The shell's measured render rate, refreshed each frame so a game's
        # HUD can print it without owning a loop of its own.
        self.fps = 60.0

    @property
    def scheme(self):
        """The active control-label scheme (`cabinet/controls.py`)."""
        return self.controls.scheme


class Game:
    """One playable title.

    The default implementations make a do-nothing game that sits on a blank
    screen, so a subclass only has to override what it actually does.
    """

    #: Fixed simulation step, in milliseconds. The shell builds this game's
    #: `GameEngine` with it, so two games may simulate at different rates.
    sim_dt_ms = None

    def __init__(self, context):
        self.context = context

    # -- lifecycle -----------------------------------------------------------

    def enter(self):
        """Control has just passed from the picker to this game."""

    def leave(self):
        """Control is going back to the picker.

        Must leave nothing running - in particular no looping audio, since the
        picker has no idea this game was ever loaded.
        """

    # -- frame ---------------------------------------------------------------

    @property
    def simulating(self):
        """True when the fixed-step engine should be stepping this frame.

        False on an attract screen or while paused: the frame is still drawn,
        but simulation time - and therefore every timer driven from it -
        freezes.
        """
        return False

    def tick_realtime(self, frame_ms):
        """Wall-clock bookkeeping, run every frame whether simulating or not."""

    def update(self, sim_dt_ms):
        """One fixed simulation step."""

    def render(self, interp):
        """Draw one frame. `interp` is the fraction between the last two steps."""

    # -- input ---------------------------------------------------------------

    def handle_action(self, action):
        """One of: up, down, left, right, select, delete, pause, mute."""

    @property
    def at_attract(self):
        """True on this game's own title screen, with nothing in progress.

        The shell reads it to decide whether the operator menu may be opened
        and whether the back-out control is live, so it must be False for the
        whole of a run - including the end-of-game sequence.
        """
        return True


class GameSpec:
    """How a game is listed, previewed and stored, without loading it.

    The picker shows every registered game and each one's high scores before
    any of them has been constructed, so all of that lives here rather than on
    the `Game` itself.
    """

    def __init__(self, id, title, factory, tagline='', preview_image=None,
                 data_file=None):
        self.id = id
        self.title = title
        # One line under the preview. Kept to ~32 characters: the panel is 208
        # logical pixels wide and the font cell is 6.
        self.tagline = tagline
        self.factory = factory
        # A still picture for the picker - a path to a PNG or JPEG, by
        # convention `games/<id>/preview.png`. Optional; a game without one
        # gets its title on a black panel rather than a broken box.
        #
        # A picture rather than a callback the picker would run every frame:
        # the picker is the screen an idle cabinet sits on for hours, and a
        # file is also the one part of a game anyone can replace without
        # touching code.
        self.preview_image = preview_image
        # Pac-Man keeps `data/data.json` so one file can still be shared with
        # the Node version; anything new gets `data/scores/<id>.json`.
        self.data_file = data_file or data_file_for(id)

    def create(self, context):
        return self.factory(context)

    def __repr__(self):
        return f'<GameSpec {self.id} {os.path.basename(self.data_file)}>'
