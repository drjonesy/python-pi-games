"""Pac-dots, power pellets and the bonus fruit (engine.js:2658)."""

import math

from .constants import FRUIT_IMAGES


class Pickup:
    def __init__(self, type_, scaled_tile_size, column, row, pacman, points,
                 events):
        self.type = type_
        self.pacman = pacman
        self.points = points
        self.events = events
        self.near_pacman = False
        self.visible = True

        self.set_style_measurements(
            type_, scaled_tile_size, column, row, points,
        )

    def reset(self):
        """Fruit starts hidden; dots start visible (engine.js:2683)."""
        self.visible = (self.type != 'fruit')

    def set_style_measurements(self, type_, scaled_tile_size, column, row,
                               points):
        """Sizes and positions the pickup (engine.js:2695).

        Pac-dots are deliberately *not* tile-centred: they are a quarter-tile
        square offset by three eighths of a tile, which is why the reference
        rounds its scale down to a half step - so an eighth of a tile stays a
        whole number of pixels. At the fixed scale used here a tile is 8px, so
        the offset is exactly 3px and the dot exactly 2px.
        """
        if type_ == 'pacdot':
            self.size = scaled_tile_size * 0.25
            self.x = (column * scaled_tile_size) + ((scaled_tile_size / 8) * 3)
            self.y = (row * scaled_tile_size) + ((scaled_tile_size / 8) * 3)
        elif type_ == 'powerPellet':
            self.size = scaled_tile_size
            self.x = column * scaled_tile_size
            self.y = row * scaled_tile_size
        else:
            self.size = scaled_tile_size * 2
            self.x = (column * scaled_tile_size) - (scaled_tile_size * 0.5)
            self.y = (row * scaled_tile_size) - (scaled_tile_size * 0.5)

        self.center = {
            'x': column * scaled_tile_size,
            'y': row * scaled_tile_size,
        }

        self.image = self.determine_image(type_, points)

        self.reset()

    def determine_image(self, type_, points):
        """Sprite key for this pickup (engine.js:2726)."""
        if type_ == 'fruit':
            return FRUIT_IMAGES.get(points, 'cherry')
        return type_

    def draw(self, renderer, pellets_visible):
        """engine.js:2744.

        Power pellets blink, which the caller drives with a shared clock so
        every pellet flashes in unison.
        """
        if not self.visible:
            return
        if self.type == 'powerPellet' and not pellets_visible:
            return

        renderer.draw_image(self.image, self.x, self.y, self.size, self.size)

    def show_fruit(self, points):
        """engine.js:2755."""
        self.points = points
        self.image = self.determine_image(self.type, points)
        self.visible = True

    def hide_fruit(self):
        """engine.js:2764 - the player was too slow."""
        self.visible = False

    def check_for_collision(self, pickup, original_pacman):
        """AABB overlap against a box at Pacman's centre (engine.js:2773).

        Pacman's 2x2-tile sprite is shrunk to its middle quarter before the
        test, so a dot is eaten when he actually covers it rather than when a
        corner of his bounding box grazes it.
        """
        pacman = dict(original_pacman)

        pacman['x'] += pacman['size'] * 0.25
        pacman['y'] += pacman['size'] * 0.25
        pacman['size'] /= 2

        return (
            pickup['x'] < pacman['x'] + pacman['size']
            and pickup['x'] + pickup['size'] > pacman['x']
            and pickup['y'] < pacman['y'] + pacman['size']
            and pickup['y'] + pickup['size'] > pacman['y']
        )

    def check_pacman_proximity(self, max_distance, pacman_center):
        """Flags whether this pickup is worth collision-checking (engine.js:2792)."""
        if self.visible:
            distance = math.sqrt(
                ((self.center['x'] - pacman_center['x']) ** 2)
                + ((self.center['y'] - pacman_center['y']) ** 2)
            )

            self.near_pacman = distance <= max_distance

    def should_check_for_collision(self):
        """engine.js:2807."""
        return self.visible and self.near_pacman

    def update(self):
        """Eats the pickup if Pacman is touching it (engine.js:2816).

        Turns itself invisible on the first collision so it cannot score twice.
        """
        if not self.should_check_for_collision():
            return

        if self.check_for_collision(
            {'x': self.x, 'y': self.y, 'size': self.size},
            {
                'x': self.pacman.position['left'],
                'y': self.pacman.position['top'],
                'size': self.pacman.measurement,
            },
        ):
            self.visible = False
            self.events.emit('awardPoints', points=self.points, type=self.type)

            if self.type == 'pacdot':
                self.events.emit('dotEaten')
            elif self.type == 'powerPellet':
                self.events.emit('dotEaten')
                self.events.emit('powerUp')
