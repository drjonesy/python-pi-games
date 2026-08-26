"""Every literal Pac-Man needs, in one place.

Each value is annotated with the `engine.js` line it came from so this file can
be diffed against `../node-version/src/game/engine.js` when the reference
changes. Nothing here is a value remembered from the arcade original - where
the codebase deviates from 1980, the codebase wins.

The cabinet-wide values this game uses - the screen, the palette, the loop rates
- are re-exported from `cabinet.constants` rather than duplicated, so game code
can keep saying `C.LOGICAL_WIDTH` and `C.WHITE` while there is still exactly one
definition of each. Only what is actually used here is listed: the rest of the
cabinet's constants (the high-score limits, the name-entry cap) belong to code
that is not this game's.
"""

from cabinet.constants import (      # noqa: F401  (re-exported for game code)
    ARCADE_CYAN,
    ARCADE_DARK,
    ARCADE_GREY,
    ARCADE_PALE,
    ARCADE_RED,
    ARCADE_YELLOW,
    BLACK,
    DIRECTIONS,
    LOGICAL_HEIGHT,
    LOGICAL_WIDTH,
    MAX_STEPS_PER_FRAME,
    MAZE_BLUE,
    PACMAN_YELLOW,
    RANK_LABELS,
    SIM_DT_MS,
    SIM_HZ,
    WHITE,
)

# --------------------------------------------------------------------------
# Board geometry (engine.js:13-19)
# --------------------------------------------------------------------------
MAZE_COLUMNS = 28              # engine.js:13
MAZE_ROWS = 31                 # engine.js:14
SCORE_ROW_TILES = 3            # engine.js:15
SCORE_GAP_TILES = 1            # engine.js:16
BOTTOM_ROW_TILES = 2           # engine.js:17

# The vertical budget is the whole game column, not just the maze. Measuring
# only the maze picks a scale ~18% too large and clips the score and lives
# rows off the top and bottom (engine.js:1275-1279).
TOTAL_UI_TILES = SCORE_ROW_TILES + SCORE_GAP_TILES + MAZE_ROWS + BOTTOM_ROW_TILES

TILE_SIZE = 4                  # engine.js:1165

# The art is authored at 8px per tile (maze_blue.svg is 224x248 = 28x31 tiles,
# character sheets are 16px frames = 2x2 tiles), so a scale of 2 rasterizes
# every SVG at exactly 1:1 with no resampling. determineScale's viewport logic
# is dropped for the native port - the scale is fixed and pygame.SCALED
# stretches the finished frame to the display (REWRITE-INSTRUCTIONS §5, §11).
SCALE = 2
SCALED_TILE_SIZE = TILE_SIZE * SCALE   # 8

MAZE_WIDTH = SCALED_TILE_SIZE * MAZE_COLUMNS    # 224
MAZE_HEIGHT = SCALED_TILE_SIZE * MAZE_ROWS      # 248

# The cabinet's logical surface was sized from this UI column - 28 tiles wide
# by 37 tall - so the two must still agree. Asserted rather than derived: the
# screen now belongs to the shell, and a game that outgrew it should fail here
# rather than draw off the edge.
assert LOGICAL_WIDTH == MAZE_WIDTH
assert LOGICAL_HEIGHT == SCALED_TILE_SIZE * TOTAL_UI_TILES

# The maze sits below the score row and its gap; every engine coordinate is
# relative to the maze's top-left corner, exactly as it was on the canvas.
MAZE_ORIGIN_X = 0
MAZE_ORIGIN_Y = SCALED_TILE_SIZE * (SCORE_ROW_TILES + SCORE_GAP_TILES)   # 32

# --------------------------------------------------------------------------
# Timing (engine.js:1157-1164, §3 of the rewrite instructions)
# --------------------------------------------------------------------------
# SIM_HZ, SIM_DT_MS, RENDER_FPS and MAX_STEPS_PER_FRAME come from
# `cabinet.constants` (imported above). The cabinet's default happens to be
# Pac-Man's 120Hz, and for this game it must not be lowered: the ghost-house
# handoff matches on exact positions inside windows only 0.2 tiles wide (see
# Ghost.entering_ghost_house / leaving_ghost_house). An eaten ghost travels at
# eye_speed = pacman_speed * 2; at 120Hz that is ~0.18 tiles per step, which
# lands inside the window, but at 60Hz it is ~0.37 tiles and steps clean over
# it - the ghost then circles forever and never respawns.
assert SIM_HZ == 120           # engine.js:1164 (this.maxFps)

# Float tolerance for the grid comparisons the JS code does with `===`. Those
# work only because snapToGrid writes the value; a tolerance keeps float drift
# from breaking respawn. 1e-6 tiles is 8e-6 px - six orders of magnitude below
# the ~1.5px a single step covers, so it can never merge two real positions.
EPSILON = 1e-6

# --------------------------------------------------------------------------
# Speeds (engine.js:93-107, 952-956)
# --------------------------------------------------------------------------
# Pacman moved at 11 tiles per second in the original game (engine.js:953).
PACMAN_TILES_PER_SECOND = 11

SLOW_SPEED_FACTOR = 0.75       # engine.js:96
MEDIUM_SPEED_FACTOR = 0.875    # engine.js:97
FAST_SPEED_FACTOR = 1.0        # engine.js:98
SCARED_SPEED_FACTOR = 0.5      # engine.js:104
TRANSITION_SPEED_FACTOR = 0.4  # engine.js:105
EYE_SPEED_FACTOR = 2.0         # engine.js:106

# --------------------------------------------------------------------------
# Scoring (engine.js:1705-1706, 1580, 2038, 2358)
# --------------------------------------------------------------------------
PACDOT_POINTS = 10             # engine.js:1706
POWER_PELLET_POINTS = 50       # engine.js:1706
STARTING_LIVES = 2             # engine.js:1580 - i.e. three total attempts
EXTRA_LIFE_THRESHOLD = 10000   # engine.js:2038
TOTAL_PICKUPS = 244            # 240 pac-dots + 4 power pellets

# engine.js:1192-1201 - level 9+ falls through to 5000.
FRUIT_POINTS = {
    1: 100,
    2: 300,
    3: 500,
    4: 700,
    5: 1000,
    6: 2000,
    7: 3000,
    8: 5000,
}
FRUIT_POINTS_DEFAULT = 5000    # engine.js:2189

# engine.js:2666-2675
FRUIT_IMAGES = {
    100: 'cherry',
    300: 'strawberry',
    500: 'orange',
    700: 'apple',
    1000: 'melon',
    2000: 'galaxian',
    3000: 'bell',
    5000: 'key',
}

# --------------------------------------------------------------------------
# Thresholds and durations
# --------------------------------------------------------------------------
FRUIT_DOT_THRESHOLDS = (174, 74)       # engine.js:2171
FRUIT_DURATION_MS = 10000              # engine.js:2192
ELROY_DOT_THRESHOLDS = (40, 20)        # engine.js:2175

SCATTER_DURATION_MS = 7000             # engine.js:1903
CHASE_DURATION_MS = 20000              # engine.js:1903
FIRST_CYCLE_MODE = 'scatter'           # engine.js:1848

GAME_START_DURATION_MS = 4500          # engine.js:1827 (first game)
LEVEL_START_DURATION_MS = 2000         # engine.js:1827 (subsequent)

EAT_GHOST_PAUSE_MS = 1000              # engine.js:2367
GHOST_FLASH_COUNT = 9                  # engine.js:2351 flashGhosts(0, 9)
GHOST_FLASH_INTERVAL_MS = 250          # engine.js:2322
POINTS_DISPLAY_MS = 2000               # engine.js:2055
PELLET_BLINK_PERIOD_MS = 300           # engine.js:1785
ONE_UP_BLINK_PERIOD_MS = 600           # game.css `blink` keyframes

# Death sequence (engine.js:2093-2123)
DEATH_FREEZE_MS = 750
DEATH_ANIMATION_MS = 2250
DEATH_COVER_MS = 500

# Game over (engine.js:2138-2160)
GAME_OVER_DELAY_MS = 2250
GAME_OVER_TEXT_MS = 4000
GAME_OVER_COVER_MS = 2500
GAME_OVER_MENU_MS = 1000

# Level advance (engine.js:2245-2277)
LEVEL_ADVANCE_DELAY_MS = 2000
MAZE_FLASH_INTERVAL_MS = 250
LEVEL_ADVANCE_COVER_MS = 250
LEVEL_ADVANCE_RESET_MS = 500

COLLISION_SCAN_INTERVAL_MS = 500       # engine.js:1591 setInterval(..., 500)
# engine.js:1750 - only pickups Pacman could plausibly reach are collided with.
COLLISION_LOOKAHEAD_MS = 750

PAUSE_DEBOUNCE_MS = 500                # engine.js:1998


def power_duration_ms(level):
    """Scared-mode window for a level (engine.js:2349).

    Level 7 and up clamp to 0: the pellet still scores and resets the combo,
    but grants no scared window at all.
    """
    return max((7 - level) * 1000, 0)


def ghost_release_delay_ms(level):
    """Delay before the next idle ghost leaves the house (engine.js:1920).

    Level 1 -> 8000ms, level 2 -> 4000ms, level 3+ -> 0.
    """
    return max((8 - ((level - 1) * 4)) * 1000, 0)


def combo_points(ghost_combo):
    """200/400/800/1600 within a single pellet (engine.js:2359)."""
    return 100 * (2 ** ghost_combo)


# Alternated on the mixer's throttled channel as dots are eaten
# (engine.js:3256). Names are this game's own - they are loaded under the
# `pacman/` prefix and no other game can see them.
DOT_SOUNDS = ('dot_1', 'dot_2')


def determine_siren(remaining_dots):
    """Background siren for the current dot count (engine.js:2211-2223)."""
    if remaining_dots > 40:
        return 'siren_1'
    if remaining_dots > 20:
        return 'siren_2'
    return 'siren_3'


# The palette, the high-score limits and DIRECTIONS are the cabinet's - see the
# re-export at the top of this file.
MAZE_FLASH_TINT = WHITE            # engine.js:8
