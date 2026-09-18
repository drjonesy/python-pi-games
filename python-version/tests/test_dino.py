"""DINO RUN: that every obstacle can be beaten with feet, and the run's rules.

The hitboxes, bird heights and jump arc in `games/dino/constants.py` were tuned
together, and a small change to any one of them can make an obstacle
unbeatable - or unlosable - without anything looking wrong. So the timing
windows are measured here by brute force: an obstacle is sent at a lone
dinosaur and ▲ / ▼ is tried at every 10ms offset.

A window is how long the player has to get the step right. On a mat a step is
slow and imprecise, so a window has to be generous, not merely non-empty.
"""

import os

import pygame
import pytest

from cabinet import constants as C
from cabinet.controls import Controls
from cabinet.font import BitmapFont
from cabinet.game import GameContext
from cabinet.leaderboard import Leaderboard
from cabinet.renderer import AssetStore, Renderer
from games.dino import constants as D
from games.dino.game import SPEC, STATE_MENU, STATE_PLAYING
from games.dino.world import DYING, RUNNING, World, overlaps

STEP = C.SIM_DT_MS
MIN_WINDOW_MS = 150


# -- a lone obstacle ---------------------------------------------------------

def lone_world(kind, speed=D.START_SPEED):
    world = World()
    world.speed = speed
    world.next_speed_up_ms = float('inf')    # hold the speed still
    world.spawn(kind)
    world.spawn_ms = float('inf')            # and send only this one
    return world


def run_until_settled(world, press_at_ms=None, press='up', release_at_ms=None):
    """Steps until the obstacle is scored or has killed. True if it scored."""
    t = 0.0
    while world.state == RUNNING and world.score == 0:
        if press_at_ms is not None and press_at_ms <= t < press_at_ms + STEP:
            world.press_up() if press == 'up' else world.press_down()
        if release_at_ms is not None and release_at_ms <= t < release_at_ms + STEP:
            world.release_down()
        world.update(STEP)
        t += STEP
        assert t < 20_000, 'the obstacle never arrived'
    return world.state == RUNNING


def clearing_offsets(kind, speed=D.START_SPEED, press='up', hold_ms=0):
    """Every press time, in ms after spawn, that gets past `kind`."""
    arrival = (D.SCREEN_W - D.DINO_X) / speed * 1000
    offsets = []
    for t in range(0, int(arrival) + 200, 10):
        world = lone_world(kind, speed)
        release = t + hold_ms if press == 'down' else None
        if run_until_settled(world, t, press, release):
            offsets.append(t)
    return offsets


def widest_window(offsets):
    """Length of the longest contiguous run of offsets, in ms."""
    best = run = 0
    for previous, current in zip([None] + offsets, offsets):
        run = run + 10 if previous is not None and current - previous == 10 else 10
        best = max(best, run)
    return best


# -- what each obstacle demands ---------------------------------------------

@pytest.mark.parametrize('kind', D.OBSTACLE_KINDS)
def test_doing_nothing_loses_to_every_obstacle(kind):
    assert not run_until_settled(lone_world(kind))


@pytest.mark.parametrize('kind', [D.ROCK, D.BIRD_LOW_KIND])
@pytest.mark.parametrize('speed_steps', [0, 5, 10])
def test_a_jump_clears_rocks_and_low_flyers_with_room_to_spare(kind, speed_steps):
    """At the start, after 50s and after 100s of speed-ups."""
    speed = D.START_SPEED * (1 + D.SPEED_STEP) ** speed_steps
    window = widest_window(clearing_offsets(kind, speed))
    assert window >= MIN_WINDOW_MS, f'{kind} at {speed:.0f}px/s: {window}ms'


@pytest.mark.parametrize('speed_steps', [0, 5, 10])
def test_a_tap_of_down_ducks_a_high_flyer(speed_steps):
    """A step is a short press: the minimum duck has to carry it."""
    speed = D.START_SPEED * (1 + D.SPEED_STEP) ** speed_steps
    offsets = clearing_offsets(D.BIRD_HIGH_KIND, speed, press='down', hold_ms=20)
    assert widest_window(offsets) >= MIN_WINDOW_MS


def test_holding_down_ducks_a_high_flyer_indefinitely():
    world = lone_world(D.BIRD_HIGH_KIND)
    world.press_down()
    assert run_until_settled(world)


def test_a_jump_is_no_answer_to_a_high_flyer():
    """Otherwise ▼ would never be needed.

    A perfect jump can sail clean over one - the apex is above it - but the
    window is a few frames wide, far too tight to aim for with a foot.
    """
    assert widest_window(clearing_offsets(D.BIRD_HIGH_KIND)) <= 50


def test_the_bird_heights_split_standing_from_ducking():
    world = World()
    world.spawn(D.BIRD_HIGH_KIND)
    bird = world.obstacles[0]
    bird.x = D.DINO_X
    standing = world.dino.hitbox()
    world.press_down()
    ducking = world.dino.hitbox()
    assert overlaps(standing, bird.hitbox())
    assert not overlaps(ducking, bird.hitbox())


# -- the run -----------------------------------------------------------------

def test_the_ground_gains_ten_percent_every_ten_seconds_compounding():
    world = World()
    world.spawn_ms = float('inf')
    for _ in range(int(20_000 / STEP) + 1):
        world.update(STEP)
    assert world.speed == pytest.approx(D.START_SPEED * 1.1 * 1.1)


def test_each_obstacle_that_gets_past_is_one_point():
    world = lone_world(D.ROCK)
    world.press_down()                  # irrelevant to a rock - never jumps
    world.dino.down_held = False
    arrival = (D.SCREEN_W - D.DINO_X) / world.speed * 1000
    press = max(clearing_offsets(D.ROCK), key=lambda t: -abs(t - arrival / 2))
    world = lone_world(D.ROCK)
    assert run_until_settled(world, press)
    assert world.score == 1


def test_up_ends_a_duck_whose_release_was_lost():
    world = World()
    world.press_down()                  # and the release never arrives
    world.press_up()
    assert world.dino.airborne
    assert not world.dino.down_held


def test_up_just_before_landing_jumps_again_on_touchdown():
    world = World()
    world.spawn_ms = float('inf')
    world.press_up()
    while world.dino.air_ms < D.JUMP_MS - D.JUMP_BUFFER_MS / 2:
        world.update(STEP)
    world.press_up()
    for _ in range(int(D.JUMP_BUFFER_MS / STEP) + 2):
        world.update(STEP)
    assert world.dino.airborne
    assert world.dino.air_ms < D.JUMP_BUFFER_MS


def test_a_dinosaur_hit_in_the_air_falls_to_the_ground():
    world = World()
    world.press_up()
    world.update(STEP * 10)
    world.state = DYING
    for _ in range(int(D.GAME_OVER_MS / STEP)):
        world.update(STEP)
    assert world.dino.altitude == 0


# -- the game, as the cabinet drives it ---------------------------------------

class Offers:
    """`context.submit_score` as the cabinet does it: a score that places opens
    name entry and calls back when the name is saved; one that does not calls
    back at once."""

    def __init__(self, places=False):
        self.places = places
        self.scores = []
        self.pending = None

    def __call__(self, score, on_close=None):
        self.scores.append(score)
        if self.places:
            self.pending = on_close
        elif on_close:
            on_close()

    def save_name(self):
        self.pending()


@pytest.fixture
def game(tmp_path):
    offers = Offers()
    context = GameContext(
        None, None, None, None, None,
        Leaderboard(str(tmp_path / 'dino.json')), submit_score=offers,
    )
    game = SPEC.create(context)
    game.offers = offers
    game.enter()
    return game


def lose(game):
    game.world.spawn(D.ROCK)
    while game.world.state != DYING:
        game.update(STEP)


def test_the_spec_matches_its_folder():
    assert SPEC.id == os.path.basename(SPEC.package_dir) == 'dino'


@pytest.mark.parametrize('action', ['up', 'select'])
def test_up_or_start_starts_a_run(game, action):
    assert game.at_attract
    game.handle_action(action)
    assert game.state == STATE_PLAYING and game.simulating
    assert not game.world.dino.airborne, 'the starting step must not jump'


@pytest.mark.parametrize('action', ['down', 'left', 'right', 'delete', 'mute'])
def test_nothing_else_starts_a_run(game, action):
    game.handle_action(action)
    assert game.state == STATE_MENU


def test_left_and_right_do_nothing_in_play(game):
    game.handle_action('select')
    game.handle_action('left')
    game.handle_action('right')
    assert not game.world.dino.airborne and not game.world.dino.ducking


def test_a_finished_run_is_offered_then_returns_to_the_title(game):
    game.handle_action('select')
    game.world.score = 7
    lose(game)

    while not game.offers.scores:
        assert not game.at_attract, 'the picker could open over the fall'
        game.update(STEP)

    assert game.offers.scores == [7]
    assert game.state == STATE_MENU and game.at_attract
    assert game.last_score == 7


def test_game_over_moves_on_to_the_title_by_itself(game):
    """A run that does not place must not leave GAME OVER stuck on screen."""
    game.handle_action('select')
    lose(game)
    for _ in range(int(D.GAME_OVER_MS / STEP) + 1):
        game.update(STEP)
    assert game.state == STATE_MENU and game.at_attract


def test_up_or_start_skips_the_rest_of_game_over(game):
    game.handle_action('select')
    lose(game)

    game.handle_action('up')             # still stamping as it dies
    assert game.state == STATE_PLAYING, 'GAME OVER was never shown'

    while game.world.dead_ms < D.GAME_OVER_SKIP_MS:
        game.update(STEP)
    game.handle_action('up')
    assert game.state == STATE_MENU

    game.handle_action('up')             # and the next step starts a run
    assert game.state == STATE_PLAYING and game.world.state == RUNNING


def test_name_entry_holds_game_over_until_the_name_is_saved(game):
    game.context.submit_score = game.offers = Offers(places=True)
    game.handle_action('select')
    game.world.score = 3
    lose(game)
    for _ in range(int(D.GAME_OVER_MS / STEP) + 1):
        game.update(STEP)

    assert game.offers.scores == [3]
    assert not game.at_attract, 'the title would open under the modal'
    game.offers.save_name()
    assert game.state == STATE_MENU


def test_pause_freezes_the_run_but_not_the_fall(game):
    game.handle_action('select')
    game.handle_action('pause')
    assert not game.simulating
    game.handle_action('up')
    assert not game.world.dino.airborne, 'input while paused'
    game.handle_action('pause')
    lose(game)
    game.handle_action('pause')
    assert game.simulating


def test_leave_leaves_nothing_behind(game):
    game.handle_action('select')
    game.handle_action('down')
    game.leave()
    assert game.world is None and game.at_attract


# -- drawing -----------------------------------------------------------------

@pytest.fixture
def drawn_game(tmp_path, monkeypatch):
    monkeypatch.setenv('SDL_VIDEODRIVER', 'dummy')
    pygame.display.init()
    pygame.display.set_mode((1, 1))
    surface = pygame.Surface((C.LOGICAL_WIDTH, C.LOGICAL_HEIGHT))

    class Silent:
        master_volume = 1

    assets = AssetStore().pack(SPEC.id, SPEC.asset_root)
    context = GameContext(
        Renderer(surface, AssetStore().shell()), assets, BitmapFont(), Silent(),
        Controls(path=str(tmp_path / 'settings.json')),
        Leaderboard(str(tmp_path / 'dino.json')), submit_score=Offers(),
    )
    game = SPEC.create(context)
    game.enter()
    return game, assets


def test_every_frame_the_game_asks_for_was_built(drawn_game):
    _, assets = drawn_game
    keys = {'idle_0', 'duck', 'rock', 'grass'}
    keys |= {f'run_{i}' for i in range(D.RUN_FRAMES)}
    keys |= {f'jump_{i}' for i in range(D.JUMP_FRAMES)}
    keys |= {f'dead_{i}' for i in range(D.DEAD_FRAMES)}
    keys |= {f'bird_{i}' for i in range(8)}
    assert keys <= set(assets.sheets)
    assert assets.spec('rock')['height'] == D.ROCK_HEIGHT
    assert assets.spec('bird_0')['height'] == D.BIRD_HEIGHT
    assert assets.spec('grass')['height'] == D.GRASS_HEIGHT


def test_every_screen_draws(drawn_game):
    game, _ = drawn_game
    game.render(0)                      # title
    game.handle_action('select')
    game.world.spawn(D.BIRD_HIGH_KIND)
    game.handle_action('down')
    for _ in range(60):
        game.update(STEP)
    game.render(0)                      # play
    game.handle_action('pause')
    game.render(0)                      # paused
    game.handle_action('pause')
    lose(game)
    game.world.dead_ms = D.GAME_OVER_MS - 1
    game.render(0)                      # GAME OVER
