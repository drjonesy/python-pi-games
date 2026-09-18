"""Every number DINO RUN plays by.

Positions are in the cabinet's 224x296 logical pixels, times in milliseconds and
speeds in pixels per second. The art sizes here are also what
`tools/convert_dino_assets.py` scales the source art to, so the drawing and the
hitboxes cannot drift apart.

Pure data - no pygame - so the build tool and the tests can import it without a
display.
"""

from cabinet import constants as C

# --------------------------------------------------------------------------
# Layout
# --------------------------------------------------------------------------
SCREEN_W = C.LOGICAL_WIDTH
SCREEN_H = C.LOGICAL_HEIGHT

SKY = C.WHITE
INK = C.ARCADE_DARK

# The ground strip, flowers and jagged top edge included, runs to the bottom of
# the screen. Its art is scaled to exactly this height.
GRASS_HEIGHT = 52
GRASS_TOP = SCREEN_H - GRASS_HEIGHT
# The row the dinosaur's feet and every obstacle's base stand on: a little way
# into the light-green field rather than on the jagged edge, as in the scenes.
FEET_Y = GRASS_TOP + 19

# Where the dinosaur runs, measured to the tip of its tail - the left edge of
# every frame. Its body starts ~12px further right. Far enough left that most
# of the screen is warning.
DINO_X = 14

# --------------------------------------------------------------------------
# Art sizes (what the build tool scales to)
# --------------------------------------------------------------------------
DINO_HEIGHT = 46       # the run cycle, head to feet
ROCK_HEIGHT = 24
BIRD_HEIGHT = 26
# Only used to decide when an obstacle has left the screen.
OBSTACLE_MAX_WIDTH = 48

# --------------------------------------------------------------------------
# Hitboxes
# --------------------------------------------------------------------------
# Relative to the anchor (DINO_X, feet), as (left, top, width, height) with top
# measured *upward* from the feet. Deliberately smaller than the drawing: this
# is played with feet on a mat, and a clipped tail is not a fair death.
DINO_HITBOX = (12, 38, 22, 36)
DUCK_HITBOX = (6, 26, 46, 24)

# Relative to the obstacle sprite's top-left, as (left, top, width, height)
# measured downward, like the art.
ROCK_HITBOX = (6, 6, 28, 18)
BIRD_HITBOX = (6, 6, 34, 14)

# --------------------------------------------------------------------------
# Obstacles
# --------------------------------------------------------------------------
# A bird flies at one of two heights, measured from the feet row to the bottom
# of its sprite. LOW skims the grass and must be jumped; HIGH is at head height
# and must be ducked. The numbers are pinned by tests/test_dino.py: standing
# must hit HIGH, ducking must clear it, and a jump must clear LOW.
BIRD_LOW = 4
BIRD_HIGH = 26

ROCK = 'rock'
BIRD_LOW_KIND = 'bird_low'
BIRD_HIGH_KIND = 'bird_high'
OBSTACLE_KINDS = (ROCK, BIRD_LOW_KIND, BIRD_HIGH_KIND)
# Relative odds of each kind being the next one.
OBSTACLE_WEIGHTS = (3, 1, 2)

# Time between one obstacle entering and the next, chosen at random in this
# range. In time rather than distance so the spacing stretches with speed and a
# landing always leaves room for the next jump.
SPAWN_GAP_MIN_MS = 1300
SPAWN_GAP_MAX_MS = 2400
# The first obstacle, after the player has had a moment to find the panels.
FIRST_SPAWN_MS = 1500

BIRD_FLAP_MS = 110     # per frame of the flap cycle

# --------------------------------------------------------------------------
# Speed
# --------------------------------------------------------------------------
# The ground and everything on it. Starts slow; every SPEED_STEP_MS of play
# it gains SPEED_STEP of its *current* value, so it compounds.
START_SPEED = 140.0
SPEED_STEP = 0.10
SPEED_STEP_MS = 10_000

# --------------------------------------------------------------------------
# Jump and duck
# --------------------------------------------------------------------------
# A fixed arc whatever the speed: apex JUMP_HEIGHT, JUMP_MS in the air.
JUMP_HEIGHT = 64.0
JUMP_MS = 800.0
GRAVITY = 8.0 * JUMP_HEIGHT / (JUMP_MS / 1000.0) ** 2      # px/s^2
JUMP_VELOCITY = 4.0 * JUMP_HEIGHT / (JUMP_MS / 1000.0)     # px/s, upward
# Holding ▼ in the air pulls the dinosaur down this many times faster, so a
# jump taken too early can be cut short.
FAST_FALL = 3.0

# A ▲ step that lands this long before touchdown still jumps on touchdown. On a
# mat a step is slow and a foot arrives early more often than late.
JUMP_BUFFER_MS = 160

# A duck lasts at least this long even if the panel is let go at once: a step
# on a mat can be a very short press, and a duck that ends before the bird
# arrives is no duck at all. Held longer, it lasts as long as it is held.
DUCK_MIN_MS = 700

# --------------------------------------------------------------------------
# Animation and the end of a run
# --------------------------------------------------------------------------
RUN_FRAMES = 8
JUMP_FRAMES = 12
DEAD_FRAMES = 8
# The run cycle's rate at START_SPEED; it quickens with the ground.
RUN_FRAME_MS = 80
DEAD_FRAME_MS = 90
# From the collision to the score being offered: the fall, then GAME OVER.
GAME_OVER_MS = 2200
# ▲ or START skips the rest of the wait, but not before this: a player stamping
# ▲ as the dinosaur dies must still get to see GAME OVER.
GAME_OVER_SKIP_MS = 1200
