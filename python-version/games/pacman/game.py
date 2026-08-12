"""Pac-Man as the cabinet sees it.

The rest of this package is the port that was here before; this file is only the
seam. It does two jobs:

* gives the coordinator a `Renderer` whose origin is the maze's top-left
  corner, since every engine coordinate is maze-relative and the shell's own
  renderer sits at the top-left of the screen;
* turns the eight shell actions into the coordinator's calls, and a finished
  run into an offer to the shared name-entry modal.

The picker's picture is `preview.png` beside this file, generated from the
game's own art by `tools/make_preview.py` and committed.
"""

import os

from cabinet.game import Game, GameSpec
from cabinet.leaderboard import DATA_FILE
from cabinet.renderer import Renderer

from . import constants as C
from .coordinator import STATE_MENU, STATE_PLAYING, GameCoordinator
from .ui.hud import Hud
from .ui.menu import Menu

TITLE = 'PAC-MAN'
TAGLINE = 'EAT THE DOTS  DODGE THE GHOSTS'
PREVIEW_IMAGE = os.path.join(os.path.dirname(os.path.abspath(__file__)),
                             'preview.png')


class PacmanGame(Game):
    sim_dt_ms = C.SIM_DT_MS

    def __init__(self, context):
        super().__init__(context)

        # A second view onto the shell's surface, offset to the maze. The
        # engine code was ported from a canvas whose origin was the maze's top
        # left, so this is what keeps it free of offset arithmetic.
        self.renderer = Renderer(
            context.renderer.surface, context.assets,
            origin=(C.MAZE_ORIGIN_X, C.MAZE_ORIGIN_Y),
        )

        self.coordinator = GameCoordinator(
            self.renderer, context.sound_manager, context.leaderboard,
        )
        self.hud = Hud(self.renderer, context.font, context.controls)
        self.menu = Menu(
            self.renderer, context.font, context.leaderboard,
            controls=context.controls, sound_manager=context.sound_manager,
        )

        self.coordinator.on_game_over = self._offer_score

        # Drives the blinking prompt on the title screen and the caret in the
        # name-entry modal. Wall-clock, so it keeps running while the
        # simulation is stopped.
        self.ui_clock_ms = 0.0

    # -- lifecycle -----------------------------------------------------------

    def enter(self):
        self.refresh_scores()

    def leave(self):
        # The picker has no idea this game was ever loaded, so nothing may be
        # left running behind it. Reachable only from the title screen, but a
        # half-finished timer chain would outlive the screen it belongs to.
        self.coordinator.timers.clear()
        self.coordinator.state = STATE_MENU
        self.coordinator.running = False
        self.coordinator.started = False
        self.context.sound_manager.stop_all()

    def refresh_scores(self):
        """Repaints both readouts of this game's board.

        The title screen's table and the HUD's HIGH SCORE mirror the same file,
        so a saved name or a reset has to reach both (engine.js:1251-1260).
        """
        self.menu.refresh()
        self.coordinator.refresh_high_score()

    def _offer_score(self, score):
        self.context.submit_score(score, on_close=self.refresh_scores)

    # -- frame ---------------------------------------------------------------

    @property
    def simulating(self):
        return (self.coordinator.state == STATE_PLAYING
                and self.coordinator.running)

    @property
    def at_attract(self):
        # False for the whole of the end-of-game sequence: the coordinator
        # holds STATE_PLAYING until the last timer in the chain fires, which is
        # exactly the behaviour the shell wants from this flag.
        return self.coordinator.state == STATE_MENU

    def tick_realtime(self, frame_ms):
        self.ui_clock_ms += frame_ms
        self.coordinator.tick_realtime(frame_ms)

    def update(self, sim_dt_ms):
        self.coordinator.update(sim_dt_ms)

    def render(self, interp):
        # One flag for the whole cabinet, so F1 means the same thing on the
        # picker as it does here.
        self.coordinator.show_fps = self.context.show_fps
        fps = self.context.fps

        if self.coordinator.state == STATE_PLAYING:
            self.coordinator.render(interp)
            self.hud.draw(self.coordinator, fps)
            if self.coordinator.paused_display:
                self.hud.draw_pause_overlay(
                    muted=self.context.sound_manager.master_volume == 0,
                )
        else:
            self.menu.draw(self.ui_clock_ms)
            if self.context.show_fps:
                self.hud.draw_fps(fps)

    # -- input ---------------------------------------------------------------

    def handle_action(self, action):
        if action in C.DIRECTIONS:
            if self.coordinator.state == STATE_PLAYING:
                self.coordinator.change_direction(action)
        elif action == 'select':
            if self.coordinator.state == STATE_MENU:
                self.menu.refresh()
                self.coordinator.start_button_click()
        elif action == 'pause':
            if self.coordinator.state == STATE_PLAYING:
                self.coordinator.handle_pause_key()


SPEC = GameSpec(
    id='pacman',
    title=TITLE,
    tagline=TAGLINE,
    factory=PacmanGame,
    preview_image=PREVIEW_IMAGE,
    # The original path, kept so a single data.json can still be shared with
    # the Node version - see `cabinet/leaderboard.py`.
    data_file=DATA_FILE,
)
