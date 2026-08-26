"""Audio startup.

`SoundManager.load` returns immediately when sound is disabled, and every test
and headless run in this repo passes `--no-sound`. That left the *enabled* path
- the one the cabinet actually takes - completely uncovered, and a missing
`import json` shipped in it: the game imported fine, passed the whole suite, and
then died on the Pi at startup with a NameError.

So these run with `enabled=True`. They need no audio device: every mixer call in
`load` is either guarded by `pygame.mixer.get_init()` or wrapped against
`pygame.error`, which is what makes the real failure - an unguarded NameError -
visible here.
"""

import json
import os

import pygame
import pytest

from cabinet.sound import SoundManager
from games import registry

pygame.init()

# Clips belong to a game, so the only real manifest on the machine is a game's.
PACMAN_ASSETS = registry.find('pacman').asset_root


def test_a_games_manifest_is_actually_readable():
    """Guards the tests below from passing vacuously.

    Loading swallows OSError, so a manifest that had moved would skip the parse
    entirely and the regression test would prove nothing.
    """
    manifest = os.path.join(PACMAN_ASSETS, 'manifest.json')
    assert os.path.exists(manifest)
    with open(manifest, encoding='utf-8') as handle:
        assert json.load(handle).get('audio')


def test_load_with_sound_enabled_does_not_raise(tmp_path):
    """The regression: this is the path the Pi takes and the desk never did."""
    sound = SoundManager(
        settings_file=str(tmp_path / 'settings.json'), enabled=True,
    ).load()
    assert sound.enabled


def test_a_games_clips_load_under_its_own_prefix(tmp_path):
    """Boot loads no game audio at all; a game brings its own when played.

    The prefix is why two games may both ship a `jump`, and why the cabinet can
    keep taking new games without a naming convention anyone has to remember.
    """
    if not pygame.mixer.get_init():
        pytest.skip('no mixer in this environment')

    sound = SoundManager(
        settings_file=str(tmp_path / 'settings.json'), enabled=True,
    ).load()
    assert sound.sounds == {}          # nothing at boot

    loaded = sound.add_clips(PACMAN_ASSETS, {'dot_1': 'audio/dot_1.ogg'},
                             prefix='pacman/')

    assert loaded == 1
    assert 'pacman/dot_1' in sound.sounds
    assert 'dot_1' not in sound.sounds


def test_two_games_can_ship_a_clip_of_the_same_name(tmp_path):
    if not pygame.mixer.get_init():
        pytest.skip('no mixer in this environment')

    sound = SoundManager(
        settings_file=str(tmp_path / 'settings.json'), enabled=True,
    ).load()
    clip = {'jump': 'audio/dot_1.ogg'}

    sound.add_clips(PACMAN_ASSETS, clip, prefix='one/')
    sound.add_clips(PACMAN_ASSETS, clip, prefix='two/')

    assert set(sound.sounds) == {'one/jump', 'two/jump'}


def test_a_games_view_adds_its_own_prefix(tmp_path):
    """Game code names its own clips and never learns it is sharing a table."""
    played = []
    sound = SoundManager(
        settings_file=str(tmp_path / 'settings.json'), enabled=False,
    )
    sound.play = played.append

    view = sound.for_game('runner/', pause_ambience='held')
    view.play('jump')

    assert played == ['runner/jump']
    assert view.master_volume == sound.master_volume


def test_starting_ambience_tells_the_mixer_this_games_pause_clip(tmp_path):
    """The mixer restores ambience on unmute, so it has to know whose loop."""
    sound = SoundManager(
        settings_file=str(tmp_path / 'settings.json'), enabled=False,
    )
    view = sound.for_game('runner/', pause_ambience='held')
    # Ambience is blocked during a cutscene, which is the state a fresh manager
    # starts in (engine.js:3203).
    view.set_cutscene(False)
    view.set_ambience('theme')

    assert sound.current_ambience == 'runner/theme'
    assert sound.pause_ambience == 'runner/held'


def test_a_game_with_no_pause_clip_falls_silent_rather_than_borrowing(tmp_path):
    """Never another game's clip: the machine would play the wrong game's music."""
    sound = SoundManager(
        settings_file=str(tmp_path / 'settings.json'), enabled=False,
    )
    stopped = []
    sound.stop_ambience = lambda: stopped.append(True)

    view = sound.for_game('runner/')
    view.set_cutscene(False)
    view.set_ambience('theme')
    sound.resume_ambience(paused=True)

    assert sound.pause_ambience is None
    assert stopped


def test_load_with_sound_disabled_is_a_noop(tmp_path):
    sound = SoundManager(
        settings_file=str(tmp_path / 'settings.json'), enabled=False,
    ).load()
    assert sound.sounds == {}


def test_a_missing_asset_root_does_not_stop_startup(tmp_path):
    """A half-deployed cabinet should still boot, silently."""
    sound = SoundManager(
        asset_root=str(tmp_path / 'nothing-here'),
        settings_file=str(tmp_path / 'settings.json'),
        enabled=True,
    ).load()
    assert sound.sounds == {}


@pytest.mark.parametrize('contents', ['', 'not json', '[]'])
def test_a_corrupt_manifest_does_not_stop_startup(tmp_path, contents):
    root = tmp_path / 'assets'
    root.mkdir()
    (root / 'manifest.json').write_text(contents, encoding='utf-8')

    sound = SoundManager(
        asset_root=str(root),
        settings_file=str(tmp_path / 'settings.json'),
        enabled=True,
    ).load()
    assert sound.sounds == {}


def test_the_volume_preference_survives_load(tmp_path):
    """Exercises the settings read that `load` ends on, with sound enabled."""
    path = str(tmp_path / 'settings.json')
    SoundManager(settings_file=path, enabled=True).save_volume_preference(0)

    assert SoundManager(
        settings_file=path, enabled=True,
    ).load().master_volume == 0
