#!/usr/bin/env python3
"""Entry point: window setup, audio, and handing over to the cabinet shell.

Run with no arguments for fullscreen. `--windowed` is for desktop testing.

The machine boots into the game picker (`cabinet/ui/game_select.py`). Everything
after the window exists lives in `cabinet/app.py`; this file is the boot
sequence, and the order of it matters - SDL reads the audio driver from the
environment before pygame is imported, and the mixer must be pre-initialised
before `pygame.init()`.
"""

import argparse
import os
import sys

# Must be decided before pygame.init(): a small buffer keeps audio latency down.
# If audio underruns on the Pi, raise this to 1024 before touching anything
# else.
AUDIO_BUFFER = 512

# The game --data-file and --reset act on unless --game says otherwise. It is
# Pac-Man because that is the board that predates the cabinet having more than
# one game, and the one the Node version shares a file with.
DEFAULT_GAME = 'pacman'


def parse_args(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--windowed', action='store_true',
                        help='run in a window instead of fullscreen')
    parser.add_argument('--scale', type=int, default=3, metavar='N',
                        help='integer upscale for --windowed (default: 3)')
    parser.add_argument('--no-sound', action='store_true',
                        help='disable audio entirely')
    parser.add_argument('--fps', action='store_true',
                        help='show the FPS counter from the start')
    parser.add_argument('--game', default=None, metavar='ID',
                        help='boot straight into this game instead of the '
                             'picker, and the game --data-file and --reset '
                             f'act on (default: {DEFAULT_GAME}). '
                             'See --list-games.')
    parser.add_argument('--list-games', action='store_true',
                        help='list the installed games and their score files, '
                             'then exit')
    parser.add_argument('--data-file', default=None, metavar='PATH',
                        help='high-score file for the game named by --game. '
                             'Point this at ../node-version/data/data.json to '
                             'share one board with the Node version.')
    parser.add_argument('--reset', action='store_true',
                        help='clear one game\'s high scores and exit '
                             '(equivalent to npm run reset)')
    parser.add_argument('--reset-all', action='store_true',
                        help='clear every installed game\'s high scores '
                             'and exit')
    parser.add_argument('--audio-buffer', type=int, default=AUDIO_BUFFER,
                        metavar='N', help='mixer buffer size (default: 512)')
    parser.add_argument('--audio-driver', default=None, metavar='NAME',
                        help='force an SDL audio driver (pulseaudio, pipewire, '
                             'alsa...). Default: let SDL choose. Run '
                             'tools/audio_check.py to find one that works.')
    parser.add_argument('--audio-device', default=None, metavar='NAME',
                        help='force a specific output device by name, e.g. an '
                             'HDMI sink. Listed by tools/audio_check.py.')
    parser.add_argument('--pad-mapping', default=None, metavar='PATH',
                        help='gamepad / dance-pad binding table '
                             '(default: data/pad_mapping.json, written by '
                             'tools/gamepad_test.py --calibrate)')
    return parser.parse_args(argv)


def resolve_specs(args):
    """The games to install, and the board overrides to apply to them.

    Returns `(specs, data_files, error)`. `specs` is what the picker lists -
    every installed game, or just one under `--game`, which is how a cabinet
    dedicated to a single title skips the picker entirely.
    """
    from cabinet.leaderboard import Leaderboard
    from games import registry

    installed = registry.all_games()
    known = ', '.join(spec.id for spec in installed)

    target_id = args.game or DEFAULT_GAME
    target = registry.find(target_id)
    if target is None:
        return (), {}, f'unknown game: {target_id} (installed: {known})'

    data_files = {target.id: args.data_file} if args.data_file else {}

    if args.reset_all:
        for spec in installed:
            path = data_files.get(spec.id, spec.data_file)
            Leaderboard(path).reset()
            print(f'{spec.id}: high scores cleared ({path})')
        return (), {}, None

    if args.reset:
        path = data_files.get(target.id, target.data_file)
        Leaderboard(path).reset()
        print(f'{target.id}: high scores cleared ({path})')
        return (), {}, None

    specs = (target,) if args.game else installed
    return specs, data_files, None


def main(argv=None):
    args = parse_args(argv)

    if args.list_games:
        from games import registry
        for spec in registry.all_games():
            print(f'{spec.id:12} {spec.title:20} {spec.data_file}')
        # A folder that would not import has already printed why during the
        # scan. Naming it again here matters because "installed but broken"
        # otherwise looks exactly like "never copied across".
        for game_id, error in registry.errors():
            print(f'{game_id:12} {"(not loadable)":20} {error}',
                  file=sys.stderr)
        return 0

    specs, data_files, error = resolve_specs(args)
    if error:
        print(error, file=sys.stderr)
        return 2
    if not specs:
        # A --reset run: the boards are cleared and there is nothing to show.
        return 0

    # Must be set before pygame is imported: SDL reads it when it
    # initialises. On a Pi whose system audio goes to HDMI via PipeWire, SDL
    # may still pick raw ALSA - and raw ALSA is the headphone jack.
    if args.audio_driver:
        os.environ['SDL_AUDIODRIVER'] = args.audio_driver

    import pygame

    from cabinet import constants as C

    sound_enabled = not args.no_sound
    audio_error = None

    if sound_enabled:
        try:
            pygame.mixer.pre_init(
                frequency=44100, size=-16, channels=2,
                buffer=args.audio_buffer,
            )
        except pygame.error as error:
            audio_error = error
            sound_enabled = False

    pygame.init()
    if sound_enabled and not pygame.mixer.get_init():
        try:
            if args.audio_device:
                pygame.mixer.init(devicename=args.audio_device)
            else:
                pygame.mixer.init()
        except (pygame.error, TypeError) as error:
            # No audio device (headless, or a Pi with audio disabled) must not
            # stop the game from running. TypeError covers an older pygame
            # without the `devicename` parameter.
            audio_error = error
            sound_enabled = False

    # Printed, not swallowed. Every audio failure here used to be silent, which
    # left "no sound on the cabinet" with nothing to go on; run-game.sh tees
    # this to run-game.log.
    if not sound_enabled:
        reason = audio_error or ('--no-sound' if args.no_sound else 'unknown')
        print(f'audio: OFF ({reason})')
    else:
        try:
            driver = pygame.mixer.get_driver()
        except (AttributeError, pygame.error):
            driver = 'unknown'
        print(f'audio: driver={driver} mixer={pygame.mixer.get_init()}')

    pygame.display.set_caption('Arcade')
    pygame.mouse.set_visible(False)

    logical_size = (C.LOGICAL_WIDTH, C.LOGICAL_HEIGHT)

    if args.windowed:
        scale = max(1, args.scale)
        window = pygame.display.set_mode(
            (logical_size[0] * scale, logical_size[1] * scale),
        )
        logical = pygame.Surface(logical_size).convert()
    else:
        # SCALED lets SDL stretch the fixed logical surface to the display,
        # letterboxing as needed, so no asset ever needs re-rasterizing and
        # there is no extra blit in the hot path. vsync pairs with the 60fps
        # render target.
        try:
            window = pygame.display.set_mode(
                logical_size, pygame.FULLSCREEN | pygame.SCALED, vsync=1,
            )
        except pygame.error:
            window = pygame.display.set_mode(
                logical_size, pygame.FULLSCREEN | pygame.SCALED,
            )
        logical = window

    from cabinet.app import Cabinet
    from cabinet.controls import Controls
    from cabinet.font import BitmapFont
    from cabinet.gamepad import MAPPING_FILE, GamepadManager, load_mapping
    from cabinet.renderer import AssetStore
    from cabinet.sound import SoundManager

    # Empty at boot. Sprites and clips belong to a game, not to the machine,
    # and are read when that game is first played - so installing a title costs
    # nothing until someone chooses it (`cabinet/renderer.py`).
    assets = AssetStore()
    font = BitmapFont()

    sound_manager = SoundManager(enabled=sound_enabled).load()
    if sound_enabled:
        print(f'audio: volume={sound_manager.master_volume}, '
              f'{len(specs)} game(s) installed')

    pads = GamepadManager(
        load_mapping(args.pad_mapping or MAPPING_FILE),
    ).open_all()

    cabinet = Cabinet(
        window=window,
        surface=logical,
        assets=assets,
        font=font,
        sound_manager=sound_manager,
        # One shared object, mutated in place by the operator menu, so every
        # screen picks up a change of scheme on the next frame.
        controls=Controls(),
        pads=pads,
        specs=specs,
        data_files=data_files,
        show_fps=args.fps,
    )

    # A cabinet pinned to one game with --game has no list to come back to, so
    # it opens on that game's own title screen rather than on the picker.
    if args.game and len(specs) == 1:
        cabinet.play(specs[0])

    status = cabinet.run()
    pygame.quit()
    return status


if __name__ == '__main__':
    sys.exit(main())
