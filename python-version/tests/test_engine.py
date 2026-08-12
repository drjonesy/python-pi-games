"""The fixed-timestep loop (§3).

Simulate at 120Hz, render at 60, and never fuse the two.
"""

import pytest

from games.pacman.constants import MAX_STEPS_PER_FRAME, SIM_DT_MS
from cabinet.engine import GameEngine


def make_engine(**kwargs):
    steps = []
    renders = []
    engine = GameEngine(steps.append, renders.append, **kwargs)
    return engine, steps, renders


def test_every_step_is_exactly_one_fixed_timestep():
    """Speeds are per-millisecond and multiplied by this value, so it must be
    constant - a variable timestep would change the ghost-house step distance."""
    engine, steps, _ = make_engine()
    engine.tick(100)
    assert steps
    assert all(step == SIM_DT_MS for step in steps)


def test_sixty_fps_frames_yield_two_steps_each():
    """120Hz simulation, 60fps render: two steps per frame on average."""
    engine, steps, renders = make_engine()

    for _ in range(60):
        engine.tick(1000 / 60)

    assert len(renders) == 60
    # 1000ms of frames at 8.3333ms per step.
    assert len(steps) == pytest.approx(120, abs=1)


def test_render_happens_once_per_frame_regardless_of_step_count():
    engine, _, renders = make_engine()
    engine.tick(0)
    engine.tick(4)
    engine.tick(100)
    assert len(renders) == 3


def test_partial_time_accumulates_rather_than_being_lost():
    """A 5ms frame does not step; two of them do."""
    engine, steps, _ = make_engine()

    engine.tick(5)
    assert steps == []

    engine.tick(5)
    assert len(steps) == 1
    assert engine.accumulator == pytest.approx(10 - SIM_DT_MS)


def test_no_drift_over_a_simulated_minute():
    """Accumulated fractional time must not lose or gain steps."""
    engine, steps, _ = make_engine()

    for _ in range(3600):           # 60 seconds at 60fps
        engine.tick(1000 / 60)

    assert len(steps) == pytest.approx(7200, abs=2)


def test_interp_is_the_fraction_between_steps():
    engine, _, renders = make_engine()
    engine.tick(SIM_DT_MS + (SIM_DT_MS / 2))
    assert renders[-1] == pytest.approx(0.5, abs=1e-6)


def test_stall_is_clamped_and_backlog_dropped():
    """A long stall must not trigger a catch-up death spiral (engine.js:2572)."""
    engine, steps, _ = make_engine()

    engine.tick(10_000)             # a ten-second freeze

    assert len(steps) == MAX_STEPS_PER_FRAME
    assert engine.accumulator == 0.0
    assert engine.panics == 1


def test_recovers_normally_after_a_stall():
    engine, steps, _ = make_engine()
    engine.tick(10_000)
    steps.clear()

    engine.tick(1000 / 60)
    assert len(steps) == 2
    assert engine.panics == 1


def test_fps_tracking_settles_towards_the_real_rate():
    engine, _, _ = make_engine()
    for _ in range(600):            # 10 seconds at 60fps
        engine.tick(1000 / 60)
    assert engine.fps == pytest.approx(60, abs=2)
