"""USB gamepads, arcade encoders and DDR dance pads.

Every pad numbers its controls differently. A cheap USB dance mat may report
its four arrows on a hat, on axes 0/1, as four plain buttons, or - on the mats
that enumerate as an HID *keyboard* rather than a gamepad - as key presses. The
shape and SELECT/START panels land on whatever button indices the pad's
firmware happened to pick.

So the binding table is data, not code: it lives in ``data/pad_mapping.json``,
and [`tools/gamepad_test.py`](../tools/gamepad_test.py) writes that file by
asking you to step on each panel in turn. ``DEFAULT_MAPPING`` below is only
what is used until you run it.

Bindings resolve to the same small set of actions the keyboard already drives
(direction + select + delete + pause + mute), so nothing downstream has to know
a pad exists. Quit is deliberately *not* in that set - no single panel press may
close the game (README "Dance pad / gamepad / arcade encoder"). A pad can still
reach EXIT GAME, but only through the operator menu in `ui/system_menu.py`,
which opens on SELECT from the main menu and needs a selection to act on.

That menu also needs to know which *panel* was pressed rather than what it
does, so alongside `bindings` there is a `panels` table. See `PANELS`.
"""

import json
import os

import pygame

ACTIONS = (
    'up', 'down', 'left', 'right', 'select', 'delete', 'pause', 'mute',
)

# Physical panels, kept in a namespace of their own because the operator menu
# has to know *which control* was pressed, not what it does. The two are not
# interchangeable: on this mat the panel labelled SELECT drives the `pause`
# action, and the `select` action is driven by START and the circle panel. So
# `PANELS`'s 'select' and `ACTIONS`'s 'select' are different things - the
# operator menu (`ui/system_menu.py`) needs the panel, the game wants the
# action. That divergence is also what makes the SELECT *panel* free to open
# that menu: `pause` does nothing on the main menu, while the `select` *action*
# starts a game.
PANELS = ('select', 'start', 'cross', 'square', 'triangle', 'circle')

MAPPING_FILE = os.path.join(
    os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
    'data', 'pad_mapping.json',
)

# An axis has to travel this far from centre before it counts as a direction.
# Dance mats are on/off switches, so they slam to +-1; the deadzone only
# matters for analogue sticks.
DEFAULT_DEADZONE = 0.5

# Measured on the target cabinet's mat: a DragonRise/Microntek PSX-to-USB board
# (USB 0079:0006, kernel name "Microntek USB Joystick") wired to a 10-panel mat.
#
# The mat reports **all ten panels as plain buttons**. Its descriptor also
# advertises a hat and four axes, but nothing on the mat drives them - a PSX
# controller's would-be d-pad and sticks simply have nothing soldered to them.
# So the arrow panels are buttons 0-3, not the hat that a gamepad would use:
#
#   0 LEFT    1 DOWN    2 UP    3 RIGHT      <- the four arrows
#   4 square  5 tri     6 cross 7 circle     <- the four shape panels
#   8 SELECT  9 START                        (10 and 11 exist but are unused)
#
# That arrow order is not arbitrary: on a PlayStation dance mat the arrows *are*
# the face buttons, and the corner shape panels get the shoulder indices.
#
# Nothing that acts *during play* is bound to a shape panel, because those four
# are the mat's corners and a foot travelling between arrows clips them. They
# are still read as `panels` for the operator menu's passcode, which is only
# reachable from the main menu - see `PANELS` and `ui/system_menu.py`.
#
# Hat bindings are kept alongside so an ordinary gamepad or arcade encoder still
# works out of the box. Axis bindings are deliberately absent: this board parks
# its unused analogue axes at full deflection often enough that binding a
# direction to one can steer the game on its own. A pad that genuinely needs
# them can say so in `data/pad_mapping.json`, which overrides all of this.
DEFAULT_MAPPING = {
    'version': 1,
    'device': None,
    'deadzone': DEFAULT_DEADZONE,
    'bindings': {
        'up': [
            {'type': 'button', 'button': 2},
            {'type': 'hat', 'hat': 0, 'axis': 'y', 'value': 1},
        ],
        'down': [
            {'type': 'button', 'button': 1},
            {'type': 'hat', 'hat': 0, 'axis': 'y', 'value': -1},
        ],
        'left': [
            {'type': 'button', 'button': 0},
            {'type': 'hat', 'hat': 0, 'axis': 'x', 'value': -1},
        ],
        'right': [
            {'type': 'button', 'button': 3},
            {'type': 'hat', 'hat': 0, 'axis': 'x', 'value': 1},
        ],
        'select': [
            {'type': 'button', 'button': 9},   # START
            {'type': 'button', 'button': 7},   # circle panel
        ],
        'delete': [
            {'type': 'button', 'button': 6},   # cross panel
        ],
        # SELECT only. The triangle panel used to be a second pause binding,
        # carried over from the gamepad layout this table started as - but on a
        # mat the shape panels are *corners*, sharing an edge with the arrows a
        # player's feet are already moving between. Clipping the corner of
        # triangle on the way to left or down paused the game mid-run, which
        # read as random because two things hide the cause: `allow_pause` is
        # false through the READY! text so an early clip does nothing, and the
        # in-game hint only ever named SELECT. SELECT is a mat edge panel, so it
        # takes a deliberate step.
        'pause': [
            {'type': 'button', 'button': 8},   # SELECT
        ],
        # Empty for the same reason: the square panel is the corner between the
        # left and down arrows, and clipping it silently toggled the sound. The
        # keyboard's Q still mutes - it is wired directly in `main.py`, not
        # through this table - so a desk setup is unaffected. A mat that wants
        # the panel back can say so in `data/pad_mapping.json`.
        'mute': [],
    },
    # Physical panels, straight off the layout comment above. Only buttons and
    # keys are honoured here - a combo entered on an analogue axis would be at
    # the mercy of the same spurious deflection that keeps axes out of
    # `bindings`. A pad that numbers its panels differently can override this
    # with a `panels` block in `data/pad_mapping.json`; the calibration tool
    # does not write one, so these defaults stand unless edited by hand.
    'panels': {
        'select': [{'type': 'button', 'button': 8}],
        'start': [{'type': 'button', 'button': 9}],
        'square': [{'type': 'button', 'button': 4}],
        'triangle': [{'type': 'button', 'button': 5}],
        'cross': [{'type': 'button', 'button': 6}],
        'circle': [{'type': 'button', 'button': 7}],
    },
}


def _sign(value):
    return -1 if value < 0 else 1 if value > 0 else 0


def binding_key(binding):
    """The hashable form a binding is looked up by, or None if malformed.

    A hand-edited mapping file must not be able to crash the game, so anything
    that does not parse is dropped rather than raised.
    """
    try:
        kind = binding['type']
        if kind == 'button':
            return ('button', int(binding['button']))
        if kind == 'hat':
            axis = binding['axis']
            if axis not in ('x', 'y'):
                return None
            return ('hat', int(binding['hat']), axis, _sign(binding['value']))
        if kind == 'axis':
            return ('axis', int(binding['axis']), _sign(binding['value']))
        if kind == 'key':
            return ('key', str(binding['key']))
    except (KeyError, TypeError, ValueError):
        return None
    return None


def describe_binding(binding):
    """A human-readable label for the calibration tool and its output."""
    key = binding_key(binding)
    if key is None:
        return '<invalid>'
    if key[0] == 'button':
        return f'button {key[1]}'
    if key[0] == 'hat':
        _, hat, axis, value = key
        arrow = {
            ('x', -1): 'left', ('x', 1): 'right',
            ('y', -1): 'down', ('y', 1): 'up',
        }[(axis, value)]
        return f'hat {hat} {arrow}'
    if key[0] == 'axis':
        return f'axis {key[1]} {"-" if key[2] < 0 else "+"}'
    return f'key {key[1]}'


def key_binding(pygame_key):
    """A `key` binding for a pygame key constant, e.g. K_UP -> `{"key": "up"}`.

    ``pygame.key.name`` is used rather than the constant's number so the file
    stays readable and survives an SDL renumbering.
    """
    return {'type': 'key', 'key': pygame.key.name(pygame_key)}


def load_mapping(path=MAPPING_FILE):
    """The saved mapping, or ``DEFAULT_MAPPING`` if there is not a usable one.

    Same rule as the leaderboard: a missing or corrupt file is a fallback, not
    an error. The game must always be playable.
    """
    if not path or not os.path.exists(path):
        return dict(DEFAULT_MAPPING)

    try:
        with open(path, encoding='utf-8') as handle:
            parsed = json.load(handle)
    except (OSError, ValueError):
        return dict(DEFAULT_MAPPING)

    if not isinstance(parsed, dict) or not isinstance(parsed.get('bindings'), dict):
        return dict(DEFAULT_MAPPING)

    return parsed


def save_mapping(mapping, path=MAPPING_FILE):
    """Atomic write, for the same reason the leaderboard uses one."""
    os.makedirs(os.path.dirname(path) or '.', exist_ok=True)
    tmp = f'{path}.tmp'

    with open(tmp, 'w', encoding='utf-8') as handle:
        json.dump(mapping, handle, indent=2)
        handle.write('\n')
        handle.flush()
        os.fsync(handle.fileno())

    os.replace(tmp, path)


class GamepadManager:
    """Opens pads, tracks hotplug, and turns their events into actions."""

    # Devices are opened in response to JOYDEVICEADDED, which SDL also emits
    # for anything already plugged in - so a pad connected after launch works
    # the same as one connected before it.
    EVENT_TYPES = frozenset({
        pygame.JOYDEVICEADDED, pygame.JOYDEVICEREMOVED,
        pygame.JOYBUTTONDOWN, pygame.JOYHATMOTION, pygame.JOYAXISMOTION,
    })

    def __init__(self, mapping=None):
        self.mapping = mapping if mapping is not None else DEFAULT_MAPPING
        self.deadzone = self._read_deadzone()
        self.device_filter = (self.mapping.get('device') or '').strip().lower()

        self.joysticks = {}          # instance_id -> Joystick
        self._axis_state = {}        # (instance_id, axis) -> -1 | 0 | 1
        self._lookup = {}            # binding key -> tuple of actions
        self._panel_lookup = {}      # binding key -> tuple of panel names
        self._build_lookup()
        self._build_panel_lookup()

    def _read_deadzone(self):
        try:
            deadzone = float(self.mapping.get('deadzone', DEFAULT_DEADZONE))
        except (TypeError, ValueError):
            return DEFAULT_DEADZONE
        # A deadzone at or past full deflection would make the axis unusable.
        return min(max(deadzone, 0.05), 0.95)

    def _build_lookup(self):
        bindings = self.mapping.get('bindings') or {}
        for action in ACTIONS:
            for binding in bindings.get(action) or ():
                key = binding_key(binding)
                if key is None:
                    continue
                # One control may drive more than one action; the mapping file
                # is hand-editable and nothing here should silently drop half
                # of what it says.
                self._lookup[key] = self._lookup.get(key, ()) + (action,)

    def _build_panel_lookup(self):
        """The same table again, keyed by physical panel instead of action.

        Falls back to the defaults when the mapping file has no `panels` block,
        which is the normal case: `tools/gamepad_test.py --calibrate` only
        writes `bindings`.
        """
        panels = self.mapping.get('panels') or DEFAULT_MAPPING['panels']
        if not isinstance(panels, dict):
            panels = DEFAULT_MAPPING['panels']

        for panel in PANELS:
            for binding in panels.get(panel) or ():
                key = binding_key(binding)
                # Axes and hats are refused rather than silently accepted: see
                # the note on DEFAULT_MAPPING['panels'].
                if key is None or key[0] not in ('button', 'key'):
                    continue
                self._panel_lookup[key] = (
                    self._panel_lookup.get(key, ()) + (panel,)
                )

    # -- devices -------------------------------------------------------------

    def open_all(self):
        """Opens every pad present now.

        Redundant with the JOYDEVICEADDED events SDL queues at init, but those
        are only delivered once the loop starts pumping - and calibration wants
        the device list before then.
        """
        if not pygame.joystick.get_init():
            pygame.joystick.init()
        for index in range(pygame.joystick.get_count()):
            self._open(index)
        return self

    def _open(self, device_index):
        try:
            stick = pygame.joystick.Joystick(device_index)
        except pygame.error:
            return None
        # No stick.init(): pygame-ce opens a Joystick on construction and has
        # deprecated the explicit call since 2.4.
        self.joysticks[stick.get_instance_id()] = stick
        return stick

    def _close(self, instance_id):
        stick = self.joysticks.pop(instance_id, None)
        if stick is not None:
            try:
                stick.quit()
            except pygame.error:
                pass
        for key in [k for k in self._axis_state if k[0] == instance_id]:
            del self._axis_state[key]

    def device_names(self):
        return [stick.get_name() for stick in self.joysticks.values()]

    def _accepts(self, instance_id):
        """Honours the mapping's optional `device` name filter.

        Left unset by default: with one pad plugged in, filtering by name only
        creates a way for the game to ignore it.
        """
        if not self.device_filter:
            return True
        stick = self.joysticks.get(instance_id)
        if stick is None:
            return True
        return self.device_filter in stick.get_name().lower()

    # -- events --------------------------------------------------------------

    def handle(self, event):
        """The actions `event` triggers, as a tuple (usually empty or one)."""
        if event.type == pygame.JOYDEVICEADDED:
            self._open(event.device_index)
            return ()
        if event.type == pygame.JOYDEVICEREMOVED:
            self._close(event.instance_id)
            return ()

        if not self._accepts(getattr(event, 'instance_id', None)):
            return ()

        if event.type == pygame.JOYBUTTONDOWN:
            return self._lookup.get(('button', event.button), ())

        if event.type == pygame.JOYHATMOTION:
            x, y = event.value
            actions = ()
            if x:
                actions += self._lookup.get(
                    ('hat', event.hat, 'x', _sign(x)), (),
                )
            if y:
                actions += self._lookup.get(
                    ('hat', event.hat, 'y', _sign(y)), (),
                )
            return actions

        if event.type == pygame.JOYAXISMOTION:
            # Axes report continuously, so only the crossing into a direction
            # counts - otherwise a panel held down would re-fire every frame.
            state_key = (event.instance_id, event.axis)
            if event.value < -self.deadzone:
                sign = -1
            elif event.value > self.deadzone:
                sign = 1
            else:
                sign = 0

            if sign == self._axis_state.get(state_key, 0):
                return ()
            self._axis_state[state_key] = sign
            if sign == 0:
                return ()
            return self._lookup.get(('axis', event.axis, sign), ())

        return ()

    def panels(self, event):
        """Which physical panels `event` is, ignoring what they are bound to.

        Buttons only - `handle` owns the axis edge-detection state, and calling
        both for one event would consume that edge twice.
        """
        if event.type != pygame.JOYBUTTONDOWN:
            return ()
        if not self._accepts(getattr(event, 'instance_id', None)):
            return ()
        return self._panel_lookup.get(('button', event.button), ())

    def key_panels(self, event):
        """`panels`, for a mat that enumerates as an HID keyboard."""
        return self._panel_lookup.get(('key', pygame.key.name(event.key)), ())

    def key_actions(self, event):
        """Actions bound to a keyboard key, for mats that enumerate as an HID
        keyboard instead of a gamepad.

        Empty unless the mapping file actually contains `key` bindings, so the
        game's own keyboard controls are untouched by default.
        """
        return self._lookup.get(('key', pygame.key.name(event.key)), ())
