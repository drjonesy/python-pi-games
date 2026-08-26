#!/usr/bin/env python3
"""Build-time asset conversion. Run this on a desktop, never on the Pi.

pygame cannot load SVG, and rasterizing vectors at runtime is exactly the kind
of work this port exists to avoid. So every SVG is rasterized to PNG here, once,
at the size it will actually be drawn at, and every MP3 is transcoded to OGG
Vorbis (pygame.mixer's MP3 support depends on the SDL build and is a common
source of Pi-specific breakage; OGG is reliable).

The output is Pac-Man's asset pack - `games/pacman/assets/sprites/*.png`,
`.../audio/*.ogg` and `.../manifest.json` - and it is committed, so the Pi needs
neither cairosvg nor ffmpeg installed. It goes beside the game rather than into
a machine-wide pool because art belongs to a title: this tool converts *this*
game's assets, and another game brings its own however it likes.

Requirements (desktop only)::

    pip install cairosvg pygame-ce      # and: brew install ffmpeg

Usage::

    python tools/convert_assets.py [--source ../node-version/public/app/style]
"""

import argparse
import json
import os
import shutil
import subprocess
import sys

REPO_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DEFAULT_SOURCE = os.path.normpath(
    os.path.join(REPO_ROOT, '..', 'node-version', 'public', 'app', 'style'),
)
ASSET_OUT = os.path.join(REPO_ROOT, 'games', 'pacman', 'assets')
SPRITE_OUT = os.path.join(ASSET_OUT, 'sprites')
AUDIO_OUT = os.path.join(ASSET_OUT, 'audio')
MANIFEST_OUT = os.path.join(ASSET_OUT, 'manifest.json')

# The art is authored at 8px per tile, which is the scale the game renders at,
# so every sprite rasterizes 1:1 with no resampling. See constants.SCALE.
GHOST_DIRECTIONS = ('up', 'down', 'left', 'right')

# ---------------------------------------------------------------------------
# Sprite inventory. `frames` is explicit rather than inferred from the aspect
# ratio, because several single images are wider than they are tall (ready.svg
# is 48x16) and would otherwise be mistaken for three-frame sheets.
# Frame counts and rates come from engine.js:139-141, 920-922 and 978-979.
# ---------------------------------------------------------------------------
def build_inventory():
    sprites = {}

    def add(key, path, frames=1):
        sprites[key] = {'source': path, 'frames': frames}

    chars = 'graphics/spriteSheets/characters'
    ghosts = f'{chars}/ghosts'
    pac = f'{chars}/pacman'

    # Pacman: 4 directions at 4 frames each, plus the 12-frame death sheet.
    for direction in GHOST_DIRECTIONS:
        add(f'pacman_{direction}', f'{pac}/pacman_{direction}.svg', frames=4)
        add(f'arrow_{direction}', f'{pac}/arrow_{direction}.svg', frames=1)
    add('pacman_death', f'{pac}/pacman_death.svg', frames=12)
    # Unused in gameplay (the web build showed it on its asset-load error
    # screen) but listed in the reference's preload, so it is converted too.
    add('pacman_error', f'{pac}/pacman_error.svg', frames=12)

    # Ghosts: 2 frames each. Blinky additionally has Cruise Elroy variants.
    for direction in GHOST_DIRECTIONS:
        for emotion in ('', '_annoyed', '_angry'):
            key = f'blinky_{direction}{emotion}'
            add(key, f'{ghosts}/blinky/{key}.svg', frames=2)
        for name in ('pinky', 'inky', 'clyde'):
            add(f'{name}_{direction}', f'{ghosts}/{name}/{name}_{direction}.svg',
                frames=2)
        add(f'eyes_{direction}', f'{ghosts}/eyes_{direction}.svg', frames=2)
    for color in ('blue', 'white'):
        add(f'scared_{color}', f'{ghosts}/scared_{color}.svg', frames=2)

    # Maze.
    add('maze_blue', 'graphics/spriteSheets/maze/maze_blue.svg')

    # Pickups.
    add('pacdot', 'graphics/spriteSheets/pickups/pacdot.svg')
    add('powerPellet', 'graphics/spriteSheets/pickups/powerPellet.svg')
    for fruit in ('apple', 'bell', 'cherry', 'galaxian', 'key', 'melon',
                  'orange', 'strawberry'):
        add(fruit, f'graphics/spriteSheets/pickups/{fruit}.svg')

    # Text and point values.
    add('ready', 'graphics/spriteSheets/text/ready.svg')
    add('game_over', 'graphics/spriteSheets/text/game_over.svg')
    for points in (100, 200, 300, 400, 500, 700, 800, 1000, 1600, 2000, 3000,
                   5000):
        add(str(points), f'graphics/spriteSheets/text/{points}.svg')

    # Misc chrome.
    add('extra_life', 'graphics/extra_life.svg')

    return sprites


# Raster chrome that is resized rather than rasterized. The backdrop ships at
# 2000x2000, which would cost ~16MB resident for an image that is never drawn
# larger than the 224x296 logical surface.
RASTER_CHROME = {
    # key: (source, target width, target height, mode)
    'backdrop': ('graphics/backdrop.png', 224, 296, 'cover'),
    'pacman_logo': ('graphics/pacman_logo.png', 176, 42, 'fit'),
}

AUDIO_CLIPS = (
    'death', 'dot_1', 'dot_2', 'eat_ghost', 'extra_life', 'eyes', 'fruit',
    'game_start', 'pause', 'pause_beat', 'power_up', 'siren_1', 'siren_2',
    'siren_3',
)


def convert_svgs(source_root, sprites):
    """Rasterizes every SVG at its native size and records real dimensions."""
    import cairosvg

    manifest = {}

    for key, spec in sorted(sprites.items()):
        src = os.path.join(source_root, spec['source'])
        if not os.path.exists(src):
            raise SystemExit(f'missing source asset: {src}')

        out = os.path.join(SPRITE_OUT, f'{key}.png')
        # No output_width/height: the SVGs carry explicit pixel dimensions that
        # already match the render scale, so this is a 1:1 rasterization.
        cairosvg.svg2png(url=src, write_to=out)

        width, height = png_size(out)
        frames = spec['frames']
        if width % frames:
            raise SystemExit(
                f'{key}: width {width} is not divisible by {frames} frames',
            )

        manifest[key] = {
            'file': f'sprites/{key}.png',
            'width': width,
            'height': height,
            'frames': frames,
            'frame_width': width // frames,
        }
        print(f'  {key:24s} {width:4d}x{height:<4d} {frames:2d} frame(s)')

    return manifest


def png_size(path):
    """Reads a PNG's dimensions straight out of the IHDR chunk."""
    import struct

    with open(path, 'rb') as handle:
        header = handle.read(24)
    return struct.unpack('>II', header[16:24])


def convert_raster_chrome(source_root):
    """Downscales the two large PNGs using pygame (no Pillow dependency)."""
    os.environ.setdefault('SDL_VIDEODRIVER', 'dummy')
    import pygame

    pygame.init()
    pygame.display.set_mode((1, 1))

    manifest = {}

    for key, (rel, target_w, target_h, mode) in sorted(RASTER_CHROME.items()):
        src = os.path.join(source_root, rel)
        if not os.path.exists(src):
            raise SystemExit(f'missing source asset: {src}')

        image = pygame.image.load(src).convert_alpha()
        src_w, src_h = image.get_size()

        if mode == 'cover':
            # Scale so the image covers the target box, then centre-crop.
            factor = max(target_w / src_w, target_h / src_h)
            scaled = pygame.transform.smoothscale(
                image, (max(1, round(src_w * factor)),
                        max(1, round(src_h * factor))),
            )
            result = pygame.Surface((target_w, target_h), pygame.SRCALPHA)
            result.blit(
                scaled,
                ((target_w - scaled.get_width()) // 2,
                 (target_h - scaled.get_height()) // 2),
            )
        else:
            factor = min(target_w / src_w, target_h / src_h)
            result = pygame.transform.smoothscale(
                image, (max(1, round(src_w * factor)),
                        max(1, round(src_h * factor))),
            )

        out = os.path.join(SPRITE_OUT, f'{key}.png')
        pygame.image.save(result, out)

        width, height = result.get_size()
        manifest[key] = {
            'file': f'sprites/{key}.png',
            'width': width,
            'height': height,
            'frames': 1,
            'frame_width': width,
        }
        print(f'  {key:24s} {width:4d}x{height:<4d} (from {src_w}x{src_h})')

    pygame.quit()
    return manifest


def vorbis_encoder_args():
    """Picks the best available Ogg Vorbis encoder.

    Vorbis rather than Opus or MP3 because SDL_mixer decodes Vorbis with a
    bundled stb_vorbis on every build, so it cannot break on the Pi the way MP3
    can. It also stores an exact sample count, so the short ambience clips
    (siren_1 is 0.39s and loops continuously) loop without the encoder padding
    that would put an audible click in an MP3 loop.

    Homebrew's ffmpeg ships without libvorbis but does carry the native
    `vorbis` encoder, which is flagged experimental and so needs `-strict -2`.
    Output from either is a standard Ogg Vorbis file; libvorbis just encodes it
    better, so it wins when present.
    """
    encoders = subprocess.run(
        ['ffmpeg', '-hide_banner', '-loglevel', 'error', '-encoders'],
        capture_output=True, text=True, check=True,
    ).stdout

    if 'libvorbis' in encoders:
        return ['-c:a', 'libvorbis', '-qscale:a', '5'], 'libvorbis'
    if 'vorbis' in encoders:
        return ['-c:a', 'vorbis', '-strict', '-2', '-qscale:a', '6'], 'vorbis'
    raise SystemExit(
        'this ffmpeg has no Vorbis encoder. Install one (brew install ffmpeg, '
        'or a build with --enable-libvorbis).',
    )


def convert_audio(source_root):
    """Transcodes MP3 -> OGG Vorbis with ffmpeg."""
    if shutil.which('ffmpeg') is None:
        raise SystemExit(
            'ffmpeg not found. Install it (brew install ffmpeg) - it is needed '
            'only for this conversion step, never on the Pi.',
        )

    codec_args, encoder_name = vorbis_encoder_args()
    print(f'  (encoder: {encoder_name})')

    manifest = {}

    for clip in AUDIO_CLIPS:
        src = os.path.join(source_root, 'audio', f'{clip}.mp3')
        if not os.path.exists(src):
            raise SystemExit(f'missing source audio: {src}')

        out = os.path.join(AUDIO_OUT, f'{clip}.ogg')
        subprocess.run(
            # Resampled to match the mixer pre-init (44100Hz stereo) so
            # SDL_mixer never has to convert a clip at load time.
            ['ffmpeg', '-y', '-loglevel', 'error', '-i', src,
             '-ar', '44100', '-ac', '2', *codec_args, out],
            check=True,
        )
        manifest[clip] = f'audio/{clip}.ogg'
        size_kb = os.path.getsize(out) / 1024
        print(f'  {clip:24s} {size_kb:7.1f} KB')

    return manifest


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--source', default=DEFAULT_SOURCE,
                        help='path to node-version/public/app/style')
    parser.add_argument('--skip-audio', action='store_true')
    args = parser.parse_args()

    source_root = os.path.abspath(args.source)
    if not os.path.isdir(source_root):
        raise SystemExit(f'source directory not found: {source_root}')

    os.makedirs(SPRITE_OUT, exist_ok=True)
    os.makedirs(AUDIO_OUT, exist_ok=True)

    print(f'source: {source_root}')
    print('\nrasterizing SVGs:')
    sprites = convert_svgs(source_root, build_inventory())

    print('\nresizing raster chrome:')
    sprites.update(convert_raster_chrome(source_root))

    audio = {}
    if args.skip_audio:
        print('\nskipping audio conversion')
    else:
        print('\ntranscoding audio to OGG:')
        audio = convert_audio(source_root)

    manifest = {'sprites': sprites, 'audio': audio}
    with open(MANIFEST_OUT, 'w', encoding='utf-8') as handle:
        json.dump(manifest, handle, indent=2, sort_keys=True)
        handle.write('\n')

    print(f'\nwrote {len(sprites)} sprites and {len(audio)} clips')
    print(f'manifest: {MANIFEST_OUT}')
    return 0


if __name__ == '__main__':
    sys.exit(main())
