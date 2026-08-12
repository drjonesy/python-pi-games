"""Per-machine preferences, in `data/settings.json`.

Two unrelated things live here - the sound toggle and the controller labelling -
written at different moments by different code. So a write *merges* into
whatever is already on disk rather than replacing the file. `SoundManager` used
to write `{"volume": ...}` wholesale, which was harmless while volume was the
only key and would have silently dropped the controller choice the first time
anyone hit mute.

Same rules as the leaderboard: a missing or corrupt file reads as empty rather
than raising, and writes go through a temp file and a rename so yanking the
power cannot leave half a file behind. The file is gitignored - it is machine
state, not project state.
"""

import json
import os

DATA_DIR = os.path.join(
    os.path.dirname(os.path.dirname(os.path.abspath(__file__))), 'data',
)
SETTINGS_FILE = os.path.join(DATA_DIR, 'settings.json')


def read(path=SETTINGS_FILE):
    """Everything on disk, or `{}` if there is nothing usable there."""
    if not path or not os.path.exists(path):
        return {}

    try:
        with open(path, encoding='utf-8') as handle:
            parsed = json.load(handle)
    except (OSError, ValueError):
        return {}

    return parsed if isinstance(parsed, dict) else {}


def update(values, path=SETTINGS_FILE):
    """Merges `values` into the file. False if it could not be written.

    A read-only filesystem is not an error the game should care about - the
    preference simply does not survive the session.
    """
    merged = read(path)
    merged.update(values)

    try:
        os.makedirs(os.path.dirname(path) or '.', exist_ok=True)
        tmp = f'{path}.tmp'
        with open(tmp, 'w', encoding='utf-8') as handle:
            json.dump(merged, handle)
            handle.write('\n')
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(tmp, path)
    except OSError:
        return False

    return True
