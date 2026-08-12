"""Pad binding resolution.

The pad is the only input path the player cannot fall back from - if a dance
mat is the whole cabinet, a mapping file that fails to parse means an unplayable
machine. So the cases pinned here are the ones that would strand it: a corrupt
or hand-mangled file, an axis that re-fires while a panel is held, and a mat
that reports one panel on two controls at once.
"""

import json
import os

import pygame
import pytest

from cabinet.gamepad import (
    DEFAULT_DEADZONE, DEFAULT_MAPPING, MAPPING_FILE, GamepadManager,
    binding_key, describe_binding, load_mapping, save_mapping,
)

pygame.init()


def event(kind, **attrs):
    attrs.setdefault('instance_id', 0)
    return pygame.event.Event(kind, attrs)


def manager(bindings, **extra):
    mapping = {'version': 1, 'bindings': bindings}
    mapping.update(extra)
    return GamepadManager(mapping)


# -- binding parsing ---------------------------------------------------------

@pytest.mark.parametrize('binding, expected', [
    ({'type': 'button', 'button': 3}, ('button', 3)),
    ({'type': 'hat', 'hat': 0, 'axis': 'y', 'value': 1}, ('hat', 0, 'y', 1)),
    # A hat value arrives as -1/1, but a hand-written file may hold any
    # magnitude; only the sign is meaningful.
    ({'type': 'hat', 'hat': 1, 'axis': 'x', 'value': -7}, ('hat', 1, 'x', -1)),
    ({'type': 'axis', 'axis': 1, 'value': -1}, ('axis', 1, -1)),
    ({'type': 'key', 'key': 'w'}, ('key', 'w')),
])
def test_binding_key_parses(binding, expected):
    assert binding_key(binding) == expected


@pytest.mark.parametrize('binding', [
    {},
    {'type': 'button'},
    {'type': 'button', 'button': 'x'},
    {'type': 'hat', 'hat': 0, 'axis': 'z', 'value': 1},
    {'type': 'nonsense', 'button': 1},
    'not a dict',
    None,
])
def test_malformed_bindings_are_dropped_not_raised(binding):
    assert binding_key(binding) is None
    assert describe_binding(binding) == '<invalid>'


def test_manager_ignores_malformed_entries_but_keeps_the_rest():
    pads = manager({
        'up': [{'type': 'hat'}, {'type': 'button', 'button': 4}],
        'select': ['junk'],
        'not_an_action': [{'type': 'button', 'button': 5}],
    })
    assert pads.handle(event(pygame.JOYBUTTONDOWN, button=4)) == ('up',)
    assert pads.handle(event(pygame.JOYBUTTONDOWN, button=5)) == ()


# -- events ------------------------------------------------------------------

def test_hat_reports_both_axes_at_once():
    """A mat pressed on two panels sends one hat event carrying both."""
    pads = GamepadManager(DEFAULT_MAPPING)
    actions = pads.handle(event(pygame.JOYHATMOTION, hat=0, value=(-1, 1)))
    assert set(actions) == {'left', 'up'}


def test_hat_centre_is_not_a_press():
    pads = GamepadManager(DEFAULT_MAPPING)
    assert pads.handle(event(pygame.JOYHATMOTION, hat=0, value=(0, 0))) == ()


#: An analogue stick or an axis-reporting mat - which the measured mat is not,
#: so these cannot lean on DEFAULT_MAPPING.
AXIS_MAPPING = {
    'left': [{'type': 'axis', 'axis': 0, 'value': -1}],
    'right': [{'type': 'axis', 'axis': 0, 'value': 1}],
    'up': [{'type': 'axis', 'axis': 1, 'value': -1}],
}


def test_axis_fires_once_per_crossing_not_per_sample():
    """Held panels stream axis events; only the crossing is a direction change.

    Without this, standing on LEFT would re-issue `change_direction` every
    frame, which is harmless for movement but re-arms the turn buffer
    constantly and makes the pad feel like it is fighting the player.
    """
    pads = manager(AXIS_MAPPING)
    held = event(pygame.JOYAXISMOTION, axis=0, value=-1.0)

    assert pads.handle(held) == ('left',)
    assert pads.handle(held) == ()
    assert pads.handle(event(pygame.JOYAXISMOTION, axis=0, value=-0.9)) == ()
    # Released, then stepped on again.
    assert pads.handle(event(pygame.JOYAXISMOTION, axis=0, value=0.0)) == ()
    assert pads.handle(held) == ('left',)


def test_axis_below_the_deadzone_is_not_a_press():
    pads = manager(AXIS_MAPPING)
    assert pads.handle(event(pygame.JOYAXISMOTION, axis=0, value=-0.4)) == ()


def test_axis_state_is_tracked_per_device():
    """Two pads on one cabinet must not cancel each other's crossings."""
    pads = manager(AXIS_MAPPING)
    assert pads.handle(
        event(pygame.JOYAXISMOTION, axis=0, value=-1.0, instance_id=0),
    ) == ('left',)
    assert pads.handle(
        event(pygame.JOYAXISMOTION, axis=0, value=-1.0, instance_id=1),
    ) == ('left',)


def test_one_control_can_drive_two_actions():
    pads = manager({
        'up': [{'type': 'button', 'button': 2}],
        'select': [{'type': 'button', 'button': 2}],
    })
    assert set(pads.handle(event(pygame.JOYBUTTONDOWN, button=2))) == {
        'up', 'select',
    }


def test_one_panel_bound_on_both_hat_and_axis():
    """What --calibrate records for a mat that reports a panel twice."""
    pads = manager({'up': [
        {'type': 'hat', 'hat': 0, 'axis': 'y', 'value': 1},
        {'type': 'axis', 'axis': 1, 'value': -1},
    ]})
    assert pads.handle(event(pygame.JOYHATMOTION, hat=0, value=(0, 1))) == ('up',)
    assert pads.handle(event(pygame.JOYAXISMOTION, axis=1, value=-1.0)) == ('up',)


def test_key_bindings_are_empty_unless_the_mapping_asks_for_them():
    """The game's own WASD/arrows must not be shadowed by a default."""
    pads = GamepadManager(DEFAULT_MAPPING)
    assert pads.key_actions(event(pygame.KEYDOWN, key=pygame.K_w)) == ()


def test_key_bindings_resolve_for_keyboard_hid_mats():
    pads = manager({'up': [{'type': 'key', 'key': 'w'}]})
    assert pads.key_actions(event(pygame.KEYDOWN, key=pygame.K_w)) == ('up',)
    assert pads.key_actions(event(pygame.KEYDOWN, key=pygame.K_s)) == ()


def test_unmapped_event_types_are_inert():
    pads = GamepadManager(DEFAULT_MAPPING)
    assert pads.handle(event(pygame.JOYBUTTONUP, button=0)) == ()


# -- deadzone ----------------------------------------------------------------

@pytest.mark.parametrize('value, expected', [
    (0.2, 0.2),
    ('nonsense', DEFAULT_DEADZONE),
    (None, DEFAULT_DEADZONE),
    (0, 0.05),      # a zero deadzone would latch on sensor noise
    (5, 0.95),      # past full deflection the axis could never fire
])
def test_deadzone_is_clamped_to_something_usable(value, expected):
    assert manager({}, deadzone=value).deadzone == expected


# -- the file ----------------------------------------------------------------

def test_missing_file_falls_back_to_the_default_mapping(tmp_path):
    assert load_mapping(str(tmp_path / 'absent.json')) == DEFAULT_MAPPING


@pytest.mark.parametrize('contents', [
    '{ not json',
    '[]',
    '"a string"',
    '{"version": 1}',                  # no bindings at all
    '{"version": 1, "bindings": []}',  # bindings of the wrong type
])
def test_unusable_file_falls_back_rather_than_raising(tmp_path, contents):
    path = tmp_path / 'pad.json'
    path.write_text(contents, encoding='utf-8')
    assert load_mapping(str(path)) == DEFAULT_MAPPING


def test_save_then_load_round_trips(tmp_path):
    path = str(tmp_path / 'nested' / 'pad.json')
    mapping = {
        'version': 1,
        'device': 'USB Gamepad',
        'deadzone': 0.4,
        'bindings': {'select': [{'type': 'button', 'button': 9}]},
    }
    save_mapping(mapping, path)

    assert load_mapping(path) == mapping
    # Written via a temp file that must not be left behind.
    assert not os.path.exists(f'{path}.tmp')


def test_saved_file_is_valid_json_with_a_trailing_newline(tmp_path):
    path = str(tmp_path / 'pad.json')
    save_mapping(DEFAULT_MAPPING, path)
    raw = open(path, encoding='utf-8').read()
    assert raw.endswith('\n')
    assert json.loads(raw) == DEFAULT_MAPPING


# -- the measured mat --------------------------------------------------------

#: Recorded off the cabinet's own mat with `tools/pad_report.py` - a DragonRise
#: 0079:0006 board wired so that all ten panels report as plain buttons.
#:
#: `None` means the panel is wired and reports, but drives no action. The square
#: and triangle panels are deliberately in that state - see
#: `test_no_shape_panel_acts_during_play`.
MEASURED_PANELS = {
    0: ('LEFT arrow', 'left'),
    1: ('DOWN arrow', 'down'),
    2: ('UP arrow', 'up'),
    3: ('RIGHT arrow', 'right'),
    4: ('SQUARE panel', None),
    5: ('TRIANGLE panel', None),
    6: ('CROSS panel', 'delete'),
    7: ('CIRCLE panel', 'select'),
    8: ('SELECT', 'pause'),
    9: ('START', 'select'),
}


@pytest.mark.parametrize('button, panel, action', [
    (b, name, action) for b, (name, action) in MEASURED_PANELS.items()
])
def test_default_mapping_matches_the_measured_mat(button, panel, action):
    pads = GamepadManager(DEFAULT_MAPPING)
    expected = () if action is None else (action,)
    assert pads.handle(event(pygame.JOYBUTTONDOWN, button=button)) == expected, (
        f'{panel} (button {button}) should be {action or "unbound"}'
    )


#: The four mat corners. Nothing that acts during play may be bound to one.
SHAPE_BUTTONS = (4, 5, 6, 7)

#: What a shape panel is still allowed to drive: both are no-ops outside the
#: name-entry modal and the main menu, so a clipped corner mid-run does nothing.
HARMLESS_DURING_PLAY = frozenset({'select', 'delete'})


@pytest.mark.parametrize('mapping_name', ['default', 'committed'])
def test_no_shape_panel_acts_during_play(mapping_name):
    """The shapes are the mat's *corners*, sharing an edge with the arrows.

    A foot travelling between left and down clips the corner between them, so
    anything bound there fires by accident mid-run. Triangle used to be a second
    `pause` and square used to be `mute`; both are unbound now. The shapes are
    still read as `panels` for the operator menu passcode, which is a different
    table and only reachable from the main menu.
    """
    mapping = (DEFAULT_MAPPING if mapping_name == 'default'
               else load_mapping(MAPPING_FILE))
    pads = GamepadManager(mapping)

    for button in SHAPE_BUTTONS:
        actions = pads.handle(event(pygame.JOYBUTTONDOWN, button=button))
        assert set(actions) <= HARMLESS_DURING_PLAY, (
            f'button {button} drives {actions} during play'
        )


@pytest.mark.parametrize('mapping_name', ['default', 'committed'])
def test_select_is_the_only_pause(mapping_name):
    """Which is what the on-screen hint has always said - see `ui/hints.py`."""
    mapping = (DEFAULT_MAPPING if mapping_name == 'default'
               else load_mapping(MAPPING_FILE))
    pads = GamepadManager(mapping)

    paused = [button for button in range(12)
              if 'pause' in pads.handle(event(pygame.JOYBUTTONDOWN, button=button))]
    assert paused == [8], 'only the SELECT panel may pause'


@pytest.mark.parametrize('mapping_name', ['default', 'committed'])
def test_the_mat_has_no_mute(mapping_name):
    """Unbinding square left the mat with no sound control at all.

    Deliberate, and the pad hint stops naming one to match (`controls.py`). The
    keyboard's Q is untouched - it is wired directly in `main.py` rather than
    through this table.
    """
    mapping = (DEFAULT_MAPPING if mapping_name == 'default'
               else load_mapping(MAPPING_FILE))
    pads = GamepadManager(mapping)

    for button in range(12):
        assert 'mute' not in pads.handle(event(pygame.JOYBUTTONDOWN, button=button))


def test_nothing_is_bound_to_an_axis_by_default():
    """The mat's CENTRE panel reports on axis 1, and the player stands there.

    Measured with `tools/pad_report.py`: stepping on the centre of the mat
    sends `axis 1 +1.0` and releasing returns it to 0. That is the neutral
    position between moves, so anything bound to an axis would fire every few
    seconds during normal play - and `axis 1 +` is exactly what a naive `down`
    binding would have used.
    """
    for action, entries in DEFAULT_MAPPING['bindings'].items():
        kinds = {binding['type'] for binding in entries}
        assert 'axis' not in kinds, f'{action} is bound to an axis'


def test_centre_panel_does_nothing():
    """Standing on the middle of the mat must not reach the game."""
    for mapping in (DEFAULT_MAPPING, load_mapping(MAPPING_FILE)):
        pads = GamepadManager(mapping)
        assert pads.handle(event(pygame.JOYAXISMOTION, axis=1, value=1.0)) == ()
        assert pads.handle(event(pygame.JOYAXISMOTION, axis=1, value=0.0)) == ()


def test_committed_mapping_matches_the_measured_mat():
    """`data/pad_mapping.json` is the cabinet's real config and is committed.

    It is checked here rather than trusted, because a bad edit to it would be
    silent - `load_mapping` deliberately falls back instead of raising.
    """
    pads = GamepadManager(load_mapping(MAPPING_FILE))
    for button, (panel, action) in MEASURED_PANELS.items():
        expected = () if action is None else (action,)
        assert pads.handle(event(pygame.JOYBUTTONDOWN, button=button)) == expected, (
            f'{panel} (button {button}) should be {action or "unbound"}'
        )


def test_spare_button_indices_do_nothing():
    """The board reports 12 buttons; the mat only wires 10."""
    pads = GamepadManager(DEFAULT_MAPPING)
    assert pads.handle(event(pygame.JOYBUTTONDOWN, button=10)) == ()
    assert pads.handle(event(pygame.JOYBUTTONDOWN, button=11)) == ()


def test_default_mapping_only_names_real_actions():
    from cabinet.gamepad import ACTIONS
    assert set(DEFAULT_MAPPING['bindings']) <= set(ACTIONS)
    assert 'quit' not in ACTIONS      # a stray panel must not close the game


def test_device_filter_is_off_by_default():
    assert DEFAULT_MAPPING['device'] is None
    pads = GamepadManager(DEFAULT_MAPPING)
    assert pads._accepts(0) is True
