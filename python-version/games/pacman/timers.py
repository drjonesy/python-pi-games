"""Pausable timers driven by simulation time (engine.js:3340).

The reference `Timer` wraps `setTimeout` and subtracts wall-clock elapsed time
on pause. A `pygame.time.set_timer` cannot express that, so these are ticked
from the fixed-step update instead. Driving them off simulation time rather
than the wall clock means they stay consistent with physics for free, and they
freeze automatically whenever the simulation does.
"""


class Timer:
    """A single pending callback.

    Two independent pause sources exist, matching the reference:

    * the player pausing the game, and
    * the game system pausing specific timers (eating a ghost freezes the
      flash, cycle, and fruit timers - engine.js:2369-2372).

    A system pause outranks a player resume: `resume()` without
    `system_resume` refuses to restart a timer the system stopped, which is
    what keeps the power-pellet flash frozen while a ghost is being eaten
    (engine.js:3368).
    """

    def __init__(self, manager, callback, delay):
        self.callback = callback
        self.remaining = delay
        self.paused = False
        self.paused_by_system = False
        self.cancelled = False
        self.fired = False
        self._manager = manager
        manager.add(self)      # mirrors the 'addTimer' dispatch

    def pause(self, system_pause=False):
        """engine.js:3352."""
        self.paused = True
        if system_pause:
            self.paused_by_system = True

    def resume(self, system_resume=False):
        """engine.js:3367."""
        if system_resume or not self.paused_by_system:
            self.paused_by_system = False
            self.paused = False

    def cancel(self):
        """Equivalent to clearTimeout + removeTimer (engine.js:2505)."""
        self.cancelled = True

    @property
    def active(self):
        """True while the timer still has a callback to fire.

        Stands in for the reference's `timerExists`, which tested for a live
        `timerId` (engine.js:2477). Guards like
        `remove_timer(self.fruit_timer)` rely on this being safe to ask about
        a timer that already fired.
        """
        return not (self.cancelled or self.fired)

    def tick(self, elapsed_ms):
        """Advances the timer, firing its callback once the delay elapses."""
        if self.paused or not self.active:
            return
        self.remaining -= elapsed_ms
        if self.remaining <= 0:
            # Marked fired *before* the callback runs: several callbacks
            # re-enter the manager (ghostCycle schedules its own successor),
            # and a re-entrant tick must not fire this one twice.
            self.fired = True
            self.callback()


class TimerManager:
    """Owns every live timer, mirroring GameCoordinator.activeTimers.

    The reference kept an `activeTimers` array plus `addTimer`/`removeTimer`
    helpers (engine.js:2468-2512); several code paths cancel timers by
    reference, so both halves are ported.
    """

    def __init__(self):
        self.active = []

    def add(self, timer):
        self.active.append(timer)

    def create(self, callback, delay):
        """Constructs a Timer registered with this manager - `new Timer(...)`."""
        return Timer(self, callback, delay)

    def remove(self, timer):
        """Cancels and forgets a timer. A `None` timer is a no-op.

        The reference guarded every call with `timerExists`, because paths like
        deathSequence unconditionally remove `this.fruitTimer` even when no
        fruit has ever spawned (engine.js:2081).
        """
        if timer is None:
            return
        timer.cancel()
        if timer in self.active:
            self.active.remove(timer)

    def pause_timer(self, timer):
        """engine.js:2485 - a system pause."""
        if timer is not None and timer.active:
            timer.pause(system_pause=True)

    def resume_timer(self, timer):
        """engine.js:2495 - a system resume."""
        if timer is not None and timer.active:
            timer.resume(system_resume=True)

    def pause_all(self):
        """Player pause (engine.js:2019)."""
        for timer in list(self.active):
            timer.pause()

    def resume_all(self):
        """Player resume - leaves system-paused timers alone (engine.js:2009)."""
        for timer in list(self.active):
            timer.resume()

    def clear(self):
        """Drops every timer, used when a game is reset (engine.js:1577)."""
        for timer in self.active:
            timer.cancel()
        self.active.clear()

    def tick(self, elapsed_ms):
        """Advances every live timer by one simulation step.

        Iterates a snapshot so callbacks may freely create timers (which then
        wait for the next step, matching setTimeout) or cancel others.
        """
        for timer in list(self.active):
            if timer.active:
                timer.tick(elapsed_ms)
        # Reap fired and cancelled timers - the 'removeTimer' dispatch that
        # the reference fired from inside its setTimeout callback.
        self.active = [timer for timer in self.active if timer.active]
