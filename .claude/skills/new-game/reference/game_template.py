"""A new title, as the cabinet sees it.

Copy to `python-version/games/<id>/game.py`, put an empty `__init__.py` beside
it, and replace every <id>/Template. Nothing else is edited: `games/registry.py`
finds this by scanning, keyed off the SPEC at the bottom.

Designed for feet: four arrow panels and START are the whole vocabulary a run
may depend on. `mute` never fires on the mat and `delete` is name-entry only -
see the skill for why the shape panels are unbound.

Delete what this game does not do. Every `Game` method's default is inert.
"""

from cabinet import constants as C
from cabinet.game import Game, GameSpec
from cabinet.ui import hints

TITLE = 'TEMPLATE'
TAGLINE = 'ONE LINE, ABOUT 32 CHARS'

STATE_MENU = 'menu'
STATE_PLAYING = 'playing'


class TemplateGame(Game):
    # Omit entirely to take the cabinet's 120Hz. Set it only if this game's
    # simulation genuinely needs a different step.
    # sim_dt_ms = 1000.0 / 60

    def __init__(self, context):
        super().__init__(context)
        self.state = STATE_MENU
        self.score = 0
        self.paused = False

        # Wall-clock, so it keeps running while the simulation is stopped -
        # blinking prompts and carets are driven from this, not from sim time.
        self.ui_clock_ms = 0.0

    # -- lifecycle -----------------------------------------------------------

    def enter(self):
        """Control has just passed from the picker."""
        self.refresh_scores()

    def leave(self):
        """Control is going back to the picker.

        Nothing may be left running: the picker has no idea this game was ever
        loaded, so a half-finished timer chain or a looping clip would outlive
        the screen it belongs to. Clear held-input state here too - a release
        is not guaranteed to arrive.
        """
        self.state = STATE_MENU
        self.paused = False
        self.context.sound_manager.stop_all()

    def refresh_scores(self):
        """Repaint every readout of this game's board (title screen + HUD)."""
        self.top_scores = self.context.leaderboard.get_top_scores()

    def _game_over(self):
        # Opens the shared name-entry modal only if the score places; on_close
        # fires either way, so the readout is repainted without checking first.
        self.context.submit_score(self.score, on_close=self.refresh_scores)

    # -- frame ---------------------------------------------------------------

    @property
    def simulating(self):
        """False on the title screen and while paused: sim time freezes."""
        return self.state == STATE_PLAYING and not self.paused

    @property
    def at_attract(self):
        """True only on this game's title screen, nothing in progress.

        The shell reads this to decide whether the operator menu may open and
        whether backing out to the picker is live, so it must stay False for
        the whole of a run - the end-of-game sequence included.
        """
        return self.state == STATE_MENU

    def tick_realtime(self, frame_ms):
        self.ui_clock_ms += frame_ms

    def update(self, sim_dt_ms):
        """One fixed simulation step. Only called while `simulating`."""

    def render(self, interp):
        """`interp` is the fraction between the last two simulation steps."""
        renderer, font = self.context.renderer, self.context.font

        if self.state == STATE_MENU:
            font.draw(renderer.surface, TITLE, C.LOGICAL_WIDTH // 2, 60,
                      C.ARCADE_YELLOW, scale=2, align='center')
            # Never spell out ENTER or START here - the operator menu can
            # switch scheme while this game is loaded.
            scheme = self.context.scheme
            if int(self.ui_clock_ms / 400) % 2 == 0:
                font.draw(renderer.surface, f'PRESS {scheme.start}',
                          C.LOGICAL_WIDTH // 2, 160, C.WHITE, align='center')
        else:
            font.draw(renderer.surface, f'{self.score}', 8, 8, C.WHITE)
            # `PAUSE = [ESC]   🔈 = [Q]`, or the mat's wording. `draw_hint`
            # strikes the speaker through when muted - that is the cabinet's
            # only visible report of mute under the pad scheme.
            muted = self.context.sound_manager.master_volume == 0
            hints.draw_hint(
                renderer.surface, font,
                hints.control_hints(self.context.scheme, 'RESUME' if self.paused
                                    else 'PAUSE'),
                C.LOGICAL_WIDTH // 2, 20, C.ARCADE_GREY,
                align='center', muted=muted,
            )

    # -- input ---------------------------------------------------------------

    def handle_action(self, action):
        """One of: up, down, left, right, select, delete, pause, mute.

        Assume only the four directions, `select` and `pause`: on the mat
        `mute` is unbound and `delete` is the ✕ panel, which is name-entry
        only. Nothing in a run may depend on either.
        """
        if action in C.DIRECTIONS:
            if self.state == STATE_PLAYING:
                pass  # move
        elif action == 'select':
            if self.state == STATE_MENU:
                self.state = STATE_PLAYING
                self.score = 0
        elif action == 'pause':
            if self.state == STATE_PLAYING:
                self.paused = not self.paused

    def handle_release(self, action):
        """Only needed for a **held** control - a crouch, a charged shot.

        On a mat that is a foot resting on a panel. A release can be lost, so
        treat this as "not held any more", never as an event to count.
        """


SPEC = GameSpec(
    id='template',        # must equal the folder name
    title=TITLE,
    tagline=TAGLINE,
    factory=TemplateGame,
    # preview.png and assets/ are found beside this file by convention.
    # pause_ambience='<clip>',   # a loop that keeps playing while paused
    # order=1,                   # pin ahead of the alphabetical list
)
