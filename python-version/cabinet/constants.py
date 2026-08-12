"""Values the whole cabinet shares, whichever game is running.

Anything specific to one game belongs in that game's own constants module
(`games/pacman/constants.py`). What is here is the screen, the palette, the
loop rates and the shape of a high-score table - the things a second game has
to agree with in order to sit next to the first one.
"""

# --------------------------------------------------------------------------
# Screen
# --------------------------------------------------------------------------
# The logical surface every game draws into. SDL stretches it to the display,
# so this is a fixed resolution rather than a viewport measurement.
#
# The numbers come from Pac-Man's UI column - 28x37 tiles at 8px - because that
# is what the cabinet was built around and the display is mounted portrait. A
# new game is expected to lay itself out inside this, not to change it.
LOGICAL_WIDTH = 224
LOGICAL_HEIGHT = 296

# --------------------------------------------------------------------------
# Loop rates (see `cabinet/engine.py`)
# --------------------------------------------------------------------------
# Defaults only. A game whose simulation needs a different step passes its own
# to `GameEngine`; Pac-Man does, and `games/pacman/constants.py` explains why
# its 120Hz must not be lowered.
SIM_HZ = 120
SIM_DT_MS = 1000.0 / SIM_HZ
RENDER_FPS = 60
# Clamp so a stall cannot compound into a death spiral.
MAX_STEPS_PER_FRAME = 10

# --------------------------------------------------------------------------
# Palette (src/styles/*.css)
# --------------------------------------------------------------------------
BLACK = (0, 0, 0)                   # #000
WHITE = (255, 255, 255)             # #fff
MAZE_BLUE = (0x21, 0x21, 0xff)      # #2121ff
ARCADE_YELLOW = (0xfc, 0xc7, 0x3f)  # #fcc73f
PACMAN_YELLOW = (0xff, 0xdf, 0x00)  # #ffdf00
ARCADE_RED = (0xee, 0x2a, 0x29)     # #ee2a29
ARCADE_CYAN = (0x33, 0xcc, 0xff)    # #33ccff
ARCADE_PALE = (0xff, 0xe9, 0x8a)    # #ffe98a
ARCADE_GREY = (0x9a, 0x9a, 0x9a)    # #9a9a9a
ARCADE_DARK = (0x23, 0x1f, 0x20)    # #231f20

# --------------------------------------------------------------------------
# High-score tables (server/leaderboard.js)
# --------------------------------------------------------------------------
# One table per game, same shape for all of them: three places, a name and a
# score. Every game gets the same board and the same reset.
MAX_ENTRIES = 3                    # leaderboard.js:13
MAX_NAME_LENGTH = 12               # leaderboard.js:14
# ScoreEntry.jsx:4 caps what a player can actually type at 10; the storage
# layer still truncates at 12 so a hand-edited data.json round-trips.
ENTRY_NAME_LENGTH = 10
DEFAULT_NAME = 'AAA'               # leaderboard.js:92

RANK_LABELS = ('1ST', '2ND', '3RD')   # Leaderboard.jsx:4

# --------------------------------------------------------------------------
# Input
# --------------------------------------------------------------------------
DIRECTIONS = ('up', 'down', 'left', 'right')
