"""The SELECT operator menu.

Two things here can strand a cabinet with no keyboard attached, so both are
pinned: the menu must always have a way out (every stage backs out to the game),
and RESET SCORES must be unreachable without the full code in the right order.

The panel table gets its own coverage because the menu is driven by physical
panels while the game is driven by actions, and the two disagree about what
'select' means - see `test_panels_resolve_independently_of_actions`.
"""

import pygame
import pytest

from cabinet.controls import KEYBOARD, PAD, SCHEME_ORDER, Controls
from cabinet.gamepad import DEFAULT_MAPPING, GamepadManager
from cabinet.leaderboard import Leaderboard
from cabinet.ui.system_menu import (
    CODE_PANELS, DEFAULT_CODE, DONE_MS, IDLE_TIMEOUT_MS, OPTIONS,
    RESULT_CLEARED, RESULT_INCORRECT, STAGE_CODE, STAGE_CONFIRM,
    STAGE_DONE, STAGE_OPTIONS, SystemMenu, load_code,
)

pygame.init()


def event(kind, **attrs):
    attrs.setdefault('instance_id', 0)
    return pygame.event.Event(kind, attrs)


class FakeLeaderboard:
    def __init__(self):
        self.reset_calls = 0

    def reset(self):
        self.reset_calls += 1
        return []


@pytest.fixture
def board():
    return FakeLeaderboard()


@pytest.fixture
def controls(tmp_path):
    # An explicit name and a throwaway path: never reads or writes the real
    # data/settings.json, so these tests do not depend on machine state.
    return Controls(name=KEYBOARD, path=str(tmp_path / 'settings.json'))


class StubSound:
    """Just the surface `SystemMenu` touches, and a call count.

    The real `SoundManager.toggle_mute` also writes `data/settings.json`, which
    these tests must not go near.
    """

    def __init__(self, master_volume=1):
        self.master_volume = master_volume
        self.toggle_calls = 0

    def toggle_mute(self):
        self.toggle_calls += 1
        self.master_volume = 0 if self.master_volume == 1 else 1
        return self.master_volume


@pytest.fixture
def sound():
    return StubSound()


@pytest.fixture
def menu(board, controls, sound):
    # renderer and font are only touched by draw(), which is not under test.
    return SystemMenu(None, None, board, controls=controls, sound_manager=sound)


def open_reset(menu):
    """Open the menu and step into the reset gate.

    RESET SCORES is not the first row - SOUND leads the list - so this cannot
    just select whatever the cursor starts on.
    """
    menu.open_menu()
    menu.index = option_index(menu, 'reset')
    menu.feed(panels=('select',))


def option_index(menu, name):
    """Read off the *menu's* rows, not the module's.

    They differ: `OPTIONS` is the full list, while `menu.options` drops SOUND
    when there is no sound manager to toggle.
    """
    return [key for key, _ in menu.options].index(name)


def enter_code(menu, panels=DEFAULT_CODE):
    for panel in panels:
        menu.feed(panels=(panel,))


# -- panel resolution --------------------------------------------------------

def test_panels_resolve_independently_of_actions():
    """The mat's SELECT panel drives the `pause` action, not `select`.

    That divergence is the entire reason panels exist. It is also what makes the
    SELECT panel free to open this menu: `pause` does nothing on the main menu,
    whereas the `select` *action* - which START drives - starts a game.
    """
    pads = GamepadManager(DEFAULT_MAPPING)

    select_panel = event(pygame.JOYBUTTONDOWN, button=8)
    assert pads.panels(select_panel) == ('select',)
    assert pads.handle(select_panel) == ('pause',)

    start_panel = event(pygame.JOYBUTTONDOWN, button=9)
    assert pads.panels(start_panel) == ('start',)
    assert pads.handle(start_panel) == ('select',)


@pytest.mark.parametrize('button, panel', [
    (4, 'square'), (5, 'triangle'), (6, 'cross'), (7, 'circle'),
])
def test_shape_panels_resolve(button, panel):
    pads = GamepadManager(DEFAULT_MAPPING)
    assert pads.panels(event(pygame.JOYBUTTONDOWN, button=button)) == (panel,)


def test_panels_default_when_mapping_omits_them():
    """A file written by --calibrate has `bindings` and nothing else."""
    pads = GamepadManager({'version': 1, 'bindings': {}})
    assert pads.panels(event(pygame.JOYBUTTONDOWN, button=9)) == ('start',)


def test_panels_refuse_axis_and_hat_bindings():
    """An axis that parks at full deflection would hold a panel down forever."""
    pads = GamepadManager({
        'version': 1,
        'bindings': {},
        'panels': {
            'start': [{'type': 'axis', 'axis': 0, 'value': 1}],
            'cross': [{'type': 'hat', 'hat': 0, 'axis': 'x', 'value': 1}],
            'circle': [{'type': 'button', 'button': 7}],
        },
    })
    assert pads.panels(event(pygame.JOYAXISMOTION, axis=0, value=1.0)) == ()
    assert pads.panels(event(pygame.JOYHATMOTION, hat=0, value=(1, 0))) == ()
    assert pads.panels(event(pygame.JOYBUTTONDOWN, button=7)) == ('circle',)


# -- option list -------------------------------------------------------------

def test_opens_on_the_first_option(menu):
    menu.open_menu()
    assert menu.open
    assert menu.stage == STAGE_OPTIONS
    assert menu.index == 0


def test_arrows_navigate_and_wrap(menu):
    # `menu.options` rather than `OPTIONS`: the rows shown depend on what this
    # open can actually do - see `test_change_game_row_is_absent_on_the_picker`.
    menu.open_menu()
    menu.feed(actions=('down',))
    assert menu.index == 1
    menu.feed(actions=('up',))
    assert menu.index == 0
    menu.feed(actions=('up',))
    assert menu.index == len(menu.options) - 1


def test_exit_option_calls_the_exit_hook(menu):
    exits = []
    menu.open_menu(on_exit=lambda: exits.append(True))
    menu.index = option_index(menu, 'exit')
    menu.feed(panels=('select',))

    assert exits == [True]
    assert not menu.open


def test_cancel_option_closes_without_side_effects(menu, board):
    exits = []
    menu.open_menu(on_exit=lambda: exits.append(True))
    menu.index = option_index(menu, 'cancel')
    menu.feed(panels=('select',))

    assert not menu.open
    assert exits == []
    assert board.reset_calls == 0


def test_start_panel_does_not_pick_an_option(menu):
    """Only SELECT picks. START is the confirm for the reset gate."""
    exits = []
    menu.open_menu(on_exit=lambda: exits.append(True))
    menu.index = option_index(menu, 'exit')
    menu.feed(panels=('start',))

    assert menu.open
    assert exits == []


# -- sound -------------------------------------------------------------------
#
# The mat has no sound panel: the square panel used to mute, but it is a corner
# a moving foot clips, so it was unbound. This row is where that control went.

def test_sound_leads_the_list(menu):
    """The cursor starts on the only row that is harmless *and* routine."""
    assert option_index(menu, 'sound') == 0


def test_the_sound_row_reads_its_own_state(menu, sound):
    menu.open_menu()
    assert menu.option_label('sound', 'SOUND') == 'SOUND  ON'

    sound.master_volume = 0
    assert menu.option_label('sound', 'SOUND') == 'SOUND  OFF'


def test_choosing_sound_toggles_and_stays_open(menu, sound):
    """Unlike every other row. The label flipping under the cursor is the
    confirmation, and staying put is the way back from a mis-step."""
    menu.open_menu()
    menu.feed(panels=('select',))

    assert sound.toggle_calls == 1
    assert sound.master_volume == 0
    assert menu.open
    assert menu.stage == STAGE_OPTIONS
    assert menu.index == option_index(menu, 'sound')


def test_sound_toggles_back(menu, sound):
    menu.open_menu()
    menu.feed(panels=('select',))
    menu.feed(panels=('select',))

    assert sound.toggle_calls == 2
    assert sound.master_volume == 1


def test_toggling_sound_resets_the_idle_timeout(menu):
    """Otherwise a slow operator gets the menu shut on them mid-adjustment."""
    menu.open_menu()
    menu.tick(IDLE_TIMEOUT_MS - 1)
    menu.feed(panels=('select',))
    assert menu.idle_ms == 0

    menu.tick(IDLE_TIMEOUT_MS - 1)
    assert menu.open


def test_the_row_is_dropped_when_there_is_no_sound_manager(board, controls):
    """A dead row would be worse than a missing one - every row must do
    something. The rest of the list has to stay reachable without it."""
    menu = SystemMenu(None, None, board, controls=controls)

    keys = [key for key, _ in menu.options]
    assert 'sound' not in keys
    assert keys == [key for key, _ in OPTIONS
                    if key not in ('sound', 'change_game')]

    exits = []
    menu.open_menu(on_exit=lambda: exits.append(True))
    menu.index = option_index(menu, 'exit')
    menu.feed(panels=('select',))
    assert exits == [True]


def test_the_rows_still_fit_above_the_nav_hint():
    """Adding SOUND made this a five-row list. Pure geometry, so it needs no
    renderer - and it is the kind of thing that only shows up on the cabinet."""
    from cabinet.font import BitmapFont
    from cabinet.ui.system_menu import (
        HINT_Y, OPTIONS_Y, PANEL_GAP, PANEL_HEIGHT, PANEL_WIDTH,
    )

    bottom = OPTIONS_Y + (len(OPTIONS) - 1) * (PANEL_HEIGHT + PANEL_GAP)
    assert bottom + PANEL_HEIGHT <= HINT_Y, 'the last row overlaps the hint'

    font = BitmapFont()
    labels = [label for _, label in OPTIONS] + ['SOUND  ON', 'SOUND  OFF']
    for label in labels:
        assert font.measure(label)[0] <= PANEL_WIDTH, f'{label} overflows'


def test_navigation_wraps_over_the_menus_own_rows(board, controls):
    """`menu.options` is what wraps, not the module-level `OPTIONS` - those
    differ in length whenever the sound row is absent."""
    menu = SystemMenu(None, None, board, controls=controls)
    menu.open_menu()
    menu.feed(actions=('up',))

    assert menu.index == len(menu.options) - 1
    assert menu.options[menu.index][0] == 'cancel'


# -- change game -------------------------------------------------------------
#
# The mat has no spare panel for backing out of a game, so this row is the only
# route from a game's title screen to the picker under the pad scheme.

def test_change_game_row_is_absent_on_the_picker(menu):
    """No game to leave, so the row would do nothing. A dead row on a machine
    with no keyboard is worse than a missing one."""
    menu.open_menu()
    assert 'change_game' not in [key for key, _ in menu.options]


def test_change_game_row_appears_over_a_game(menu):
    changes = []
    menu.open_menu(on_change_game=lambda: changes.append(True))

    menu.index = option_index(menu, 'change_game')
    menu.feed(panels=('select',))

    assert changes == [True]
    assert not menu.open


def test_change_game_sits_second(menu):
    """Behind SOUND, ahead of everything destructive."""
    menu.open_menu(on_change_game=lambda: None)
    assert option_index(menu, 'change_game') == 1


def test_the_row_list_is_rebuilt_per_open(menu):
    """A menu opened over a game and then over the picker must not keep the
    row - `options` is state for one open, not for the object."""
    menu.open_menu(on_change_game=lambda: None)
    assert 'change_game' in [key for key, _ in menu.options]

    menu.close()
    menu.open_menu()
    assert 'change_game' not in [key for key, _ in menu.options]


# -- reset target ------------------------------------------------------------
#
# Every game has its own board, so this menu clears exactly one of them:
# whichever game it was opened over.

def test_open_menu_rebinds_the_board_it_would_clear(menu, board):
    other = FakeLeaderboard()
    menu.open_menu(leaderboard=other, target_label='OTHER')

    menu.index = option_index(menu, 'reset')
    menu.feed(panels=('select',))
    enter_code(menu)
    menu.feed(panels=('start',))

    assert other.reset_calls == 1
    assert board.reset_calls == 0, 'cleared the board it was opened over last'


def test_the_target_label_is_kept_for_the_confirmation(menu):
    """The gate names the board, because 'RESET HIGH SCORES' is ambiguous on a
    machine that has several of them."""
    menu.open_menu(leaderboard=FakeLeaderboard(), target_label='PAC-MAN')
    assert menu.target_label == 'PAC-MAN'


def test_omitting_the_board_keeps_the_previous_one(menu, board):
    """`open_menu()` with no board must not silently unbind the one in use -
    several tests, and the reset gate itself, rely on that."""
    menu.open_menu()
    assert menu.leaderboard is board


# -- controller picker -------------------------------------------------------

def open_controls(menu):
    menu.open_menu()
    menu.index = option_index(menu, 'controls')
    menu.feed(panels=('select',))


def test_controls_stage_starts_on_the_active_scheme(menu, controls):
    """The list doubles as a readout of what is in force."""
    controls.name = PAD
    open_controls(menu)
    assert SCHEME_ORDER[menu.index] == PAD


def test_choosing_a_scheme_switches_and_closes(menu, controls):
    open_controls(menu)
    menu.index = SCHEME_ORDER.index(PAD)
    menu.feed(panels=('select',))

    assert controls.name == PAD
    assert not menu.open


def test_choosing_the_active_scheme_is_a_harmless_exit(menu, controls):
    """The cursor starts on it, so SELECT twice is the way out of this stage."""
    open_controls(menu)
    menu.feed(panels=('select',))

    assert controls.name == KEYBOARD
    assert not menu.open


def test_the_scheme_survives_a_restart(tmp_path):
    path = str(tmp_path / 'settings.json')
    Controls(name=KEYBOARD, path=path).select(PAD)
    assert Controls(path=path).name == PAD


def test_switching_scheme_does_not_touch_the_reset_gate(menu, board, controls):
    open_controls(menu)
    menu.index = SCHEME_ORDER.index(PAD)
    menu.feed(panels=('select',))

    open_reset(menu)
    enter_code(menu)
    menu.feed(panels=('start',))
    assert board.reset_calls == 1


def test_labels_differ_between_the_two_schemes():
    from cabinet.controls import SCHEMES
    keyboard, pad = SCHEMES[KEYBOARD], SCHEMES[PAD]
    assert keyboard.start == 'ENTER' and pad.start == 'START'
    assert keyboard.pause != pad.pause
    assert keyboard.sound != pad.sound


# -- reset gate --------------------------------------------------------------

def test_full_code_then_start_clears_the_board(menu, board):
    resets = []
    menu.open_menu(on_reset=lambda: resets.append(True))
    menu.index = option_index(menu, 'reset')
    menu.feed(panels=('select',))
    assert menu.stage == STAGE_CODE

    enter_code(menu)
    assert menu.stage == STAGE_CONFIRM
    assert board.reset_calls == 0         # code alone must not clear anything

    menu.feed(panels=('start',))
    assert board.reset_calls == 1
    assert resets == [True]
    assert menu.stage == STAGE_DONE

    menu.tick(DONE_MS)
    assert not menu.open


def test_start_before_the_code_is_complete_does_nothing(menu, board):
    open_reset(menu)
    enter_code(menu, DEFAULT_CODE[:3])

    menu.feed(panels=('start',))
    assert board.reset_calls == 0
    assert menu.stage == STAGE_CODE


def wrong_code(code=DEFAULT_CODE):
    """A sequence of the same length that is not the code."""
    other = tuple(reversed(code))
    return other if other != tuple(code) else (code[0],) * len(code)


def test_a_wrong_panel_is_accepted_without_comment(menu):
    """The gate must not say *which* press was wrong.

    Rejecting per press would leak the code one position at a time - four
    guesses per slot instead of a blind search over every sequence.
    """
    open_reset(menu)

    menu.feed(panels=(wrong_code()[0],))
    assert len(menu.entered) == 1         # counted, not rejected
    assert menu.stage == STAGE_CODE       # and no visible change of state


def test_a_wrong_code_reaches_confirm_then_is_refused(menu, board):
    open_reset(menu)
    enter_code(menu, wrong_code())

    # Indistinguishable from a correct code until START is pressed.
    assert menu.stage == STAGE_CONFIRM

    menu.feed(panels=('start',))
    assert board.reset_calls == 0
    assert menu.result == RESULT_INCORRECT
    assert menu.stage == STAGE_DONE

    menu.tick(DONE_MS)
    assert not menu.open


def test_a_refused_code_cannot_be_resubmitted(menu, board):
    """START must not be repeatable against a sequence still held in memory."""
    open_reset(menu)
    enter_code(menu, wrong_code())
    menu.feed(panels=('start',))

    for _ in range(3):
        menu.feed(panels=('start',))
    assert board.reset_calls == 0


def test_overlong_input_does_not_slide_into_a_match(menu, board):
    """Pressing extra panels first must not leave a matching tail behind.

    A naive 'compare the last N presses' check would let someone mash every
    panel and hit the code by accident.
    """
    open_reset(menu)
    enter_code(menu, (wrong_code()[0],) + tuple(DEFAULT_CODE))

    menu.feed(panels=('start',))
    assert board.reset_calls == 0


def test_correct_code_is_order_sensitive(menu, board):
    open_reset(menu)
    enter_code(menu, tuple(reversed(DEFAULT_CODE)))
    menu.feed(panels=('start',))
    assert board.reset_calls == 0


def test_a_custom_code_replaces_the_default(board, controls):
    menu = SystemMenu(None, None, board, code=('circle', 'circle', 'cross'),
                      controls=controls)
    open_reset(menu)

    enter_code(menu, DEFAULT_CODE)
    assert board.reset_calls == 0         # the default must no longer work

    open_reset(menu)
    enter_code(menu, ('circle', 'circle', 'cross'))
    menu.feed(panels=('start',))
    assert board.reset_calls == 1
    assert menu.result == RESULT_CLEARED


def test_select_backs_out_of_the_code_stage(menu, board):
    """Otherwise a half-entered code is a dead end on a keyboardless cabinet."""
    open_reset(menu)
    menu.feed(panels=('cross',))
    menu.feed(panels=('select',))

    assert not menu.open
    assert board.reset_calls == 0


def test_reopening_forgets_previous_progress(menu):
    open_reset(menu)
    enter_code(menu, DEFAULT_CODE[:2])
    menu.close()

    menu.open_menu()
    assert menu.stage == STAGE_OPTIONS
    assert menu.entered == []


# -- passcode file -----------------------------------------------------------

def write_code(tmp_path, payload):
    import json
    path = tmp_path / 'passcode.json'
    path.write_text(json.dumps(payload), encoding='utf-8')
    return str(path)


def test_code_is_read_from_the_file(tmp_path):
    path = write_code(tmp_path, {'code': ['circle', 'cross', 'circle']})
    assert load_code(path) == ('circle', 'cross', 'circle')


def test_a_bare_list_is_accepted(tmp_path):
    path = write_code(tmp_path, ['cross', 'cross', 'square'])
    assert load_code(path) == ('cross', 'cross', 'square')


def test_missing_file_falls_back_to_the_default(tmp_path):
    assert load_code(str(tmp_path / 'nope.json')) == DEFAULT_CODE


@pytest.mark.parametrize('payload', [
    {'code': []},                          # would reset on a bare START
    {'code': ['cross']},                   # under the minimum length
    {'code': ['cross'] * 40},              # unenterable before the timeout
    {'code': ['cross', 'up', 'square']},   # not a shape panel
    {'code': ['cross', 3, 'square']},      # not even a name
    {'code': 'crosssquare'},               # a string, not a list
    {'nope': ['cross', 'square', 'circle']},
    'not an object',
    42,
])
def test_unusable_files_fall_back_rather_than_raise(tmp_path, payload):
    """A hand-edited file must never make the cabinet unbootable."""
    assert load_code(write_code(tmp_path, payload)) == DEFAULT_CODE


def test_corrupt_json_falls_back(tmp_path):
    path = tmp_path / 'passcode.json'
    path.write_text('{"code": [', encoding='utf-8')
    assert load_code(str(path)) == DEFAULT_CODE


def test_every_default_panel_is_enterable():
    """The default must be drawn from panels the code stage actually accepts."""
    assert all(panel in CODE_PANELS for panel in DEFAULT_CODE)


# -- timeout -----------------------------------------------------------------

def test_idle_timeout_closes_an_abandoned_menu(menu):
    menu.open_menu()
    menu.tick(IDLE_TIMEOUT_MS - 1)
    assert menu.open
    menu.tick(2)
    assert not menu.open


def test_input_resets_the_idle_timer(menu):
    menu.open_menu()
    menu.tick(IDLE_TIMEOUT_MS - 1)
    menu.feed(actions=('down',))
    menu.tick(IDLE_TIMEOUT_MS - 1)
    assert menu.open


# -- integration -------------------------------------------------------------

def test_reset_actually_empties_the_file(tmp_path, controls):
    data_file = tmp_path / 'data.json'
    board = Leaderboard(str(data_file))
    board.submit_score('RYAN', 4200)
    assert board.read_scores()

    menu = SystemMenu(None, None, board, controls=controls)
    open_reset(menu)
    enter_code(menu)
    menu.feed(panels=('start',))

    assert board.read_scores() == []


def test_a_failed_write_still_closes_the_menu(menu):
    class Broken:
        def reset(self):
            raise OSError('read-only filesystem')

    menu.leaderboard = Broken()
    open_reset(menu)
    enter_code(menu)
    menu.feed(panels=('start',))

    assert menu.stage == STAGE_DONE
    menu.tick(DONE_MS)
    assert not menu.open
