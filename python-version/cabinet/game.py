"""The contract between the cabinet and a game.

Adding a title to the machine is **one folder and no edits to anything else**::

    games/<id>/
        __init__.py
        game.py          # a `Game` subclass, and `SPEC = GameSpec(...)`
        preview.png      # the picker's picture (optional)
        assets/          # this game's own sprites and clips (optional)
            manifest.json
            sprites/
            audio/

`games/registry.py` finds it by looking, so nothing shared has to learn the new
game's name: the picker lists it, it gets its own high-score file, its own
sprite pack, its own audio namespace and its own entry in the operator menu's
reset, all keyed off the `GameSpec`. Drop the folder in, and the machine has
another title; delete it, and it does not.

Everything else is lent to it. The shell owns the window, the font, the mixer,
the pad, the control-label scheme, the high-score file, the name-entry modal
and the operator menu, and hands them over in a `GameContext`. A game is
therefore never responsible for anything cabinet-wide, which is what keeps two
of them from disagreeing about it.

The two things a game **does** own are its art and its audio, and it owns them
privately: `context.assets` is that game's pack alone (`cabinet/renderer.py`)
and `context.sound_manager` is a view that prefixes its clip names
(`cabinet/sound.py`). Two games may both ship a sprite called `player` and a
clip called `jump` without knowing about each other. Both are loaded when the
game is first played rather than at boot, so installing a title costs nothing
until someone chooses it.

The split of responsibility for input is worth stating explicitly, because it
is the one place the boundary is not obvious. The shell resolves a keypress or
a mat panel into one of eight **actions** - the four directions plus `select`,
`delete`, `pause`, `mute` - and routes it. Modals it owns (name entry, operator
menu) get first refusal; only if none is up does the action reach
`Game.handle_action`. A game never sees a raw pygame event, never learns which
physical panel was pressed, and never has to know a modal is open.
"""

import os
import sys

from .leaderboard import data_file_for

GAMES_DIR = os.path.join(
    os.path.dirname(os.path.dirname(os.path.abspath(__file__))), 'games',
)


def package_dir_of(factory):
    """The directory the game's code lives in, found from its own module.

    This is what lets a spec default its preview, its art and its clips to the
    files sitting beside it, so a game folder describes itself and a path never
    has to be written out twice. A factory defined somewhere without a file - a
    lambda in a test, a class built at runtime - simply gets no directory, and
    the spec falls back to `games/<id>/`.
    """
    module = sys.modules.get(getattr(factory, '__module__', None))
    path = getattr(module, '__file__', None)
    return os.path.dirname(os.path.abspath(path)) if path else None


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
        # This game's sprite pack, not the machine's - see
        # `cabinet/renderer.py`. Sprite keys are the game's own.
        self.assets = assets
        self.font = font
        # A view of the one mixer, scoped to this game's clip names
        # (`cabinet/sound.py`). Mute and the master volume stay cabinet-wide.
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

    def handle_release(self, action):
        """The same action, let go of.

        Only games with a **held** control need this - a crouch or a charged
        shot, which on a mat is a foot standing on a panel. Nothing the
        cabinet itself draws uses releases (a menu cares when a panel goes
        down, never when it comes up), so they are delivered only to a running
        game and only while no modal is up.

        A release is not guaranteed to be paired with the press that caused it:
        a pad unplugged mid-press, or a modal opening between the two, can
        swallow one. A game must therefore treat this as "not held any more"
        rather than as an event to count, and `leave` should clear whatever it
        tracks.
        """

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

    The picker shows every installed game and each one's high scores before any
    of them has been constructed, so all of that lives here rather than on the
    `Game` itself. Nothing here touches the disk or pygame: a spec is cheap
    enough that a machine with fifty titles builds all fifty at boot.

    Everything but `id`, `title` and `factory` defaults to the convention, and
    the convention is "the file sitting beside your game.py". A spec that names
    nothing else is the normal case::

        SPEC = GameSpec(id='runner', title='RUNNER', factory=RunnerGame)
    """

    def __init__(self, id, title, factory, tagline='', preview_image=None,
                 data_file=None, package_dir=None, asset_root=None,
                 order=None, pause_ambience=None):
        self.id = id
        self.title = title
        # One line under the preview. Kept to ~32 characters: the panel is 208
        # logical pixels wide and the font cell is 6.
        self.tagline = tagline
        self.factory = factory

        # Where this game's own files live. Found from the factory's module, so
        # a game that follows the layout names no paths at all.
        self.package_dir = (package_dir or package_dir_of(factory)
                            or os.path.join(GAMES_DIR, str(id)))

        # A still picture for the picker - a PNG or JPEG, by convention
        # `preview.png` beside the game. Optional; a game without one gets its
        # title on a black panel rather than a broken box.
        #
        # A picture rather than a callback the picker would run every frame:
        # the picker is the screen an idle cabinet sits on for hours, and a
        # file is also the one part of a game anyone can replace without
        # touching code.
        self.preview_image = preview_image or os.path.join(self.package_dir,
                                                           'preview.png')

        # This game's sprites and clips, described by a `manifest.json` inside
        # it. Loaded into a pack of this game's own when it is first played -
        # see `cabinet/renderer.py`. A game with no art has no directory here
        # and simply gets an empty pack.
        self.asset_root = asset_root or os.path.join(self.package_dir, 'assets')

        # Pac-Man keeps `data/data.json` so one file can still be shared with
        # the Node version; anything new gets `data/scores/<id>.json`.
        self.data_file = data_file or data_file_for(id)

        # Where the picker lists it. Left unset, games sort by title, which is
        # the only order that stays stable as folders come and go; set it to
        # pin a favourite to the top of the machine.
        self.order = order

        # This game's name for the clip that loops while it is paused, if it
        # has one. The mixer restores ambience on unmute, so it has to be told
        # rather than asked - and it is per game, since the machine must not
        # play one game's pause loop over another's (`cabinet/sound.py`).
        self.pause_ambience = pause_ambience

    @property
    def sound_prefix(self):
        """This game's audio namespace, so two games may both ship a `jump`."""
        return f'{self.id}/'

    def create(self, context):
        return self.factory(context)

    def sort_key(self):
        """Explicitly-ordered games first, in that order, then by title."""
        return (0, self.order, '') if self.order is not None else (1, 0, self.title)

    def __repr__(self):
        return f'<GameSpec {self.id} {os.path.basename(self.data_file)}>'
