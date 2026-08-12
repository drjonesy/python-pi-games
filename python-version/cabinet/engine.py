"""The fixed-timestep loop (engine.js:2516).

The simulation runs at a fixed 120 steps per second and rendering at 60. They
are **not** fused, and the simulation rate must not be lowered - see
`constants.SIM_HZ` and §3 of the rewrite instructions for why (the ghost-house
handoff windows are 0.2 tiles wide and an eaten ghost steps 0.18 tiles at 120Hz
but 0.37 at 60Hz, so at 60 it steps over them and never respawns).

Kept free of pygame so the stepping behaviour can be unit-tested.
"""

from .constants import MAX_STEPS_PER_FRAME, RENDER_FPS, SIM_DT_MS


class GameEngine:
    def __init__(self, update, render, sim_dt_ms=SIM_DT_MS,
                 max_steps_per_frame=MAX_STEPS_PER_FRAME):
        self.update = update
        self.render = render
        self.sim_dt_ms = sim_dt_ms
        self.max_steps_per_frame = max_steps_per_frame

        self.accumulator = 0.0
        self.steps_last_frame = 0
        self.total_steps = 0
        self.panics = 0

        self.fps = float(RENDER_FPS)
        self._frames_this_second = 0
        self._ms_since_fps_update = 0.0

    def tick(self, frame_ms):
        """Drains one frame's worth of simulation steps, then renders once.

        Returns the interpolation fraction handed to `render`: how far the
        drawn frame sits between the last two simulation steps.
        """
        self.accumulator += frame_ms

        steps = 0
        while (self.accumulator >= self.sim_dt_ms
               and steps < self.max_steps_per_frame):
            self.update(self.sim_dt_ms)
            self.accumulator -= self.sim_dt_ms
            steps += 1

        if steps == self.max_steps_per_frame:
            # A stall must not compound into a death spiral: drop the backlog
            # rather than trying to catch up on it (engine.js:2572 panic()).
            self.accumulator = 0.0
            self.panics += 1

        self.steps_last_frame = steps
        self.total_steps += steps

        interp = self.accumulator / self.sim_dt_ms
        self.track_fps(frame_ms)
        self.render(interp)

        return interp

    def track_fps(self, frame_ms):
        """Smoothed once-per-second FPS average (engine.js:2550)."""
        self._frames_this_second += 1
        self._ms_since_fps_update += frame_ms

        if self._ms_since_fps_update >= 1000:
            self.fps = (self._frames_this_second + self.fps) / 2
            self._frames_this_second = 0
            self._ms_since_fps_update = 0.0
