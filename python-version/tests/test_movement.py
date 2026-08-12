"""Pacman movement, turn buffering, the tunnel warp, and grid math (§10)."""

import pytest

from conftest import Harness, grid_to_pixels, pixels_to_grid
from games.pacman.character_util import CharacterUtil, approx
from games.pacman.constants import MAZE_COLUMNS, SCALED_TILE_SIZE, SIM_DT_MS
from games.pacman.maze import MAZE_ARRAY

TILE = SCALED_TILE_SIZE


@pytest.fixture
def util():
    return CharacterUtil()


# ---------------------------------------------------------------------------
# Grid math
# ---------------------------------------------------------------------------

def test_grid_position_is_offset_by_half_a_tile(util):
    assert util.determine_grid_position({'top': 0, 'left': 0}, TILE) == {
        'x': 0.5, 'y': 0.5,
    }
    assert util.determine_grid_position(grid_to_pixels(13, 23), TILE) == {
        'x': 13, 'y': 23,
    }


def test_snap_to_grid_rounds_only_the_axis_of_travel(util):
    """This is what preserves the half-tile x while descending into the house."""
    snapped = util.snap_to_grid({'x': 13.5, 'y': 11.9}, 'down', TILE)
    grid = pixels_to_grid(snapped)
    assert grid['x'] == pytest.approx(13.5), 'x must be untouched'
    assert grid['y'] == pytest.approx(12)


@pytest.mark.parametrize('direction, y, expected', [
    ('down', 11.9, 12),      # ceil
    ('right', 11.9, 11.9),   # untouched (x axis rounds instead)
    ('up', 11.9, 11),        # floor
])
def test_rounding_direction(util, direction, y, expected):
    snapped = util.snap_to_grid({'x': 5, 'y': y}, direction, TILE)
    assert pixels_to_grid(snapped)['y'] == pytest.approx(expected)


@pytest.mark.parametrize('direction, opposite', [
    ('up', 'down'), ('down', 'up'), ('left', 'right'), ('right', 'left'),
])
def test_opposite_directions(util, direction, opposite):
    assert util.get_opposite_direction(direction) == opposite
    assert util.turning_around(direction, opposite) is True
    assert util.turning_around(direction, direction) is False


@pytest.mark.parametrize('direction, prop, sign', [
    ('up', 'top', -1), ('down', 'top', 1),
    ('left', 'left', -1), ('right', 'left', 1),
])
def test_velocity_signs(util, direction, prop, sign):
    assert util.get_property_to_change(direction) == prop
    assert util.get_velocity(direction, 10) == 10 * sign


def test_wall_collision_detects_walls(util):
    # Row 0 is solid, so moving up from row 1 hits it.
    assert util.check_for_wall_collision({'x': 1, 'y': 0.4}, MAZE_ARRAY, 'up')
    # Row 1 is open.
    assert not util.check_for_wall_collision({'x': 2, 'y': 1}, MAZE_ARRAY, 'right')


def test_wall_collision_off_the_tunnel_is_not_a_wall(util):
    """Walking off the end of row 14 must be legal - the warp handles it.

    A negative Python index would wrap to the far side of the row and report a
    wall, sealing the tunnel shut.
    """
    assert not util.check_for_wall_collision(
        {'x': -1, 'y': 14}, MAZE_ARRAY, 'left',
    )
    assert not util.check_for_wall_collision(
        {'x': MAZE_COLUMNS + 1, 'y': 14}, MAZE_ARRAY, 'right',
    )


def test_interpolation_between_steps(util):
    old = {'top': 0, 'left': 0}
    new = {'top': 10, 'left': 20}
    assert util.calculate_new_draw_value(0.5, 'top', old, new) == 5
    assert util.calculate_new_draw_value(0.5, 'left', old, new) == 10
    assert util.calculate_new_draw_value(1.0, 'left', old, new) == 20


def test_stutter_hides_a_teleporting_character(util):
    """One tile of separation cleanly distinguishes a warp from real movement."""
    assert util.check_for_stutter(
        {'top': 0, 'left': 0}, {'top': 0, 'left': TILE * 27}, TILE,
    ) is True
    # The fastest legitimate step (~0.37 tiles) must never trip it.
    assert util.check_for_stutter(
        {'top': 0, 'left': 3}, {'top': 0, 'left': 0}, TILE,
    ) is False


def test_approx_tolerance_is_far_below_a_single_step():
    """The float tolerance must not be able to merge two real positions."""
    assert approx(13.5, 13.5 + 1e-9)
    assert not approx(13.5, 13.55)      # smaller than one eye step


# ---------------------------------------------------------------------------
# Warp
# ---------------------------------------------------------------------------

def test_warp_wraps_left_to_right(util):
    # The threshold is grid x < -0.75, so the character has to be most of a
    # tile past the edge (engine.js:3103).
    warped = util.handle_warp(
        {'top': TILE * 13.5, 'left': -TILE * 1.5}, TILE, MAZE_ARRAY,
    )
    assert warped['left'] == pytest.approx(TILE * (MAZE_COLUMNS - 0.75))


def test_warp_does_not_trigger_just_past_the_edge(util):
    """grid x of -0.5 is not yet far enough - it must reach -0.75."""
    position = {'top': TILE * 13.5, 'left': -TILE}
    assert util.handle_warp(position, TILE, MAZE_ARRAY) == position


def test_warp_wraps_right_to_left(util):
    warped = util.handle_warp(
        {'top': TILE * 13.5, 'left': TILE * MAZE_COLUMNS}, TILE, MAZE_ARRAY,
    )
    assert warped['left'] == pytest.approx(TILE * -1.25)


def test_warp_leaves_normal_positions_alone(util):
    position = {'top': TILE * 13.5, 'left': TILE * 13}
    assert util.handle_warp(position, TILE, MAZE_ARRAY) == position


def test_pacman_traverses_the_tunnel_end_to_end():
    """End to end: walking left off row 14 reappears on the right."""
    harness = Harness()
    harness.place_pacman(6, 14, 'left')
    harness.pacman.moving = True

    for _ in range(600):
        harness.pacman.update(SIM_DT_MS)
        if pixels_to_grid(harness.pacman.position)['x'] > 20:
            break

    grid = pixels_to_grid(harness.pacman.position)
    assert grid['x'] > 20, 'Pacman never wrapped through the tunnel'
    assert grid['y'] == pytest.approx(14)


# ---------------------------------------------------------------------------
# Pacman movement
# ---------------------------------------------------------------------------

def test_pacman_starts_below_the_ghost_house(harness):
    """engine.js:939."""
    assert harness.pacman.position == {
        'top': TILE * 22.5, 'left': TILE * 13,
    }
    assert harness.pacman.direction == 'left'
    assert harness.pacman.moving is False


def test_pacman_does_not_move_until_told_to(harness):
    start = dict(harness.pacman.position)
    for _ in range(120):
        harness.pacman.update(SIM_DT_MS)
    assert harness.pacman.position == start


def test_pacman_moves_along_a_corridor(harness):
    harness.place_pacman(13, 23, 'left')
    harness.pacman.moving = True

    for _ in range(60):
        harness.pacman.update(SIM_DT_MS)

    assert pixels_to_grid(harness.pacman.position)['x'] < 13


def test_pacman_stops_at_a_wall(harness):
    """Row 23 runs out at x=1; he must stop rather than pass through."""
    harness.place_pacman(2, 23, 'left')
    harness.pacman.moving = True

    for _ in range(600):
        harness.pacman.update(SIM_DT_MS)

    grid = pixels_to_grid(harness.pacman.position)
    assert grid['x'] >= 1
    assert harness.pacman.moving is False


def test_desired_direction_is_buffered_until_the_turn_is_legal(harness):
    """engine.js:1008 - a turn pressed before a junction still registers.

    This buffering is a large part of how the controls feel and is easy to lose
    in a port, so it is pinned here.
    """
    harness.place_pacman(13, 26, 'left')
    harness.pacman.moving = True

    # Ask to go up while in a horizontal corridor with walls above.
    harness.pacman.change_direction('up', True)
    assert harness.pacman.desired_direction == 'up'

    harness.pacman.update(SIM_DT_MS)
    assert harness.pacman.direction == 'left', 'the turn is not legal yet'
    assert harness.pacman.desired_direction == 'up', 'but it is remembered'

    # Travel until a tile that does allow it.
    for _ in range(600):
        harness.pacman.update(SIM_DT_MS)
        if harness.pacman.direction == 'up':
            break

    assert harness.pacman.direction == 'up', 'the buffered turn eventually fires'


def test_pacman_can_reverse_immediately_mid_corridor(harness):
    """Unlike the ghosts, Pacman may turn around between tiles (engine.js:1048)."""
    harness.place_pacman(13, 26, 'left')
    harness.pacman.moving = True
    harness.pacman.update(SIM_DT_MS)     # get off the grid line

    harness.pacman.change_direction('right', True)
    harness.pacman.update(SIM_DT_MS)

    assert harness.pacman.direction == 'right'


def test_arrow_sprite_follows_the_desired_direction(harness):
    harness.pacman.change_direction('up', False)
    assert harness.pacman.arrow_sheet == 'arrow_up'
    harness.pacman.change_direction('right', False)
    assert harness.pacman.arrow_sheet == 'arrow_right'


def test_sprite_sheet_follows_the_actual_direction(harness):
    harness.pacman.set_sprite_sheet('down')
    assert harness.pacman.sheet == 'pacman_down'


# ---------------------------------------------------------------------------
# Animation
# ---------------------------------------------------------------------------

def test_pacman_animation_loops_over_four_frames(harness, util):
    pacman = harness.pacman
    assert pacman.sprite_frames == 4
    assert pacman.ms_between_sprites == 50

    offsets = []
    for _ in range(8):
        pacman.ms_since_last_sprite = 100
        updated = util.advance_sprite_sheet(pacman)
        pacman.background_offset_pixels = updated['backgroundOffsetPixels']
        offsets.append(pacman.background_offset_pixels // pacman.measurement)

    assert offsets == [1, 2, 3, 0, 1, 2, 3, 0]


def test_death_animation_is_twelve_frames_and_does_not_loop(harness, util):
    """engine.js:976 - it stops on the last frame."""
    pacman = harness.pacman
    pacman.prep_death_animation()

    assert pacman.sprite_frames == 12
    assert pacman.ms_between_sprites == 125
    assert pacman.loop_animation is False
    assert pacman.arrow_sheet is None

    for _ in range(30):
        pacman.ms_since_last_sprite = 200
        updated = util.advance_sprite_sheet(pacman)
        pacman.background_offset_pixels = updated['backgroundOffsetPixels']

    assert pacman.background_offset_pixels == pacman.measurement * 11, (
        'the death animation must hold its final frame, not wrap to 0'
    )


def test_ghost_animation_is_two_frames_at_250ms(harness):
    for ghost in harness.ghosts:
        assert ghost.sprite_frames == 2
        assert ghost.ms_between_sprites == 250


def test_animation_does_not_advance_when_animate_is_false(harness, util):
    """Eating a ghost freezes every ghost's animation (engine.js:2399)."""
    ghost = harness.blinky
    ghost.animate = False
    ghost.ms_since_last_sprite = 1000

    updated = util.advance_sprite_sheet(ghost)
    assert updated['backgroundOffsetPixels'] == 0


# ---------------------------------------------------------------------------
# Ghost speeds in context
# ---------------------------------------------------------------------------

def test_ghost_slows_in_the_tunnel(harness):
    """is_in_tunnel is row 14 with x < 6 or x > 21 (engine.js:225)."""
    ghost = harness.blinky
    assert ghost.determine_velocity({'x': 3, 'y': 14}, 'chase') == pytest.approx(
        ghost.transition_speed,
    )
    assert ghost.determine_velocity({'x': 25, 'y': 14}, 'chase') == pytest.approx(
        ghost.transition_speed,
    )
    # x=8 on row 14 is neither tunnel nor ghost house, so full speed.
    assert ghost.determine_velocity({'x': 8, 'y': 14}, 'chase') == pytest.approx(
        ghost.default_speed,
    )


def test_ghost_slows_in_the_house(harness):
    """is_in_ghost_house is 9 < x < 18 and 11 < y < 17 (engine.js:237).

    Note that row 14 at x=13 is inside the house, not the tunnel - the two
    regions meet on that row.
    """
    ghost = harness.blinky
    assert ghost.determine_velocity({'x': 13, 'y': 14}, 'chase') == pytest.approx(
        ghost.transition_speed,
    )
    assert ghost.determine_velocity({'x': 13, 'y': 13}, 'chase') == pytest.approx(
        ghost.transition_speed,
    )
    # Just outside the house boundary on both axes.
    assert ghost.determine_velocity({'x': 9, 'y': 13}, 'chase') == pytest.approx(
        ghost.default_speed,
    )
    assert ghost.determine_velocity({'x': 13, 'y': 11}, 'chase') == pytest.approx(
        ghost.default_speed,
    )


def test_eyes_ignore_the_pause_flag(harness):
    """Order matters in determine_velocity - eyes are checked before paused."""
    ghost = harness.blinky
    ghost.pause(True)
    assert ghost.determine_velocity({'x': 5, 'y': 5}, 'eyes') == pytest.approx(
        ghost.eye_speed,
    )
    assert ghost.determine_velocity({'x': 5, 'y': 5}, 'chase') == 0


def test_tunnel_slowdown_outranks_scared_speed(harness):
    ghost = harness.blinky
    assert ghost.determine_velocity({'x': 3, 'y': 14}, 'scared') == pytest.approx(
        ghost.transition_speed,
    )
    assert ghost.determine_velocity({'x': 13, 'y': 5}, 'scared') == pytest.approx(
        ghost.scared_speed,
    )


# ---------------------------------------------------------------------------
# Collision
# ---------------------------------------------------------------------------

def test_ghost_contact_kills_pacman(harness):
    harness.place_pacman(13, 23)
    harness.place_ghost(harness.blinky, 13, 23, 'left')
    harness.blinky.mode = 'chase'

    harness.blinky.check_collision({'x': 13, 'y': 23}, {'x': 13, 'y': 23})
    assert 'deathSequence' in harness.names_fired()


def test_scared_ghost_contact_is_eaten_instead(harness):
    harness.place_ghost(harness.blinky, 13, 23, 'left', mode='scared')

    harness.blinky.check_collision({'x': 13, 'y': 23}, {'x': 13, 'y': 23})
    assert 'eatGhost' in harness.names_fired()
    assert 'deathSequence' not in harness.names_fired()
    assert harness.blinky.mode == 'eyes'


def test_eyes_do_not_collide(harness):
    harness.place_ghost(harness.blinky, 13, 23, 'left', mode='eyes')
    harness.blinky.check_collision({'x': 13, 'y': 23}, {'x': 13, 'y': 23})
    assert harness.names_fired() == []


def test_collision_requires_less_than_one_tile(harness):
    harness.blinky.mode = 'chase'
    harness.blinky.check_collision({'x': 13, 'y': 23}, {'x': 14, 'y': 23})
    assert harness.names_fired() == [], 'exactly one tile apart is not contact'


def test_allow_collision_flag_suppresses_contact(harness):
    """Set while a ghost is being eaten (engine.js:2401)."""
    harness.blinky.mode = 'chase'
    harness.blinky.allow_collision = False
    harness.blinky.check_collision({'x': 13, 'y': 23}, {'x': 13, 'y': 23})
    assert harness.names_fired() == []
