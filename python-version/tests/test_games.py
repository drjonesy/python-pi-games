"""Installing a game, and the isolation between two of them.

The cabinet is meant to take an unlimited number of titles, added by dropping a
folder into `games/`. Four things have to hold for that to be true, and none of
them is visible from inside Pac-Man - which is the only game installed today, so
every one of them is checked here against folders built in a tmpdir:

* **A folder is enough.** No shared file is edited to install a game, so no
  shared file can be forgotten - `games/registry.py` finds it by looking.
* **A broken game costs one title, not the machine.** A cabinet has no keyboard
  and cannot be recovered from a traceback at boot.
* **Games cannot collide.** Two of them may use the same sprite key, the same
  clip name and the same score, and must still see only their own.
* **Nothing is read from disk until a game is played**, so the hundredth
  installed title costs nothing until someone chooses it.
"""

import os
import sys
import textwrap

import pygame
import pytest

from cabinet.game import Game, GameSpec
from cabinet.renderer import AssetPack, AssetStore
from cabinet.sound import SoundManager
from games import registry

pygame.init()


# -- a game folder, built in a tmpdir ----------------------------------------

GAME_PY = '''
from cabinet.game import Game, GameSpec


class {cls}(Game):
    def __init__(self, context):
        super().__init__(context)
        self.entered = False

    def enter(self):
        self.entered = True


SPEC = GameSpec(id={id!r}, title={title!r}, tagline='A TEST GAME',
                factory={cls})
'''


def write_game(games_dir, game_id, title=None, body=None):
    """A minimal but genuine game package: the folder a new title arrives as."""
    package = games_dir / game_id
    package.mkdir(parents=True)
    (package / '__init__.py').write_text('', encoding='utf-8')
    (package / 'game.py').write_text(
        body if body is not None else GAME_PY.format(
            cls=game_id.title(), id=game_id, title=title or game_id.upper(),
        ),
        encoding='utf-8',
    )
    return package


@pytest.fixture
def games_dir(tmp_path):
    """An importable `games` package of our own, in place of the real one.

    The scan reads `registry.PACKAGE_DIR`, so pointing that at a tmpdir - and
    putting the tmpdir on the import path under a package name of its own - runs
    the real discovery code against folders this test wrote.

    The scan result is cached for the life of the process, which is right on a
    cabinet and would be poison here: a fake registry left in that cache would
    follow this file into every test that runs after it. So the cache is saved
    and put back rather than merely refreshed - refreshing would still leave the
    *real* scan un-run until something asked for it.
    """
    root = tmp_path / 'fakegames'
    root.mkdir()
    (root / '__init__.py').write_text('', encoding='utf-8')

    saved = (registry.PACKAGE_DIR, registry.__package__,
             registry._cache, registry._errors)
    sys.path.insert(0, str(tmp_path))
    registry.PACKAGE_DIR = str(root)
    registry.__package__ = 'fakegames'

    try:
        yield root
    finally:
        (registry.PACKAGE_DIR, registry.__package__,
         registry._cache, registry._errors) = saved
        sys.path.remove(str(tmp_path))
        for name in [n for n in sys.modules if n.startswith('fakegames')]:
            del sys.modules[name]


def scan(games_dir):
    return registry.all_games(refresh=True)


# -- a folder is enough ------------------------------------------------------

def test_a_dropped_in_folder_is_an_installed_game(games_dir):
    write_game(games_dir, 'runner', title='RUNNER')

    specs = scan(games_dir)

    assert [spec.id for spec in specs] == ['runner']
    assert specs[0].title == 'RUNNER'


def test_games_can_be_added_without_touching_anything_shared(games_dir):
    """The whole promise: three folders, no edits, three games."""
    for game_id in ('alpha', 'beta', 'gamma'):
        write_game(games_dir, game_id)

    assert [spec.id for spec in scan(games_dir)] == ['alpha', 'beta', 'gamma']


def test_a_single_file_game_may_put_its_spec_in_the_package(games_dir):
    """`game.py` is the convention, not a requirement."""
    package = games_dir / 'tiny'
    package.mkdir()
    (package / '__init__.py').write_text(
        GAME_PY.format(cls='Tiny', id='tiny', title='TINY'), encoding='utf-8',
    )

    assert [spec.id for spec in scan(games_dir)] == ['tiny']


def test_a_directory_that_is_not_a_package_is_not_a_game(games_dir):
    """Art, notes, a stray folder of assets - none of it is a title."""
    (games_dir / 'notes').mkdir()
    (games_dir / 'notes' / 'todo.md').write_text('later', encoding='utf-8')

    assert scan(games_dir) == ()


def test_games_are_listed_by_title_with_pinned_ones_first(games_dir):
    """Alphabetical is the only order that stays stable as folders come and go;
    `order` is how a favourite is pinned to the top of the machine."""
    write_game(games_dir, 'zeta', title='ZETA')
    write_game(games_dir, 'alpha', title='ALPHA')
    write_game(games_dir, 'pinned', body=GAME_PY.format(
        cls='Pinned', id='pinned', title='PINNED',
    ).replace('factory=Pinned)', 'factory=Pinned, order=0)'))

    assert [spec.id for spec in scan(games_dir)] == ['pinned', 'alpha', 'zeta']


# -- a broken game costs one title -------------------------------------------

def test_a_game_that_will_not_import_is_skipped(games_dir, capsys):
    """The rest of the machine still boots. A cabinet has no keyboard."""
    write_game(games_dir, 'good')
    write_game(games_dir, 'broken', body='import nonexistent_module\n')

    specs = scan(games_dir)

    assert [spec.id for spec in specs] == ['good']
    assert 'broken' in capsys.readouterr().out


def test_a_game_that_raises_at_import_time_is_skipped(games_dir):
    """Any failure at all, not just an import error - this is the boundary with
    code the cabinet did not write."""
    write_game(games_dir, 'good')
    write_game(games_dir, 'exploding', body='raise RuntimeError("boom")\n')

    assert [spec.id for spec in scan(games_dir)] == ['good']
    assert dict(registry.errors())['exploding'].args == ('boom',)


def test_a_folder_with_no_spec_is_skipped(games_dir):
    write_game(games_dir, 'good')
    write_game(games_dir, 'empty', body='# nothing here yet\n')

    assert [spec.id for spec in scan(games_dir)] == ['good']
    assert 'empty' in dict(registry.errors())


def test_an_id_that_disagrees_with_its_folder_is_refused(games_dir):
    """The id names the folder, the score file and `--game`. Letting them
    disagree would write one game's scores under another game's name."""
    write_game(games_dir, 'runner', body=GAME_PY.format(
        cls='Runner', id='sprinter', title='RUNNER',
    ))

    assert scan(games_dir) == ()
    assert isinstance(dict(registry.errors())['runner'], ValueError)


def test_the_broken_ones_are_kept_for_reporting(games_dir):
    """`--list-games` names them: installed-but-broken otherwise looks exactly
    like never-copied-across."""
    write_game(games_dir, 'broken', body='import nonexistent_module\n')

    scan(games_dir)
    assert [game_id for game_id, _ in registry.errors()] == ['broken']


# -- games cannot collide ----------------------------------------------------

def test_two_packs_may_use_the_same_sprite_key(tmp_path):
    """Keys are scoped to a pack, so ported code keeps its own names."""
    store = AssetStore()
    one = store.pack('one', str(tmp_path / 'one'))
    two = store.pack('two', str(tmp_path / 'two'))

    one.sheets['player'] = pygame.Surface((8, 8))
    two.sheets['player'] = pygame.Surface((16, 16))

    assert one.scaled('player', 8, 8).get_size() == (8, 8)
    assert two.scaled('player', 16, 16).get_size() == (16, 16)


def test_a_pack_is_loaded_once_and_kept(tmp_path):
    """Leaving and re-entering a game must not re-read a single PNG."""
    store = AssetStore()
    root = str(tmp_path / 'art')

    assert store.pack('one', root) is store.pack('one', root)


def test_a_game_with_no_assets_gets_an_empty_pack_not_an_error(tmp_path):
    """A game may ship no art at all, and a half-deployed one must still boot."""
    pack = AssetPack(str(tmp_path / 'nothing-here')).load()

    assert pack.manifest == {'sprites': {}, 'audio': {}}
    assert pack.scaled('anything', 8, 8) is None
    assert pack.frames('anything', 8) == []


def test_a_corrupt_manifest_is_an_empty_pack(tmp_path):
    root = tmp_path / 'art'
    root.mkdir()
    (root / 'manifest.json').write_text('not json at all', encoding='utf-8')

    assert AssetPack(str(root)).load().manifest['sprites'] == {}


def test_a_sprite_that_will_not_load_is_skipped(tmp_path):
    """One missing PNG leaves a game drawing one thing less, not a dead cabinet."""
    root = tmp_path / 'art'
    root.mkdir()
    (root / 'manifest.json').write_text(textwrap.dedent('''
        {"sprites": {"gone": {"file": "sprites/gone.png", "frames": 1,
                              "width": 8, "height": 8}}}
    '''), encoding='utf-8')

    pack = AssetPack(str(root)).load()

    assert pack.loaded
    assert pack.sheets == {}


# -- nothing is read until a game is played ----------------------------------

def test_the_store_starts_empty(tmp_path):
    """Boot cost is independent of how many games are installed."""
    assert AssetStore().packs == {}


def test_the_shell_draws_from_an_empty_pack():
    """Every screen the cabinet owns is text and rectangles."""
    shell = AssetStore().shell()

    assert shell.sheets == {}
    assert shell.manifest['sprites'] == {}


# -- the spec's own defaults -------------------------------------------------

class _Stub(Game):
    pass


def test_a_pack_reports_its_games_clips_for_the_mixer(tmp_path):
    root = tmp_path / 'art'
    root.mkdir()
    (root / 'manifest.json').write_text(
        '{"audio": {"jump": "audio/jump.ogg"}}', encoding='utf-8',
    )

    assert AssetPack(str(root)).load().audio == {'jump': 'audio/jump.ogg'}


def test_every_installed_game_has_a_distinct_sound_namespace():
    prefixes = [spec.sound_prefix for spec in registry.all_games()]
    assert len(set(prefixes)) == len(prefixes)


def test_a_game_only_ever_sees_its_own_clips(tmp_path):
    """`for_game` is a view, not a copy: one table, one mute, no leakage."""
    manager = SoundManager(settings_file=str(tmp_path / 's.json'),
                           enabled=False)
    asked = []
    manager.play = asked.append

    manager.for_game('alpha/').play('jump')
    manager.for_game('beta/').play('jump')

    assert asked == ['alpha/jump', 'beta/jump']


# -- two games, through the real shell ---------------------------------------
#
# Only one game is installed, so the isolation the refactor is *for* would
# otherwise be untested until the day a second one arrives - which is the worst
# possible moment to find out about it. These run two games through the actual
# `Cabinet`, one after the other, and check that neither can see the other.

class _Recorder(Game):
    def __init__(self, context):
        super().__init__(context)
        self.entered = 0

    def enter(self):
        self.entered += 1


@pytest.fixture
def two_game_shell(tmp_path):
    from cabinet.app import Cabinet
    from cabinet.controls import KEYBOARD, Controls
    from cabinet.font import BitmapFont

    from cabinet import constants as C

    def art(game_id, sprite):
        """A game's asset folder, with one sprite and one clip of its own."""
        root = tmp_path / game_id / 'assets'
        (root / 'sprites').mkdir(parents=True)
        pygame.image.save(pygame.Surface((8, 8)), str(root / 'sprites' / 'a.png'))
        (root / 'manifest.json').write_text(
            '{"sprites": {"%s": {"file": "sprites/a.png", "frames": 1,'
            ' "width": 8, "height": 8}}, "audio": {"jump": "audio/none.ogg"}}'
            % sprite, encoding='utf-8',
        )
        return str(root)

    specs = [
        GameSpec(id=game_id, title=game_id.upper(), factory=_Recorder,
                 asset_root=art(game_id, 'player'),
                 data_file=str(tmp_path / f'{game_id}.json'))
        for game_id in ('alpha', 'beta')
    ]

    surface = pygame.Surface((C.LOGICAL_WIDTH, C.LOGICAL_HEIGHT))
    return Cabinet(
        window=surface, surface=surface, assets=AssetStore(),
        font=BitmapFont(), sound_manager=SoundManager(
            settings_file=str(tmp_path / 'settings.json'), enabled=False),
        controls=Controls(name=KEYBOARD, path=os.devnull),
        pads=None, specs=specs,
    ), specs


def test_each_game_is_handed_its_own_pack(two_game_shell):
    """Same sprite key in both games, and neither sees the other's."""
    shell, specs = two_game_shell

    shell.play(specs[0])
    alpha = shell.game.context.assets
    shell.to_picker()
    shell.play(specs[1])
    beta = shell.game.context.assets

    assert alpha is not beta
    assert alpha.name == 'alpha' and beta.name == 'beta'
    assert 'player' in alpha.manifest['sprites']
    assert 'player' in beta.manifest['sprites']


def test_each_game_is_handed_its_own_audio_namespace(two_game_shell):
    shell, specs = two_game_shell
    asked = []
    shell.sound_manager.play = asked.append

    for spec in specs:
        shell.play(spec)
        shell.game.context.sound_manager.play('jump')
        shell.to_picker()

    assert asked == ['alpha/jump', 'beta/jump']


def test_each_game_keeps_its_own_board(two_game_shell):
    shell, specs = two_game_shell

    shell.leaderboard_for(specs[0]).submit_score('AAA', 4200)

    assert shell.leaderboard_for(specs[1]).read_scores() == []


def test_a_game_is_built_once_and_reused(two_game_shell):
    """Its pack and clips are loaded once with it, not on every visit."""
    shell, specs = two_game_shell

    shell.play(specs[0])
    first = shell.game
    shell.to_picker()
    shell.play(specs[0])

    assert shell.game is first
    assert first.entered == 2
    assert shell.assets.packs['alpha'] is first.context.assets


def test_a_spec_names_its_own_asset_root():
    spec = GameSpec(id='runner', title='RUNNER', factory=_Stub,
                    package_dir='/games/runner')

    assert spec.asset_root == os.path.join('/games/runner', 'assets')
    assert spec.preview_image == os.path.join('/games/runner', 'preview.png')
