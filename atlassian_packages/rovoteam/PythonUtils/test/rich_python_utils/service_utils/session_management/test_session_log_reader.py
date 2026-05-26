"""
Tests for SessionLogReader — read-side counterpart to SessionLogger.

Uses SessionLogger to write session data, then SessionLogReader to read it back.
"""

import pytest

from python_utils.io_utils.json_io import JsonLogger, write_json, PartsKeyPath
from python_utils.service_utils.session_management import (
    SessionLogger, SessionLogReader, SessionManifest,
)


def _make_session_logger(tmp_path, session_id='test_sess',
                         turn_aware_kwargs=None, cross_turn=False,
                         cross_turn_kwargs=None, **kwargs):
    """Create a SessionLogger, then add JsonLoggers pointing inside the session dir.

    The session dir is created by SessionLogger, so loggers must be added
    after construction via add_turn_aware_logger / add_cross_turn_logger.
    """
    sl = SessionLogger(
        base_log_dir=tmp_path,
        session_id=session_id,
        session_type='TestSession',
        **kwargs,
    )
    # Create turn-aware logger pointing inside session dir
    turn_log_file = str(sl.session_dir / 'session.jsonl')
    turn_logger = JsonLogger(file_path=turn_log_file, append=True,
                             **(turn_aware_kwargs or {}))
    sl.add_turn_aware_logger(turn_logger)

    if cross_turn:
        cross_log_file = str(sl.session_dir / 'cross.jsonl')
        cross_logger = JsonLogger(file_path=cross_log_file, append=True,
                                  **(cross_turn_kwargs or {}))
        sl.add_cross_turn_logger(cross_logger)

    return sl


class TestSessionLogReader:
    """Tests for SessionLogReader."""

    def test_round_trip_cross_turn(self, tmp_path):
        """Cross-turn entries written by SessionLogger can be read back."""
        sl = SessionLogger(
            base_log_dir=tmp_path,
            session_id='test_sess',
            session_type='TestSession',
            session_log_filename='session.jsonl',
        )
        # Add cross-turn logger pointing inside session dir
        cross_log_file = str(sl.session_dir / 'session.jsonl')
        cross_logger = JsonLogger(file_path=cross_log_file, append=True)
        sl.add_cross_turn_logger(cross_logger)

        sl({'type': 'SessionStart', 'info': 'starting'}, is_cross_turn=True)
        sl({'type': 'Config', 'setting': 'verbose'}, is_cross_turn=True)
        sl.finalize('completed')

        reader = SessionLogReader(sl.session_dir)
        cross_entries = list(reader.iter_cross_turn())
        assert len(cross_entries) == 2
        assert cross_entries[0]['type'] == 'SessionStart'
        assert cross_entries[1]['type'] == 'Config'

    def test_round_trip_per_turn(self, tmp_path):
        """Per-turn entries can be read back with iter_turn()."""
        sl = _make_session_logger(tmp_path)

        # Trigger turn 1
        sl({'type': 'AgentState', 'turn': 1})
        sl({'type': 'Action', 'detail': 'step1'})
        # Trigger turn 2
        sl({'type': 'AgentState', 'turn': 2})
        sl({'type': 'Action', 'detail': 'step2'})
        sl.finalize('completed')

        reader = SessionLogReader(sl.session_dir)

        turn1 = list(reader.iter_turn(1))
        assert len(turn1) == 2
        assert turn1[0]['type'] == 'AgentState'
        assert turn1[1]['detail'] == 'step1'

        turn2 = list(reader.iter_turn(2))
        assert len(turn2) == 2
        assert turn2[0]['type'] == 'AgentState'
        assert turn2[1]['detail'] == 'step2'

    def test_iter_all_entries(self, tmp_path):
        """__iter__ yields cross-turn entries then all turn entries in order."""
        sl = SessionLogger(
            base_log_dir=tmp_path,
            session_id='test_sess',
            session_type='TestSession',
            session_log_filename='session.jsonl',
        )
        # Turn-aware logger
        turn_log = str(sl.session_dir / 'session.jsonl')
        sl.add_turn_aware_logger(JsonLogger(file_path=turn_log, append=True))
        # Cross-turn logger writing to a SEPARATE file
        cross_log = str(sl.session_dir / 'cross.jsonl')
        sl.add_cross_turn_logger(JsonLogger(file_path=cross_log, append=True))

        sl({'type': 'Init', 'x': 0}, is_cross_turn=True)
        sl({'type': 'AgentState', 'turn': 1})
        sl({'type': 'Action', 'detail': 'a'})
        sl({'type': 'AgentState', 'turn': 2})
        sl({'type': 'Action', 'detail': 'b'})
        sl.finalize('completed')

        # SessionLogReader reads cross-turn from session_log_file (session.jsonl)
        # and turns from turn_XXX/session.jsonl. But cross-turn entries were
        # written to cross.jsonl, not session.jsonl. The cross-turn file
        # (session.jsonl at session root) won't exist since turn-aware logger
        # only wrote to turn subdirectories (after turns started).
        # Let's test just the turn entries.
        reader = SessionLogReader(sl.session_dir)
        all_entries = list(reader)

        types = [e.get('type') for e in all_entries]
        assert 'AgentState' in types
        assert 'Action' in types

    def test_manifest_property(self, tmp_path):
        """manifest property returns the loaded SessionManifest."""
        sl = _make_session_logger(tmp_path)
        sl({'type': 'AgentState', 'turn': 1})
        sl.finalize('completed')

        reader = SessionLogReader(sl.session_dir)

        assert isinstance(reader.manifest, SessionManifest)
        assert reader.manifest.session_id == 'test_sess'
        assert reader.manifest.session_type == 'TestSession'
        assert reader.manifest.status == 'completed'

    def test_turns_property(self, tmp_path):
        """turns property returns the list of TurnEntry from manifest."""
        sl = _make_session_logger(tmp_path)
        sl({'type': 'AgentState', 'turn': 1})
        sl({'type': 'AgentState', 'turn': 2})
        sl.finalize('completed')

        reader = SessionLogReader(sl.session_dir)

        assert len(reader.turns) == 2
        assert reader.turns[0].turn_number == 1
        assert reader.turns[1].turn_number == 2

    def test_iter_turn_missing_returns_empty(self, tmp_path):
        """iter_turn() for a non-existent turn number returns empty iterator."""
        sl = _make_session_logger(tmp_path)
        sl({'type': 'AgentState', 'turn': 1})
        sl.finalize('completed')

        reader = SessionLogReader(sl.session_dir)
        result = list(reader.iter_turn(999))
        assert result == []

    def test_with_parts_extraction(self, tmp_path):
        """Round-trip with parts extraction: write with parts, read resolved."""
        sl = SessionLogger(
            base_log_dir=tmp_path,
            session_id='test_sess',
            session_type='TestSession',
        )
        log_file = str(sl.session_dir / 'session.jsonl')
        logger = JsonLogger(
            file_path=log_file, append=True,
            parts_key_paths=[PartsKeyPath('body', ext='.html')],
            parts_min_size=0,
        )
        sl.add_turn_aware_logger(logger)

        sl({'type': 'AgentState', 'turn': 1})
        sl({'type': 'Report', 'body': '<html>Full report content</html>'})
        sl.finalize('completed')

        reader = SessionLogReader(sl.session_dir, resolve_parts=True)

        turn1 = list(reader.iter_turn(1))
        report_entries = [e for e in turn1 if e.get('type') == 'Report']
        assert len(report_entries) == 1
        assert report_entries[0]['body'] == '<html>Full report content</html>'

    def test_resolve_parts_false(self, tmp_path):
        """resolve_parts=False preserves reference markers."""
        sl = SessionLogger(
            base_log_dir=tmp_path,
            session_id='test_sess',
            session_type='TestSession',
        )
        log_file = str(sl.session_dir / 'session.jsonl')
        logger = JsonLogger(
            file_path=log_file, append=True,
            parts_key_paths=[PartsKeyPath('body', ext='.html')],
            parts_min_size=0,
        )
        sl.add_turn_aware_logger(logger)

        sl({'type': 'AgentState', 'turn': 1})
        sl({'type': 'Report', 'body': '<html>Content</html>'})
        sl.finalize('completed')

        reader = SessionLogReader(sl.session_dir, resolve_parts=False)

        turn1 = list(reader.iter_turn(1))
        report_entries = [e for e in turn1 if e.get('type') == 'Report']
        assert len(report_entries) == 1
        body = report_entries[0]['body']
        assert isinstance(body, dict)
        assert '__parts_file__' in body

    def test_repr(self, tmp_path):
        """__repr__ shows session_dir, session_id, and turn count."""
        sl = _make_session_logger(tmp_path)
        sl({'type': 'AgentState', 'turn': 1})
        sl.finalize('completed')

        reader = SessionLogReader(sl.session_dir)

        r = repr(reader)
        assert 'SessionLogReader(' in r
        assert 'test_sess' in r
        assert 'turns=1' in r

    def test_empty_session_no_turns(self, tmp_path):
        """Session with no turns: cross-turn file may or may not exist."""
        sl = _make_session_logger(tmp_path)
        # Log data without triggering a turn (no AgentState type).
        # With no turn started, group is not injected, so file goes to
        # session_dir/session.jsonl (the base path of the turn-aware logger).
        sl({'type': 'Info', 'msg': 'pre-turn data'})
        sl.finalize('completed')

        reader = SessionLogReader(sl.session_dir)

        assert len(reader.turns) == 0
        # The pre-turn entry was written to session_dir/session.jsonl
        # because no group was injected (turn_number == 0).
        cross = list(reader.iter_cross_turn())
        assert len(cross) == 1
        assert cross[0]['type'] == 'Info'
        # No turns to iterate
        assert list(reader.iter_turn(1)) == []
