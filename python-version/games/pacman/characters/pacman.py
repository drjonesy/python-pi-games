"""Pacman (engine.js:879)."""

from ..constants import PACMAN_TILES_PER_SECOND


class Pacman:
    def __init__(self, scaled_tile_size, maze_array, character_util):
        self.scaled_tile_size = scaled_tile_size
        self.maze_array = maze_array
        self.character_util = character_util
        self.direction = 'left'

        self.reset()

    def reset(self):
        """Returns Pacman to his default state (engine.js:891)."""
        self.set_movement_stats(self.scaled_tile_size)
        self.set_sprite_animation_stats()
        self.set_style_measurements(self.scaled_tile_size)
        self.set_default_position(self.scaled_tile_size)
        self.set_sprite_sheet(self.direction)
        self.set_arrow_sheet(self.direction)

    def set_movement_stats(self, scaled_tile_size):
        """engine.js:904."""
        self.velocity_per_ms = self.calculate_velocity_per_ms(scaled_tile_size)
        self.desired_direction = 'left'
        self.direction = 'left'
        self.moving = False

    def set_sprite_animation_stats(self):
        """engine.js:914."""
        self.special_animation = False
        self.display = True
        self.visible = True
        self.animate = True
        self.loop_animation = True
        self.ms_between_sprites = 50
        self.ms_since_last_sprite = 0
        self.sprite_frames = 4
        self.background_offset_pixels = 0

    def set_style_measurements(self, scaled_tile_size):
        """engine.js:930 - Pacman is 2x2 tiles, his arrow twice that."""
        self.measurement = scaled_tile_size * 2
        self.arrow_measurement = self.measurement * 2

    def set_default_position(self, scaled_tile_size):
        """engine.js:939."""
        self.default_position = {
            'top': scaled_tile_size * 22.5,
            'left': scaled_tile_size * 13,
        }
        self.position = dict(self.default_position)
        self.old_position = dict(self.position)

    def calculate_velocity_per_ms(self, scaled_tile_size):
        """engine.js:952 - Pacman moved at 11 tiles per second in the original."""
        velocity_per_second = scaled_tile_size * PACMAN_TILES_PER_SECOND
        return velocity_per_second / 1000

    def set_sprite_sheet(self, direction):
        """engine.js:962."""
        self.sheet = f'pacman_{direction}'

    def set_arrow_sheet(self, direction):
        """engine.js:971 - the leading arrow showing the buffered turn."""
        self.arrow_sheet = f'arrow_{direction}'

    def prep_death_animation(self):
        """Swaps in the one-shot 12-frame death sheet (engine.js:976)."""
        self.loop_animation = False
        self.ms_between_sprites = 125
        self.sprite_frames = 12
        self.special_animation = True
        self.background_offset_pixels = 0
        self.sheet = 'pacman_death'
        self.arrow_sheet = None

    def change_direction(self, new_direction, start_moving):
        """Buffers a turn (engine.js:992).

        Only `desired_direction` changes here - the actual turn happens later,
        once Pacman reaches a tile where it is legal. That buffering is a large
        part of how the controls feel: a turn pressed slightly before a
        junction still registers.
        """
        self.desired_direction = new_direction
        self.set_arrow_sheet(self.desired_direction)

        if start_moving:
            self.moving = True

    def handle_snapped_movement(self, elapsed_ms):
        """Movement while exactly aligned to the grid (engine.js:1006).

        Tries the buffered direction first and falls back to the current one,
        stopping only when both are walled off.
        """
        desired = self.character_util.determine_new_positions(
            self.position, self.desired_direction, self.velocity_per_ms,
            elapsed_ms, self.scaled_tile_size,
        )
        alternate = self.character_util.determine_new_positions(
            self.position, self.direction, self.velocity_per_ms,
            elapsed_ms, self.scaled_tile_size,
        )

        if self.character_util.check_for_wall_collision(
            desired['newGridPosition'], self.maze_array, self.desired_direction,
        ):
            if self.character_util.check_for_wall_collision(
                alternate['newGridPosition'], self.maze_array, self.direction,
            ):
                self.moving = False
                return self.position
            return alternate['newPosition']

        self.direction = self.desired_direction
        self.set_sprite_sheet(self.direction)
        return desired['newPosition']

    def handle_unsnapped_movement(self, grid_position, elapsed_ms):
        """Movement while between tiles (engine.js:1038).

        A reversal is allowed immediately - Pacman can turn around mid-corridor
        without waiting for a tile edge, unlike the ghosts.
        """
        desired = self.character_util.determine_new_positions(
            self.position, self.desired_direction, self.velocity_per_ms,
            elapsed_ms, self.scaled_tile_size,
        )
        alternate = self.character_util.determine_new_positions(
            self.position, self.direction, self.velocity_per_ms,
            elapsed_ms, self.scaled_tile_size,
        )

        if self.character_util.turning_around(
            self.direction, self.desired_direction,
        ):
            self.direction = self.desired_direction
            self.set_sprite_sheet(self.direction)
            return desired['newPosition']

        if self.character_util.changing_grid_position(
            grid_position, alternate['newGridPosition'],
        ):
            return self.character_util.snap_to_grid(
                grid_position, self.direction, self.scaled_tile_size,
            )

        return alternate['newPosition']

    def draw(self, interp, renderer):
        """engine.js:1071."""
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

        if self.arrow_sheet:
            renderer.draw_image(
                self.arrow_sheet,
                self.position['left'] - self.scaled_tile_size,
                self.position['top'] - self.scaled_tile_size,
                self.arrow_measurement, self.arrow_measurement,
            )

        frame = int(self.background_offset_pixels / self.measurement)
        renderer.draw_frame(
            self.sheet, frame, self.sprite_frames, left, top, self.measurement,
        )

    def update(self, elapsed_ms):
        """One simulation step (engine.js:1109)."""
        self.old_position = dict(self.position)

        if self.moving:
            grid_position = self.character_util.determine_grid_position(
                self.position, self.scaled_tile_size,
            )

            if self.character_util.is_snapped_to_grid(
                self.position, grid_position, self.direction,
                self.scaled_tile_size,
            ):
                self.position = self.handle_snapped_movement(elapsed_ms)
            else:
                self.position = self.handle_unsnapped_movement(
                    grid_position, elapsed_ms,
                )

            self.position = self.character_util.handle_warp(
                self.position, self.scaled_tile_size, self.maze_array,
            )

        if self.moving or self.special_animation:
            self.ms_since_last_sprite += elapsed_ms
