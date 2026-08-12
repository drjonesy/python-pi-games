"""High scores on disk - a direct port of node-version/server/leaderboard.js.

There is no web server here; the cabinet reads and writes the files itself.

**One board per game.** Every game on the machine gets its own file, its own
top three and its own reset, and none of them can see another's. Pac-Man keeps
the original ``data/data.json`` so a single file can still be shared with the
Node version; every other game gets ``data/scores/<id>.json``. See
`data_file_for`.

The on-disk format is the Node version's, byte for byte::

    { "scores": [{ "name": "RYAN", "score": 4200 }] }

Two behaviours matter more on a Pi than they did in a browser:

* A missing **or corrupt** file is an empty leaderboard, never an error. The
  game must always be playable.
* Writes go to a temp file and are then renamed over the real one, so a crash
  mid-write can never leave a half-written ``data.json`` behind. Yanking the
  power is the normal way to turn a Pi off.
"""

import json
import math
import os

from .constants import DEFAULT_NAME, MAX_ENTRIES, MAX_NAME_LENGTH

DATA_DIR = os.path.join(
    os.path.dirname(os.path.dirname(os.path.abspath(__file__))), 'data',
)
SCORES_DIR = os.path.join(DATA_DIR, 'scores')

# Pac-Man's board, and the only one that is not under `scores/`. It predates
# the cabinet having more than one game and the Node version writes to the same
# path, so moving it would break that interop for nothing.
DATA_FILE = os.path.join(DATA_DIR, 'data.json')

LEGACY_DATA_FILES = {'pacman': DATA_FILE}


def data_file_for(game_id, data_dir=None):
    """Where `game_id` keeps its top three.

    `game_id` is used as a filename, so it is restricted to the characters a
    package name may contain. A registry entry is written by hand, but this is
    the one place a typo in one would escape the `data/` directory.
    """
    if data_dir is None and game_id in LEGACY_DATA_FILES:
        return LEGACY_DATA_FILES[game_id]

    safe = ''.join(ch for ch in str(game_id).lower() if ch.isalnum() or ch == '_')
    if not safe:
        raise ValueError(f'unusable game id: {game_id!r}')

    return os.path.join(data_dir or SCORES_DIR, f'{safe}.json')


def _to_number(value):
    """`Number(value)` semantics: a non-numeric value becomes NaN, not an error."""
    if isinstance(value, bool) or value is None:
        return math.nan
    if isinstance(value, (int, float)):
        return float(value)
    if isinstance(value, str):
        try:
            return float(value.strip() or 'nan')
        except ValueError:
            return math.nan
    return math.nan


def _emit_number(value):
    """Writes 4200 rather than 4200.0 so the JSON matches the Node version."""
    return int(value) if float(value).is_integer() else value


class Leaderboard:
    def __init__(self, data_file=DATA_FILE):
        self.data_file = data_file

    # -- reading -------------------------------------------------------------

    def read_scores(self):
        """A sanitised, already-sorted list of entries (leaderboard.js:22).

        Accepts either a bare array or ``{"scores": [...]}``.
        """
        if not os.path.exists(self.data_file):
            return []

        try:
            with open(self.data_file, encoding='utf-8') as handle:
                parsed = json.load(handle)
        except (OSError, ValueError):
            return []

        if isinstance(parsed, list):
            entries = parsed
        elif isinstance(parsed, dict):
            entries = parsed.get('scores')
        else:
            entries = None

        if not isinstance(entries, list):
            return []

        cleaned = []
        for entry in entries:
            if not isinstance(entry, dict):
                # `entry?.name` on a non-object yields undefined -> '' and NaN,
                # which the score filter then drops.
                continue
            name = str(entry.get('name') if entry.get('name') is not None else '')
            cleaned.append({
                'name': name[:MAX_NAME_LENGTH],
                'score': _to_number(entry.get('score')),
            })

        cleaned = [
            entry for entry in cleaned
            if math.isfinite(entry['score']) and entry['score'] > 0
        ]
        # Python's sort is stable, matching the JS behaviour that keeps an
        # existing holder ahead of a newcomer with the same score.
        cleaned.sort(key=lambda entry: entry['score'], reverse=True)

        return cleaned[:MAX_ENTRIES]

    def get_top_scores(self):
        """leaderboard.js:60."""
        return self.read_scores()

    def high_score(self):
        """First place, or 0 on an empty board.

        The HUD's HIGH SCORE readout mirrors this (engine.js:1264-1272) and must
        be refreshed whenever a new name is saved.
        """
        scores = self.read_scores()
        return int(scores[0]['score']) if scores else 0

    def qualifies(self, score):
        """True when `score` would earn a place (leaderboard.js:70)."""
        score = _to_number(score)
        if not math.isfinite(score) or score <= 0:
            return False

        top = self.read_scores()
        if len(top) < MAX_ENTRIES:
            return True

        return score > top[-1]['score']

    # -- writing -------------------------------------------------------------

    def write_scores(self, scores):
        """Atomically replaces the file (leaderboard.js:49)."""
        os.makedirs(os.path.dirname(self.data_file) or '.', exist_ok=True)
        tmp = f'{self.data_file}.tmp'

        payload = {
            'scores': [
                {'name': entry['name'], 'score': _emit_number(entry['score'])}
                for entry in scores
            ],
        }

        with open(tmp, 'w', encoding='utf-8') as handle:
            json.dump(payload, handle, indent=2)
            handle.write('\n')
            # Flushed and synced before the rename so the replacement is
            # durable, not just atomic.
            handle.flush()
            os.fsync(handle.fileno())

        os.replace(tmp, self.data_file)   # atomic on POSIX

    def submit_score(self, name, score):
        """Adds a score and keeps only the top three (leaderboard.js:88).

        This is how a new high score "replaces" the previous 2nd/3rd place
        holder. Ties keep the existing holder ahead of the newcomer.
        """
        clean_name = str(name if name is not None else '').strip()[:MAX_NAME_LENGTH]
        if not clean_name:
            clean_name = DEFAULT_NAME

        clean_score = _to_number(score)
        if not math.isfinite(clean_score) or clean_score <= 0:
            return self.read_scores()

        updated = self.read_scores() + [
            {'name': clean_name, 'score': clean_score},
        ]
        updated.sort(key=lambda entry: entry['score'], reverse=True)
        updated = updated[:MAX_ENTRIES]

        self.write_scores(updated)
        return updated

    def reset(self):
        """Equivalent to `npm run reset` (server/reset-scores.js)."""
        self.write_scores([])
        return []
