#!/usr/bin/env python3
"""Build-time art for DINO RUN. Run this on a desktop, never on the Pi.

The source art is in `../_games/dino-run/assets/`, and none of it is at a size
the cabinet can blit directly:

* the dinosaur's run / jump / dead / idle frames are 680x472 PNGs with a lot of
  empty canvas around a character that has to end up ~46px tall;
* the duck pose, the rock, the bird strip and the grass are JPEGs on a white
  background, so they have no alpha at all.

So every frame is keyed, cropped and scaled here, once, and written into
`games/dino/assets/` with a `manifest.json` beside it and the picker's
`preview.png`. The output is committed; the Pi loads PNGs only.

Keying removes white **connected to the image border** rather than every white
pixel, so the whites of the dinosaur's eyes and teeth survive.

Every dinosaur PNG frame is cropped with one shared rectangle - the union of all
of them - so the feet sit on the same pixel row in every frame and the game can
anchor all of them at one point. The duck pose comes from a different drawing
at a different scale, so it is sized against the run frames instead.

Usage::

    python tools/convert_dino_assets.py [--source ../_games/dino-run/assets]
"""

import argparse
import json
import os
import sys

REPO_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, REPO_ROOT)

os.environ.setdefault('SDL_VIDEODRIVER', 'dummy')

import pygame                                            # noqa: E402

from games.dino import constants as D                    # noqa: E402

DEFAULT_SOURCE = os.path.normpath(
    os.path.join(REPO_ROOT, '..', '_games', 'dino-run', 'assets'),
)
ASSET_OUT = os.path.join(REPO_ROOT, 'games', 'dino', 'assets')
SPRITE_OUT = os.path.join(ASSET_OUT, 'sprites')
PREVIEW_OUT = os.path.join(REPO_ROOT, 'games', 'dino', 'preview.png')

# How the source PNGs are numbered, and how many of each there are.
DINO_ANIMATIONS = {'run': 8, 'jump': 12, 'dead': 8, 'idle': 1}

# A pixel at least this bright in every channel counts as background, if the
# border can reach it. JPEG noise keeps the "white" sky a few levels below 255.
WHITE_THRESHOLD = 225

# The grass JPEG is a white sky over a strip of ground. Everything above this
# row is sky except the tallest flower, which starts just below it.
GRASS_CROP_TOP = 465

# The ducking dinosaur's height as a fraction of the standing one's. The duck
# art is a separate drawing at its own scale, so there is nothing in the files
# to size it by. The "Flyer Duck" scene measures ~0.79; slightly lower leaves
# visible daylight between a ducked head and a bird flying at BIRD_HIGH.
DUCK_HEIGHT_RATIO = 0.74


# -- keying and cropping ------------------------------------------------------

def key_white(surface):
    """The surface with its border-connected white made transparent."""
    surface = surface.convert_alpha()
    width, height = surface.get_size()

    white = pygame.mask.from_threshold(
        surface, (255, 255, 255, 255),
        (256 - WHITE_THRESHOLD,) * 3 + (255,),
    )

    background = pygame.mask.Mask((width, height))
    border = ([(x, 0) for x in range(width)]
              + [(x, height - 1) for x in range(width)]
              + [(0, y) for y in range(height)]
              + [(width - 1, y) for y in range(height)])
    for point in border:
        if white.get_at(point) and not background.get_at(point):
            background.draw(white.connected_component(point), (0, 0))

    # Multiplying by opaque white is the identity and by transparent black
    # clears the pixel, so this one blit is the whole key.
    stencil = background.to_surface(
        surface=pygame.Surface((width, height), pygame.SRCALPHA),
        setcolor=(0, 0, 0, 0), unsetcolor=(255, 255, 255, 255),
    )
    keyed = surface.copy()
    keyed.blit(stencil, (0, 0), special_flags=pygame.BLEND_RGBA_MULT)
    return keyed


def opaque_bounds(surface):
    """The smallest rect holding every visibly opaque pixel."""
    rects = pygame.mask.from_surface(surface, 16).get_bounding_rects()
    if not rects:
        return surface.get_rect()
    return rects[0].unionall(rects[1:])


def scale(surface, factor):
    width, height = surface.get_size()
    size = (max(1, round(width * factor)), max(1, round(height * factor)))
    return pygame.transform.smoothscale(surface, size)


# -- the pieces ---------------------------------------------------------------

def load(source, name):
    return pygame.image.load(os.path.join(source, name))


def dino_frames(source):
    """{key: surface} for every PNG frame, and the feet row within them."""
    raw = {}
    for name, count in DINO_ANIMATIONS.items():
        for index in range(count):
            image = load(source, f'{name.title()} ({index + 1}).png').convert_alpha()
            raw[f'{name}_{index}'] = image

    union = None
    for image in raw.values():
        bounds = opaque_bounds(image)
        union = bounds if union is None else union.union(bounds)

    # Sized by the run cycle, since that is the pose on screen almost always.
    run_bounds = None
    for index in range(DINO_ANIMATIONS['run']):
        bounds = opaque_bounds(raw[f'run_{index}'])
        run_bounds = bounds if run_bounds is None else run_bounds.union(bounds)
    factor = D.DINO_HEIGHT / run_bounds.height

    frames = {key: scale(image.subsurface(union), factor)
              for key, image in raw.items()}
    # Feet: the bottom of the run cycle, measured from the top of the crop.
    return frames, round((run_bounds.bottom - union.top) * factor)


def duck_frame(source):
    keyed = key_white(load(source, 'Duck (1).jpeg'))
    keyed = keyed.subsurface(opaque_bounds(keyed))
    return scale(keyed, D.DINO_HEIGHT * DUCK_HEIGHT_RATIO / keyed.get_height())


def bird_frames(source):
    """The strip split on its fully transparent columns, one surface each.

    The frames are not evenly spaced in the strip, so they are found rather
    than cut on a grid. Each keeps the strip's full height, so a bird's body
    stays at the height it was drawn at from frame to frame, and all are padded
    to one width with the beak at the left edge.
    """
    keyed = key_white(load(source, 'bird-dino.jpeg'))
    bounds = opaque_bounds(keyed)
    mask = pygame.mask.from_surface(keyed, 16)

    columns = [any(mask.get_at((x, y)) for y in range(bounds.top, bounds.bottom))
               for x in range(keyed.get_width())]
    spans, start = [], None
    for x, filled in enumerate(columns + [False]):
        if filled and start is None:
            start = x
        elif not filled and start is not None:
            if x - start > 20:          # ignore specks of JPEG noise
                spans.append((start, x))
            start = None

    widest = max(end - begin for begin, end in spans)
    factor = D.BIRD_HEIGHT / bounds.height
    frames = []
    for begin, end in spans:
        frame = pygame.Surface((widest, bounds.height), pygame.SRCALPHA)
        frame.blit(keyed, (0, 0),
                   pygame.Rect(begin, bounds.top, end - begin, bounds.height))
        frames.append(scale(frame, factor))
    return frames


def rock_frame(source):
    keyed = key_white(load(source, 'rock.jpeg'))
    keyed = keyed.subsurface(opaque_bounds(keyed))
    return scale(keyed, D.ROCK_HEIGHT / keyed.get_height())


def grass_tile(source):
    """One seamless tile of ground: the strip, then its mirror image.

    The source strip's two ends do not meet, so tiling it as-is would put a
    visible seam across the screen once every tile width. Mirrored, the right
    edge of each half is the left edge of the next.
    """
    image = load(source, 'grass-field.jpeg')
    strip = image.subsurface(pygame.Rect(
        0, GRASS_CROP_TOP, image.get_width(), image.get_height() - GRASS_CROP_TOP,
    ))
    keyed = key_white(strip)
    keyed = scale(keyed, D.GRASS_HEIGHT / keyed.get_height())
    width, height = keyed.get_size()
    tile = pygame.Surface((width * 2, height), pygame.SRCALPHA)
    tile.blit(keyed, (0, 0))
    tile.blit(pygame.transform.flip(keyed, True, False), (width, 0))
    return tile


# -- output -------------------------------------------------------------------

def write_sprite(sprites, key, surface, **extra):
    path = f'sprites/{key}.png'
    pygame.image.save(surface, os.path.join(ASSET_OUT, path))
    width, height = surface.get_size()
    sprites[key] = {'file': path, 'width': width, 'height': height,
                    'frame_width': width, 'frames': 1, **extra}


def render_preview(pieces, width, height):
    """The picker's still: mid-jump over a rock, a flyer coming in."""
    preview = pygame.Surface((width, height))
    preview.fill(D.SKY)

    grass = pieces['grass']
    ground_top = height - grass.get_height() + 4
    preview.blit(grass, (-20, ground_top))
    feet_y = ground_top + (D.FEET_Y - D.GRASS_TOP)

    rock = pieces['rock']
    preview.blit(rock, (46, feet_y - rock.get_height()))

    dino = pieces['jump_5']
    preview.blit(dino, (18, feet_y - pieces['feet'] - 38))

    bird = pieces['birds'][0]
    preview.blit(bird, (width - bird.get_width() + 6, 18))
    return preview


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--source', default=DEFAULT_SOURCE)
    args = parser.parse_args(argv)

    pygame.init()
    pygame.display.set_mode((1, 1))      # convert_alpha needs a video mode

    os.makedirs(SPRITE_OUT, exist_ok=True)
    for name in os.listdir(SPRITE_OUT):
        if name.endswith('.png'):
            os.remove(os.path.join(SPRITE_OUT, name))

    sprites = {}
    frames, feet = dino_frames(args.source)
    for key, surface in frames.items():
        # `feet` is the row the dinosaur stands on, so the game places every
        # frame - the duck included - by the same point.
        write_sprite(sprites, key, surface, feet=feet)

    duck = duck_frame(args.source)
    write_sprite(sprites, 'duck', duck, feet=duck.get_height())

    birds = bird_frames(args.source)
    for index, surface in enumerate(birds):
        write_sprite(sprites, f'bird_{index}', surface)

    rock = rock_frame(args.source)
    write_sprite(sprites, 'rock', rock)

    grass = grass_tile(args.source)
    write_sprite(sprites, 'grass', grass)

    manifest = {'sprites': sprites, 'audio': {}}
    with open(os.path.join(ASSET_OUT, 'manifest.json'), 'w', encoding='utf-8') as handle:
        json.dump(manifest, handle, indent=2, sort_keys=True)
        handle.write('\n')

    from cabinet.ui.game_select import PREVIEW_INNER
    preview = render_preview(
        {'grass': grass, 'rock': rock, 'birds': birds, 'feet': feet, **frames},
        PREVIEW_INNER.width, PREVIEW_INNER.height,
    )
    pygame.image.save(preview, PREVIEW_OUT)

    for key in ('run_0', 'duck', 'bird_0', 'rock', 'grass'):
        spec = sprites[key]
        print(f'{key:8} {spec["width"]}x{spec["height"]}'
              + (f'  feet={spec["feet"]}' if 'feet' in spec else ''))
    print(f'{len(birds)} bird frames, {len(sprites)} sprites -> {ASSET_OUT}')
    print(f'wrote {PREVIEW_OUT}')

    pygame.quit()
    return 0


if __name__ == '__main__':
    sys.exit(main())
