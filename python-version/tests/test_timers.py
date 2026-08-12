"""Pausable timers (engine.js:3340).

The important property is that a *system* pause outranks a *player* resume -
that is what keeps the power-pellet flash frozen while a ghost is being eaten
(engine.js:2369-2372).
"""

from games.pacman.timers import TimerManager


def advance(manager, ms, dt=8.3333333):
    steps = int(round(ms / dt))
    for _ in range(steps):
        manager.tick(dt)


def test_timer_fires_after_its_delay():
    manager = TimerManager()
    fired = []
    manager.create(lambda: fired.append(True), 1000)

    advance(manager, 990)
    assert fired == []

    advance(manager, 20)
    assert fired == [True]


def test_timer_fires_only_once():
    manager = TimerManager()
    fired = []
    manager.create(lambda: fired.append(True), 100)

    advance(manager, 1000)
    assert fired == [True]


def test_fired_timers_are_reaped():
    manager = TimerManager()
    manager.create(lambda: None, 100)
    advance(manager, 200)
    assert manager.active == []


def test_cancelled_timer_never_fires():
    manager = TimerManager()
    fired = []
    timer = manager.create(lambda: fired.append(True), 100)
    manager.remove(timer)

    advance(manager, 500)
    assert fired == []
    assert manager.active == []


def test_removing_none_is_a_no_op():
    """deathSequence removes this.fruitTimer even when no fruit ever spawned."""
    manager = TimerManager()
    manager.remove(None)


def test_paused_timer_does_not_advance():
    manager = TimerManager()
    fired = []
    timer = manager.create(lambda: fired.append(True), 100)

    timer.pause()
    advance(manager, 500)
    assert fired == []

    timer.resume()
    advance(manager, 200)
    assert fired == [True]


def test_pause_preserves_remaining_time():
    manager = TimerManager()
    fired = []
    timer = manager.create(lambda: fired.append(True), 1000)

    advance(manager, 600)
    timer.pause()
    advance(manager, 5000)
    timer.resume()

    advance(manager, 300)
    assert fired == []
    advance(manager, 150)
    assert fired == [True]


def test_system_pause_survives_a_player_resume():
    """engine.js:3368 - `if (systemResume || !this.pausedBySystem)`."""
    manager = TimerManager()
    fired = []
    timer = manager.create(lambda: fired.append(True), 100)

    manager.pause_timer(timer)          # system pause, e.g. eating a ghost
    manager.resume_all()                # player un-pauses the game

    advance(manager, 500)
    assert fired == [], 'a system-paused timer must stay paused'

    manager.resume_timer(timer)         # system releases it
    advance(manager, 200)
    assert fired == [True]


def test_player_pause_resumes_normally():
    manager = TimerManager()
    fired = []
    manager.create(lambda: fired.append(True), 100)

    manager.pause_all()
    advance(manager, 500)
    assert fired == []

    manager.resume_all()
    advance(manager, 200)
    assert fired == [True]


def test_callback_can_create_another_timer():
    """ghostCycle schedules its own successor from inside its callback."""
    manager = TimerManager()
    fired = []

    def chain(index):
        fired.append(index)
        if index < 3:
            manager.create(lambda: chain(index + 1), 100)

    manager.create(lambda: chain(0), 100)
    advance(manager, 1000)
    assert fired == [0, 1, 2, 3]


def test_callback_can_cancel_another_timer():
    manager = TimerManager()
    fired = []
    victim = manager.create(lambda: fired.append('victim'), 200)
    manager.create(lambda: manager.remove(victim), 100)

    advance(manager, 500)
    assert fired == []


def test_clear_drops_everything():
    manager = TimerManager()
    fired = []
    manager.create(lambda: fired.append(True), 100)
    manager.clear()

    advance(manager, 500)
    assert fired == []
    assert manager.active == []


def test_active_flag_tracks_lifecycle():
    manager = TimerManager()
    timer = manager.create(lambda: None, 100)
    assert timer.active is True

    advance(manager, 200)
    assert timer.active is False

    # Safe to interrogate and pause a spent timer, which several paths do.
    manager.pause_timer(timer)
    manager.resume_timer(timer)
    manager.remove(timer)
