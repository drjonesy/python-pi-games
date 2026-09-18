"""The run itself: the dinosaur, the ground, the obstacles and the score.

No pygame here - the cabinet steps this at a fixed rate and `game.py` draws
it, so every rule can be checked headless (tests/test_dino.py).

Heights are **altitudes**: pixels above the feet row, upward positive. Screen
space is only worked out when drawing.

The whole control scheme is two panels. ▲ jumps; ▼ ducks on the ground and, in
the air, pulls the dinosaur down fast so an early jump can be cut short.
"""

import random

from . import constants as D

RUNNING = 'running'
DYING = 'dying'


class Obstacle:
    def __init__(self, kind, x):
        self.kind = kind
        self.x = float(x)           # left edge of the sprite
        self.age_ms = 0.0           # drives the bird's flap
        self.scored = False

    @property
    def altitude(self):
        """Height of the sprite's bottom edge above the feet row."""
        if self.kind == D.BIRD_LOW_KIND:
            return D.BIRD_LOW
        if self.kind == D.BIRD_HIGH_KIND:
            return D.BIRD_HIGH
        return 0

    @property
    def sprite_height(self):
        return D.ROCK_HEIGHT if self.kind == D.ROCK else D.BIRD_HEIGHT

    def hitbox(self):
        """(left, right, bottom, top) - x on screen, y as altitude."""
        left, top, width, height = (D.ROCK_HITBOX if self.kind == D.ROCK
                                    else D.BIRD_HITBOX)
        bottom = self.altitude + self.sprite_height - top - height
        return (self.x + left, self.x + left + width, bottom, bottom + height)


class Dino:
    def __init__(self):
        self.altitude = 0.0
        self.velocity = 0.0         # px/s, upward positive
        self.airborne = False
        self.air_ms = 0.0           # time since take-off, for the jump frames

        self.down_held = False
        self.duck_ms = 0.0          # minimum-duck time still owed
        self.jump_buffer_ms = 0.0   # a ▲ that arrived before touchdown

    @property
    def ducking(self):
        return not self.airborne and (self.down_held or self.duck_ms > 0)

    def hitbox(self):
        left, top, width, height = D.DUCK_HITBOX if self.ducking else D.DINO_HITBOX
        return (D.DINO_X + left, D.DINO_X + left + width,
                self.altitude + top - height, self.altitude + top)

    def jump(self):
        self.airborne = True
        self.velocity = D.JUMP_VELOCITY
        self.air_ms = 0.0
        self.jump_buffer_ms = 0.0

    def update(self, dt_ms):
        seconds = dt_ms / 1000.0
        self.duck_ms = max(0.0, self.duck_ms - dt_ms)
        self.jump_buffer_ms = max(0.0, self.jump_buffer_ms - dt_ms)

        if not self.airborne:
            return

        self.air_ms += dt_ms
        gravity = D.GRAVITY * (D.FAST_FALL if self.down_held else 1.0)
        self.velocity -= gravity * seconds
        self.altitude += self.velocity * seconds

        if self.altitude <= 0:
            self.altitude = 0.0
            self.velocity = 0.0
            self.airborne = False
            if self.jump_buffer_ms > 0:
                self.jump()


def overlaps(a, b):
    return a[0] < b[1] and b[0] < a[1] and a[2] < b[3] and b[2] < a[3]


class World:
    """One run, from the first step to the collision that ends it."""

    def __init__(self, rng=None):
        self.rng = rng or random.Random()
        self.dino = Dino()
        self.obstacles = []
        self.state = RUNNING

        self.score = 0
        self.speed = D.START_SPEED
        self.elapsed_ms = 0.0
        self.next_speed_up_ms = D.SPEED_STEP_MS
        self.spawn_ms = D.FIRST_SPAWN_MS
        # How far the ground has scrolled, in px - the grass's offset and the
        # run cycle's clock, so the legs keep pace with the ground.
        self.distance = 0.0
        self.dead_ms = 0.0

    # -- input ---------------------------------------------------------------

    def press_up(self):
        if self.state != RUNNING:
            return
        dino = self.dino
        # ▲ also ends a duck outright. Two feet can be on the mat at once,
        # and a ▼ release that never arrived must not leave the dinosaur
        # crouched - or fast-falling every jump - for the rest of the run.
        dino.down_held = False
        dino.duck_ms = 0.0
        if dino.airborne:
            dino.jump_buffer_ms = D.JUMP_BUFFER_MS
        else:
            dino.jump()

    def press_down(self):
        if self.state != RUNNING:
            return
        self.dino.down_held = True
        self.dino.duck_ms = D.DUCK_MIN_MS
        self.dino.jump_buffer_ms = 0.0

    def release_down(self):
        self.dino.down_held = False

    # -- simulation ----------------------------------------------------------

    def update(self, dt_ms):
        if self.state == DYING:
            # The ground stops, but a dinosaur hit in mid-air still falls.
            self.dead_ms += dt_ms
            self.dino.jump_buffer_ms = 0.0
            self.dino.update(dt_ms)
            return

        self.elapsed_ms += dt_ms
        while self.elapsed_ms >= self.next_speed_up_ms:
            self.speed *= 1.0 + D.SPEED_STEP
            self.next_speed_up_ms += D.SPEED_STEP_MS

        step = self.speed * dt_ms / 1000.0
        self.distance += step
        self.dino.update(dt_ms)

        dino_box = self.dino.hitbox()
        for obstacle in self.obstacles:
            obstacle.x -= step
            obstacle.age_ms += dt_ms
            box = obstacle.hitbox()
            if overlaps(dino_box, box):
                self.state = DYING
                return
            # A point for every obstacle that gets past, as it clears the
            # dinosaur's standing body - the same line whatever the pose.
            if not obstacle.scored and box[1] < D.DINO_X + D.DINO_HITBOX[0]:
                obstacle.scored = True
                self.score += 1

        self.obstacles = [o for o in self.obstacles
                          if o.x > -D.OBSTACLE_MAX_WIDTH]

        self.spawn_ms -= dt_ms
        if self.spawn_ms <= 0:
            self.spawn()

    def spawn(self, kind=None):
        kind = kind or self.rng.choices(D.OBSTACLE_KINDS, D.OBSTACLE_WEIGHTS)[0]
        self.obstacles.append(Obstacle(kind, D.SCREEN_W))
        self.spawn_ms = self.rng.uniform(D.SPAWN_GAP_MIN_MS, D.SPAWN_GAP_MAX_MS)

    # -- what to draw --------------------------------------------------------

    def dino_sprite(self):
        """The dinosaur's current frame key."""
        dino = self.dino
        if self.state == DYING:
            index = int(self.dead_ms / D.DEAD_FRAME_MS)
            return f'dead_{min(index, D.DEAD_FRAMES - 1)}'
        if dino.airborne:
            index = int(dino.air_ms / D.JUMP_MS * D.JUMP_FRAMES)
            return f'jump_{min(index, D.JUMP_FRAMES - 1)}'
        if dino.ducking:
            return 'duck'
        stride = D.START_SPEED * D.RUN_FRAME_MS / 1000.0
        return f'run_{int(self.distance / stride) % D.RUN_FRAMES}'
