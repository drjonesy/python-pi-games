"""The ghost-house respawn regression. Non-negotiable (§3, §13).

An eaten ghost becomes a pair of eyes and travels home at `pacman_speed * 2`.
The handoff into the house matches on windows only 0.2 tiles wide
(Ghost.entering_ghost_house / entered_ghost_house). At the fixed 120Hz
simulation rate the eyes step ~0.18 tiles and land inside those windows; at 60Hz
they step ~0.37 tiles and jump clean over them, after which the ghost circles
the maze forever and never respawns.

These tests pin that down from all four corners, and also assert that lowering
the rate genuinely breaks it - otherwise the tests would keep passing if someone
"optimized" SIM_HZ down to 60.
"""

import pytest

from conftest import Harness, pixels_to_grid
from games.pacman.constants import EYE_SPEED_FACTOR, SIM_DT_MS

# The four open corners of the maze.
CORNERS = [
    pytest.param(1, 1, 'right', id='top-left'),
    pytest.param(26, 1, 'left', id='top-right'),
    pytest.param(1, 29, 'right', id='bottom-left'),
    pytest.param(26, 29, 'left', id='bottom-right'),
]

# 60 seconds of simulation is far more than the ~2s the trip actually takes.
MAX_STEPS = int(60_000 / SIM_DT_MS)


def run_eyes_home(start_x, start_y, direction, dt_ms=SIM_DT_MS,
                  max_steps=MAX_STEPS):
    """Sends an eaten Blinky home from a corner. Returns (respawned, steps)."""
    harness = Harness()
    ghost = harness.blinky

    # Keep Pacman far from the route so no collision interferes once the ghost
    # is restored mid-loop.
    harness.place_pacman(1, 1)

    harness.place_ghost(ghost, start_x, start_y, direction, mode='eyes')

    for step in range(max_steps):
        ghost.update(dt_ms)
        if 'restoreGhost' in harness.names_fired():
            return True, step

    return False, max_steps


@pytest.mark.parametrize('start_x, start_y, direction', CORNERS)
def test_eaten_ghost_respawns_from_every_corner(start_x, start_y, direction):
    """The whole point of the 120Hz simulation rate."""
    respawned, steps = run_eyes_home(start_x, start_y, direction)

    assert respawned, (
        f'eyes starting at ({start_x}, {start_y}) never re-entered the ghost '
        f'house within {MAX_STEPS} steps'
    )
    # Sanity check that it actually travelled rather than starting there.
    assert steps > 10


@pytest.mark.parametrize('start_x, start_y, direction', CORNERS)
def test_respawned_ghost_leaves_eyes_mode(start_x, start_y, direction):
    """After the handoff the ghost is a real ghost again, at the house centre."""
    harness = Harness()
    ghost = harness.blinky
    harness.place_pacman(1, 1)
    harness.place_ghost(ghost, start_x, start_y, direction, mode='eyes')

    for _ in range(MAX_STEPS):
        ghost.update(SIM_DT_MS)
        if 'restoreGhost' in harness.names_fired():
            break

    assert ghost.mode != 'eyes'
    assert ghost.mode == ghost.default_mode

    grid = pixels_to_grid(ghost.position)
    assert grid['x'] == pytest.approx(13.5)
    assert grid['y'] == pytest.approx(14)


def test_sixty_hertz_breaks_respawn():
    """Guards the guard: at 60Hz the eyes step over the handoff window.

    If this ever starts passing, the 0.2-tile windows have been widened into
    zone tests and the 120Hz requirement can be revisited (§3). Until then, a
    passing test here would mean the respawn tests above had stopped proving
    anything.
    """
    respawned, _ = run_eyes_home(
        1, 1, 'right', dt_ms=1000.0 / 60, max_steps=int(60_000 / (1000.0 / 60)),
    )
    assert not respawned, (
        'the ghost-house handoff now survives a 60Hz timestep - if the windows '
        'were widened deliberately, update this test and §3'
    )


def test_eye_step_distance_fits_inside_the_window():
    """The arithmetic behind the 120Hz requirement, stated explicitly.

    The handoff windows are 0.2 tiles wide, so a single step must be smaller
    than that or it can skip the window entirely.
    """
    harness = Harness()
    ghost = harness.blinky

    tiles_per_step = (ghost.eye_speed * SIM_DT_MS) / harness.pacman.scaled_tile_size

    assert ghost.eye_speed == pytest.approx(
        harness.pacman.velocity_per_ms * EYE_SPEED_FACTOR,
    )
    assert tiles_per_step == pytest.approx(0.18333, abs=1e-4)
    assert tiles_per_step < 0.2

    # And the 60Hz figure that motivates the whole constraint.
    assert (ghost.eye_speed * (1000.0 / 60)) / harness.pacman.scaled_tile_size > 0.2


def test_idle_ghost_leaves_the_house():
    """The reverse handoff: an idle ghost slides out and fires releaseGhost."""
    harness = Harness()
    ghost = harness.pinky
    harness.place_pacman(13, 23)

    ghost.moving = True
    ghost.end_idle_mode()
    assert ghost.idle_mode == 'leaving'

    for _ in range(MAX_STEPS):
        ghost.update(SIM_DT_MS)
        if 'releaseGhost' in harness.names_fired():
            break

    assert 'releaseGhost' in harness.names_fired()
    assert ghost.idle_mode is None

    grid = pixels_to_grid(ghost.position)
    assert grid['y'] == pytest.approx(11)
    assert ghost.direction == 'left'


@pytest.mark.parametrize('name', ['pinky', 'inky', 'clyde'])
def test_every_idle_ghost_can_leave(name):
    """Inky and Clyde start off-centre and must slide to the middle first."""
    harness = Harness()
    ghost = getattr(harness, name)
    harness.place_pacman(13, 23)

    ghost.moving = True
    ghost.end_idle_mode()

    for _ in range(MAX_STEPS):
        ghost.update(SIM_DT_MS)
        if 'releaseGhost' in harness.names_fired():
            break

    assert 'releaseGhost' in harness.names_fired(), (
        f'{name} never made it out of the ghost house'
    )
