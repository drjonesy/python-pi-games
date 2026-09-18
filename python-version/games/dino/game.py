"""DINO RUN as the cabinet sees it.

A runner played with two panels: ▲ jumps a rock or a low flyer, ▼ ducks a
high one. The ground starts slow and gains 10% every ten seconds; each obstacle
that gets past is a point, and the first one that doesn't ends the run.

The rules are in `world.py`. This file is the seam: it turns the cabinet's
actions into ▲ / ▼, draws the world, and hands a finished run to the shared
name-entry modal. Art is built from `_games/dino-run/` by
`tools/convert_dino_assets.py`, which also writes `preview.png`.
"""

import pygame

from cabinet import constants as C
from cabinet.game import Game, GameSpec
from cabinet.renderer import Renderer
from cabinet.ui import hints

from . import constants as D
from .world import DYING, World

TITLE = 'DINO RUN'
TAGLINE = 'JUMP THE ROCKS  DUCK THE FLYERS'

STATE_MENU = 'menu'
STATE_PLAYING = 'playing'

# The HUD: two lines at the top, high score on the left and score on the right,
# as in the "Game Start" scene.
HUD_LABEL_Y = 8
HUD_VALUE_Y = 18
HUD_MARGIN = 8
HINT_Y = 32

BUTTON = pygame.Rect(0, 0, 124, 30)
BUTTON.center = (D.SCREEN_W // 2, 108)

BIRD_FRAMES = 8


def score_text(score):
    return f'{score:06d}'


class DinoGame(Game):
    def __init__(self, context):
        super().__init__(context)
        # The shell's own renderer draws from the cabinet's (empty) pack; the
        # sprites here are this game's, so it needs a view onto its own.
        self.renderer = (Renderer(context.renderer.surface, context.assets)
                         if context.renderer is not None else None)

        self.state = STATE_MENU
        self.world = None
        self.paused = False
        self.offered = False        # the finished run has gone to name entry
        self.last_score = 0
        self.top = None             # {'name', 'score'} or None
        self.ui_clock_ms = 0.0

    # -- lifecycle -----------------------------------------------------------

    def enter(self):
        self.refresh_scores()

    def leave(self):
        # Only reachable from the title screen, but nothing may outlive it.
        self.state = STATE_MENU
        self.world = None
        self.paused = False

    def refresh_scores(self):
        scores = self.context.leaderboard.get_top_scores()
        self.top = scores[0] if scores else None

    def start(self):
        self.world = World()
        self.state = STATE_PLAYING
        self.paused = False
        self.offered = False

    def _offer_score(self):
        self.offered = True
        self.last_score = self.world.score
        self.context.submit_score(self.world.score, on_close=self._to_title)

    def _to_title(self):
        self.refresh_scores()
        self.state = STATE_MENU
        self.world = None

    # -- frame ---------------------------------------------------------------

    @property
    def simulating(self):
        return self.state == STATE_PLAYING and not self.paused

    @property
    def at_attract(self):
        # False from the first step until the score has been dealt with, the
        # fall and GAME OVER included.
        return self.state == STATE_MENU

    def tick_realtime(self, frame_ms):
        self.ui_clock_ms += frame_ms

    def update(self, sim_dt_ms):
        world = self.world
        if world is None:
            return
        world.update(sim_dt_ms)
        if (world.state == DYING and not self.offered
                and world.dead_ms >= D.GAME_OVER_MS):
            self._offer_score()

    # -- input ---------------------------------------------------------------

    def handle_action(self, action):
        """▲ and ▼ are the whole game. START also starts, like every title,
        and either one moves on from GAME OVER.

        ← and → do nothing: on a mat they are where a foot lands on the way
        between the other panels.
        """
        if self.state == STATE_MENU:
            if action in ('up', 'select'):
                self.start()
            return

        if self.world.state == DYING:
            if (action in ('up', 'select') and not self.offered
                    and self.world.dead_ms >= D.GAME_OVER_SKIP_MS):
                self._offer_score()
            return

        if action == 'pause':
            self.paused = not self.paused
            return
        if self.paused:
            return

        if action == 'up':
            self.world.press_up()
        elif action == 'down':
            self.world.press_down()

    def handle_release(self, action):
        if action == 'down' and self.world is not None:
            self.world.release_down()

    # -- drawing -------------------------------------------------------------

    def render(self, interp):
        surface = self.renderer.surface
        surface.fill(D.SKY)

        world = self.world
        self._draw_ground(world.distance if world else 0.0)

        if world is None:
            self._draw_sprite('idle_0', D.DINO_X, 0)
            self._draw_title()
            self._draw_hud(self.last_score)
            return

        for obstacle in world.obstacles:
            if obstacle.kind == D.ROCK:
                key = 'rock'
            else:
                key = f'bird_{int(obstacle.age_ms / D.BIRD_FLAP_MS) % BIRD_FRAMES}'
            self.renderer.draw_image_at(
                key, obstacle.x,
                D.FEET_Y - obstacle.altitude - obstacle.sprite_height,
            )
        self._draw_sprite(world.dino_sprite(), D.DINO_X, world.dino.altitude)

        self._draw_hud(world.score)
        if world.state == DYING:
            if world.dead_ms >= D.DEAD_FRAMES * D.DEAD_FRAME_MS:
                self._center('GAME OVER', 104, D.INK, scale=3)
        elif self.paused:
            self._draw_pause()
        else:
            self._draw_control_hint('PAUSE')

    def _draw_sprite(self, key, x, altitude):
        """A dinosaur frame, placed by its feet rather than its corner."""
        spec = self.context.assets.manifest['sprites'].get(key)
        if spec is None:
            return
        feet = spec.get('feet', spec['height'])
        self.renderer.draw_image_at(key, x, D.FEET_Y - altitude - feet)

    def _draw_ground(self, distance):
        spec = self.context.assets.manifest['sprites'].get('grass')
        if spec is None:
            return
        width = spec['width']
        offset = -(distance % width)
        while offset < D.SCREEN_W:
            self.renderer.draw_image_at('grass', offset, D.GRASS_TOP)
            offset += width

    def _draw_hud(self, score):
        font, surface = self.context.font, self.renderer.surface
        font.draw(surface, 'HIGH SCORE', HUD_MARGIN, HUD_LABEL_Y, D.INK)
        if self.top:
            # The board stores numbers as JSON does, so 3401 can read back 3401.0.
            best = f'{self.top["name"]} {int(self.top["score"])}'
            font.draw(surface, best, HUD_MARGIN, HUD_VALUE_Y, D.INK)
        right = D.SCREEN_W - HUD_MARGIN
        font.draw(surface, 'SCORE', right, HUD_LABEL_Y, D.INK, align='right')
        font.draw(surface, score_text(score), right, HUD_VALUE_Y, D.INK,
                  align='right')

    def _draw_title(self):
        surface, scheme = self.renderer.surface, self.context.scheme
        self._center(TITLE, 60, D.INK, scale=2)

        # The START button from the "Game Start" scene, naming whichever
        # control starts a game under the active scheme.
        pygame.draw.rect(surface, D.INK, BUTTON.move(0, 3), border_radius=15)
        pygame.draw.rect(surface, C.ARCADE_YELLOW, BUTTON, border_radius=15)
        pygame.draw.rect(surface, D.INK, BUTTON, width=2, border_radius=15)
        if int(self.ui_clock_ms / 500) % 3 != 2:
            self._center(scheme.start, BUTTON.centery - 7, D.INK, scale=2)

        self._center('▲ JUMP    ▼ DUCK', 142, D.INK)
        if scheme.back:
            self._center(f'{scheme.back} = GAMES', 166, C.ARCADE_GREY)
        self._draw_control_hint('PAUSE', y=178)

    def _draw_pause(self):
        veil = pygame.Surface((D.SCREEN_W, D.SCREEN_H), pygame.SRCALPHA)
        veil.fill((*D.SKY, 170))
        self.renderer.surface.blit(veil, (0, 0))
        self._center('PAUSED', 104, D.INK, scale=2)
        self._draw_control_hint('RESUME', y=128)

    def _draw_control_hint(self, verb, y=HINT_Y):
        hints.draw_hint(
            self.renderer.surface, self.context.font,
            hints.control_hints(self.context.scheme, verb),
            D.SCREEN_W // 2, y, C.ARCADE_GREY, align='center',
            muted=self.context.sound_manager.master_volume == 0,
        )

    def _center(self, text, y, color, scale=1):
        self.context.font.draw(self.renderer.surface, text, D.SCREEN_W // 2, y,
                               color, scale=scale, align='center')


SPEC = GameSpec(
    id='dino',
    title=TITLE,
    tagline=TAGLINE,
    factory=DinoGame,
)
