"""The multi-game shell: the registry, per-game boards, and the picker.

Three things here would only show up on the cabinet itself, so they are pinned
in software:

* **One board per game.** Every game's high scores live in their own file, and
  no game may reach another's. A registry typo must not put one somewhere
  outside `data/`.
* **The picker keeps its board in step with the cursor.** The whole point of
  showing scores on the picker is that they belong to the highlighted game;
  a stale table is worse than none.
* **Both screens survive a rendered frame.** The picker is the first thing the
  machine draws, so an exception there is an unbootable cabinet - and the
  layout constants that place its panels do not fail loudly when they overlap.
"""

import os

import pygame
import pytest

from cabinet import constants as C
from cabinet.controls import KEYBOARD, Controls
from cabinet.font import GLYPHS, BitmapFont
from cabinet.game import Game, GameContext, GameSpec
from cabinet.leaderboard import DATA_FILE, Leaderboard, data_file_for
from cabinet.renderer import AssetStore, Renderer
from cabinet.ui import game_select
from cabinet.ui.game_select import (
    HINT_Y, PANEL_HEIGHT, PANEL_Y, PREVIEW_INNER, VISIBLE_ROWS, GameSelect,
)
from games import registry

pygame.init()


# -- registry ----------------------------------------------------------------

def test_pacman_is_installed():
    assert 'pacman' in registry.ids()


def test_find_returns_the_matching_spec():
    assert registry.find('pacman').id == 'pacman'
    assert registry.find('nope') is None


def test_every_spec_is_complete():
    """A half-filled entry would reach the picker as a blank row."""
    for spec in registry.all_games():
        assert spec.id and spec.title
        assert callable(spec.factory)
        assert spec.data_file


def test_ids_are_unique():
    """Ids key the board files and the loaded-game cache, so a duplicate would
    have two games sharing one high-score table."""
    ids = registry.ids()
    assert len(set(ids)) == len(ids)


def test_titles_fit_the_list_column():
    for spec in registry.all_games():
        assert len(spec.title) <= game_select.MAX_LABEL_CHARS, spec.id


def test_taglines_fit_the_detail_panel():
    font = BitmapFont()
    for spec in registry.all_games():
        width = font.measure(spec.tagline)[0]
        assert width <= game_select.PANEL_WIDTH, spec.id


def test_every_installed_game_ships_its_preview_image():
    """A generated file (`tools/make_preview.py`) that has to be committed -
    the Pi never runs the generator, so a missing one is a blank panel."""
    for spec in registry.all_games():
        assert spec.preview_image, spec.id
        assert os.path.exists(spec.preview_image), spec.preview_image


def test_the_preview_image_is_the_panel_size():
    """Authored at the panel's exact size so it is blitted 1:1. Pixel art
    survives an integer downscale and very little else."""
    for spec in registry.all_games():
        image = pygame.image.load(spec.preview_image)
        assert image.get_size() == (PREVIEW_INNER.width, PREVIEW_INNER.height)


def test_every_character_of_every_title_has_a_glyph():
    """An unmapped character renders as a hollow box - visible, but only on the
    cabinet."""
    for spec in registry.all_games():
        for char in (spec.title + spec.tagline).upper():
            assert char in GLYPHS, f'{spec.id}: no glyph for {char!r}'


# -- per-game boards ---------------------------------------------------------

def test_pacman_keeps_the_original_file():
    """Shared with the Node version, so moving it would break that interop."""
    assert registry.find('pacman').data_file == DATA_FILE


def test_a_new_game_gets_its_own_file():
    path = data_file_for('breakout')
    assert path.endswith(os.path.join('scores', 'breakout.json'))
    assert path != DATA_FILE


def test_two_games_never_share_a_file():
    paths = [spec.data_file for spec in registry.all_games()]
    assert len(set(paths)) == len(paths)


@pytest.mark.parametrize('game_id', ['../../etc/passwd', 'a/b', 'x y!', 'A B'])
def test_ids_cannot_escape_the_data_directory(game_id):
    """A registry entry is written by hand; this is the one place a typo in one
    could put a file outside `data/`."""
    path = data_file_for(game_id, data_dir='/scores')
    assert os.path.dirname(path) == '/scores'


@pytest.mark.parametrize('game_id', ['', '///', '!!'])
def test_an_unusable_id_is_refused_rather_than_guessed(game_id):
    with pytest.raises(ValueError):
        data_file_for(game_id, data_dir='/scores')


def test_boards_are_independent(tmp_path):
    one = Leaderboard(str(tmp_path / 'one.json'))
    two = Leaderboard(str(tmp_path / 'two.json'))

    one.submit_score('RYAN', 4200)
    assert two.read_scores() == []

    two.reset()
    assert one.high_score() == 4200


# -- the picker --------------------------------------------------------------

class StubGame(Game):
    def __init__(self, context):
        super().__init__(context)
        self.actions = []

    def handle_action(self, action):
        self.actions.append(action)


def spec_named(name, data_file, preview_image=None):
    return GameSpec(id=name.lower().replace(' ', ''), title=name,
                    tagline=f'{name} TAGLINE', factory=StubGame,
                    preview_image=preview_image, data_file=data_file)


@pytest.fixture
def boards():
    return {}


@pytest.fixture
def specs(tmp_path):
    return [spec_named(f'GAME {index}', str(tmp_path / f'{index}.json'))
            for index in range(1, 4)]


@pytest.fixture
def leaderboard_for(boards):
    def lookup(spec):
        return boards.setdefault(spec.id, Leaderboard(spec.data_file))
    return lookup


@pytest.fixture
def picker(specs, leaderboard_for):
    surface = pygame.Surface((C.LOGICAL_WIDTH, C.LOGICAL_HEIGHT))
    return GameSelect(
        Renderer(surface, AssetStore().shell()), BitmapFont(), specs,
        leaderboard_for, controls=Controls(name=KEYBOARD, path=os.devnull),
    )


def test_the_cursor_starts_on_the_first_game(picker, specs):
    assert picker.index == 0
    assert picker.selected is specs[0]


def test_up_and_down_move_the_cursor(picker):
    picker.handle_action('down')
    assert picker.index == 1
    picker.handle_action('up')
    assert picker.index == 0


def test_the_cursor_wraps(picker, specs):
    picker.handle_action('up')
    assert picker.index == len(specs) - 1


def test_select_plays_the_highlighted_game(picker):
    chosen = []
    picker.on_choose = chosen.append

    picker.handle_action('down')
    picker.handle_action('select')

    assert [spec.id for spec in chosen] == [picker.specs[1].id]


def test_the_scores_follow_the_cursor(picker, leaderboard_for, specs):
    """The table under the preview is the highlighted game's, not the
    machine's - that is the whole reason it is on this screen."""
    leaderboard_for(specs[0]).submit_score('AAA', 100)
    leaderboard_for(specs[1]).submit_score('BBB', 900)
    picker.refresh()

    assert [entry['name'] for entry in picker.scores] == ['AAA']
    picker.handle_action('down')
    assert [entry['name'] for entry in picker.scores] == ['BBB']


def test_an_empty_board_shows_no_rows_rather_than_raising(picker):
    assert picker.scores == []
    picker.draw()


# -- preview images ----------------------------------------------------------

def test_a_missing_preview_file_falls_back_to_the_title(picker, specs):
    """The picker must still list a game whose art did not ship."""
    specs[0].preview_image = '/nowhere/preview.png'
    assert picker.preview_surface(specs[0]) is None
    picker.draw()


def test_a_corrupt_preview_file_falls_back_too(picker, specs, tmp_path):
    broken = tmp_path / 'broken.png'
    broken.write_text('not a png', encoding='utf-8')
    specs[0].preview_image = str(broken)

    assert picker.preview_surface(specs[0]) is None
    picker.draw()


def test_a_failed_load_is_cached(picker, specs, monkeypatch):
    """Otherwise a missing file means a disk hit on every frame the cursor
    sits on that row - which, on the picker, is most of the time."""
    specs[0].preview_image = '/nowhere/preview.png'
    picker.preview_surface(specs[0])

    calls = []
    monkeypatch.setattr(picker, '_load_preview',
                        lambda spec: calls.append(spec) or None)
    picker.preview_surface(specs[0])
    assert calls == []


def test_an_off_size_image_is_fitted_without_stretching(picker, specs, tmp_path):
    path = tmp_path / 'wide.png'
    pygame.image.save(pygame.Surface((200, 50)), str(path))
    specs[0].preview_image = str(path)

    fitted = picker.preview_surface(specs[0])
    width, height = fitted.get_size()

    assert width <= PREVIEW_INNER.width and height <= PREVIEW_INNER.height
    # Aspect preserved to within the rounding of a whole pixel.
    assert abs(width / height - 4.0) < 0.1


def test_pacmans_preview_loads_at_one_to_one(picker):
    spec = registry.find('pacman')
    assert picker.preview_surface(spec).get_size() == (
        PREVIEW_INNER.width, PREVIEW_INNER.height
    )


def test_a_long_list_scrolls_to_keep_the_cursor_visible(tmp_path):
    many = [spec_named(f'G{index}', str(tmp_path / f'{index}.json'))
            for index in range(VISIBLE_ROWS + 3)]
    surface = pygame.Surface((C.LOGICAL_WIDTH, C.LOGICAL_HEIGHT))
    picker = GameSelect(Renderer(surface, AssetStore().shell()), BitmapFont(), many,
                        lambda spec: Leaderboard(spec.data_file),
                        controls=Controls(name=KEYBOARD, path=os.devnull))

    for _ in range(len(many) - 1):
        picker.handle_action('down')

    assert picker.index == len(many) - 1
    assert picker.scroll <= picker.index < picker.scroll + VISIBLE_ROWS

    # Wrapping back to the top has to bring the window with it, or the cursor
    # is off-screen and the machine looks frozen.
    picker.handle_action('down')
    assert picker.index == 0
    assert picker.scroll == 0


def test_an_empty_registry_draws_rather_than_crashing():
    """A cabinet with nothing installed must still boot and say so."""
    surface = pygame.Surface((C.LOGICAL_WIDTH, C.LOGICAL_HEIGHT))
    picker = GameSelect(Renderer(surface, AssetStore().shell()), BitmapFont(), (),
                        lambda spec: Leaderboard(os.devnull),
                        controls=Controls(name=KEYBOARD, path=os.devnull))

    assert picker.selected is None
    picker.handle_action('down')
    picker.handle_action('select')
    picker.draw()


# -- layout ------------------------------------------------------------------
#
# Pure geometry, so it needs no display - and it is exactly the kind of thing
# that only shows up on the cabinet.

def test_the_list_clears_the_preview_panel():
    assert game_select.LIST_X + game_select.LIST_WIDTH <= game_select.PREVIEW_X


def test_the_preview_is_an_integer_downscale_of_the_maze():
    """Half of 224x248. A fractional scale makes the preview mushy, and it is
    the only picture on the screen."""
    from games.pacman import constants as P

    assert P.MAZE_WIDTH % PREVIEW_INNER.width == 0
    assert P.MAZE_HEIGHT % PREVIEW_INNER.height == 0


def test_the_panels_do_not_overlap():
    list_bottom = (game_select.LIST_Y
                   + VISIBLE_ROWS * game_select.ROW_PITCH - game_select.ROW_GAP)
    preview_bottom = game_select.PREVIEW_Y + game_select.PREVIEW_HEIGHT

    assert list_bottom <= PANEL_Y
    assert preview_bottom <= PANEL_Y
    assert PANEL_Y + PANEL_HEIGHT <= HINT_Y


def test_everything_fits_on_the_screen():
    assert HINT_Y + 7 <= C.LOGICAL_HEIGHT
    assert PREVIEW_INNER.right <= C.LOGICAL_WIDTH


# -- the game contract -------------------------------------------------------

def test_the_default_game_is_inert():
    """A subclass overrides only what it does, so the base has to be safe."""
    game = Game(GameContext(None, None, None, None, None, None))

    assert game.at_attract is True
    assert game.simulating is False
    game.enter()
    game.update(8.0)
    game.render(0.0)
    game.handle_action('select')
    game.leave()


def test_a_context_without_hooks_does_not_raise():
    """The hooks are optional so a game can be built in a test harness."""
    context = GameContext(None, None, None, None, None, None)
    context.submit_score(4200)
    context.exit_to_picker()
    context.quit_cabinet()


def test_a_spec_defaults_every_path_to_the_folder_beside_it():
    """The whole of "adding a game is dropping a folder in".

    A spec that names only its id, title and factory still knows where its
    preview, its art and its clips are - they are beside the module the factory
    came from. Nothing shared has to be edited to install a game, so nothing
    shared can be forgotten.
    """
    spec = GameSpec(id='demo', title='DEMO', factory=StubGame)

    here = os.path.dirname(os.path.abspath(__file__))
    assert spec.package_dir == here          # StubGame is defined in this file
    assert spec.preview_image == os.path.join(here, 'preview.png')
    assert spec.asset_root == os.path.join(here, 'assets')
    assert spec.sound_prefix == 'demo/'


def test_a_spec_for_a_factory_with_no_file_falls_back_to_games():
    """A factory from a module with no file on disk still resolves.

    Nothing in `games/` looks like this, which is the point: the fallback is
    what keeps a spec's paths from being `None` for a game built at runtime.
    """
    class Homeless(StubGame):
        __module__ = 'not.a.real.module'

    spec = GameSpec(id='demo', title='DEMO', factory=Homeless)
    assert spec.package_dir.endswith(os.path.join('games', 'demo'))
    assert spec.preview_image.endswith(os.path.join('demo', 'preview.png'))


# -- releases ----------------------------------------------------------------
#
# The one asymmetry in the shell's input routing: nothing the cabinet draws has
# a held control, so a let-go action skips the routing table and goes straight
# to the running game. What has to be pinned is where it does *not* go.

class RecordingGame(Game):
    def __init__(self, context):
        super().__init__(context)
        self.pressed = []
        self.released = []
        self.playing = False

    def handle_action(self, action):
        self.pressed.append(action)

    def handle_release(self, action):
        self.released.append(action)

    @property
    def at_attract(self):
        return not self.playing


class StubPads:
    """Enough of `GamepadManager` for the shell's routing."""

    def key_actions(self, event):
        return ()

    def key_panels(self, event):
        return ()

    def key_releases(self, event):
        return ()


@pytest.fixture
def shell(tmp_path, monkeypatch):
    from cabinet import app as app_module

    spec = GameSpec(id='rec', title='REC', factory=RecordingGame,
                    data_file=str(tmp_path / 'rec.json'))
    surface = pygame.Surface((C.LOGICAL_WIDTH, C.LOGICAL_HEIGHT))

    cabinet = app_module.Cabinet(
        window=surface, surface=surface, assets=AssetStore(), font=BitmapFont(),
        sound_manager=_Sound(), controls=Controls(name=KEYBOARD,
                                                  path=os.devnull),
        pads=StubPads(), specs=(spec,),
    )
    cabinet.play(spec)
    return cabinet


class _Sound:
    """Enough of `SoundManager` for the shell to load a game and route to it."""

    master_volume = 1
    enabled = False

    def add_clips(self, root, clips, prefix=''):
        return 0

    def for_game(self, prefix, pause_ambience=None):
        return self

    def toggle_mute(self):
        self.master_volume = 0 if self.master_volume else 1

    def stop_all(self):
        pass


def keyup(key):
    return pygame.event.Event(pygame.KEYUP, {'key': key, 'mod': 0})


def test_a_released_key_reaches_the_running_game(shell):
    shell._handle_keyup(keyup(pygame.K_DOWN))
    assert shell.game.released == ['down']


def test_releases_are_dropped_while_a_modal_is_up(shell):
    """The game is told what is *not* held; holding that back until the modal
    closes would deliver a stale fact."""
    shell.score_entry.open = True
    shell._handle_keyup(keyup(pygame.K_DOWN))
    assert shell.game.released == []


def test_releases_are_dropped_on_the_picker(shell):
    shell.to_picker()
    shell._handle_keyup(keyup(pygame.K_DOWN))
    assert shell.game.released == []


def test_a_key_with_no_action_releases_nothing(shell):
    shell._handle_keyup(keyup(pygame.K_F5))
    assert shell.game.released == []


def test_pressing_still_goes_through_the_routing_table(shell):
    """Releases bypass it; presses must not start doing the same."""
    shell.score_entry.open = True
    shell._handle_action('down')
    assert shell.game.pressed == []


# -- per-game audio ----------------------------------------------------------
#
# Real files, borrowed from the only game that ships any. What is being pinned
# is the contract every game uses: clips land in the *shared* table, under the
# prefix that keeps two games from fighting over a name like `jump`.

PACMAN_ASSETS = registry.find('pacman').asset_root
GAME_CLIPS = {'jump': 'audio/pause.ogg', 'point': 'audio/dot_1.ogg'}
GAME_PREFIX = 'demo/'


def test_a_game_can_add_its_own_clips():
    """Into the same table as everything else, so one mute covers the cabinet."""
    from cabinet.sound import SoundManager

    if not pygame.mixer.get_init():
        pytest.skip('no mixer in this environment')

    manager = SoundManager(enabled=True)
    loaded = manager.add_clips(PACMAN_ASSETS, GAME_CLIPS, prefix=GAME_PREFIX)

    assert loaded == len(GAME_CLIPS)
    assert set(manager.sounds) == {f'{GAME_PREFIX}{n}' for n in GAME_CLIPS}


def test_missing_clips_are_skipped_rather_than_raised():
    from cabinet.sound import SoundManager

    manager = SoundManager(enabled=True)
    assert manager.add_clips('/nowhere', {'a': 'a.wav'}) == 0


def test_a_disabled_manager_loads_nothing():
    from cabinet.sound import SoundManager

    assert SoundManager(enabled=False).add_clips(PACMAN_ASSETS, GAME_CLIPS) == 0
