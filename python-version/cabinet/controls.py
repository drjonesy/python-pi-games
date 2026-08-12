"""What the on-screen hints call the controls.

The cabinet is played two ways - at a desk on a keyboard, and on the mat - and
the hints were written for the first: PRESS ENTER, ESC PAUSE, Q SOUND. None of
that means anything to someone standing on a dance mat.

This is **labelling only**. Both input paths stay live whichever scheme is
selected, so picking the wrong one can never lock anyone out of a machine with
no keyboard attached - the worst case is misleading text. That is deliberate:
the choice is reachable from the operator menu, which is itself reachable only
from the mat or from Ctrl-R.

The pad labels name the panel a player is standing on rather than the action it
is bound to, because that is what is printed on the mat. Note PAUSE is the
SELECT panel: on the main menu that panel opens the operator menu instead, but
the hint describes play, where it does pause.
"""

from . import settings

KEYBOARD = 'keyboard'
PAD = 'pad'

SETTINGS_KEY = 'controller'


class ControlScheme:
    """The labels one input style uses. Two instances, both below."""

    def __init__(self, key, label, start, pause, sound, sound_icon, move, pick,
                 menu_pick, cancel, confirm, back=None):
        self.key = key              # persisted value
        self.label = label          # how the operator menu lists it
        self.start = start          # main menu: PRESS <start>
        self.pause = pause          # main menu hint: <pause> PAUSE
        # Both None on a scheme with no sound control, which is what the pad is
        # since the square panel was unbound. Callers must handle that rather
        # than print an empty pair of brackets.
        self.sound = sound          # main menu hint: <sound> SOUND
        # The same control as `sound`, drawn rather than spelled, for the
        # in-game hint where there is no room for a word. A key keeps its
        # letter; a mat panel becomes the shape printed on it.
        self.sound_icon = sound_icon
        self.move = move            # name entry: <move> MOVE
        self.pick = pick            # name entry: <pick> PICK
        self.menu_pick = menu_pick  # operator menu: <menu_pick> PICKS
        self.cancel = cancel        # operator menu: <cancel> CANCELS
        self.confirm = confirm      # operator menu: PRESS <confirm> TO CONFIRM
        # A game's title screen: <back> = GAMES, the way back to the picker.
        # None on a scheme that has no spare control for it - the mat has not
        # got one, so under that scheme the route back is the CHANGE GAME row
        # in the operator menu and the hint is dropped rather than lying.
        self.back = back


SCHEMES = {
    KEYBOARD: ControlScheme(
        key=KEYBOARD, label='KEYBOARD',
        start='ENTER', pause='ESC', sound='Q', sound_icon='Q',
        move='ARROWS', pick='ENTER',
        menu_pick='ENTER', cancel='ESC', confirm='ENTER',
        back='ESC',
    ),
    PAD: ControlScheme(
        key=PAD, label='DDR PAD',
        # START and the circle panel both drive `select`; START is the one
        # printed on the mat, so that is what the hint says.
        #
        # `sound` is None because the mat has no sound *control* any more: the
        # square panel used to mute, but it is a corner panel and feet moving
        # between the arrows kept clipping it, so sound moved into the operator
        # menu. The hint drops the bracketed control and keeps the speaker as a
        # bare state indicator - see `ui/hints.sound_hint`.
        start='START', pause='SELECT', sound=None, sound_icon=None,
        move='ARROWS', pick='START',
        menu_pick='SELECT', cancel='SELECT', confirm='START',
        # No spare panel: SELECT already opens the operator menu on a title
        # screen, which is where CHANGE GAME lives.
        back=None,
    ),
}

# Order shown in the operator menu.
SCHEME_ORDER = (KEYBOARD, PAD)

DEFAULT_SCHEME = KEYBOARD


def load_choice(path=None):
    """The saved scheme name, or the default if there is not a usable one."""
    stored = settings.read(path or settings.SETTINGS_FILE).get(SETTINGS_KEY)
    return stored if stored in SCHEMES else DEFAULT_SCHEME


class Controls:
    """The active scheme, shared by every screen that draws a hint.

    Mutated in place rather than replaced so the UI objects can hold a reference
    to it and pick up a change without being rebuilt.
    """

    def __init__(self, name=None, path=None):
        self.path = path
        self.name = name if name in SCHEMES else load_choice(path)

    @property
    def scheme(self):
        return SCHEMES[self.name]

    @property
    def is_pad(self):
        return self.name == PAD

    def select(self, name):
        """Switches scheme and persists it. Unknown names are ignored.

        A failed write is not surfaced: the label change still applies for this
        session, which is the part the player asked for.
        """
        if name not in SCHEMES or name == self.name:
            return False

        self.name = name
        settings.update({SETTINGS_KEY: name}, self.path or settings.SETTINGS_FILE)
        return True
