"""The shared preferences file.

The one behaviour worth pinning is the merge. Two unrelated features write this
file - the sound toggle and the controller choice - and the write used to
replace it wholesale, so whichever was saved last would have erased the other.
Everything else here is the same rule the leaderboard follows: a bad file is an
empty one, never an exception.
"""

import json

import pytest

from cabinet import settings
from cabinet.controls import KEYBOARD, PAD, Controls, load_choice
from cabinet.sound import SoundManager


@pytest.fixture
def path(tmp_path):
    return str(tmp_path / 'settings.json')


def test_missing_file_reads_as_empty(path):
    assert settings.read(path) == {}


def test_round_trip(path):
    assert settings.update({'volume': 0}, path) is True
    assert settings.read(path) == {'volume': 0}


def test_update_merges_rather_than_replaces(path):
    settings.update({'volume': 0}, path)
    settings.update({'controller': PAD}, path)

    assert settings.read(path) == {'volume': 0, 'controller': PAD}


def test_muting_does_not_drop_the_controller_choice(path):
    """The regression this file exists to prevent."""
    Controls(name=KEYBOARD, path=path).select(PAD)

    sound = SoundManager(settings_file=path, enabled=False)
    sound.save_volume_preference(0)

    assert load_choice(path) == PAD
    assert sound.load_volume_preference() == 0


def test_choosing_a_controller_does_not_drop_the_volume(path):
    SoundManager(settings_file=path, enabled=False).save_volume_preference(0)
    Controls(name=KEYBOARD, path=path).select(PAD)

    assert SoundManager(
        settings_file=path, enabled=False,
    ).load_volume_preference() == 0


@pytest.mark.parametrize('contents', ['', '{', '[]', 'null', '"text"', '42'])
def test_unusable_files_read_as_empty(tmp_path, contents):
    path = tmp_path / 'settings.json'
    path.write_text(contents, encoding='utf-8')
    assert settings.read(str(path)) == {}


def test_a_corrupt_file_is_overwritten_not_merged(tmp_path):
    path = tmp_path / 'settings.json'
    path.write_text('{ broken', encoding='utf-8')

    assert settings.update({'volume': 1}, str(path)) is True
    assert json.loads(path.read_text(encoding='utf-8')) == {'volume': 1}


def test_an_unwritable_path_reports_failure_without_raising(tmp_path):
    """A read-only filesystem must not stop the game, only the saving."""
    blocked = tmp_path / 'file'
    blocked.write_text('x', encoding='utf-8')

    # A path *under* a regular file cannot be created.
    assert settings.update({'volume': 1}, str(blocked / 'settings.json')) is False


def test_unknown_controller_falls_back_to_the_default(path):
    settings.update({'controller': 'joystick'}, path)
    assert load_choice(path) == KEYBOARD
