"""The ghosts - all four, parameterized by name (engine.js:42)."""

import math

from ..character_util import approx
from ..constants import (
    EYE_SPEED_FACTOR,
    FAST_SPEED_FACTOR,
    MEDIUM_SPEED_FACTOR,
    SCARED_SPEED_FACTOR,
    SLOW_SPEED_FACTOR,
    TRANSITION_SPEED_FACTOR,
)
from ..maze import get_tile

# engine.js:159-191, in tile units as (left, top).
DEFAULT_POSITIONS = {
    'blinky': (13, 10.5),
    'pinky': (13, 13.5),
    'inky': (11, 13.5),
    'clyde': (15, 13.5),
}

# engine.js:111-127
DEFAULT_DIRECTIONS = {
    'blinky': 'left',
    'pinky': 'down',
    'inky': 'up',
    'clyde': 'up',
}

# engine.js:385-399. Blinky's is conditional - see get_target.
SCATTER_TARGETS = {
    'blinky': {'x': 27, 'y': 0},
    'pinky': {'x': 0, 'y': 0},
    'inky': {'x': 27, 'y': 30},
    'clyde': {'x': 0, 'y': 30},
}

# engine.js:376 - where eaten ghosts head for.
GHOST_HOUSE_TARGET = {'x': 13.5, 'y': 10}

# engine.js:362 - Clyde's retreat corner, and the distance that triggers it.
CLYDE_RETREAT = {'x': 0, 'y': 30}
CLYDE_FLIP_DISTANCE = 8


class Ghost:
    def __init__(self, scaled_tile_size, maze_array, pacman, name, level,
                 character_util, events, blinky=None):
        self.scaled_tile_size = scaled_tile_size
        self.maze_array = maze_array
        self.pacman = pacman
        self.name = name
        self.level = level
        self.character_util = character_util
        self.events = events
        self.blinky = blinky

        # `default_speed` and `cruise_elroy` deliberately live outside reset():
        # they survive a plain reset and are only cleared by a full game reset,
        # which is what lets Blinky keep his Cruise Elroy speed across a death
        # (engine.js:61-65, 100-102).
        self.default_speed = None
        self.cruise_elroy = False
        self.idle_mode = None
        self.paused = False
        self.scared_color = 'blue'

        self.reset()

    def reset(self, full_game_reset=False):
        """engine.js:61."""
        if full_game_reset:
            self.default_speed = None
            self.cruise_elroy = False

        self.set_default_mode()
        self.set_movement_stats(self.pacman, self.name, self.level)
        self.set_sprite_animation_stats()
        self.set_style_measurements(self.scaled_tile_size)
        self.set_default_position(self.scaled_tile_size, self.name)
        self.set_sprite_sheet(self.name, self.direction, self.mode)

    def set_default_mode(self):
        """engine.js:78.

        Every ghost except Blinky starts idling in the house; Blinky begins on
        the board.
        """
        self.allow_collision = True
        self.default_mode = 'scatter'
        self.mode = 'scatter'
        if self.name != 'blinky':
            self.idle_mode = 'idle'

    def set_movement_stats(self, pacman, name, level):
        """Derives every speed from Pacman's (engine.js:92)."""
        pacman_speed = pacman.velocity_per_ms
        level_adjustment = level / 100

        self.slow_speed = pacman_speed * (SLOW_SPEED_FACTOR + level_adjustment)
        self.medium_speed = pacman_speed * (MEDIUM_SPEED_FACTOR + level_adjustment)
        self.fast_speed = pacman_speed * (FAST_SPEED_FACTOR + level_adjustment)

        if not self.default_speed:
            self.default_speed = self.slow_speed

        self.scared_speed = pacman_speed * SCARED_SPEED_FACTOR
        self.transition_speed = pacman_speed * TRANSITION_SPEED_FACTOR
        self.eye_speed = pacman_speed * EYE_SPEED_FACTOR

        self.velocity_per_ms = self.default_speed
        self.moving = False

        self.default_direction = DEFAULT_DIRECTIONS.get(name, 'left')
        self.direction = self.default_direction

    def set_sprite_animation_stats(self):
        """engine.js:134 - ghosts are a 2-frame loop at 250ms."""
        self.display = True
        self.visible = True
        self.loop_animation = True
        self.animate = True
        self.ms_between_sprites = 250
        self.ms_since_last_sprite = 0
        self.sprite_frames = 2
        self.background_offset_pixels = 0

    def set_style_measurements(self, scaled_tile_size):
        """engine.js:149 - the ghosts are 2x2 game tiles."""
        self.measurement = scaled_tile_size * 2

    def set_default_position(self, scaled_tile_size, name):
        """engine.js:159."""
        left, top = DEFAULT_POSITIONS.get(name, (0, 0))
        self.default_position = {
            'top': scaled_tile_size * top,
            'left': scaled_tile_size * left,
        }
        self.position = dict(self.default_position)
        self.old_position = dict(self.position)

    def set_sprite_sheet(self, name, direction, mode):
        """Chooses the sheet for the current direction and mode (engine.js:202).

        Cruise Elroy changes Blinky's appearance: one rung up is `_annoyed`,
        two is `_angry`.
        """
        emotion = ''
        if not approx(self.default_speed, self.slow_speed):
            emotion = ('_annoyed' if approx(self.default_speed, self.medium_speed)
                       else '_angry')

        if mode == 'scared':
            self.sheet = f'scared_{self.scared_color}'
        elif mode == 'eyes':
            self.sheet = f'eyes_{direction}'
        else:
            self.sheet = f'{name}_{direction}{emotion}'

    def is_in_tunnel(self, grid_position):
        """engine.js:225 - the horizontal wrap-around row."""
        return (
            approx(grid_position['y'], 14)
            and (grid_position['x'] < 6 or grid_position['x'] > 21)
        )

    def is_in_ghost_house(self, grid_position):
        """engine.js:237."""
        return (
            (grid_position['x'] > 9 and grid_position['x'] < 18)
            and (grid_position['y'] > 11 and grid_position['y'] < 17)
        )

    def get_tile(self, maze_array, y, x):
        """engine.js:251 - see maze.get_tile for the JS behaviours preserved."""
        return get_tile(maze_array, y, x)

    def determine_possible_moves(self, grid_position, direction, maze_array):
        """Every legal move for this turn (engine.js:271).

        Insertion order is up, down, left, right and must stay that way:
        `determine_best_move` keeps the first strictly-better option, so this
        ordering *is* the tie-break rule.
        """
        x = grid_position['x']
        y = grid_position['y']

        possible_moves = {
            'up': self.get_tile(maze_array, y - 1, x),
            'down': self.get_tile(maze_array, y + 1, x),
            'left': self.get_tile(maze_array, y, x - 1),
            'right': self.get_tile(maze_array, y, x + 1),
        }

        # Ghosts are not allowed to turn around at crossroads.
        possible_moves[self.character_util.get_opposite_direction(direction)] = False

        return {key: value for key, value in possible_moves.items() if value}

    def calculate_distance(self, position, pacman):
        """Euclidean distance (engine.js:299)."""
        return math.sqrt(
            ((position['x'] - pacman['x']) ** 2)
            + ((position['y'] - pacman['y']) ** 2)
        )

    def get_position_in_front_of_pacman(self, pacman_grid_position, spaces):
        """A point `spaces` tiles ahead of Pacman (engine.js:310).

        Offsets a single axis based on Pacman's facing. This does **not**
        reproduce the arcade's famous "Pinky up-target overflow" bug, and it
        must not - the codebase is the specification here.
        """
        target = dict(pacman_grid_position)
        pac_direction = self.pacman.direction
        prop_to_change = 'y' if pac_direction in ('up', 'down') else 'x'
        tile_offset = (spaces * -1) if pac_direction in ('up', 'left') else spaces
        target[prop_to_change] += tile_offset

        return target

    def determine_pinky_target(self, pacman_grid_position):
        """Four tiles ahead of Pacman (engine.js:327)."""
        return self.get_position_in_front_of_pacman(pacman_grid_position, 4)

    def determine_inky_target(self, pacman_grid_position):
        """Blinky's position mirrored through a pivot 2 tiles ahead (engine.js:340)."""
        blinky_grid_position = self.character_util.determine_grid_position(
            self.blinky.position, self.scaled_tile_size,
        )
        pivot_point = self.get_position_in_front_of_pacman(
            pacman_grid_position, 2,
        )
        return {
            'x': pivot_point['x'] + (pivot_point['x'] - blinky_grid_position['x']),
            'y': pivot_point['y'] + (pivot_point['y'] - blinky_grid_position['y']),
        }

    def determine_clyde_target(self, grid_position, pacman_grid_position):
        """Pacman when far, the lower-left corner when close (engine.js:360)."""
        distance = self.calculate_distance(grid_position, pacman_grid_position)
        return (pacman_grid_position if distance > CLYDE_FLIP_DISTANCE
                else dict(CLYDE_RETREAT))

    def get_target(self, name, grid_position, pacman_grid_position, mode):
        """The tile this ghost is currently steering toward (engine.js:373)."""
        # Ghosts return to the ghost-house after being eaten.
        if mode == 'eyes':
            return dict(GHOST_HOUSE_TARGET)

        # Scared ghosts target Pacman, but flee him - see determine_best_move.
        if mode == 'scared':
            return pacman_grid_position

        if mode == 'scatter':
            if name == 'blinky':
                # Blinky chases Pacman even in Scatter mode once he is in
                # Cruise Elroy form. This exception is deliberate.
                return (pacman_grid_position if self.cruise_elroy
                        else dict(SCATTER_TARGETS['blinky']))
            return dict(SCATTER_TARGETS.get(name, {'x': 0, 'y': 0}))

        if name == 'blinky':
            return pacman_grid_position
        if name == 'pinky':
            return self.determine_pinky_target(pacman_grid_position)
        if name == 'inky':
            return self.determine_inky_target(pacman_grid_position)
        if name == 'clyde':
            return self.determine_clyde_target(
                grid_position, pacman_grid_position,
            )
        return pacman_grid_position

    def determine_best_move(self, name, possible_moves, grid_position,
                            pacman_grid_position, mode):
        """Picks the move that best serves the current target (engine.js:426).

        Scared mode inverts the whole comparison: `best_distance` starts at 0
        instead of infinity and the test flips, so the ghost *maximizes*
        distance from Pacman. Both halves have to flip together - a single sign
        error here makes scared ghosts hunt the player.
        """
        best_distance = 0 if mode == 'scared' else math.inf
        best_move = None
        target = self.get_target(
            name, grid_position, pacman_grid_position, mode,
        )

        for move, tile in possible_moves.items():
            distance = self.calculate_distance(tile, target)
            better_move = ((distance > best_distance) if mode == 'scared'
                           else (distance < best_distance))

            if better_move:
                best_distance = distance
                best_move = move

        return best_move

    def determine_direction(self, name, grid_position, pacman_grid_position,
                            direction, maze_array, mode):
        """engine.js:460.

        With exactly one legal move it is taken unconditionally (corridors and
        dead ends); with several, the AI chooses. With none - which happens on
        the ghost-house centre line, where the fractional x makes every lookup
        miss - the current direction is kept.
        """
        new_direction = direction
        possible_moves = self.determine_possible_moves(
            grid_position, direction, maze_array,
        )

        if len(possible_moves) == 1:
            new_direction = next(iter(possible_moves))
        elif len(possible_moves) > 1:
            new_direction = self.determine_best_move(
                name, possible_moves, grid_position, pacman_grid_position, mode,
            )

        return new_direction

    def handle_idle_movement(self, elapsed_ms, position, velocity):
        """Bobbing in the house, and the path out of it (engine.js:486).

        `position` is a grid position. The exit is a three-stage handoff: slide
        to the centre column, rise to the door, then step out heading left.
        """
        new_position = dict(self.position)

        if position['y'] <= 13.5:
            self.direction = 'down'
        elif position['y'] >= 14.5:
            self.direction = 'up'

        if self.idle_mode == 'leaving':
            if (approx(position['x'], 13.5)
                    and (position['y'] > 10.8 and position['y'] < 11)):
                self.idle_mode = None
                new_position['top'] = self.scaled_tile_size * 10.5
                self.direction = 'left'
                self.events.emit('releaseGhost')
            elif position['x'] > 13.4 and position['x'] < 13.6:
                new_position['left'] = self.scaled_tile_size * 13
                self.direction = 'up'
            elif position['y'] > 13.9 and position['y'] < 14.1:
                new_position['top'] = self.scaled_tile_size * 13.5
                self.direction = ('right' if position['x'] < 13.5 else 'left')

        new_position[self.character_util.get_property_to_change(self.direction)] += (
            self.character_util.get_velocity(self.direction, velocity) * elapsed_ms
        )

        return new_position

    def end_idle_mode(self):
        """Lets this ghost start leaving the house (engine.js:521)."""
        self.idle_mode = 'leaving'

    def handle_snapped_movement(self, elapsed_ms, grid_position, velocity,
                                pacman_grid_position):
        """Movement while aligned to the grid - i.e. at a decision point
        (engine.js:533)."""
        new_position = dict(self.position)

        self.direction = self.determine_direction(
            self.name, grid_position, pacman_grid_position, self.direction,
            self.maze_array, self.mode,
        )
        new_position[self.character_util.get_property_to_change(self.direction)] += (
            self.character_util.get_velocity(self.direction, velocity) * elapsed_ms
        )

        return new_position

    def entering_ghost_house(self, mode, position):
        """Eyes arriving at the house door (engine.js:552).

        The window is only 0.2 tiles wide. At the fixed 120Hz simulation rate
        the eyes step ~0.18 tiles and land inside it; at 60Hz they would step
        ~0.37 tiles and skip clean over, and the ghost would never respawn.
        """
        return (
            mode == 'eyes'
            and approx(position['y'], 11)
            and (position['x'] > 13.4 and position['x'] < 13.6)
        )

    def entered_ghost_house(self, mode, position):
        """Eyes reaching the centre of the house (engine.js:566)."""
        return (
            mode == 'eyes'
            and approx(position['x'], 13.5)
            and (position['y'] > 13.8 and position['y'] < 14.2)
        )

    def leaving_ghost_house(self, mode, position):
        """A restored ghost at the exit (engine.js:580)."""
        return (
            mode != 'eyes'
            and approx(position['x'], 13.5)
            and (position['y'] > 10.8 and position['y'] < 11)
        )

    def handle_ghost_house(self, grid_position):
        """The three-stage handoff in and out of the house (engine.js:593).

        Each stage snaps the ghost onto the centre line or the door row so the
        next stage's window test has an exact value to match.
        """
        grid_position_copy = dict(grid_position)

        if self.entering_ghost_house(self.mode, grid_position):
            self.direction = 'down'
            grid_position_copy['x'] = 13.5
            self.position = self.character_util.snap_to_grid(
                grid_position_copy, self.direction, self.scaled_tile_size,
            )

        if self.entered_ghost_house(self.mode, grid_position):
            self.direction = 'up'
            grid_position_copy['y'] = 14
            self.position = self.character_util.snap_to_grid(
                grid_position_copy, self.direction, self.scaled_tile_size,
            )
            self.mode = self.default_mode
            self.events.emit('restoreGhost')

        if self.leaving_ghost_house(self.mode, grid_position):
            grid_position_copy['y'] = 11
            self.position = self.character_util.snap_to_grid(
                grid_position_copy, self.direction, self.scaled_tile_size,
            )
            self.direction = 'left'

        return grid_position_copy

    def handle_unsnapped_movement(self, elapsed_ms, grid_position, velocity):
        """Movement while between tiles (engine.js:632)."""
        grid_position_copy = self.handle_ghost_house(grid_position)

        desired = self.character_util.determine_new_positions(
            self.position, self.direction, velocity, elapsed_ms,
            self.scaled_tile_size,
        )

        if self.character_util.changing_grid_position(
            grid_position_copy, desired['newGridPosition'],
        ):
            return self.character_util.snap_to_grid(
                grid_position_copy, self.direction, self.scaled_tile_size,
            )

        return desired['newPosition']

    def handle_movement(self, elapsed_ms):
        """engine.js:655.

        The grid position is computed once, at the top, and threaded through -
        the ghost-house window tests depend on seeing the position from the
        *start* of the step, not a freshly recomputed one.
        """
        grid_position = self.character_util.determine_grid_position(
            self.position, self.scaled_tile_size,
        )
        pacman_grid_position = self.character_util.determine_grid_position(
            self.pacman.position, self.scaled_tile_size,
        )
        velocity = self.determine_velocity(grid_position, self.mode)

        if self.idle_mode:
            new_position = self.handle_idle_movement(
                elapsed_ms, grid_position, velocity,
            )
        elif self.character_util.is_snapped_to_grid(
            self.position, grid_position, self.direction, self.scaled_tile_size,
        ):
            new_position = self.handle_snapped_movement(
                elapsed_ms, grid_position, velocity, pacman_grid_position,
            )
        else:
            new_position = self.handle_unsnapped_movement(
                elapsed_ms, grid_position, velocity,
            )

        new_position = self.character_util.handle_warp(
            new_position, self.scaled_tile_size, self.maze_array,
        )

        self.check_collision(grid_position, pacman_grid_position)

        return new_position

    def change_mode(self, new_mode):
        """Switches chase/scatter and turns the ghost around (engine.js:698).

        A forced mode change is the only time a ghost may reverse - and not
        even then while Cruise Elroy is active.
        """
        self.default_mode = new_mode

        grid_position = self.character_util.determine_grid_position(
            self.position, self.scaled_tile_size,
        )

        if self.mode in ('chase', 'scatter') and not self.cruise_elroy:
            self.mode = new_mode

            if not self.is_in_ghost_house(grid_position):
                self.direction = self.character_util.get_opposite_direction(
                    self.direction,
                )

    def toggle_scared_color(self):
        """Flips blue/white during the end-of-powerup flash (engine.js:720)."""
        self.scared_color = 'white' if self.scared_color == 'blue' else 'blue'
        self.set_sprite_sheet(self.name, self.direction, self.mode)

    def become_scared(self):
        """engine.js:730."""
        grid_position = self.character_util.determine_grid_position(
            self.position, self.scaled_tile_size,
        )

        if self.mode != 'eyes':
            if not self.is_in_ghost_house(grid_position) and self.mode != 'scared':
                self.direction = self.character_util.get_opposite_direction(
                    self.direction,
                )
            self.mode = 'scared'
            self.scared_color = 'blue'
            self.set_sprite_sheet(self.name, self.direction, self.mode)

    def end_scared(self):
        """engine.js:750."""
        self.mode = self.default_mode
        self.set_sprite_sheet(self.name, self.direction, self.mode)

    def speed_up(self):
        """Promotes Blinky one speed rung - Cruise Elroy (engine.js:758)."""
        self.cruise_elroy = True

        if approx(self.default_speed, self.slow_speed):
            self.default_speed = self.medium_speed
        elif approx(self.default_speed, self.medium_speed):
            self.default_speed = self.fast_speed

    def reset_default_speed(self):
        """engine.js:771."""
        self.default_speed = self.slow_speed
        self.cruise_elroy = False
        self.set_sprite_sheet(self.name, self.direction, self.mode)

    def pause(self, new_value):
        """engine.js:781."""
        self.paused = new_value

    def check_collision(self, position, pacman):
        """Ghost-vs-Pacman contact (engine.js:790)."""
        if (self.calculate_distance(position, pacman) < 1
                and self.mode != 'eyes'
                and self.allow_collision):
            if self.mode == 'scared':
                self.events.emit('eatGhost', ghost=self)
                self.mode = 'eyes'
            else:
                self.events.emit('deathSequence')

    def determine_velocity(self, position, mode):
        """The ghost's speed right now (engine.js:813).

        Order matters: eyes ignore the pause flag entirely, and the tunnel and
        ghost-house slowdown outranks scared speed.
        """
        if mode == 'eyes':
            return self.eye_speed

        if self.paused:
            return 0

        if self.is_in_tunnel(position) or self.is_in_ghost_house(position):
            return self.transition_speed

        if mode == 'scared':
            return self.scared_speed

        return self.default_speed

    def draw(self, interp, renderer):
        """engine.js:838."""
        updated = self.character_util.advance_sprite_sheet(self)
        self.ms_since_last_sprite = updated['msSinceLastSprite']
        self.background_offset_pixels = updated['backgroundOffsetPixels']

        self.visible = self.display and not self.character_util.check_for_stutter(
            self.position, self.old_position, self.scaled_tile_size,
        )

        if not self.visible:
            return

        top = self.character_util.calculate_new_draw_value(
            interp, 'top', self.old_position, self.position,
        )
        left = self.character_util.calculate_new_draw_value(
            interp, 'left', self.old_position, self.position,
        )
        frame = int(self.background_offset_pixels / self.measurement)

        renderer.draw_frame(
            self.sheet, frame, self.sprite_frames, left, top, self.measurement,
        )

    def update(self, elapsed_ms):
        """One simulation step (engine.js:867)."""
        self.old_position = dict(self.position)

        if self.moving:
            self.position = self.handle_movement(elapsed_ms)
            self.set_sprite_sheet(self.name, self.direction, self.mode)
            self.ms_since_last_sprite += elapsed_ms
