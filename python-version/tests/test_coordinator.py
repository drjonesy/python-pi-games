"""Game rules driven through the coordinator (§8, §13).

Runs headless against stub renderer and sound objects, so the whole rules layer
is testable without a window or an audio device.
"""

import pytest

from games.pacman import constants as C
from games.pacman.coordinator import STATE_MENU, STATE_PLAYING, GameCoordinator
from cabinet.leaderboard import Leaderboard


class StubRenderer:
    """Records draw calls; the coordinator never reads anything back."""

    def __init__(self):
        self.calls = []

    def draw_image(self, *args, **kwargs):
        self.calls.append(('image', args))

    def draw_frame(self, *args, **kwargs):
        self.calls.append(('frame', args))

    def fill_rect(self, *args, **kwargs):
        self.calls.append(('rect', args))


class StubSound:
    def __init__(self):
        self.played = []
        self.ambience = []
        self.cutscene = True

    def play(self, sound):
        self.played.append(sound)

    def play_dot_sound(self):
        self.played.append('dot')

    def set_ambience(self, sound, keep_current_ambience=False):
        self.ambience.append(sound)

    def resume_ambience(self, paused=False):
        pass

    def stop_ambience(self):
        self.ambience.append(None)

    def stop_all(self):
        pass

    def set_cutscene(self, value):
        self.cutscene = value

    def update(self):
        pass


@pytest.fixture
def game(tmp_path):
    coordinator = GameCoordinator(
        StubRenderer(), StubSound(), Leaderboard(str(tmp_path / 'data.json')),
    )
    coordinator.reset()
    return coordinator


def tick_timers(coordinator, ms, dt=C.SIM_DT_MS):
    """Advances only the timers, leaving the characters still."""
    for _ in range(int(round(ms / dt))):
        coordinator.timers.tick(dt)


# ---------------------------------------------------------------------------
# Setup
# ---------------------------------------------------------------------------

def test_initial_state(game):
    assert game.remaining_dots == C.TOTAL_PICKUPS == 244
    assert game.lives == 2, 'engine.js:1580 - two spare lives, three attempts'
    assert game.points == 0
    assert game.level == 1
    assert game.extra_life_given is False
    assert len(game.pickups) == 245, '244 dots plus the fruit'


def test_pickup_types_and_values(game):
    dots = [p for p in game.pickups if p.type == 'pacdot']
    pellets = [p for p in game.pickups if p.type == 'powerPellet']

    assert len(dots) == 240
    assert len(pellets) == 4
    assert all(p.points == 10 for p in dots)
    assert all(p.points == 50 for p in pellets)


def test_pacdot_sub_tile_offsets(game):
    """§5 - dots are a quarter tile, offset three eighths into the tile."""
    tile = C.SCALED_TILE_SIZE
    dot = next(p for p in game.pickups if p.type == 'pacdot')

    assert dot.size == tile * 0.25
    assert (dot.x % tile) == (tile / 8) * 3
    assert (dot.y % tile) == (tile / 8) * 3
    # The whole point of the fixed even tile size: no fractional pixels.
    assert float(dot.x).is_integer() and float(dot.y).is_integer()


def test_starts_on_the_menu_and_transitions_on_start(game):
    assert game.state == STATE_MENU
    game.start_button_click()
    assert game.state == STATE_PLAYING
    assert game.running is True


# ---------------------------------------------------------------------------
# Dot thresholds
# ---------------------------------------------------------------------------

def test_fruit_spawns_at_174_and_74_exactly_once(game):
    """engine.js:2171."""
    spawns = []
    original = game.create_fruit

    def spy():
        spawns.append(game.remaining_dots)
        original()

    game.create_fruit = spy

    for _ in range(244):
        game.dot_eaten()

    assert spawns == [174, 74]


def test_cruise_elroy_fires_at_40_and_20_exactly_once(game):
    """engine.js:2175 - two promotions, slow -> medium -> fast."""
    promotions = []
    original = game.speed_up_blinky

    def spy():
        promotions.append(game.remaining_dots)
        original()

    game.speed_up_blinky = spy

    for _ in range(244):
        game.dot_eaten()

    assert promotions == [40, 20]
    assert game.blinky.default_speed == pytest.approx(game.blinky.fast_speed)
    assert game.blinky.cruise_elroy is True


def test_level_advances_when_the_last_dot_is_eaten(game):
    advanced = []
    game.advance_level = lambda: advanced.append(True)

    for _ in range(244):
        game.dot_eaten()

    assert game.remaining_dots == 0
    assert advanced == [True]


def test_fruit_shows_the_right_sprite_and_expires(game):
    game.remaining_dots = 175
    game.dot_eaten()

    assert game.fruit.visible is True
    assert game.fruit.points == 100        # level 1
    assert game.fruit.image == 'cherry'

    tick_timers(game, C.FRUIT_DURATION_MS - 100)
    assert game.fruit.visible is True

    tick_timers(game, 200)
    assert game.fruit.visible is False, 'fruit lives for exactly 10,000ms'


def test_siren_follows_the_dot_count(game):
    game.remaining_dots = 41
    game.speed_up_blinky()
    assert game.sound_manager.ambience[-1] == 'siren_1'

    game.remaining_dots = 40
    game.speed_up_blinky()
    assert game.sound_manager.ambience[-1] == 'siren_2'

    game.remaining_dots = 20
    game.speed_up_blinky()
    assert game.sound_manager.ambience[-1] == 'siren_3'


def test_siren_is_not_touched_while_ghosts_are_scared(game):
    """engine.js:2201."""
    game.remaining_dots = 40
    game.scared_ghosts = [game.blinky]
    before = list(game.sound_manager.ambience)
    game.speed_up_blinky()
    assert game.sound_manager.ambience == before


# ---------------------------------------------------------------------------
# Scoring
# ---------------------------------------------------------------------------

def test_points_and_high_score_track_together(game):
    game.award_points(points=50)
    assert game.points == 50
    assert game.high_score == 50


def test_extra_life_granted_once_at_ten_thousand(game):
    """engine.js:2038."""
    game.award_points(points=9990)
    assert game.lives == 2
    assert game.extra_life_given is False

    game.award_points(points=10)
    assert game.points == 10000
    assert game.lives == 3
    assert game.extra_life_given is True
    assert 'extra_life' in game.sound_manager.played

    game.award_points(points=50000)
    assert game.lives == 3, 'the extra life is granted only once'


def test_ghost_combo_doubles_within_one_pellet(game):
    """200/400/800/1600 (engine.js:2358)."""
    game.ghost_combo = 0
    awarded = []
    for _ in range(4):
        game.ghost_combo += 1
        awarded.append(game.determine_combo_points())
    assert awarded == [200, 400, 800, 1600]


def test_power_up_resets_the_combo(game):
    game.ghost_combo = 3
    game.power_up()
    assert game.ghost_combo == 0


def test_fruit_points_display_widens_for_four_digits(game):
    """engine.js:2046 - 1000+ is drawn three tiles wide, shifted half a tile."""
    tile = C.SCALED_TILE_SIZE

    game.award_points(points=100, type='fruit')
    small = game.text_overlays[-1]
    assert small['width'] == tile * 2
    assert small['left'] == tile * 13

    game.award_points(points=2000, type='fruit')
    large = game.text_overlays[-1]
    assert large['width'] == tile * 3
    assert large['left'] == tile * 12.5


def test_eaten_fruit_is_logged_and_capped_at_seven(game):
    """engine.js:1887."""
    for points in (100, 300, 500, 700, 1000, 2000, 3000, 5000):
        game.award_points(points=points, type='fruit')

    assert len(game.fruit_display) == 7
    assert game.fruit_display[-1] == 'key'      # 5000
    assert 'cherry' not in game.fruit_display   # the oldest rolled off


# ---------------------------------------------------------------------------
# Power pellets
# ---------------------------------------------------------------------------

def test_power_up_scares_every_ghost_not_already_eyes(game):
    game.inky.mode = 'eyes'
    game.power_up()

    assert game.inky not in game.scared_ghosts
    assert len(game.scared_ghosts) == 3
    for ghost in game.scared_ghosts:
        assert ghost.mode == 'scared'
        assert ghost.scared_color == 'blue'


def test_scared_window_length_follows_the_level(game):
    game.level = 1
    game.power_up()
    tick_timers(game, C.power_duration_ms(1) - 100)
    assert all(g.mode == 'scared' for g in game.scared_ghosts)

    # The flash then runs nine beats of 250ms before scared mode ends.
    tick_timers(game, 200 + C.GHOST_FLASH_COUNT * C.GHOST_FLASH_INTERVAL_MS + 100)
    assert game.scared_ghosts == []


def test_level_seven_grants_no_scared_window(game):
    """engine.js:2349 clamps to 0 - points and combo reset only."""
    game.level = 7
    assert C.power_duration_ms(7) == 0

    game.power_up()
    assert len(game.scared_ghosts) == 4

    # The flash timer fires on the very next step.
    tick_timers(game, C.GHOST_FLASH_COUNT * C.GHOST_FLASH_INTERVAL_MS + 100)
    assert game.scared_ghosts == []


def test_flash_toggles_colors_nine_times_then_ends_scared(game):
    game.power_up()
    ghost = game.scared_ghosts[0]

    game.flash_ghosts(0, C.GHOST_FLASH_COUNT)
    assert ghost.scared_color == 'white'

    tick_timers(game, C.GHOST_FLASH_INTERVAL_MS + 10)
    assert ghost.scared_color == 'blue'

    tick_timers(game, C.GHOST_FLASH_COUNT * C.GHOST_FLASH_INTERVAL_MS)
    assert game.scared_ghosts == []
    assert ghost.mode == ghost.default_mode


def test_eating_a_ghost_pauses_the_flash_timer(game):
    """engine.js:2370 - and a player un-pause must not restart it."""
    game.power_up()
    flash_timer = game.ghost_flash_timer
    ghost = game.scared_ghosts[0]

    game.eat_ghost(ghost=ghost)

    assert flash_timer.paused is True
    assert flash_timer.paused_by_system is True

    game.timers.resume_all()
    assert flash_timer.paused is True, 'system pause outranks a player resume'


def test_eating_a_ghost_freezes_movement_for_one_second(game):
    game.power_up()
    ghost = game.scared_ghosts[0]
    game.eat_ghost(ghost=ghost)

    assert game.pacman.moving is False
    assert game.pacman.display is False
    assert game.eye_ghosts == 1
    assert all(g.paused for g in game.ghosts)
    assert all(not g.allow_collision for g in game.ghosts)

    tick_timers(game, C.EAT_GHOST_PAUSE_MS + 10)

    assert game.pacman.moving is True
    assert game.pacman.display is True
    assert all(not g.paused for g in game.ghosts)
    assert all(g.allow_collision for g in game.ghosts)
    assert game.ghost_flash_timer.paused is False


def test_eating_a_ghost_awards_combo_points_and_shows_them(game):
    game.power_up()
    game.eat_ghost(ghost=game.scared_ghosts[0])
    assert game.points == 200
    assert game.text_overlays[-1]['image'] == '200'

    game.eat_ghost(ghost=game.scared_ghosts[0])
    assert game.points == 600      # 200 + 400


def test_eat_ghost_to_respawn_round_trip_through_the_live_loop(game):
    """The full critical path, driven by `update` rather than called directly.

    Collision -> eatGhost -> eyes -> the ghost-house handoff -> restoreGhost.
    The individual halves are covered by test_ghost_house.py and the unit tests
    above; this pins down the two working together, which is where the 120Hz
    requirement actually bites.
    """
    # Put everyone on the board in a quiet corridor.
    for ghost in game.ghosts:
        ghost.idle_mode = None
        ghost.moving = True
    game.pacman.moving = False
    game.allow_pacman_movement = False

    game.pacman.position = {
        'top': C.SCALED_TILE_SIZE * (26 - 0.5),
        'left': C.SCALED_TILE_SIZE * (6 - 0.5),
    }
    game.pacman.old_position = dict(game.pacman.position)

    game.power_up()
    victim = game.blinky
    # Park the victim right on top of Pacman so the collision fires on the next
    # step, through Ghost.check_collision rather than by calling eat_ghost.
    victim.position = dict(game.pacman.position)
    victim.old_position = dict(victim.position)

    for _ in range(20):
        game.update(C.SIM_DT_MS)
        if victim.mode == 'eyes':
            break

    assert victim.mode == 'eyes', 'the collision never registered as a meal'
    assert game.eye_ghosts == 1
    assert game.points == 200

    # Isolate the trip home: keep the other ghosts still so they cannot kill
    # Pacman and halt the simulation mid-journey.
    for ghost in game.ghosts:
        if ghost is not victim:
            ghost.moving = False
            ghost.allow_collision = False

    for _ in range(int(20_000 / C.SIM_DT_MS)):
        game.update(C.SIM_DT_MS)
        if game.eye_ghosts == 0:
            break

    assert game.eye_ghosts == 0, 'the eaten ghost never made it home'
    assert victim.mode != 'eyes'
    assert game.death_in_progress is False


def test_restore_ghost_returns_the_siren(game):
    game.remaining_dots = 100
    game.eye_ghosts = 1
    game.restore_ghost()
    assert game.eye_ghosts == 0
    assert game.sound_manager.ambience[-1] == 'siren_1'


def test_restore_ghost_returns_power_up_if_others_still_scared(game):
    """engine.js:2431."""
    game.eye_ghosts = 1
    game.scared_ghosts = [game.pinky]
    game.restore_ghost()
    assert game.sound_manager.ambience[-1] == 'power_up'


# ---------------------------------------------------------------------------
# Death and game over
# ---------------------------------------------------------------------------

def test_death_costs_exactly_one_life_even_if_reported_twice(game):
    """engine.js:2072 - the deathInProgress guard.

    Collisions are checked every step, so an overlapping ghost fires this many
    times during the animation. Without the guard a single death would drain
    several lives.
    """
    game.death_sequence()
    game.death_sequence()
    game.death_sequence()

    tick_timers(game, C.DEATH_FREEZE_MS + 10)
    assert game.lives == 1


def test_death_sequence_timings_then_restart(game):
    game.death_sequence()
    assert game.pacman.moving is False
    assert game.allow_key_presses is False

    tick_timers(game, C.DEATH_FREEZE_MS + 10)
    assert game.pacman.special_animation is True
    assert game.pacman.sheet == 'pacman_death'
    assert game.pacman.sprite_frames == 12
    assert 'death' in game.sound_manager.played

    tick_timers(game, C.DEATH_ANIMATION_MS + 10)
    assert game.maze_cover_visible is True

    tick_timers(game, C.DEATH_COVER_MS + 10)
    assert game.maze_cover_visible is False
    assert game.death_in_progress is False
    assert game.pacman.special_animation is False


def test_last_life_leads_to_game_over_and_the_menu(game):
    game.lives = 0
    game.state = STATE_PLAYING

    scores = []
    game.on_game_over = scores.append

    game.death_sequence()
    tick_timers(game, C.DEATH_FREEZE_MS + 10)
    assert scores == [0], 'the final score is reported for name entry'

    tick_timers(game, C.GAME_OVER_DELAY_MS + 10)
    assert game.text_overlays[-1]['image'] == 'game_over'

    tick_timers(game, C.GAME_OVER_COVER_MS + C.GAME_OVER_MENU_MS + 20)
    assert game.state == STATE_MENU


def test_death_cancels_the_fruit_and_cycle_timers(game):
    game.remaining_dots = 175
    game.dot_eaten()                 # spawns fruit
    fruit_timer = game.fruit_timer
    game.ghost_cycle('scatter')
    cycle_timer = game.ghost_cycle_timer

    game.death_sequence()

    assert fruit_timer.active is False
    assert cycle_timer.active is False


# ---------------------------------------------------------------------------
# Scatter / chase cycle and releases
# ---------------------------------------------------------------------------

def test_scatter_chase_cycle_alternates_on_schedule(game):
    """engine.js:1903 - 7000ms scatter, then 20000ms chase, repeating."""
    for ghost in game.ghosts:
        ghost.mode = 'scatter'
        ghost.idle_mode = None

    game.ghost_cycle('scatter')

    tick_timers(game, C.SCATTER_DURATION_MS - 100)
    assert all(g.default_mode == 'scatter' for g in game.ghosts)

    tick_timers(game, 200)
    assert all(g.default_mode == 'chase' for g in game.ghosts)

    tick_timers(game, C.CHASE_DURATION_MS + 100)
    assert all(g.default_mode == 'scatter' for g in game.ghosts)


def test_ghosts_are_released_one_at_a_time(game):
    """engine.js:1918, level 1 -> 8000ms apart."""
    game.idle_ghosts = [game.pinky, game.inky, game.clyde]
    game.release_ghost()

    assert game.pinky.idle_mode == 'idle'
    tick_timers(game, C.ghost_release_delay_ms(1) + 10)
    assert game.pinky.idle_mode == 'leaving'
    assert len(game.idle_ghosts) == 2


def test_level_three_releases_ghosts_immediately(game):
    game.level = 3
    game.idle_ghosts = [game.pinky]
    game.release_ghost()

    tick_timers(game, C.SIM_DT_MS * 2)
    assert game.pinky.idle_mode == 'leaving'


# ---------------------------------------------------------------------------
# Level advance
# ---------------------------------------------------------------------------

def test_level_advance_flashes_then_resets_the_board(game):
    game.remaining_dots = 0
    game.blinky.speed_up()
    game.advance_level()

    tick_timers(game, C.LEVEL_ADVANCE_DELAY_MS + 10)
    assert game.maze_tint == C.MAZE_FLASH_TINT
    assert all(not g.display for g in game.ghosts)

    # Five 250ms tint beats, a 250ms gap, the cover, then the reset.
    tick_timers(game, 6 * C.MAZE_FLASH_INTERVAL_MS
                + C.LEVEL_ADVANCE_RESET_MS + 50)

    assert game.level == 2
    assert game.maze_tint is None
    assert game.maze_cover_visible is False
    assert game.remaining_dots == C.TOTAL_PICKUPS
    assert game.blinky.cruise_elroy is False, (
        'resetBoardForNextLevel calls resetDefaultSpeed (engine.js:2290)'
    )
    assert all(g.level == 2 for g in game.ghosts)


def test_level_advance_rebuilds_the_ghost_speeds(game):
    game.remaining_dots = 0
    game.advance_level()
    tick_timers(game, C.LEVEL_ADVANCE_DELAY_MS
                + 6 * C.MAZE_FLASH_INTERVAL_MS
                + C.LEVEL_ADVANCE_RESET_MS + 50)

    expected = game.pacman.velocity_per_ms * (0.75 + 2 / 100)
    assert game.blinky.slow_speed == pytest.approx(expected)


def test_new_game_starts_at_level_one_speeds(game):
    """A fresh game must not inherit the previous run's ghost speeds.

    The reference never reassigned `ghost.level` outside resetBoardForNextLevel
    (engine.js:2288), so a new game after reaching level 5 kept level-5 speeds.
    See the deviation note in GameCoordinator.reset.
    """
    game.level = 5
    for ghost in game.ghosts:
        ghost.level = 5
        ghost.reset()

    fast_slow_speed = game.blinky.slow_speed

    game.first_game = False
    game.reset()

    expected = game.pacman.velocity_per_ms * (0.75 + 1 / 100)
    assert game.blinky.slow_speed == pytest.approx(expected)
    assert game.blinky.slow_speed < fast_slow_speed
    assert all(ghost.level == 1 for ghost in game.ghosts)
    assert game.remaining_dots == C.TOTAL_PICKUPS


def test_new_game_clears_cruise_elroy(game):
    game.blinky.speed_up()
    game.first_game = False
    game.reset()

    assert game.blinky.cruise_elroy is False
    assert game.blinky.default_speed == pytest.approx(game.blinky.slow_speed)


def test_all_pickups_return_on_the_next_level(game):
    for pickup in game.pickups:
        pickup.visible = False

    game.remaining_dots = 0
    game.reset_board_for_next_level()

    dots = [p for p in game.pickups if p.type != 'fruit']
    assert all(p.visible for p in dots)
    assert game.fruit.visible is False, 'fruit stays hidden until it spawns'
    assert game.remaining_dots == 244


# ---------------------------------------------------------------------------
# Pause
# ---------------------------------------------------------------------------

def test_pause_toggles_and_debounces_on_the_wall_clock(game):
    """The debounce must not be a simulation timer, or un-pausing deadlocks."""
    game.state = STATE_PLAYING
    game.running = True
    game.allow_pause = True
    game.cutscene = False

    game.handle_pause_key()
    assert game.running is False
    assert game.paused_display is True
    assert game.allow_pause is False

    # No simulation happens while paused - only wall-clock ticks.
    game.tick_realtime(C.PAUSE_DEBOUNCE_MS + 10)
    assert game.allow_pause is True, 'the game must be un-pausable'

    game.handle_pause_key()
    assert game.running is True
    assert game.paused_display is False


def test_pause_is_blocked_during_cutscenes(game):
    game.allow_pause = False
    game.handle_pause_key()
    assert game.running is False    # unchanged; still on the menu


# ---------------------------------------------------------------------------
# Collision shortlist
# ---------------------------------------------------------------------------

def test_nearby_pickups_are_a_small_subset(game):
    """engine.js:1750 - only pickups Pacman could reach in 750ms.

    The radius is `velocity_per_ms * 750`, i.e. 8.25 tiles, so this is a
    generous shortlist rather than a tight one - but it still removes most of
    the board from the per-step collision check.
    """
    game.collision_detection_loop()

    radius_tiles = (game.pacman.velocity_per_ms * C.COLLISION_LOOKAHEAD_MS
                    / C.SCALED_TILE_SIZE)
    assert radius_tiles == pytest.approx(8.25)

    assert len(game.nearby_pickups) > 0
    assert len(game.nearby_pickups) < len(game.pickups) / 2


def test_invisible_pickups_are_excluded(game):
    game.collision_detection_loop()
    for pickup in game.nearby_pickups:
        pickup.visible = False

    game.collision_detection_loop()
    assert game.nearby_pickups == []
