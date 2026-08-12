"""GameCoordinator - the game's state machine (engine.js:1137).

A direct port. The DOM wiring from the reference constructor
(engine.js:1139-1156) is gone, as is the asset-preloading screen, and the
browser `CustomEvent` plumbing is replaced by the small bus in `events.py` -
with the event names preserved so both codebases stay greppable.

Everything else, including the exact ordering of the death and level-advance
timer chains, is the reference's.
"""

from . import constants as C
from .character_util import CharacterUtil
from .characters.ghost import Ghost
from .characters.pacman import Pacman
from .events import EventBus
from .maze import MAZE_ARRAY, validate_maze
from .pickup import Pickup
from .timers import TimerManager

# Game-level states. The web build expressed these as CSS visibility on a menu
# overlay plus a pair of sliding covers; here they are explicit.
STATE_MENU = 'menu'
STATE_PLAYING = 'playing'


class GameCoordinator:
    def __init__(self, renderer, sound_manager, leaderboard, scaled_tile_size=None):
        self.renderer = renderer
        self.sound_manager = sound_manager
        self.leaderboard = leaderboard

        self.scaled_tile_size = (scaled_tile_size if scaled_tile_size is not None
                                 else C.SCALED_TILE_SIZE)
        self.first_game = True

        self.events = EventBus()
        self.timers = TimerManager()

        self.maze_array = MAZE_ARRAY
        validate_maze(self.maze_array)

        self.text_overlays = []
        self.maze_cover_visible = False
        self.maze_tint = None
        self.pellet_blink_ms = 0
        self.nearby_pickups = []
        self.collision_scan_ms = 0

        self.state = STATE_MENU
        self.running = False        # False while paused - see change_paused_state
        self.started = False
        self.show_fps = False
        self.paused_display = False

        # Populated by reset(); declared here so the menu can render before the
        # first game has ever been started.
        self.points = 0
        self.level = 1
        self.lives = C.STARTING_LIVES
        self.remaining_dots = 0
        self.pickups = []
        self.ghosts = []
        self.fruit_display = []
        self.high_score = self.leaderboard.high_score()

        self.ghost_cycle_timer = None
        self.end_idle_timer = None
        self.ghost_flash_timer = None
        self.fruit_timer = None
        self.pause_cooldown_ms = 0
        self.ghost_combo = 0
        self.scared_ghosts = []
        self.eye_ghosts = 0
        self.idle_ghosts = []

        # Flags the menu can be rendered against before any game has started.
        self.cutscene = True
        self.death_in_progress = False
        self.extra_life_given = False
        self.allow_key_presses = False
        self.allow_pacman_movement = False
        self.allow_pause = False

        # Set by main.py so the coordinator can open the name-entry overlay and
        # hand control back when it closes.
        self.on_game_over = None

        self.register_event_listeners()

    # ------------------------------------------------------------------
    # High score
    # ------------------------------------------------------------------

    def refresh_high_score(self):
        """Repaints HIGH SCORE from first place on the board (engine.js:1556).

        The web version had to cope with an unreachable HTTP API and fell back
        to localStorage; a local file is always readable, and a corrupt one
        reads as an empty board, so the fallback is dropped (§11).
        """
        self.high_score = max(self.leaderboard.high_score(), self.points or 0)
        return self.high_score

    # ------------------------------------------------------------------
    # Setup and reset
    # ------------------------------------------------------------------

    def reset(self):
        """Returns every value to its default state (engine.js:1576)."""
        self.timers.clear()
        self.points = 0
        self.level = 1
        self.lives = C.STARTING_LIVES
        self.death_in_progress = False
        self.extra_life_given = False
        self.remaining_dots = 0
        self.allow_key_presses = True
        self.allow_pacman_movement = False
        self.allow_pause = False
        self.cutscene = True
        self.high_score = self.leaderboard.high_score()

        self.ghost_cycle_timer = None
        self.end_idle_timer = None
        self.ghost_flash_timer = None
        self.fruit_timer = None
        self.ghost_combo = 0

        character_util = CharacterUtil()

        if self.first_game:
            self.pacman = Pacman(
                self.scaled_tile_size, self.maze_array, CharacterUtil(),
            )
            self.blinky = Ghost(
                self.scaled_tile_size, self.maze_array, self.pacman, 'blinky',
                self.level, CharacterUtil(), self.events,
            )
            self.pinky = Ghost(
                self.scaled_tile_size, self.maze_array, self.pacman, 'pinky',
                self.level, CharacterUtil(), self.events,
            )
            self.inky = Ghost(
                self.scaled_tile_size, self.maze_array, self.pacman, 'inky',
                self.level, CharacterUtil(), self.events, self.blinky,
            )
            self.clyde = Ghost(
                self.scaled_tile_size, self.maze_array, self.pacman, 'clyde',
                self.level, CharacterUtil(), self.events,
            )
            self.fruit = Pickup(
                'fruit', self.scaled_tile_size, 13.5, 17, self.pacman, 100,
                self.events,
            )

        self.ghosts = [self.blinky, self.pinky, self.inky, self.clyde]

        self.scared_ghosts = []
        self.eye_ghosts = 0
        self.idle_ghosts = []
        self.text_overlays.clear()
        self.maze_cover_visible = False
        self.maze_tint = None

        if self.first_game:
            self.build_pickups(self.maze_array)
        else:
            self.pacman.reset()
            for ghost in self.ghosts:
                # DEVIATION FROM THE REFERENCE (deliberate, one line).
                #
                # `Ghost.reset` derives every speed from the ghost's own
                # `level` attribute (engine.js:68). The reference only ever
                # assigns that in resetBoardForNextLevel (engine.js:2288), so
                # after a game that reached level 5, starting a *new* game
                # left the ghosts on level-5 speeds - level 1 was silently
                # harder than it should be, and got harder the further the
                # previous run went.
                #
                # Assigning the level before the reset makes a new game
                # actually start at level 1. Move this line below reset(True)
                # to restore the original behaviour exactly.
                ghost.level = self.level
                # A full game reset also clears Cruise Elroy, which a plain
                # reset deliberately preserves (engine.js:1638).
                ghost.reset(True)
            for pickup in self.pickups:
                if pickup.type != 'fruit':
                    self.remaining_dots += 1
                pickup.reset()

        self.fruit_display = []
        del character_util

        # Populated immediately rather than waiting up to 500ms for the first
        # scan, so a dot next to Pacman's start tile is collidable at once.
        self.collision_scan_ms = 0
        self.collision_detection_loop()

    def build_pickups(self, maze_array):
        """Builds the pickup list from the maze array (engine.js:1697).

        Unlike the original DOM implementation these are plain objects - all 244
        of them are drawn to one surface rather than being individual
        positioned divs.
        """
        self.pickups = [self.fruit]

        for row_index, row in enumerate(maze_array):
            for column_index, block in enumerate(row):
                if block in ('o', 'O'):
                    type_ = 'pacdot' if block == 'o' else 'powerPellet'
                    points = (C.PACDOT_POINTS if block == 'o'
                              else C.POWER_PELLET_POINTS)
                    self.pickups.append(Pickup(
                        type_, self.scaled_tile_size, column_index, row_index,
                        self.pacman, points, self.events,
                    ))
                    self.remaining_dots += 1

        assert self.remaining_dots == C.TOTAL_PICKUPS, (
            f'expected {C.TOTAL_PICKUPS} pickups, built {self.remaining_dots}'
        )

    def register_event_listeners(self):
        """engine.js:1932, minus the keyboard and touch wiring."""
        self.events.on('awardPoints', self.award_points)
        self.events.on('deathSequence', self.death_sequence)
        self.events.on('dotEaten', self.dot_eaten)
        self.events.on('powerUp', self.power_up)
        self.events.on('eatGhost', self.eat_ghost)
        self.events.on('restoreGhost', self.restore_ghost)
        self.events.on('releaseGhost', self.release_ghost)

    def start_button_click(self):
        """Starts a game from the menu (engine.js:1309)."""
        self.reset()
        if self.first_game:
            self.first_game = False
        self.state = STATE_PLAYING
        self.running = True
        self.started = True
        self.start_gameplay(True)

    # ------------------------------------------------------------------
    # Simulation
    # ------------------------------------------------------------------

    def update(self, elapsed_ms):
        """Advances the simulation by one fixed timestep (engine.js:1679).

        Only the five characters and the handful of pickups currently near
        Pacman are stepped - the other ~240 dots cannot be collided with, so
        there is nothing to update.
        """
        self.timers.tick(elapsed_ms)
        self.sound_manager.update()

        self.pellet_blink_ms += elapsed_ms

        # The reference ran this on a 500ms setInterval (engine.js:1591).
        # Driving it from simulation time instead means it freezes with the rest
        # of the game while paused.
        self.collision_scan_ms += elapsed_ms
        if self.collision_scan_ms >= C.COLLISION_SCAN_INTERVAL_MS:
            self.collision_scan_ms -= C.COLLISION_SCAN_INTERVAL_MS
            self.collision_detection_loop()

        self.pacman.update(elapsed_ms)
        for ghost in self.ghosts:
            ghost.update(elapsed_ms)
        for pickup in list(self.nearby_pickups):
            pickup.update()

    def tick_realtime(self, frame_ms):
        """Wall-clock bookkeeping that must keep running while paused.

        Only the pause debounce lives here - everything else in the game is
        driven by simulation time. See handle_pause_key.
        """
        if self.pause_cooldown_ms > 0:
            self.pause_cooldown_ms -= frame_ms
            if self.pause_cooldown_ms <= 0 and not self.cutscene:
                self.allow_pause = True

    def collision_detection_loop(self):
        """Rebuilds the shortlist of collidable pickups (engine.js:1748).

        With ~244 pickups on the board, restricting collision checks to those
        Pacman could plausibly reach in the next 750ms is a real win.
        """
        if not getattr(self, 'pacman', None) or not self.pickups:
            return

        max_distance = self.pacman.velocity_per_ms * C.COLLISION_LOOKAHEAD_MS
        pacman_center = {
            'x': self.pacman.position['left'] + self.scaled_tile_size,
            'y': self.pacman.position['top'] + self.scaled_tile_size,
        }

        self.nearby_pickups = []
        for pickup in self.pickups:
            pickup.check_pacman_proximity(max_distance, pacman_center)
            if pickup.should_check_for_collision():
                self.nearby_pickups.append(pickup)

    # ------------------------------------------------------------------
    # Gameplay flow
    # ------------------------------------------------------------------

    def start_gameplay(self, initial_start=False):
        """Shows READY! and releases the characters after a delay (engine.js:1816)."""
        if initial_start:
            self.sound_manager.play('game_start')

        self.scared_ghosts = []
        self.eye_ghosts = 0
        self.allow_pacman_movement = False

        tile = self.scaled_tile_size
        duration = (C.GAME_START_DURATION_MS if initial_start
                    else C.LEVEL_START_DURATION_MS)

        self.display_text(
            {'left': tile * 11, 'top': tile * 16.5}, 'ready', duration,
            tile * 6, tile * 2,
        )

        def begin():
            self.allow_pause = True
            self.cutscene = False
            self.sound_manager.set_cutscene(self.cutscene)
            self.sound_manager.set_ambience(
                C.determine_siren(self.remaining_dots),
            )

            self.allow_pacman_movement = True
            self.pacman.moving = True

            for ghost in self.ghosts:
                ghost.moving = True

            self.ghost_cycle(C.FIRST_CYCLE_MODE)

            self.idle_ghosts = [self.pinky, self.inky, self.clyde]
            self.release_ghost()

        self.timers.create(begin, duration)

    def ghost_cycle(self, mode):
        """Cycles the ghosts between chase and scatter (engine.js:1902)."""
        delay = (C.SCATTER_DURATION_MS if mode == 'scatter'
                 else C.CHASE_DURATION_MS)
        next_mode = 'chase' if mode == 'scatter' else 'scatter'

        def advance():
            for ghost in self.ghosts:
                ghost.change_mode(next_mode)
            self.ghost_cycle(next_mode)

        self.ghost_cycle_timer = self.timers.create(advance, delay)

    def release_ghost(self):
        """Releases the next idle ghost after a delay (engine.js:1918)."""
        if self.idle_ghosts:
            delay = C.ghost_release_delay_ms(self.level)

            def release():
                if self.idle_ghosts:
                    self.idle_ghosts[0].end_idle_mode()
                    self.idle_ghosts.pop(0)

            self.end_idle_timer = self.timers.create(release, delay)

    def change_direction(self, direction):
        """engine.js:1963."""
        if self.allow_key_presses and self.running:
            self.pacman.change_direction(direction, self.allow_pacman_movement)

    def handle_pause_key(self):
        """Toggles pause (engine.js:1990).

        The reference stopped its animation frame loop outright, which froze the
        simulation and is why its `Timer`s needed explicit pausing. Here the
        engine simply stops calling `update`, so timers - being driven by
        simulation time - stop with it. The `activeTimers` pause/resume calls
        are still made so a system-paused timer (see `eat_ghost`) keeps
        outranking a player resume.
        """
        if not self.allow_pause:
            return

        self.allow_pause = False
        # Deliberately a wall-clock cooldown, not a Timer. The reference used a
        # bare setTimeout here (engine.js:1994) rather than its pausable Timer,
        # so the debounce keeps running while the game is paused. A simulation
        # timer would freeze along with everything else and the game could never
        # be un-paused.
        self.pause_cooldown_ms = C.PAUSE_DEBOUNCE_MS

        self.change_paused_state(self.running)
        self.sound_manager.play('pause')

        if self.running:
            self.sound_manager.resume_ambience()
            self.paused_display = False
            self.timers.resume_all()
        else:
            self.sound_manager.stop_ambience()
            self.sound_manager.set_ambience('pause_beat', True)
            self.paused_display = True
            self.timers.pause_all()

    def change_paused_state(self, running):
        """engine.js:2538."""
        self.running = not running

    def award_points(self, points, type=None):  # noqa: A002 - matches the reference
        """Adds points, and grants the one-time extra life (engine.js:2030)."""
        self.points += points
        if self.points > (self.high_score or 0):
            self.high_score = self.points

        if self.points >= C.EXTRA_LIFE_THRESHOLD and not self.extra_life_given:
            self.extra_life_given = True
            self.sound_manager.play('extra_life')
            self.lives += 1

        if type == 'fruit':
            tile = self.scaled_tile_size
            # The four-digit sprites are drawn a tile wider, and shifted half a
            # tile left to stay centred (engine.js:2046-2053).
            left = tile * 12.5 if points >= 1000 else tile * 13
            width = tile * 3 if points >= 1000 else tile * 2

            self.display_text(
                {'left': left, 'top': tile * 16.5}, points,
                C.POINTS_DISPLAY_MS, width, tile * 2,
            )
            self.sound_manager.play('fruit')
            self.update_fruit_display(
                self.fruit.determine_image('fruit', points),
            )

    def update_fruit_display(self, image_key):
        """A rolling log of the seven most recently eaten fruit (engine.js:1887)."""
        if len(self.fruit_display) == 7:
            self.fruit_display.pop(0)
        self.fruit_display.append(image_key)

    def death_sequence(self):
        """Animates Pacman's death and costs a life (engine.js:2067)."""
        # Ghost collisions are checked every step, so an overlapping ghost can
        # fire this many times during the death animation. Without this guard
        # each repeat would subtract another life, draining several lives (and
        # skipping to game over) from a single death.
        if self.death_in_progress:
            return
        self.death_in_progress = True

        self.allow_pause = False
        self.cutscene = True
        self.sound_manager.set_cutscene(self.cutscene)
        self.sound_manager.stop_ambience()
        self.timers.remove(self.fruit_timer)
        self.timers.remove(self.ghost_cycle_timer)
        self.timers.remove(self.end_idle_timer)
        self.timers.remove(self.ghost_flash_timer)

        self.allow_key_presses = False
        self.pacman.moving = False
        for ghost in self.ghosts:
            ghost.moving = False

        def begin_death():
            for ghost in self.ghosts:
                ghost.display = False
            self.pacman.prep_death_animation()
            self.sound_manager.play('death')

            if self.lives > 0:
                self.lives -= 1

                def cover():
                    self.maze_cover_visible = True

                    def restart():
                        self.allow_key_presses = True
                        self.maze_cover_visible = False
                        self.pacman.reset()
                        for ghost in self.ghosts:
                            ghost.reset()
                        self.fruit.hide_fruit()

                        self.death_in_progress = False
                        self.start_gameplay()

                    self.timers.create(restart, C.DEATH_COVER_MS)

                self.timers.create(cover, C.DEATH_ANIMATION_MS)
            else:
                self.game_over()

        self.timers.create(begin_death, C.DEATH_FREEZE_MS)

    def game_over(self):
        """Shows GAME OVER and returns to the menu (engine.js:2129)."""
        final_score = self.points

        # Offer name entry when the run earned a place. The reference dispatched
        # a `gameOver` CustomEvent that its React layer listened for; the
        # overlay opens immediately, over the still-visible board, exactly as it
        # did there.
        if self.on_game_over:
            self.on_game_over(final_score)

        def show_text():
            tile = self.scaled_tile_size
            self.display_text(
                {'left': tile * 9, 'top': tile * 16.5}, 'game_over',
                C.GAME_OVER_TEXT_MS, tile * 10, tile * 2,
            )
            self.fruit.hide_fruit()

            def to_menu():
                def show_menu():
                    self.state = STATE_MENU
                    self.started = False
                    self.running = False
                    self.sound_manager.stop_all()
                    self.refresh_high_score()

                self.timers.create(show_menu, C.GAME_OVER_MENU_MS)

            self.timers.create(to_menu, C.GAME_OVER_COVER_MS)

        self.timers.create(show_text, C.GAME_OVER_DELAY_MS)

    def dot_eaten(self):
        """engine.js:2166."""
        self.remaining_dots -= 1

        self.sound_manager.play_dot_sound()

        if self.remaining_dots in C.FRUIT_DOT_THRESHOLDS:
            self.create_fruit()

        if self.remaining_dots in C.ELROY_DOT_THRESHOLDS:
            self.speed_up_blinky()

        if self.remaining_dots == 0:
            self.advance_level()

    def create_fruit(self):
        """Spawns a bonus fruit for ten seconds (engine.js:2187)."""
        self.timers.remove(self.fruit_timer)
        self.fruit.show_fruit(
            C.FRUIT_POINTS.get(self.level, C.FRUIT_POINTS_DEFAULT),
        )
        self.fruit_timer = self.timers.create(
            self.fruit.hide_fruit, C.FRUIT_DURATION_MS,
        )

    def speed_up_blinky(self):
        """Cruise Elroy, and the higher siren pitch (engine.js:2198)."""
        self.blinky.speed_up()

        if not self.scared_ghosts and self.eye_ghosts == 0:
            self.sound_manager.set_ambience(
                C.determine_siren(self.remaining_dots),
            )

    def advance_level(self):
        """Flashes the maze and prepares the next level (engine.js:2228)."""
        self.allow_pause = False
        self.cutscene = True
        self.sound_manager.set_cutscene(self.cutscene)
        self.allow_key_presses = False
        self.sound_manager.stop_ambience()
        self.pacman.moving = False
        for ghost in self.ghosts:
            ghost.moving = False

        self.timers.remove(self.fruit_timer)
        self.timers.remove(self.ghost_cycle_timer)
        self.timers.remove(self.end_idle_timer)
        self.timers.remove(self.ghost_flash_timer)

        # The reference nested eight setTimeouts to alternate the tint
        # (engine.js:2245-2277). Expressed as a step list, it is the same
        # sequence of 250ms beats.
        def flash_step(index):
            steps = [
                (C.MAZE_FLASH_TINT, C.MAZE_FLASH_INTERVAL_MS),
                (None, C.MAZE_FLASH_INTERVAL_MS),
                (C.MAZE_FLASH_TINT, C.MAZE_FLASH_INTERVAL_MS),
                (None, C.MAZE_FLASH_INTERVAL_MS),
                (C.MAZE_FLASH_TINT, C.MAZE_FLASH_INTERVAL_MS),
                (None, C.LEVEL_ADVANCE_COVER_MS),
            ]

            if index >= len(steps):
                self.maze_cover_visible = True

                def next_level():
                    self.maze_cover_visible = False
                    self.level += 1
                    self.allow_key_presses = True
                    self.reset_board_for_next_level()
                    self.start_gameplay()

                self.timers.create(next_level, C.LEVEL_ADVANCE_RESET_MS)
                return

            tint, delay = steps[index]
            self.maze_tint = tint
            self.timers.create(lambda: flash_step(index + 1), delay)

        def begin_flash():
            for ghost in self.ghosts:
                ghost.display = False
            flash_step(0)

        self.timers.create(begin_flash, C.LEVEL_ADVANCE_DELAY_MS)

    def reset_board_for_next_level(self):
        """engine.js:2283."""
        self.pacman.reset()

        for ghost in self.ghosts:
            ghost.level = self.level
            ghost.reset()
            ghost.reset_default_speed()

        for pickup in self.pickups:
            pickup.reset()
            if pickup.type != 'fruit':
                self.remaining_dots += 1

    # ------------------------------------------------------------------
    # Power pellets
    # ------------------------------------------------------------------

    def power_up(self):
        """Sets the ghosts to scared mode (engine.js:2329)."""
        if self.remaining_dots != 0:
            self.sound_manager.set_ambience('power_up')

        self.timers.remove(self.ghost_flash_timer)

        self.ghost_combo = 0
        self.scared_ghosts = []

        for ghost in self.ghosts:
            if ghost.mode != 'eyes':
                self.scared_ghosts.append(ghost)

        for ghost in self.scared_ghosts:
            ghost.become_scared()

        power_duration = C.power_duration_ms(self.level)
        self.ghost_flash_timer = self.timers.create(
            lambda: self.flash_ghosts(0, C.GHOST_FLASH_COUNT), power_duration,
        )

    def flash_ghosts(self, flashes, max_flashes):
        """Flashes the ghosts blue/white to warn the powerup is ending
        (engine.js:2306)."""
        if flashes == max_flashes:
            for ghost in self.scared_ghosts:
                ghost.end_scared()
            self.scared_ghosts = []
            if self.eye_ghosts == 0:
                self.sound_manager.set_ambience(
                    C.determine_siren(self.remaining_dots),
                )
        elif self.scared_ghosts:
            for ghost in self.scared_ghosts:
                ghost.toggle_scared_color()

            self.ghost_flash_timer = self.timers.create(
                lambda: self.flash_ghosts(flashes + 1, max_flashes),
                C.GHOST_FLASH_INTERVAL_MS,
            )

    def determine_combo_points(self):
        """engine.js:2358."""
        return C.combo_points(self.ghost_combo)

    def eat_ghost(self, ghost):
        """Awards combo points and freezes everything briefly (engine.js:2366)."""
        pause_duration = C.EAT_GHOST_PAUSE_MS
        position = ghost.position
        measurement = ghost.measurement

        # A system pause, so a player un-pause during the freeze cannot restart
        # these early (see Timer.resume).
        self.timers.pause_timer(self.ghost_flash_timer)
        self.timers.pause_timer(self.ghost_cycle_timer)
        self.timers.pause_timer(self.fruit_timer)
        self.sound_manager.play('eat_ghost')

        self.scared_ghosts = [
            other for other in self.scared_ghosts if other.name != ghost.name
        ]
        self.eye_ghosts += 1

        self.ghost_combo += 1
        combo = self.determine_combo_points()
        self.events.emit('awardPoints', points=combo)
        self.display_text(position, combo, pause_duration, measurement)

        self.allow_pacman_movement = False
        self.pacman.display = False
        self.pacman.moving = False
        ghost.display = False
        ghost.moving = False

        for other in self.ghosts:
            other.animate = False
            other.pause(True)
            other.allow_collision = False

        def resume():
            self.sound_manager.set_ambience('eyes')

            self.timers.resume_timer(self.ghost_flash_timer)
            self.timers.resume_timer(self.ghost_cycle_timer)
            self.timers.resume_timer(self.fruit_timer)
            self.allow_pacman_movement = True
            self.pacman.display = True
            self.pacman.moving = True
            ghost.display = True
            ghost.moving = True
            for other in self.ghosts:
                other.animate = True
                other.pause(False)
                other.allow_collision = True

        self.timers.create(resume, pause_duration)

    def restore_ghost(self):
        """A ghost finished its trip home (engine.js:2427)."""
        self.eye_ghosts -= 1

        if self.eye_ghosts == 0:
            sound = ('power_up' if self.scared_ghosts
                     else C.determine_siren(self.remaining_dots))
            self.sound_manager.set_ambience(sound)

    # ------------------------------------------------------------------
    # Text overlays
    # ------------------------------------------------------------------

    def display_text(self, position, amount, duration, width, height=None):
        """Shows a sprite for `duration` ms (engine.js:2445)."""
        overlay = {
            'image': str(amount),
            'left': position['left'],
            'top': position['top'],
            'width': width,
            'height': height if height is not None else width,
        }

        self.text_overlays.append(overlay)

        def expire():
            if overlay in self.text_overlays:
                self.text_overlays.remove(overlay)

        self.timers.create(expire, duration)

    # ------------------------------------------------------------------
    # Rendering
    # ------------------------------------------------------------------

    def render(self, interp):
        """Draws one frame of the board (engine.js:1772).

        Ordering here replaces what CSS z-index used to do: maze, pickups, then
        the point/status text, then the characters. Note the text overlays are
        drawn *beneath* the characters, which is the reference's order.
        """
        renderer = self.renderer

        renderer.draw_image(
            'maze_blue', 0, 0,
            self.scaled_tile_size * C.MAZE_COLUMNS,
            self.scaled_tile_size * C.MAZE_ROWS,
            self.maze_tint,
        )

        # Power pellets blink on a 300ms cycle, driven off the game clock so
        # they freeze while paused rather than running on their own timeline.
        pellets_visible = (self.pellet_blink_ms % C.PELLET_BLINK_PERIOD_MS) >= 150
        for pickup in self.pickups:
            pickup.draw(renderer, pellets_visible)

        for overlay in self.text_overlays:
            renderer.draw_image(
                overlay['image'], overlay['left'], overlay['top'],
                overlay['width'], overlay['height'],
            )

        self.pacman.draw(interp, renderer)
        for ghost in self.ghosts:
            ghost.draw(interp, renderer)

        if self.maze_cover_visible:
            renderer.fill_rect(
                0, 0,
                self.scaled_tile_size * C.MAZE_COLUMNS,
                self.scaled_tile_size * C.MAZE_ROWS,
                C.BLACK,
            )
