"""A tiny internal pub/sub, replacing the browser's window.dispatchEvent.

The reference engine wired its subsystems together with `CustomEvent`s on
`window` (engine.js:1932-1942). Those are gone, but the event *names* are kept
verbatim so the reference stays greppable: searching for `eatGhost` finds the
same handful of call sites in both codebases.
"""


class EventBus:
    def __init__(self):
        self._handlers = {}

    def on(self, name, handler):
        """Registers a handler. Mirrors registerEventListeners (engine.js:1932)."""
        self._handlers.setdefault(name, []).append(handler)

    def emit(self, name, **detail):
        """Fires every handler for `name`, passing the event's `detail` as kwargs.

        Handlers are copied before iterating because several of them (notably
        deathSequence) register or cancel timers while running.
        """
        for handler in list(self._handlers.get(name, ())):
            handler(**detail)
