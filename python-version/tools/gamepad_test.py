#!/usr/bin/env python3
"""Identify a USB pad and write its binding table. Run this on the Pi.

A DDR dance mat, a generic gamepad and an arcade encoder all report their
controls differently, and two mats of the same model can disagree - so rather
than guessing button numbers, this asks you to step on each panel and records
what the pad actually sent.

Three modes::

    python tools/gamepad_test.py --list        # what SDL can see
    python tools/gamepad_test.py               # live event monitor
    python tools/gamepad_test.py --calibrate   # step on each panel; writes the file

``--calibrate`` writes ``data/pad_mapping.json``, which the game loads at
startup. Nothing else needs changing.

If ``--list`` shows no devices at all, the problem is below SDL - see the
"Dance pad / gamepad" section of the README for the Linux side (``lsusb``,
``/dev/input/js0``, the ``input`` group).
"""

import argparse
import os
import sys

REPO_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, REPO_ROOT)

import pygame                                            # noqa: E402

from cabinet.gamepad import (                             # noqa: E402
    ACTIONS, DEFAULT_DEADZONE, MAPPING_FILE, binding_key, describe_binding,
    key_binding, load_mapping, save_mapping,
)

# What to ask for, in the order a dance mat's panels are easiest to reach.
# Every action is optional - the pad is unlikely to have ten controls you want
# ten of, and skipping one just leaves it keyboard-only.
PROMPTS = (
    ('up', 'the UP arrow panel'),
    ('down', 'the DOWN arrow panel'),
    ('left', 'the LEFT arrow panel'),
    ('right', 'the RIGHT arrow panel'),
    ('select', 'START  (starts a game, confirms a letter)'),
    ('delete', 'X      (deletes a letter during name entry)'),
    ('pause', 'SELECT (pauses during play)'),
    # Skip this one on a dance mat. There is no panel left that is safe to put
    # it on: the shapes are corners a moving foot clips, and the arrows are the
    # controls. It was on SQUARE until that turned out to mute mid-run.
    ('mute', 'SQUARE (toggles sound) - SKIP THIS ON A DANCE MAT'),
)

# A mat's panel can bounce, and many report one press on both a hat and an
# axis. So a press is not one event: everything seen within this window of the
# first event is recorded for that action.
CAPTURE_WINDOW_MS = 500
# Then wait for the pad to go quiet before prompting again, so the release
# does not get read as the next answer.
SETTLE_MS = 400


def init_pygame():
    """A real window if there is a display, a dummy one otherwise.

    Keyboard events need a focused window, so over SSH (no display) a mat that
    enumerates as an HID keyboard cannot be calibrated - joystick events still
    arrive fine. Run it on the Pi's own screen if `--list` finds no joystick.
    """
    windowed = True
    try:
        pygame.display.init()
        pygame.display.set_mode((480, 160))
        pygame.display.set_caption('Pac-Man - pad setup')
    except pygame.error:
        os.environ['SDL_VIDEODRIVER'] = 'dummy'
        pygame.display.quit()
        try:
            pygame.display.init()
            pygame.display.set_mode((1, 1))
        except pygame.error:
            pass
        windowed = False

    pygame.joystick.init()
    return windowed


def open_joysticks():
    # Constructing a Joystick opens it; the explicit init() has been deprecated
    # since pygame-ce 2.4.
    return [pygame.joystick.Joystick(index)
            for index in range(pygame.joystick.get_count())]


def list_devices(sticks):
    if not sticks:
        print('No joystick devices found.\n')
        print('On Linux, check in this order:')
        print('  lsusb                       # is the pad enumerating at all?')
        print('  ls -l /dev/input/js* /dev/input/event*')
        print('  groups                      # your user needs to be in `input`')
        print('  sudo evtest                 # does the kernel see the panels?')
        print('\nIf evtest shows key presses rather than a joystick, the mat is')
        print("an HID keyboard - run --calibrate on the Pi's own screen and it")
        print('will record key bindings instead.')
        return

    print(f'{len(sticks)} device(s):\n')
    for stick in sticks:
        print(f'  [{stick.get_instance_id()}] {stick.get_name()}')
        print(f'      guid    {stick.get_guid()}')
        print(f'      axes    {stick.get_numaxes()}')
        print(f'      hats    {stick.get_numhats()}')
        print(f'      buttons {stick.get_numbuttons()}')
        print()


def event_binding(event, deadzone):
    """The binding an event represents, or None if it is not a press.

    Axis events fire continuously; only a crossing out of the deadzone counts,
    and the return to centre is not a press at all.
    """
    if event.type == pygame.JOYBUTTONDOWN:
        return {'type': 'button', 'button': event.button}

    if event.type == pygame.JOYHATMOTION:
        x, y = event.value
        if x:
            return {'type': 'hat', 'hat': event.hat, 'axis': 'x', 'value': x}
        if y:
            return {'type': 'hat', 'hat': event.hat, 'axis': 'y', 'value': y}
        return None

    if event.type == pygame.JOYAXISMOTION:
        if event.value < -deadzone:
            return {'type': 'axis', 'axis': event.axis, 'value': -1}
        if event.value > deadzone:
            return {'type': 'axis', 'axis': event.axis, 'value': 1}
        return None

    if event.type == pygame.KEYDOWN:
        return key_binding(event.key)

    return None


def draw_banner(windowed, lines):
    """Mirrors the console prompt into the window, since a dance mat is played
    standing up and nowhere near the terminal."""
    if not windowed:
        return
    surface = pygame.display.get_surface()
    if surface is None:
        return
    surface.fill((0, 0, 0))
    font = pygame.font.Font(None, 26)
    for index, line in enumerate(lines[:4]):
        surface.blit(font.render(line, True, (255, 255, 0)), (16, 20 + index * 32))
    pygame.display.flip()


def monitor(sticks, windowed, deadzone):
    print('Live event monitor. Step on a panel; Ctrl-C to stop.')
    if windowed:
        print('(Key presses only register while the pad-setup window is focused.)')
    print()
    draw_banner(windowed, ['Step on a panel.', 'Ctrl-C in the terminal to stop.'])

    clock = pygame.time.Clock()
    while True:
        for event in pygame.event.get():
            if event.type == pygame.QUIT:
                return
            if event.type == pygame.KEYDOWN and event.key == pygame.K_ESCAPE:
                return
            if event.type == pygame.JOYDEVICEADDED:
                stick = pygame.joystick.Joystick(event.device_index)
                sticks.append(stick)
                print(f'+ connected: {stick.get_name()}')
                continue
            if event.type == pygame.JOYDEVICEREMOVED:
                print(f'- disconnected: instance {event.instance_id}')
                continue

            binding = event_binding(event, deadzone)
            if binding is not None:
                print(f'  {describe_binding(binding):<16} {binding}')
            elif event.type == pygame.JOYAXISMOTION and abs(event.value) > 0.05:
                # Shown but not bindable, so a drifting analogue stick is
                # visible rather than mysterious.
                print(f'  axis {event.axis} at {event.value:+.2f} (below deadzone)')

        clock.tick(60)


def capture(label, deadzone, taken, windowed):
    """Blocks until the pad is pressed; returns the bindings it produced.

    Returns None when the action is skipped, which the caller leaves unbound.
    """
    print(f'\n  Step on / press: {label}')
    print('    (ESC on a keyboard, or 30s of nothing, skips it)')
    draw_banner(windowed, [
        f'Press:  {label}',
        'ESC to skip this one.',
    ])

    pygame.event.clear()
    found = {}
    deadline = None
    clock = pygame.time.Clock()
    elapsed = 0

    while True:
        for event in pygame.event.get():
            if event.type == pygame.QUIT:
                raise KeyboardInterrupt
            if event.type == pygame.KEYDOWN and event.key == pygame.K_ESCAPE:
                print('    skipped')
                return None

            binding = event_binding(event, deadzone)
            if binding is None:
                continue

            key = binding_key(binding)
            if key is None or key in found:
                continue
            if key in taken:
                # Two actions on one control would make the pad ambiguous;
                # usually it means a panel is still bouncing from the last one.
                print(f'    ignoring {describe_binding(binding)} - already '
                      f'bound to {taken[key]}')
                continue

            found[key] = binding
            print(f'    got {describe_binding(binding)}')
            if deadline is None:
                deadline = CAPTURE_WINDOW_MS

        if deadline is not None:
            deadline -= clock.get_time()
            if deadline <= 0:
                break

        elapsed += clock.get_time()
        if not found and elapsed > 30_000:
            print('    nothing received for 30s - skipped')
            return None

        clock.tick(60)

    settle(clock)
    return list(found.values())


def settle(clock):
    """Drains events until the pad has been quiet for SETTLE_MS."""
    quiet = 0
    while quiet < SETTLE_MS:
        if pygame.event.get():
            quiet = 0
        else:
            quiet += clock.get_time()
        clock.tick(60)


def calibrate(sticks, windowed, args):
    if not sticks and windowed:
        print('No joystick found. Continuing anyway - if the mat enumerates as')
        print('a keyboard, its panels will be recorded as key bindings.\n')
    elif not sticks:
        print('No joystick found, and no display for keyboard input.')
        print('Run --list first.')
        return 1

    print('Calibrating. Each prompt waits for you to press that control.')
    print('Press ESC (keyboard) or wait 30s to leave one unbound.\n')
    print('A dance mat often reports one panel on both a hat and an axis;')
    print('both get recorded, which is correct.')

    bindings = {}
    taken = {}
    for action, label in PROMPTS:
        captured = capture(label, args.deadzone, taken, windowed)
        if not captured:
            continue
        bindings[action] = captured
        for binding in captured:
            taken[binding_key(binding)] = action

    if not bindings:
        print('\nNothing was captured; leaving the existing mapping alone.')
        return 1

    mapping = {
        'version': 1,
        'device': sticks[0].get_name() if args.lock_device and sticks else None,
        'deadzone': args.deadzone,
        'bindings': {
            action: bindings[action] for action in ACTIONS if action in bindings
        },
    }

    draw_banner(windowed, ['Done.', 'Mapping saved.'])
    print('\n' + '-' * 60)
    for action in ACTIONS:
        entries = mapping['bindings'].get(action)
        label = ', '.join(describe_binding(b) for b in entries) if entries else '-'
        print(f'  {action:<8} {label}')
    print('-' * 60)

    save_mapping(mapping, args.output)
    print(f'\nWritten: {args.output}')
    print('Start the game normally; it loads this file at launch.')
    print('Re-run with --calibrate any time to redo it.')
    return 0


def parse_args(argv=None):
    parser = argparse.ArgumentParser(description=__doc__,
                                     formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument('--list', action='store_true',
                        help='print the pads SDL can see, then exit')
    parser.add_argument('--calibrate', action='store_true',
                        help='step through each control and write the mapping')
    parser.add_argument('--output', default=MAPPING_FILE, metavar='PATH',
                        help=f'where to write the mapping (default: {MAPPING_FILE})')
    parser.add_argument('--deadzone', type=float, default=None, metavar='F',
                        help='axis threshold, 0-1 (default: %.2f)' % DEFAULT_DEADZONE)
    parser.add_argument('--lock-device', action='store_true',
                        help='bind the mapping to this pad\'s name, so other '
                             'controllers are ignored')
    args = parser.parse_args(argv)

    if args.deadzone is None:
        # An existing mapping's deadzone is the better default when redoing
        # only part of a calibration.
        args.deadzone = load_mapping(args.output).get('deadzone', DEFAULT_DEADZONE)
    args.deadzone = min(max(float(args.deadzone), 0.05), 0.95)
    return args


def main(argv=None):
    args = parse_args(argv)

    pygame.init()
    windowed = init_pygame()
    sticks = open_joysticks()

    try:
        if args.list:
            list_devices(sticks)
            return 0

        list_devices(sticks)
        if args.calibrate:
            return calibrate(sticks, windowed, args)

        monitor(sticks, windowed, args.deadzone)
        return 0
    except KeyboardInterrupt:
        print('\nstopped')
        return 0
    finally:
        pygame.quit()


if __name__ == '__main__':
    sys.exit(main())
