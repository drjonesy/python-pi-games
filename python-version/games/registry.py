"""Every game installed on the cabinet, in the order the picker lists them.

Adding a title is one line here plus a package beside this file. Nothing else
in the codebase needs to learn about it: the picker, the per-game high-score
file, the name-entry modal and the operator menu's reset all key off the
`GameSpec`. See `cabinet/game.py` for what a spec has to provide.

Imports are done inside `all_games()` rather than at module level so that
importing this module is free. A game package pulls in pygame, so at module
level a single stale entry would make the registry itself unimportable, and
`main.py` reads it before the display exists.
"""


def all_games():
    """The registered specs, in list order."""
    from .pacman.game import SPEC as PACMAN

    return (PACMAN,)


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
