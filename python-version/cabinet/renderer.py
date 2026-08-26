"""Sprite cache and blit layer (informed by node-version/src/game/renderer.js).

The browser version rasterized each SVG once per target size into an offscreen
canvas and blitted from there. The equivalent here is simpler, because
`tools/convert_assets.py` already rasterized everything at the size it will be
drawn at: `AssetPack` loads the PNGs, calls `convert_alpha()` on each - blitting
an unconverted surface every frame is one of the few genuinely slow things you
can do in pygame - and keeps a small cache for the handful of sprites that are
drawn at a size other than their native one.

**A pack per game, not a pool per cabinet.** Each game's art lives under
`games/<id>/assets/`, described by a `manifest.json` beside it, and is loaded
into a pack of its own. Two consequences, and they are the point:

* sprite keys are scoped, so a second game may have its own `player` without
  renaming Pac-Man's, and a game is handed *its* pack as `context.assets` -
  ported code keeps calling `assets.scaled('maze_blue', ...)` unchanged;
* nothing is read from disk until a game is first played, so a machine with
  thirty titles installed boots as fast as one with a single title and holds
  only the art it has actually shown.

`AssetStore` is the registry of packs, and the thing the shell holds.

A game's world-space coordinates are relative to its playfield's top-left
corner - for Pac-Man, the maze's, exactly as they were on the canvas. `origin`
translates them into screen space, so ported engine code needs no offset
arithmetic of its own. It defaults to the top-left of the screen; a game with a
playfield inset below a score row passes its own (see `games/pacman/game.py`).
"""

import json
import os

import pygame

# The cabinet's own directory - the icon and anything else the shell owns. A
# game's art is *not* here any more; it is under `games/<id>/assets/`.
ASSET_ROOT = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
                          'assets')

EMPTY_MANIFEST = {'sprites': {}, 'audio': {}}


def read_manifest(root):
    """The manifest at `root`, or an empty one.

    A missing, unparseable or wrongly-shaped file is an empty pack rather than
    an error: the cabinet has to boot, and a game whose art did not ship must
    fail as one unplayable title on the picker, not as a machine that does not
    start. `AssetPack.load` reports the sprite count so the loss is visible.
    """
    try:
        with open(os.path.join(root, 'manifest.json'), encoding='utf-8') as handle:
            parsed = json.load(handle)
    except (OSError, ValueError):
        return dict(EMPTY_MANIFEST)

    if not isinstance(parsed, dict):
        return dict(EMPTY_MANIFEST)

    manifest = dict(EMPTY_MANIFEST)
    for section in ('sprites', 'audio'):
        value = parsed.get(section)
        if isinstance(value, dict):
            manifest[section] = value
    return manifest


class AssetPack:
    """One game's sprites, loaded and cached.

    Keys are whatever that game's manifest calls them; nothing outside the pack
    can see them, which is what lets two games use the same name.
    """

    def __init__(self, root, name=''):
        self.root = root
        self.name = name
        self.manifest = dict(EMPTY_MANIFEST)
        self.loaded = False
        self.sheets = {}        # key -> native Surface
        self._scaled = {}       # (key, w, h) -> Surface
        self._frames = {}       # (key, size) -> [Surface]
        self._tinted = {}       # (key, w, h, tint) -> Surface

    def load(self):
        """Loads the manifest and every PNG it lists. Idempotent.

        A sprite that will not load is skipped, exactly as a clip that will not
        decode is (`cabinet/sound.py`). One missing PNG leaves a game drawing
        one thing less; raising here would take the whole cabinet down with it.
        """
        if self.loaded:
            return self

        self.manifest = read_manifest(self.root)

        for key, spec in self.manifest['sprites'].items():
            try:
                path = os.path.join(self.root, spec['file'])
                self.sheets[key] = pygame.image.load(path).convert_alpha()
            except (pygame.error, OSError, TypeError, KeyError):
                continue

        self.loaded = True
        return self

    @property
    def audio(self):
        """`{name: relative path}` for this game's clips, for `SoundManager`."""
        return self.manifest['audio']

    def spec(self, key):
        return self.manifest['sprites'][key]

    def scaled(self, key, width, height):
        """The sprite at an arbitrary size, cached.

        Most sprites are requested at their native size and returned as-is.
        Only the point-value text is ever stretched (the 1000+ fruit values are
        drawn 3 tiles wide from a 2-tile-square source, engine.js:2050).
        Nearest-neighbour scaling keeps the pixel art crisp.
        """
        width = max(1, round(width))
        height = max(1, round(height))
        cache_key = (key, width, height)

        cached = self._scaled.get(cache_key)
        if cached is not None:
            return cached

        surface = self.sheets.get(key)
        if surface is None:
            return None

        if surface.get_size() != (width, height):
            surface = pygame.transform.scale(surface, (width, height))

        self._scaled[cache_key] = surface
        return surface

    def frames(self, key, size):
        """A list of one Surface per animation frame, each `size` square.

        Frames are subsurfaces of the (possibly scaled) sheet, so they share
        its pixels rather than copying them.
        """
        size = max(1, round(size))
        cache_key = (key, size)

        cached = self._frames.get(cache_key)
        if cached is not None:
            return cached

        sheet = self.sheets.get(key)
        if sheet is None:
            return []

        count = self.spec(key)['frames']
        scaled = self.scaled(key, size * count, size)
        result = [
            scaled.subsurface(pygame.Rect(index * size, 0, size, size))
            for index in range(count)
        ]

        self._frames[cache_key] = result
        return result

    def tinted(self, key, width, height, tint):
        """A recoloured copy, cached.

        This reproduces the browser's `color-dodge` composite against white
        (renderer.js:76): every non-black pixel blows out to full brightness
        while black stays exactly black. A plain fill would flood the whole
        board, because the maze SVG paints an opaque black background behind its
        walls.

        Repeatedly adding the surface to itself doubles every channel, so after
        eight passes any value of 1 or more has saturated to 255 while 0 is
        still 0 - which is precisely what dividing by zero does in the
        color-dodge formula. It runs once per (sprite, size, tint).
        """
        width = max(1, round(width))
        height = max(1, round(height))
        cache_key = (key, width, height, tint)

        cached = self._tinted.get(cache_key)
        if cached is not None:
            return cached

        base = self.scaled(key, width, height)
        if base is None:
            return None

        result = base.copy()
        for _ in range(8):
            result.blit(result, (0, 0), special_flags=pygame.BLEND_RGB_ADD)

        # The dodge saturates to white; anything else multiplies that mask down
        # to the requested tint.
        if tint != (255, 255, 255):
            result.fill(tint, special_flags=pygame.BLEND_RGB_MULT)

        self._tinted[cache_key] = result
        return result


class AssetStore:
    """Every pack the cabinet has loaded, keyed by game id.

    The shell holds one of these and hands each game its own pack. It is a
    registry rather than a pool: nothing is shared between packs, so a game can
    neither see another's art nor be broken by it. `pack()` is cached, so
    leaving and re-entering a game does not re-read a single PNG.

    The shell's own pack is the empty one - the picker, the name-entry modal and
    the operator menu draw text and rectangles only, which is why nothing but a
    game has art to load.
    """

    def __init__(self):
        self.packs = {}

    def pack(self, name, root):
        """The named pack, loading it from `root` the first time it is asked for.

        Called as a game is constructed, which is the moment the delay is
        affordable - a fraction of a second behind the picker, and never during
        play.
        """
        existing = self.packs.get(name)
        if existing is None:
            existing = AssetPack(root, name).load()
            self.packs[name] = existing
        return existing

    def shell(self):
        """The empty pack the cabinet's own screens draw with."""
        return self.packs.setdefault('', AssetPack(ASSET_ROOT, ''))


class Renderer:
    def __init__(self, surface, assets, origin=(0, 0)):
        self.surface = surface
        self.assets = assets
        self.origin = origin

    def clear(self):
        """renderer.js:125 - the whole frame starts black."""
        self.surface.fill((0, 0, 0))

    # -- world space (maze-relative), used by the ported engine code ---------

    def draw_image(self, key, x, y, width, height, tint=None):
        """renderer.js:143."""
        surface = (self.assets.tinted(key, width, height, tint) if tint
                   else self.assets.scaled(key, width, height))
        if surface is not None:
            self.surface.blit(
                surface,
                (round(x + self.origin[0]), round(y + self.origin[1])),
            )

    def draw_frame(self, key, frame_index, frames, x, y, size):
        """Draws one frame of a horizontal spritesheet (renderer.js:157)."""
        frame_list = self.assets.frames(key, size)
        if not frame_list:
            return
        # Defensive clamp: a non-looping sheet can be asked for its last frame
        # repeatedly, and a mismatched manifest should not raise mid-frame.
        index = max(0, min(int(frame_index), len(frame_list) - 1))
        self.surface.blit(
            frame_list[index],
            (round(x + self.origin[0]), round(y + self.origin[1])),
        )

    def fill_rect(self, x, y, width, height, color):
        """renderer.js:133 - the maze cover during transitions."""
        self.surface.fill(
            color,
            (round(x + self.origin[0]), round(y + self.origin[1]),
             round(width), round(height)),
        )

    # -- screen space, used by the HUD and menus -----------------------------

    def draw_image_at(self, key, x, y, width=None, height=None):
        """Blits a sprite in absolute screen coordinates."""
        spec = self.assets.manifest['sprites'].get(key)
        if spec is None:
            return
        width = spec['width'] if width is None else width
        height = spec['height'] if height is None else height
        surface = self.assets.scaled(key, width, height)
        if surface is not None:
            self.surface.blit(surface, (round(x), round(y)))

    def fill_rect_at(self, x, y, width, height, color):
        self.surface.fill(color, (round(x), round(y), round(width), round(height)))
