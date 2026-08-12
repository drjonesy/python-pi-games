"""Ghost AI targeting, table-driven against §7 of the rewrite instructions."""

import pytest

from conftest import Harness, grid_to_pixels
from games.pacman.characters.ghost import CLYDE_RETREAT, GHOST_HOUSE_TARGET


@pytest.mark.parametrize('name, expected', [
    ('blinky', {'x': 27, 'y': 0}),
    ('pinky', {'x': 0, 'y': 0}),
    ('inky', {'x': 27, 'y': 30}),
    ('clyde', {'x': 0, 'y': 30}),
])
def test_scatter_targets(harness, name, expected):
    ghost = getattr(harness, name)
    target = ghost.get_target(name, {'x': 5, 'y': 5}, {'x': 10, 'y': 10},
                              'scatter')
    assert target == expected


def test_blinky_chases_during_scatter_when_cruise_elroy(harness):
    """Deliberate exception: Elroy Blinky ignores his scatter corner."""
    pacman_position = {'x': 10, 'y': 20}

    assert harness.blinky.get_target(
        'blinky', {'x': 5, 'y': 5}, pacman_position, 'scatter',
    ) == {'x': 27, 'y': 0}

    harness.blinky.cruise_elroy = True
    assert harness.blinky.get_target(
        'blinky', {'x': 5, 'y': 5}, pacman_position, 'scatter',
    ) == pacman_position


def test_blinky_chase_targets_pacman(harness):
    pacman_position = {'x': 12, 'y': 18}
    assert harness.blinky.get_target(
        'blinky', {'x': 1, 'y': 1}, pacman_position, 'chase',
    ) == pacman_position


@pytest.mark.parametrize('direction, expected', [
    ('up', {'x': 10, 'y': 16}),
    ('down', {'x': 10, 'y': 24}),
    ('left', {'x': 6, 'y': 20}),
    ('right', {'x': 14, 'y': 20}),
])
def test_pinky_targets_four_tiles_ahead(harness, direction, expected):
    """engine.js:327. A single axis is offset - no arcade overflow bug."""
    harness.pacman.direction = direction
    assert harness.pinky.determine_pinky_target({'x': 10, 'y': 20}) == expected


def test_pinky_up_target_has_no_overflow_bug(harness):
    """The arcade's Pinky bug also shifted x by 4 when facing up. Not here."""
    harness.pacman.direction = 'up'
    target = harness.pinky.determine_pinky_target({'x': 10, 'y': 20})
    assert target['x'] == 10, 'x must be untouched when Pacman faces up'


def test_inky_mirrors_blinky_through_a_pivot(harness):
    """target = pivot + (pivot - blinky), pivot 2 tiles ahead (engine.js:340)."""
    harness.pacman.direction = 'right'
    harness.blinky.position = grid_to_pixels(5, 5)

    # pivot = (12, 20); target = (12 + (12-5), 20 + (20-5)) = (19, 35)
    assert harness.inky.determine_inky_target({'x': 10, 'y': 20}) == {
        'x': 19, 'y': 35,
    }


def test_inky_target_collapses_onto_pivot_when_blinky_is_there(harness):
    harness.pacman.direction = 'right'
    harness.blinky.position = grid_to_pixels(12, 20)
    assert harness.inky.determine_inky_target({'x': 10, 'y': 20}) == {
        'x': 12, 'y': 20,
    }


@pytest.mark.parametrize('ghost_pos, pacman_pos, chases', [
    ({'x': 1, 'y': 1}, {'x': 20, 'y': 20}, True),     # far -> chase
    ({'x': 10, 'y': 10}, {'x': 11, 'y': 11}, False),  # close -> retreat
    ({'x': 0, 'y': 0}, {'x': 0, 'y': 9}, True),       # 9 tiles -> chase
    ({'x': 0, 'y': 0}, {'x': 0, 'y': 8}, False),      # exactly 8 -> retreat
])
def test_clyde_flips_at_eight_tiles(harness, ghost_pos, pacman_pos, chases):
    """`distance > 8` - so exactly 8 retreats (engine.js:362)."""
    target = harness.clyde.determine_clyde_target(ghost_pos, pacman_pos)
    assert target == (pacman_pos if chases else CLYDE_RETREAT)


def test_eyes_target_the_ghost_house(harness):
    for ghost in harness.ghosts:
        assert ghost.get_target(
            ghost.name, {'x': 1, 'y': 1}, {'x': 20, 'y': 20}, 'eyes',
        ) == GHOST_HOUSE_TARGET


def test_scared_target_is_pacman_but_movement_flees(harness):
    """The target is Pacman; the *comparison* inverts (engine.js:429-439).

    A sign error in either half makes scared ghosts hunt the player, so both
    are pinned: same possible moves, opposite choice.
    """
    ghost = harness.blinky
    pacman_position = {'x': 10, 'y': 20}

    assert ghost.get_target('blinky', {'x': 5, 'y': 5}, pacman_position,
                            'scared') == pacman_position

    # Two candidate tiles: one nearer Pacman, one further away.
    possible_moves = {
        'down': {'x': 5, 'y': 6},     # closer to (10, 20)
        'up': {'x': 5, 'y': 4},       # further from (10, 20)
    }

    chase_move = ghost.determine_best_move(
        'blinky', possible_moves, {'x': 5, 'y': 5}, pacman_position, 'chase',
    )
    scared_move = ghost.determine_best_move(
        'blinky', possible_moves, {'x': 5, 'y': 5}, pacman_position, 'scared',
    )

    assert chase_move == 'down'
    assert scared_move == 'up'


def test_scared_ghost_increases_distance_over_time(harness):
    """End to end: a scared ghost in the open gets further from Pacman."""
    ghost = harness.blinky
    harness.place_pacman(13, 23)
    harness.place_ghost(ghost, 6, 23, 'left', mode='scared')

    start = ghost.calculate_distance(
        {'x': 6, 'y': 23}, {'x': 13, 'y': 23},
    )

    from games.pacman.constants import SIM_DT_MS
    for _ in range(240):        # ~2 seconds
        ghost.update(SIM_DT_MS)

    grid = harness.blinky.character_util.determine_grid_position(
        ghost.position, ghost.scaled_tile_size,
    )
    end = ghost.calculate_distance(grid, {'x': 13, 'y': 23})

    assert end > start


def test_ghosts_cannot_reverse_at_a_junction(harness):
    """engine.js:282 removes the opposite direction from the candidate list."""
    ghost = harness.blinky
    moves = ghost.determine_possible_moves(
        {'x': 6, 'y': 5}, 'right', harness.pacman.maze_array,
    )
    assert 'left' not in moves


def test_possible_moves_keep_up_down_left_right_order(harness):
    """Insertion order is the tie-break rule - up beats down beats left."""
    ghost = harness.blinky
    moves = ghost.determine_possible_moves(
        {'x': 6, 'y': 5}, 'up', harness.pacman.maze_array,
    )
    assert list(moves) == [
        key for key in ('up', 'down', 'left', 'right') if key in moves
    ]


def test_fractional_x_yields_no_legal_moves(harness):
    """On the house centre line every lookup misses, so direction is kept.

    This is what carries the eyes down into the house; `int()`-ing the index
    here would break respawn.
    """
    ghost = harness.blinky
    moves = ghost.determine_possible_moves(
        {'x': 13.5, 'y': 12}, 'down', harness.pacman.maze_array,
    )
    assert moves == {}

    direction = ghost.determine_direction(
        'blinky', {'x': 13.5, 'y': 12}, {'x': 13, 'y': 23}, 'down',
        harness.pacman.maze_array, 'eyes',
    )
    assert direction == 'down'


def test_change_mode_reverses_direction_but_not_for_elroy(harness):
    """A forced mode change is the only legal reversal - unless Elroy."""
    ghost = harness.pinky
    harness.place_ghost(ghost, 6, 5, 'right')
    ghost.mode = 'scatter'
    ghost.change_mode('chase')
    assert ghost.direction == 'left'
    assert ghost.mode == 'chase'

    elroy = harness.blinky
    harness.place_ghost(elroy, 6, 5, 'right')
    elroy.mode = 'scatter'
    elroy.cruise_elroy = True
    elroy.change_mode('chase')
    assert elroy.direction == 'right', 'Elroy must not turn around'
    assert elroy.mode == 'scatter'
    assert elroy.default_mode == 'chase'


def test_ghost_in_house_does_not_reverse_on_mode_change(harness):
    ghost = harness.pinky
    harness.place_ghost(ghost, 13, 14, 'down')
    ghost.mode = 'scatter'
    ghost.change_mode('chase')
    assert ghost.direction == 'down'
