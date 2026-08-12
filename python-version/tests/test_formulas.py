"""Speeds, durations and thresholds (§6, §8, §13)."""

import pytest

from conftest import Harness
from games.pacman import constants as C


def test_pacman_speed_is_eleven_tiles_per_second(harness):
    """engine.js:953."""
    expected = (C.SCALED_TILE_SIZE * 11) / 1000
    assert harness.pacman.velocity_per_ms == pytest.approx(expected)
    # 11 tiles/s means one tile every ~90.9ms.
    assert C.SCALED_TILE_SIZE / harness.pacman.velocity_per_ms == pytest.approx(
        1000 / 11,
    )


@pytest.mark.parametrize('level', [1, 2, 5, 10, 21])
def test_ghost_speed_formulas_scale_with_level(level):
    """engine.js:93-107, level_adjustment = level / 100."""
    harness = Harness(level=level)
    ghost = harness.blinky
    pacman_speed = harness.pacman.velocity_per_ms
    adjustment = level / 100

    assert ghost.slow_speed == pytest.approx(pacman_speed * (0.75 + adjustment))
    assert ghost.medium_speed == pytest.approx(pacman_speed * (0.875 + adjustment))
    assert ghost.fast_speed == pytest.approx(pacman_speed * (1.0 + adjustment))
    assert ghost.scared_speed == pytest.approx(pacman_speed * 0.5)
    assert ghost.transition_speed == pytest.approx(pacman_speed * 0.4)
    assert ghost.eye_speed == pytest.approx(pacman_speed * 2)


def test_default_speed_starts_slow(harness):
    for ghost in harness.ghosts:
        assert ghost.default_speed == pytest.approx(ghost.slow_speed)
        assert ghost.cruise_elroy is False


def test_ghosts_outrun_pacman_at_high_levels():
    """At level 25 fast_speed exceeds Pacman's - the formula has no cap."""
    harness = Harness(level=25)
    assert harness.blinky.fast_speed > harness.pacman.velocity_per_ms


def test_speed_up_promotes_one_rung_then_stops(harness):
    """engine.js:758 - slow -> medium -> fast, and no further."""
    ghost = harness.blinky

    ghost.speed_up()
    assert ghost.default_speed == pytest.approx(ghost.medium_speed)
    assert ghost.cruise_elroy is True

    ghost.speed_up()
    assert ghost.default_speed == pytest.approx(ghost.fast_speed)

    ghost.speed_up()
    assert ghost.default_speed == pytest.approx(ghost.fast_speed)


def test_reset_default_speed_clears_elroy(harness):
    ghost = harness.blinky
    ghost.speed_up()
    ghost.reset_default_speed()
    assert ghost.default_speed == pytest.approx(ghost.slow_speed)
    assert ghost.cruise_elroy is False


def test_elroy_survives_a_plain_reset_but_not_a_full_one(harness):
    """engine.js:61-65 and 2110: a death does *not* clear Cruise Elroy."""
    ghost = harness.blinky
    ghost.speed_up()
    promoted = ghost.default_speed

    ghost.reset()
    assert ghost.default_speed == pytest.approx(promoted)
    assert ghost.cruise_elroy is True

    ghost.reset(True)
    assert ghost.default_speed == pytest.approx(ghost.slow_speed)
    assert ghost.cruise_elroy is False


def test_elroy_changes_blinkys_sprite(harness):
    """engine.js:204 - _annoyed then _angry."""
    ghost = harness.blinky
    ghost.set_sprite_sheet('blinky', 'left', 'scatter')
    assert ghost.sheet == 'blinky_left'

    ghost.speed_up()
    ghost.set_sprite_sheet('blinky', 'left', 'scatter')
    assert ghost.sheet == 'blinky_left_annoyed'

    ghost.speed_up()
    ghost.set_sprite_sheet('blinky', 'left', 'scatter')
    assert ghost.sheet == 'blinky_left_angry'


@pytest.mark.parametrize('mode, direction, expected', [
    ('scatter', 'up', 'blinky_up'),
    ('chase', 'right', 'blinky_right'),
    ('eyes', 'down', 'eyes_down'),
    ('scared', 'left', 'scared_blue'),
])
def test_sprite_sheet_selection(harness, mode, direction, expected):
    harness.blinky.scared_color = 'blue'
    harness.blinky.set_sprite_sheet('blinky', direction, mode)
    assert harness.blinky.sheet == expected


def test_scared_color_toggles(harness):
    ghost = harness.blinky
    ghost.mode = 'scared'
    ghost.scared_color = 'blue'
    ghost.toggle_scared_color()
    assert ghost.sheet == 'scared_white'
    ghost.toggle_scared_color()
    assert ghost.sheet == 'scared_blue'


@pytest.mark.parametrize('level, expected', [
    (1, 6000), (2, 5000), (3, 4000), (4, 3000), (5, 2000), (6, 1000),
    (7, 0), (8, 0), (20, 0),
])
def test_power_duration(level, expected):
    """engine.js:2349 - level 7+ grants no scared window at all."""
    assert C.power_duration_ms(level) == expected


@pytest.mark.parametrize('level, expected', [
    (1, 8000), (2, 4000), (3, 0), (4, 0), (10, 0),
])
def test_ghost_release_delay(level, expected):
    """engine.js:1920."""
    assert C.ghost_release_delay_ms(level) == expected


@pytest.mark.parametrize('combo, expected', [
    (0, 100), (1, 200), (2, 400), (3, 800), (4, 1600),
])
def test_combo_points(combo, expected):
    """engine.js:2359. ghost_combo is incremented before use, so an in-game
    combo runs 200/400/800/1600."""
    assert C.combo_points(combo) == expected


@pytest.mark.parametrize('dots, expected', [
    (244, 'siren_1'), (41, 'siren_1'), (40, 'siren_2'), (21, 'siren_2'),
    (20, 'siren_3'), (0, 'siren_3'),
])
def test_siren_selection(dots, expected):
    """engine.js:2211."""
    assert C.determine_siren(dots) == expected


@pytest.mark.parametrize('level, expected', [
    (1, 100), (2, 300), (3, 500), (4, 700), (5, 1000), (6, 2000), (7, 3000),
    (8, 5000), (9, 5000), (15, 5000),
])
def test_fruit_points_by_level(level, expected):
    """engine.js:1192-1201 with the 5000 fallthrough at engine.js:2189."""
    assert C.FRUIT_POINTS.get(level, C.FRUIT_POINTS_DEFAULT) == expected


def test_every_fruit_value_maps_to_a_sprite():
    for points in C.FRUIT_POINTS.values():
        assert points in C.FRUIT_IMAGES


def test_total_ui_tiles_budget():
    """§5 - measuring only the maze picks a scale ~18% too large."""
    assert C.TOTAL_UI_TILES == 37
    assert C.LOGICAL_HEIGHT == 37 * C.SCALED_TILE_SIZE
    assert C.MAZE_ORIGIN_Y == 4 * C.SCALED_TILE_SIZE
    # The maze plus the bottom row must exactly fill the surface.
    assert C.MAZE_ORIGIN_Y + C.MAZE_HEIGHT + (
        C.BOTTOM_ROW_TILES * C.SCALED_TILE_SIZE
    ) == C.LOGICAL_HEIGHT


def test_simulation_rate_is_not_lowered():
    """A guard on the one constant this whole port hinges on (§3)."""
    assert C.SIM_HZ == 120
    assert C.SIM_DT_MS == pytest.approx(8.3333, abs=1e-4)
