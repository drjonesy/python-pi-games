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

from cabinet.sound import ASSET_ROOT, SoundManager

pygame.init()


def test_manifest_is_actually_readable():
    """Guards the test below from passing vacuously.

    `load` swallows OSError, so a manifest that had moved would skip the parse
    entirely and the regression test would prove nothing.
    """
    manifest = os.path.join(ASSET_ROOT, 'manifest.json')
    assert os.path.exists(manifest)
    with open(manifest, encoding='utf-8') as handle:
        assert json.load(handle).get('audio')


def test_load_with_sound_enabled_does_not_raise(tmp_path):
    """The regression: this is the path the Pi takes and the desk never did."""
    sound = SoundManager(
        settings_file=str(tmp_path / 'settings.json'), enabled=True,
    ).load()
    assert sound.enabled


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
