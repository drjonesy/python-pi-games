"""Every game installed on the cabinet, found by looking rather than by list.

**Adding a title is dropping a folder in beside this file.** A directory here
is a game if it is an importable package whose `game` module (or the package
itself) exposes a `SPEC`. Nothing else in the codebase learns its name: the
picker, the per-game high-score file, its sprite pack, its audio namespace, the
name-entry modal and the operator menu's reset all key off that `GameSpec`. See
`cabinet/game.py` for what a spec has to provide.

Two rules make an unattended machine survivable, and both are about the fact
that a cabinet with no keyboard cannot be recovered from a traceback:

* **A game that will not import is skipped, not fatal.** One title with a typo
  in it must cost that title and nothing else - the rest of the machine still
  boots and still plays. What went wrong is printed, since `run-game.sh` tees
  the log.
* **A game is imported at most once**, and only when the registry is first
  asked. Importing a game package pulls in pygame, and `main.py` reads the
  registry before the display exists; a game that touched the display at import
  time would fail here rather than mysteriously later.

The scan result is cached for the life of the process. A cabinet does not gain
games while it is running, and rescanning would re-print every skip.
"""

import importlib
import os
import pkgutil

PACKAGE_DIR = os.path.dirname(os.path.abspath(__file__))

# Folders that are here for the packaging, not because they are games.
IGNORED = {'__pycache__'}

_cache = None
_errors = None


def _candidate_ids(package_dir):
    """Importable sub-packages of `games/`, alphabetically.

    `pkgutil` rather than `os.listdir` so the answer matches what Python will
    actually import - a directory with no `__init__.py` is not a package and is
    not a game, however much it looks like one.
    """
    found = [
        module.name
        for module in pkgutil.iter_modules([package_dir])
        if module.ispkg and not module.name.startswith('_')
        and module.name not in IGNORED
    ]
    return sorted(found)


def _load_spec(game_id):
    """The `SPEC` from `games/<id>/game.py`, or from the package itself.

    Both are supported because a small game has no reason to be split in two:
    `game.py` is the convention and what Pac-Man does, but a single-file title
    may put everything in its `__init__.py`.

    Which of the two to import is decided by whether the file is *there*, not
    by importing one and catching the failure: a `game.py` whose own imports are
    broken raises ImportError too, and falling back on that would report the
    package's missing SPEC instead of the real cause.
    """
    has_game_module = os.path.exists(
        os.path.join(PACKAGE_DIR, game_id, 'game.py'),
    )
    module = importlib.import_module(
        f'{__package__}.{game_id}.game' if has_game_module
        else f'{__package__}.{game_id}',
    )

    spec = getattr(module, 'SPEC', None)
    if spec is None:
        raise AttributeError(
            f'no SPEC in games/{game_id}/ - see cabinet/game.py',
        )
    if getattr(spec, 'id', None) != game_id:
        # The id is the folder name, the score file's name and what `--game`
        # takes. Letting the two disagree would put `games/runner/`'s scores in
        # `data/scores/something-else.json`, which is only ever a typo.
        raise ValueError(
            f'games/{game_id}/ declares id {spec.id!r}; they must match',
        )
    return spec


def _scan(package_dir=None):
    specs, errors = [], []

    for game_id in _candidate_ids(package_dir or PACKAGE_DIR):
        try:
            specs.append(_load_spec(game_id))
        except Exception as error:                 # noqa: BLE001 - see below
            # Deliberately every exception. This is the boundary between the
            # cabinet and code it did not write, and a game is allowed to fail
            # in any way it likes without taking the machine with it.
            errors.append((game_id, error))
            print(f'games: skipped {game_id!r} ({type(error).__name__}: {error})')

    specs.sort(key=lambda spec: spec.sort_key())
    return tuple(specs), tuple(errors)


def all_games(refresh=False):
    """The installed specs, in the order the picker lists them."""
    global _cache, _errors
    if _cache is None or refresh:
        _cache, _errors = _scan()
    return _cache


def errors(refresh=False):
    """`(game_id, exception)` for every folder that would not load.

    Kept rather than discarded so `--list-games` can report a title that is
    installed but broken, which otherwise looks identical to one that was never
    copied across.
    """
    all_games(refresh=refresh)
    return _errors


def find(game_id):
    """The spec with this id, or None.

    Used by `--game` on the command line to boot straight into one title, which
    is how a single-game cabinet skips the picker.
    """
    for spec in all_games():
        if spec.id == game_id:
            return spec
    return None


def ids():
    return tuple(spec.id for spec in all_games())
