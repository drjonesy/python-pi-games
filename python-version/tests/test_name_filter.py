"""High-score names must not contain death or sexual words."""

import pytest

from cabinet.constants import DEFAULT_NAME
from cabinet.leaderboard import Leaderboard
from cabinet.name_filter import is_allowed
from cabinet.ui.score_entry import KEY_ROWS, ScoreEntry


@pytest.mark.parametrize('name', [
    'KILL', 'DIE', 'SEX', 'BOOB', 'kill',
    'KILLER', 'IKILLU', 'SEXY', 'BOOBS', 'UDIE', 'DEADMAN', 'MURDER',
    'K I L L', 'S E X', 'BO OB',       # spaced out
    'SKILLKILL', 'EDDIE DIE',          # an allowed word does not excuse the rest
    'TIT', 'CUM', 'MY TIT',            # whole-word-only terms
    'XXX', 'PORN', 'P O R N', 'XXXGAMER', 'PORNSTAR',
])
def test_blocked_names(name):
    assert not is_allowed(name)


@pytest.mark.parametrize('name', [
    '', 'RYAN', 'PACMAN', 'AAA',
    'EDDIE', 'FREDDIE', 'SADIE', 'DIEGO', 'SKILL', 'SKILLZ', 'KILLIAN',
    'GRAPE', 'PEACOCK', 'CANAL', 'SUSSEX', 'STABLE',
    'TITAN', 'CUCUMBER',
])
def test_allowed_names(name):
    assert is_allowed(name)


def test_leaderboard_stores_blocked_name_as_default(tmp_path):
    board = Leaderboard(str(tmp_path / 'data.json'))
    board.submit_score('KILLER', 500)
    assert board.get_top_scores()[0]['name'] == DEFAULT_NAME


class _Board:
    def __init__(self):
        self.saved = []

    def qualifies(self, score):
        return True

    def submit_score(self, name, score):
        self.saved.append((name, score))


def _confirm(entry):
    entry.row = len(KEY_ROWS) - 1
    entry.col = next(i for i, key in enumerate(KEY_ROWS[entry.row])
                     if key['type'] == 'confirm')
    entry.select()


def test_score_entry_refuses_blocked_name_and_stays_open():
    board = _Board()
    entry = ScoreEntry(None, None, board)
    assert entry.try_open(100)
    entry.name = 'SEX'

    _confirm(entry)

    assert entry.open
    assert entry.rejected
    assert entry.name == ''
    assert board.saved == []

    entry.activate_key({'label': 'A', 'type': 'char'})
    assert not entry.rejected

    entry.name = 'RYAN'
    _confirm(entry)
    assert not entry.open
    assert board.saved == [('RYAN', 100)]
