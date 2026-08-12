"""Maze integrity (§13).

If the dot count drifts, every dot threshold in the game - fruit at 174/74,
Cruise Elroy at 40/20, level advance at 0 - silently stops firing.
"""

import pytest

from games.pacman.constants import MAZE_COLUMNS, MAZE_ROWS, TOTAL_PICKUPS
from games.pacman.maze import MAZE_ARRAY, get_tile, validate_maze


def test_dimensions():
    assert len(MAZE_ARRAY) == MAZE_ROWS
    for row in MAZE_ARRAY:
        assert len(row) == MAZE_COLUMNS


def test_pickup_counts():
    counts = validate_maze()
    assert counts['pacdots'] == 240
    assert counts['pellets'] == 4
    assert counts['pacdots'] + counts['pellets'] == TOTAL_PICKUPS == 244


def test_power_pellets_are_on_rows_three_and_twenty_three():
    """§5 - four pellets, in the corners of the playfield."""
    rows = {
        index for index, row in enumerate(MAZE_ARRAY) if 'O' in row
    }
    assert rows == {3, 23}

    positions = [
        (index, row.index('O')) for index, row in enumerate(MAZE_ARRAY)
        if 'O' in row
    ]
    assert positions == [(3, 1), (23, 1)]
    # And the mirrored pair on the right-hand side.
    assert [row.count('O') for row in MAZE_ARRAY if 'O' in row] == [2, 2]


def test_only_expected_characters_appear():
    allowed = {'X', 'o', 'O', ' '}
    for row in MAZE_ARRAY:
        assert set(row) <= allowed


def test_walls_enclose_the_board_except_the_tunnel():
    """Top and bottom rows are solid; the sides open only on the tunnel row."""
    assert set(MAZE_ARRAY[0]) == {'X'}
    assert set(MAZE_ARRAY[MAZE_ROWS - 1]) == {'X'}

    for index, row in enumerate(MAZE_ARRAY):
        if index == 14:
            assert row[0] == ' ' and row[MAZE_COLUMNS - 1] == ' '
        else:
            assert row[0] == 'X', f'row {index} is open on the left'
            assert row[MAZE_COLUMNS - 1] == 'X', f'row {index} open on the right'


def test_tunnel_row_is_passable_end_to_end():
    """Row 14 must have no wall anywhere, or the warp is unreachable."""
    assert 'X' not in MAZE_ARRAY[14][:6]
    assert 'X' not in MAZE_ARRAY[14][22:]


def test_get_tile_rejects_walls_and_accepts_open_space():
    assert get_tile(MAZE_ARRAY, 0, 0) is False          # wall
    assert get_tile(MAZE_ARRAY, 1, 1) == {'x': 1, 'y': 1}   # pac-dot
    assert get_tile(MAZE_ARRAY, 3, 1) == {'x': 1, 'y': 3}   # power pellet
    assert get_tile(MAZE_ARRAY, 14, 0) == {'x': 0, 'y': 14}  # bare space


def test_get_tile_rejects_fractional_indices():
    """`mazeArray[11][13.5]` is undefined in JS - and must miss here too."""
    assert get_tile(MAZE_ARRAY, 11, 13.5) is False
    assert get_tile(MAZE_ARRAY, 11.5, 13) is False


@pytest.mark.parametrize('y, x', [
    (14, -1), (14, 28), (-1, 1), (31, 1), (14, -5), (100, 100),
])
def test_get_tile_rejects_out_of_range_without_wrapping(y, x):
    """A negative index must not wrap round and report the far side of the row.

    If it did, the tunnel would appear walled off and the warp would never
    trigger.
    """
    assert get_tile(MAZE_ARRAY, y, x) is False


def test_ghost_house_region_is_open():
    """The area Ghost.is_in_ghost_house covers must actually be enterable."""
    assert MAZE_ARRAY[14][13] == ' '
    assert MAZE_ARRAY[11][13] == ' '


def test_validate_maze_rejects_a_broken_board():
    broken = [list(row) for row in MAZE_ARRAY]
    broken[1][1] = ' '          # remove one pac-dot
    with pytest.raises(AssertionError):
        validate_maze(broken)
