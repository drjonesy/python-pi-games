"""The maze array and tile queries (engine.js:1203-1239).

MAZE_ARRAY is copied verbatim from the reference. Legend:

===== =========================================
``X`` wall
``o`` pac-dot
``O`` power pellet (4 total, on rows 3 and 23)
` `   open, no pickup
===== =========================================
"""

from .constants import MAZE_COLUMNS, MAZE_ROWS, TOTAL_PICKUPS

# engine.js:1204-1235
MAZE_ROWS_RAW = [
    'XXXXXXXXXXXXXXXXXXXXXXXXXXXX',
    'XooooooooooooXXooooooooooooX',
    'XoXXXXoXXXXXoXXoXXXXXoXXXXoX',
    'XOXXXXoXXXXXoXXoXXXXXoXXXXOX',
    'XoXXXXoXXXXXoXXoXXXXXoXXXXoX',
    'XooooooooooooooooooooooooooX',
    'XoXXXXoXXoXXXXXXXXoXXoXXXXoX',
    'XoXXXXoXXoXXXXXXXXoXXoXXXXoX',
    'XooooooXXooooXXooooXXooooooX',
    'XXXXXXoXXXXX XX XXXXXoXXXXXX',
    'XXXXXXoXXXXX XX XXXXXoXXXXXX',
    'XXXXXXoXX          XXoXXXXXX',
    'XXXXXXoXX XXXXXXXX XXoXXXXXX',
    'XXXXXXoXX X      X XXoXXXXXX',
    '      o   X      X   o      ',
    'XXXXXXoXX X      X XXoXXXXXX',
    'XXXXXXoXX XXXXXXXX XXoXXXXXX',
    'XXXXXXoXX          XXoXXXXXX',
    'XXXXXXoXX XXXXXXXX XXoXXXXXX',
    'XXXXXXoXX XXXXXXXX XXoXXXXXX',
    'XooooooooooooXXooooooooooooX',
    'XoXXXXoXXXXXoXXoXXXXXoXXXXoX',
    'XoXXXXoXXXXXoXXoXXXXXoXXXXoX',
    'XOooXXooooooo  oooooooXXooOX',
    'XXXoXXoXXoXXXXXXXXoXXoXXoXXX',
    'XXXoXXoXXoXXXXXXXXoXXoXXoXXX',
    'XooooooXXooooXXooooXXooooooX',
    'XoXXXXXXXXXXoXXoXXXXXXXXXXoX',
    'XoXXXXXXXXXXoXXoXXXXXXXXXXoX',
    'XooooooooooooooooooooooooooX',
    'XXXXXXXXXXXXXXXXXXXXXXXXXXXX',
]

# engine.js:1237-1239 splits each row string into a list of characters.
MAZE_ARRAY = [list(row) for row in MAZE_ROWS_RAW]


def validate_maze(maze_array=None):
    """Asserts the board's integrity at load time (rewrite instructions §5).

    `remaining_dots` counts pac-dots *and* power pellets (engine.js:1713), so
    it starts at 244 and every dot threshold in the game - fruit at 174/74,
    Cruise Elroy at 40/20 - is relative to that. If this count ever drifts,
    those thresholds silently stop firing, so it is checked rather than
    trusted.
    """
    maze_array = maze_array if maze_array is not None else MAZE_ARRAY

    assert len(maze_array) == MAZE_ROWS, (
        f'expected {MAZE_ROWS} rows, got {len(maze_array)}'
    )
    for index, row in enumerate(maze_array):
        assert len(row) == MAZE_COLUMNS, (
            f'row {index} has {len(row)} columns, expected {MAZE_COLUMNS}'
        )

    pacdots = sum(row.count('o') for row in maze_array)
    pellets = sum(row.count('O') for row in maze_array)

    assert pacdots == 240, f'expected 240 pac-dots, got {pacdots}'
    assert pellets == 4, f'expected 4 power pellets, got {pellets}'
    assert pacdots + pellets == TOTAL_PICKUPS

    return {'pacdots': pacdots, 'pellets': pellets}


def get_tile(maze_array, y, x):
    """An x-y pair if the tile is open, otherwise False (engine.js:251).

    Two JS behaviours are load-bearing here and are reproduced deliberately:

    1. **Fractional indices miss.** `mazeArray[11][13.5]` is `undefined` in JS,
       so a ghost sitting at x=13.5 (the ghost-house centre line) finds *no*
       legal moves and simply keeps its current direction. That is precisely
       how the eyes descend into the house, so a naive `int()` here would break
       respawn.
    2. **Out-of-range indices miss.** A negative index must not wrap to the far
       end of the row, or the tunnel at row 14 would report a wall.

    Open tiles are ``' '``, ``'o'`` and ``'O'`` - note the reference's
    truthiness test treats a space as open (engine.js:254).
    """
    if y != int(y) or x != int(x):
        return False

    y = int(y)
    x = int(x)

    if not (0 <= y < len(maze_array)):
        return False
    row = maze_array[y]
    if not (0 <= x < len(row)):
        return False
    if row[x] == 'X':
        return False

    return {'x': x, 'y': y}
