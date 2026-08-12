"""Grid math shared by Pacman and the ghosts (engine.js:2849).

Two coordinate systems are in play, and they are kept named exactly as the
reference names them so the two files can be read side by side:

* **pixel position** - a ``{'top': y, 'left': x}`` dict, the character's
  top-left corner in logical pixels. This is what gets drawn.
* **grid position** - an ``{'x': col, 'y': row}`` dict in tile units, offset by
  half a tile (``determine_grid_position``). This is what the maze is indexed
  by and what the ghost AI reasons about.

Positions stay as plain dicts rather than becoming a Vec2 class for exactly
that reason: `newPosition[this.getPropertyToChange(direction)] += ...` ports
across as-is.
"""

import math

from .constants import EPSILON

DIRECTIONS = {
    'up': 'up',
    'down': 'down',
    'left': 'left',
    'right': 'right',
}


def approx(a, b, epsilon=EPSILON):
    """Tolerance-based equality for the reference's exact `===` comparisons.

    The JS engine relies on `position.x === 13.5` being exactly true, which
    works only because snapToGrid wrote that value. Porting the comparison
    verbatim would make ghost respawn depend on float bit patterns, so every
    such test goes through here instead (rewrite instructions §3).
    """
    return abs(a - b) < epsilon


class CharacterUtil:
    def __init__(self):
        self.directions = DIRECTIONS

    def check_for_stutter(self, position, old_position, scaled_tile_size):
        """True when a character should be hidden for one frame (engine.js:2866).

        This exists to hide a character for the single frame it teleports
        through a tunnel, which moves it ~28 tiles sideways. The threshold is
        measured in tiles rather than a fixed pixel count because legitimate
        movement per step scales with both the tile size and the timestep: the
        fastest thing in the game (a ghost's eyes returning home) covers about
        0.37 tiles per step, so one tile separates the two cleanly.
        """
        threshold = scaled_tile_size

        if position and old_position:
            return (
                abs(position['top'] - old_position['top']) > threshold
                or abs(position['left'] - old_position['left']) > threshold
            )

        return False

    def is_snapped_to_grid(self, position, grid_position, direction,
                           scaled_tile_size):
        """True when a character is exactly aligned to the maze grid.

        engine.js:2895 compares the numbers directly; this uses `approx` so
        accumulated float error cannot make a genuinely snapped character look
        unsnapped. The tolerance is ~6 orders of magnitude below the distance
        covered in one step, so it can never merge two distinct positions.
        """
        snapped = self.snap_to_grid(grid_position, direction, scaled_tile_size)

        return (
            approx(position['top'], snapped['top'])
            and approx(position['left'], snapped['left'])
        )

    def get_property_to_change(self, direction):
        """Which pixel axis a direction moves along (engine.js:2908)."""
        if direction in ('up', 'down'):
            return 'top'
        return 'left'

    def get_velocity(self, direction, velocity_per_ms):
        """Signs a speed for a direction (engine.js:2924).

        Down and right are positive; up and left are negative.
        """
        if direction in ('up', 'left'):
            return velocity_per_ms * -1
        return velocity_per_ms

    def calculate_new_draw_value(self, interp, prop, old_position, position):
        """Interpolates between the last two simulation steps (engine.js:2942).

        The simulation runs at 120Hz and rendering at 60, so a drawn frame
        always sits somewhere between two steps. `interp` is that fraction.
        """
        return (old_position[prop]
                + (position[prop] - old_position[prop]) * interp)

    def determine_grid_position(self, position, scaled_tile_size):
        """Pixel position -> grid position (engine.js:2952)."""
        return {
            'x': (position['left'] / scaled_tile_size) + 0.5,
            'y': (position['top'] / scaled_tile_size) + 0.5,
        }

    def turning_around(self, direction, desired_direction):
        """engine.js:2965."""
        return desired_direction == self.get_opposite_direction(direction)

    def get_opposite_direction(self, direction):
        """engine.js:2974."""
        if direction == 'up':
            return 'down'
        if direction == 'down':
            return 'up'
        if direction == 'left':
            return 'right'
        return 'left'

    def determine_rounding_function(self, direction):
        """Rounds toward the wall a character is approaching (engine.js:2992)."""
        if direction in ('up', 'left'):
            return math.floor
        return math.ceil

    def changing_grid_position(self, old_position, position):
        """True when a step crosses into a new tile (engine.js:3008)."""
        return (
            math.floor(old_position['x']) != math.floor(position['x'])
            or math.floor(old_position['y']) != math.floor(position['y'])
        )

    def check_for_wall_collision(self, desired_new_grid_position, maze_array,
                                 direction):
        """True when the next step would run into a wall (engine.js:3022).

        Out-of-range lookups must read as "not a wall", which is what lets a
        character walk off the end of the tunnel row before `handle_warp`
        teleports it. In JS `mazeArray[14][-1]` is simply `undefined`; in
        Python a negative index would wrap around to the far side of the row
        and report a wall there, sealing the tunnel. Hence the explicit bounds
        check.
        """
        rounding_function = self.determine_rounding_function(direction)

        desired_x = rounding_function(desired_new_grid_position['x'])
        desired_y = rounding_function(desired_new_grid_position['y'])

        if not (0 <= desired_y < len(maze_array)):
            return False
        row = maze_array[desired_y]
        if not (0 <= desired_x < len(row)):
            return False

        return row[desired_x] == 'X'

    def determine_new_positions(self, position, direction, velocity_per_ms,
                                elapsed_ms, scaled_tile_size):
        """Advances a position by one step (engine.js:3047).

        Returns both the new pixel position and its grid position, since every
        caller needs to test the latter before committing to the former.
        """
        new_position = dict(position)
        new_position[self.get_property_to_change(direction)] += (
            self.get_velocity(direction, velocity_per_ms) * elapsed_ms
        )
        new_grid_position = self.determine_grid_position(
            new_position, scaled_tile_size,
        )

        return {
            'newPosition': new_position,
            'newGridPosition': new_grid_position,
        }

    def snap_to_grid(self, position, direction, scaled_tile_size):
        """Grid position -> the pixel position of the nearest tile edge.

        engine.js:3070. Only the axis of travel is rounded; the other is left
        alone, which is what preserves the half-tile x of 13.5 while a ghost
        descends into the house.
        """
        new_position = dict(position)
        rounding_function = self.determine_rounding_function(direction)

        if direction in ('up', 'down'):
            new_position['y'] = rounding_function(new_position['y'])
        else:
            new_position['x'] = rounding_function(new_position['x'])

        return {
            'top': (new_position['y'] - 0.5) * scaled_tile_size,
            'left': (new_position['x'] - 0.5) * scaled_tile_size,
        }

    def handle_warp(self, position, scaled_tile_size, maze_array):
        """Teleports a character across the tunnel at row 14 (engine.js:3099)."""
        new_position = dict(position)
        grid_position = self.determine_grid_position(position, scaled_tile_size)
        columns = len(maze_array[0])

        if grid_position['x'] < -0.75:
            new_position['left'] = scaled_tile_size * (columns - 0.75)
        elif grid_position['x'] > (columns - 0.25):
            new_position['left'] = scaled_tile_size * -1.25

        return new_position

    def advance_sprite_sheet(self, character):
        """Advances an animation by one frame if enough time has passed.

        engine.js:3116. Non-looping sheets (Pacman's 12-frame death animation)
        stop on their last frame rather than wrapping.
        """
        ms_since_last_sprite = character.ms_since_last_sprite
        background_offset_pixels = character.background_offset_pixels

        ready = (ms_since_last_sprite > character.ms_between_sprites
                 and character.animate)
        if ready:
            ms_since_last_sprite = 0

            if background_offset_pixels < (character.measurement
                                           * (character.sprite_frames - 1)):
                background_offset_pixels += character.measurement
            elif character.loop_animation:
                background_offset_pixels = 0

        return {
            'msSinceLastSprite': ms_since_last_sprite,
            'backgroundOffsetPixels': background_offset_pixels,
        }
