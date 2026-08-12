"""The shell: two screens, the modals over them, and the frame loop.

The cabinet is always on exactly one of two screens - the game picker, or a
game - with two modals that may sit over either: the name-entry overlay and the
operator menu. `main.py` builds the window and the shared services and hands
them here; everything from the first frame on is this class.

**Input funnels through one place on purpose.** Pygame events become the eight
actions the whole machine speaks (four directions, `select`, `delete`, `pause`,
`mute`), and `_dispatch` decides who gets them: a modal if one is up, otherwise
the current screen. That is the only routing table, so a game cannot be reached
by a keypress meant for a dialog and does not have to check whether one is
open. The rules that used to be scattered through `main.py` as
`if score_entry.open` guards are now one function.

The mat is handled ahead of that, in `_handle_pad_event`, because the operator
menu is opened and driven by *physical panels* rather than by actions - see
`ui/system_menu.py` for why those are not the same thing.
"""

import pygame

from . import constants as C
from .engine import GameEngine
from .game import GameContext
from .gamepad import GamepadManager
from .leaderboard import Leaderboard
from .renderer import Renderer
from .ui.game_select import GameSelect
from .ui.score_entry import ScoreEntry
from .ui.system_menu import SystemMenu

SCREEN_PICKER = 'picker'
SCREEN_GAME = 'game'

# engine.js:1178-1190. The on-screen d-pad and all touch handling are dropped -
# there is no touchscreen and no portrait layout (§10).
MOVEMENT_KEYS = {
    pygame.K_w: 'up',
    pygame.K_s: 'down',
    pygame.K_a: 'left',
    pygame.K_d: 'right',
    pygame.K_UP: 'up',
    pygame.K_DOWN: 'down',
    pygame.K_LEFT: 'left',
    pygame.K_RIGHT: 'right',
}

# Desktop stand-ins for the mat, so the operator menu can be exercised with no
# pad plugged in. Arrows navigate; the shapes sit on their initials.
SYSTEM_MENU_KEYS = {
    pygame.K_UP: ((), ('up',)),
    pygame.K_DOWN: ((), ('down',)),
    pygame.K_x: (('cross',), ()),
    pygame.K_s: (('square',), ()),
    pygame.K_t: (('triangle',), ()),
    pygame.K_c: (('circle',), ()),
}


class Cabinet:
    def __init__(self, window, surface, assets, font, sound_manager, controls,
                 pads, specs, data_files=None, show_fps=False):
        self.window = window
        # The logical surface. Identical to `window` when SDL is scaling for
        # us; a separate buffer under --windowed.
        self.surface = surface
        self.assets = assets
        self.font = font
        self.sound_manager = sound_manager
        self.controls = controls
        self.pads = pads
        self.specs = tuple(specs)
        # `{game_id: path}` from --data-file, which points one game's board
        # somewhere else - at the Node version's file, usually.
        self.data_files = dict(data_files or {})

        # Origin at the top-left of the screen. A game whose world coordinates
        # are relative to an inset playfield makes its own - see
        # `games/pacman/game.py`.
        self.renderer = Renderer(surface, assets)

        self.running = True
        self.screen = SCREEN_PICKER
        self.game = None
        self.spec = None

        # Both keyed by game id and built on demand. A board is read from disk
        # per call, so holding one costs nothing; a game holds its whole sprite
        # and timer state, so it is built the first time it is played and kept
        # for the rest of the session.
        self._boards = {}
        self._games = {}

        self.picker = GameSelect(
            self.renderer, font, self.specs, self.leaderboard_for,
            controls=controls, sound_manager=sound_manager,
        )
        self.picker.on_choose = self.play

        self.score_entry = ScoreEntry(self.renderer, font, None,
                                      controls=controls)
        self.system_menu = SystemMenu(self.renderer, font, controls=controls,
                                      sound_manager=sound_manager)

        self.show_fps = show_fps
        self.ui_clock_ms = 0.0
        self.engine = GameEngine(self._update, self._render)

    # -- games and boards ----------------------------------------------------

    def leaderboard_for(self, spec):
        """This game's board. One instance per game, shared with the game."""
        board = self._boards.get(spec.id)
        if board is None:
            board = Leaderboard(self.data_files.get(spec.id, spec.data_file))
            self._boards[spec.id] = board
        return board

    def _game_for(self, spec):
        game = self._games.get(spec.id)
        if game is None:
            context = GameContext(
                renderer=self.renderer,
                assets=self.assets,
                font=self.font,
                sound_manager=self.sound_manager,
                controls=self.controls,
                leaderboard=self.leaderboard_for(spec),
                submit_score=self._submit_score,
                exit_to_picker=self.to_picker,
                quit_cabinet=self.quit,
            )
            game = spec.create(context)
            self._games[spec.id] = game
        return game

    # -- screens -------------------------------------------------------------

    def play(self, spec):
        self.spec = spec
        self.game = self._game_for(spec)
        self.screen = SCREEN_GAME
        # Rebuilt per game: two games may simulate at different rates, and the
        # accumulator must not carry a partial step across from the last one.
        self.engine = GameEngine(
            self._update, self._render,
            sim_dt_ms=self.game.sim_dt_ms or C.SIM_DT_MS,
        )
        self.game.enter()

    def to_picker(self):
        """Back to the game list. Safe to call when already there."""
        if self.game is not None:
            self.game.leave()
        self.screen = SCREEN_PICKER
        # The board may have changed while the game was up.
        self.picker.refresh()

    def quit(self):
        self.running = False

    # -- modals --------------------------------------------------------------

    def _submit_score(self, score, on_close=None):
        """Offers a finished run to the name-entry modal.

        Called by a game through its context, so the board is bound here rather
        than by the game: the modal writes to whichever game asked, and cannot
        be pointed at another one's file.
        """
        self.score_entry.leaderboard = self.leaderboard_for(self.spec)
        self.score_entry.try_open(
            score, on_close=lambda: self._scores_changed(on_close),
        )

    def _scores_changed(self, on_close=None):
        self.picker.refresh()
        if on_close:
            on_close()

    def _open_system_menu(self):
        """Opens over whichever screen is up, pointed at that screen's board."""
        spec = self.spec if self.screen == SCREEN_GAME else self.picker.selected
        if spec is None:
            return

        self.system_menu.open_menu(
            on_reset=lambda: self._scores_changed(self._refresh_game_scores),
            on_exit=self.quit,
            # Absent on the picker: there is no game to leave, and a row that
            # did nothing would be worse than a missing one.
            on_change_game=(self.to_picker if self.screen == SCREEN_GAME
                            else None),
            leaderboard=self.leaderboard_for(spec),
            target_label=spec.title,
        )

    def _refresh_game_scores(self):
        refresh = getattr(self.game, 'refresh_scores', None)
        if refresh is not None:
            refresh()

    @property
    def _modal_open(self):
        return self.score_entry.open or self.system_menu.open

    def _system_menu_armed(self):
        """Whether SELECT may open the operator menu right now.

        Title screens only - never mid-run, and never behind the name-entry
        modal, which is still up while a game's state has already gone back to
        its menu.
        """
        if self.score_entry.open or self.system_menu.open:
            return False
        if self.screen == SCREEN_PICKER:
            return True
        return self.game is not None and self.game.at_attract

    def _can_leave_game(self):
        return (self.screen == SCREEN_GAME and not self._modal_open
                and self.game is not None and self.game.at_attract)

    # -- input ---------------------------------------------------------------

    def _dispatch(self, actions):
        for action in actions:
            self._handle_action(action)

    def _handle_action(self, action):
        """The one routing table. Modals first, then the current screen."""
        if self.score_entry.open:
            if action in C.DIRECTIONS:
                self.score_entry.move(action)
            elif action == 'select':
                self.score_entry.select()
            elif action == 'delete':
                self.score_entry.backspace()
            return

        if action == 'mute':
            self.sound_manager.toggle_mute()
            return

        if self.screen == SCREEN_PICKER:
            self.picker.handle_action(action)
        elif self.game is not None:
            self.game.handle_action(action)

    def _handle_pad_event(self, event):
        # Always let the manager see the event first: it also does the hotplug
        # bookkeeping, which has nothing to do with what a modal wants.
        actions = self.pads.handle(event)
        panels = self.pads.panels(event)

        if self.system_menu.open:
            self.system_menu.feed(panels=panels, actions=actions)
        elif self._system_menu_armed() and 'select' in panels:
            # Free to take: the SELECT panel drives `pause`, and there is
            # nothing to pause on a title screen. Everywhere else it still
            # does.
            self._open_system_menu()
        else:
            self._dispatch(actions)

    def _handle_system_menu_key(self, event):
        # A mat enumerating as a keyboard still gets first refusal here, exactly
        # as it does outside the modal.
        panels = self.pads.key_panels(event)
        if panels:
            self.system_menu.feed(panels=panels,
                                  actions=self.pads.key_actions(event))
            return

        if event.key == pygame.K_ESCAPE:
            self.system_menu.close()
        elif event.key in (pygame.K_RETURN, pygame.K_KP_ENTER):
            # Enter stands in for whichever panel this stage is waiting on:
            # SELECT to pick an option, START to commit the reset.
            self.system_menu.feed(
                panels=('start' if self.system_menu.awaiting_confirm
                        else 'select',),
            )
        else:
            panels, actions = SYSTEM_MENU_KEYS.get(event.key, ((), ()))
            if panels or actions:
                self.system_menu.feed(panels=panels, actions=actions)

    def _handle_keydown(self, event):
        # Modal, like the name entry: while it is up it consumes every key, so
        # nothing being typed at it can reach what is behind.
        if self.system_menu.open:
            self._handle_system_menu_key(event)
            return

        # A mat that enumerates as an HID keyboard gets first refusal, so its
        # panels win over whatever those keys would otherwise mean. Only
        # populated if the mapping file actually contains `key` bindings.
        pad_bound = self.pads.key_actions(event)
        pad_panels = self.pads.key_panels(event)
        if pad_bound or pad_panels:
            if self._system_menu_armed() and 'select' in pad_panels:
                self._open_system_menu()
                return
            if pad_bound:
                self._dispatch(pad_bound)
                return

        if event.key in MOVEMENT_KEYS:
            self._handle_action(MOVEMENT_KEYS[event.key])
        elif event.key in (pygame.K_RETURN, pygame.K_KP_ENTER):
            self._handle_action('select')
        elif event.key == pygame.K_BACKSPACE:
            self._handle_action('delete')
        elif event.key == pygame.K_ESCAPE:
            self._handle_escape()
        elif event.key == pygame.K_q:
            if event.mod & pygame.KMOD_CTRL:
                self.quit()
            else:
                self._handle_action('mute')
        elif event.key == pygame.K_F10:
            self.quit()
        elif event.key == pygame.K_F1:
            self.show_fps = not self.show_fps
        elif event.key == pygame.K_r and event.mod & pygame.KMOD_CTRL:
            # Desktop stand-in for the SELECT panel on the mat.
            if self._system_menu_armed():
                self._open_system_menu()

    def _handle_escape(self):
        """Pause, back out, or quit - whichever the current screen affords.

        ESC is pause during play, as in the reference (engine.js:1976). On a
        title screen it steps back to the game list, and on the game list -
        where there is nothing left to back out to and no browser chrome to
        close the window with - it quits (§10).
        """
        if self.score_entry.open:
            return
        if self._can_leave_game():
            self.to_picker()
        elif self.screen == SCREEN_GAME:
            self._handle_action('pause')
        else:
            self.quit()

    # -- frame ---------------------------------------------------------------

    def _update(self, elapsed_ms):
        if self.game is not None:
            self.game.update(elapsed_ms)

    def _render(self, interp):
        self.renderer.clear()

        if self.screen == SCREEN_GAME and self.game is not None:
            self.game.render(interp)
        else:
            self.picker.draw()
            if self.show_fps:
                self._draw_fps()

        if self.score_entry.open:
            self.score_entry.draw(self.ui_clock_ms)

        if self.system_menu.open:
            self.system_menu.draw(self.ui_clock_ms)

        if self.surface is not self.window:
            pygame.transform.scale(self.surface, self.window.get_size(),
                                   self.window)

        pygame.display.flip()

    def _draw_fps(self):
        self.font.draw(self.surface, f'{round(self.engine.fps)} FPS',
                       C.LOGICAL_WIDTH - 2, 1, C.ARCADE_CYAN, align='right')

    def _sync_context(self):
        """Push the cabinet-wide flags into the loaded game's context."""
        if self.game is None:
            return
        self.game.context.show_fps = self.show_fps
        self.game.context.fps = self.engine.fps

    def run(self):
        clock = pygame.time.Clock()

        while self.running:
            for event in pygame.event.get():
                if event.type == pygame.QUIT:
                    self.quit()
                elif event.type == pygame.KEYDOWN:
                    self._handle_keydown(event)
                elif event.type in GamepadManager.EVENT_TYPES:
                    # Includes the hotplug events, so a pad plugged in after
                    # launch starts working without a restart.
                    self._handle_pad_event(event)

            frame_ms = clock.tick(C.RENDER_FPS)
            self.ui_clock_ms += frame_ms
            self._sync_context()

            if self.screen == SCREEN_GAME and self.game is not None:
                self.game.tick_realtime(frame_ms)

            # Wall-clock, not simulation time: nothing is simulating behind the
            # operator menu, so its idle timeout cannot be driven by the engine.
            if self.system_menu.open:
                self.system_menu.tick(frame_ms)

            simulating = (self.screen == SCREEN_GAME and self.game is not None
                          and self.game.simulating)
            if simulating:
                self.engine.tick(frame_ms)
            else:
                # Nothing to simulate on a menu or while paused, but the frame
                # still has to be drawn. Timers are driven by simulation time,
                # so they freeze here exactly as the reference's did when it
                # stopped its animation-frame loop (engine.js:2601).
                self.engine.track_fps(frame_ms)
                self._render(1.0)

        return 0
