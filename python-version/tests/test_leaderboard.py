"""Leaderboard behaviour, ported from server/leaderboard.js.

The format has to stay interchangeable with the Node version, and the file has
to survive being corrupted or half-written - on a Pi, pulling the power is the
normal way to turn the machine off.
"""

import json
import os

import pytest

from cabinet.leaderboard import Leaderboard


@pytest.fixture
def board(tmp_path):
    return Leaderboard(str(tmp_path / 'data.json'))


def write_raw(board, text):
    with open(board.data_file, 'w', encoding='utf-8') as handle:
        handle.write(text)


def test_missing_file_is_an_empty_board(board):
    assert board.get_top_scores() == []
    assert board.high_score() == 0


def test_corrupt_file_is_an_empty_board(board):
    write_raw(board, '{"scores": [ this is not json')
    assert board.get_top_scores() == []
    assert board.high_score() == 0


@pytest.mark.parametrize('payload', [
    'null', '42', '"a string"', '{}', '{"scores": "nope"}', '[]',
])
def test_unexpected_shapes_are_empty_boards(board, payload):
    write_raw(board, payload)
    assert board.get_top_scores() == []


def test_bare_array_format_is_accepted(board):
    """leaderboard.js:27 accepts either shape."""
    write_raw(board, json.dumps([{'name': 'RYAN', 'score': 4200}]))
    assert board.get_top_scores() == [{'name': 'RYAN', 'score': 4200.0}]


def test_wrapped_format_is_accepted(board):
    write_raw(board, json.dumps({'scores': [{'name': 'RYAN', 'score': 4200}]}))
    assert board.high_score() == 4200


def test_scores_are_sorted_descending_and_capped_at_three(board):
    board.write_scores([
        {'name': 'A', 'score': 100},
        {'name': 'B', 'score': 900},
        {'name': 'C', 'score': 500},
        {'name': 'D', 'score': 700},
    ])
    assert [entry['name'] for entry in board.get_top_scores()] == ['B', 'D', 'C']


def test_non_positive_and_non_finite_scores_are_dropped(board):
    write_raw(board, json.dumps({'scores': [
        {'name': 'ZERO', 'score': 0},
        {'name': 'NEG', 'score': -5},
        {'name': 'TEXT', 'score': 'banana'},
        {'name': 'NULL', 'score': None},
        {'name': 'GOOD', 'score': 10},
    ]}))
    assert [entry['name'] for entry in board.get_top_scores()] == ['GOOD']


def test_numeric_strings_are_coerced(board):
    """`Number('4200')` is 4200 in JS, so a hand-edited file still works."""
    write_raw(board, json.dumps({'scores': [{'name': 'RYAN', 'score': '4200'}]}))
    assert board.high_score() == 4200


def test_long_names_are_truncated_on_read(board):
    write_raw(board, json.dumps({'scores': [
        {'name': 'ABCDEFGHIJKLMNOPQRSTUVWXYZ', 'score': 10},
    ]}))
    assert board.get_top_scores()[0]['name'] == 'ABCDEFGHIJKL'   # 12 chars


def test_long_names_are_truncated_on_submit(board):
    board.submit_score('ABCDEFGHIJKLMNOPQRSTUVWXYZ', 10)
    assert board.get_top_scores()[0]['name'] == 'ABCDEFGHIJKL'


@pytest.mark.parametrize('name', ['', '   ', None])
def test_blank_names_become_the_default(board, name):
    """leaderboard.js:92."""
    board.submit_score(name, 500)
    assert board.get_top_scores()[0]['name'] == 'AAA'


def test_names_are_trimmed(board):
    board.submit_score('  RYAN  ', 500)
    assert board.get_top_scores()[0]['name'] == 'RYAN'


def test_ties_keep_the_incumbent_ahead(board):
    """A stable sort is the whole mechanism (leaderboard.js:100)."""
    board.submit_score('FIRST', 1000)
    board.submit_score('SECOND', 1000)

    scores = board.get_top_scores()
    assert [entry['name'] for entry in scores] == ['FIRST', 'SECOND']


def test_tie_does_not_displace_third_place(board):
    board.write_scores([
        {'name': 'A', 'score': 300},
        {'name': 'B', 'score': 200},
        {'name': 'C', 'score': 100},
    ])
    # Equal to the lowest score does not qualify...
    assert board.qualifies(100) is False
    # ...and submitting it anyway leaves C in place.
    board.submit_score('D', 100)
    assert [entry['name'] for entry in board.get_top_scores()] == ['A', 'B', 'C']


def test_qualifies_on_an_empty_slot(board):
    assert board.qualifies(1) is True
    board.write_scores([{'name': 'A', 'score': 5000}])
    assert board.qualifies(1) is True


def test_qualifies_only_above_the_lowest_when_full(board):
    board.write_scores([
        {'name': 'A', 'score': 300},
        {'name': 'B', 'score': 200},
        {'name': 'C', 'score': 100},
    ])
    assert board.qualifies(101) is True
    assert board.qualifies(100) is False
    assert board.qualifies(99) is False


@pytest.mark.parametrize('score', [0, -1, None, 'banana'])
def test_invalid_scores_never_qualify_or_save(board, score):
    assert board.qualifies(score) is False
    board.submit_score('RYAN', score)
    assert board.get_top_scores() == []


def test_scores_are_written_as_integers(board):
    """`4200`, not `4200.0` - so the JSON matches the Node version byte for byte."""
    board.submit_score('RYAN', 4200)

    with open(board.data_file, encoding='utf-8') as handle:
        raw = handle.read()

    assert '"score": 4200' in raw
    assert '4200.0' not in raw


def test_file_format_matches_the_node_version(board):
    """Two-space indent and a trailing newline (leaderboard.js:52)."""
    board.submit_score('RYAN', 4200)

    with open(board.data_file, encoding='utf-8') as handle:
        raw = handle.read()

    assert raw == '{\n  "scores": [\n    {\n      "name": "RYAN",\n' \
                  '      "score": 4200\n    }\n  ]\n}\n'


def test_write_leaves_no_temp_file_behind(board):
    board.submit_score('RYAN', 4200)
    assert not os.path.exists(f'{board.data_file}.tmp')


def test_write_is_atomic_via_replace(board, monkeypatch):
    """A crash mid-write must leave the previous file intact.

    The temp file is written first and only then renamed, so a failure before
    the rename cannot damage `data.json`.
    """
    board.submit_score('SAFE', 1000)
    original = open(board.data_file, encoding='utf-8').read()

    def explode(*args, **kwargs):
        raise OSError('simulated power loss')

    monkeypatch.setattr(os, 'replace', explode)

    with pytest.raises(OSError):
        board.submit_score('LOST', 9999)

    assert open(board.data_file, encoding='utf-8').read() == original
    assert board.high_score() == 1000


def test_reset_empties_the_board(board):
    board.submit_score('RYAN', 4200)
    board.reset()
    assert board.get_top_scores() == []

    with open(board.data_file, encoding='utf-8') as handle:
        assert json.load(handle) == {'scores': []}


def test_creates_parent_directory(tmp_path):
    board = Leaderboard(str(tmp_path / 'nested' / 'deeper' / 'data.json'))
    board.submit_score('RYAN', 100)
    assert board.high_score() == 100


def test_non_dict_entries_are_skipped(board):
    write_raw(board, json.dumps({'scores': [
        'garbage', 42, None, {'name': 'GOOD', 'score': 10},
    ]}))
    assert [entry['name'] for entry in board.get_top_scores()] == ['GOOD']
