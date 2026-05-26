"""Callable session logger with turn-aware file routing and manifest tracking.

A callable logger that any Debuggable can use directly. Manages turn-aware
file routing via the ``group`` parameter (e.g. ``JsonLogger`` maps
``group -> subfolder``), session directory structure, and manifest tracking.

Thread Safety: All manifest writes and state mutations are protected by
a threading.RLock.
"""

import json
import threading
from datetime import datetime
from pathlib import Path
from typing import Callable, List, Optional

from python_utils.io_utils.json_io import iter_json_objs

from .session_manifest import SessionManifest, TurnEntry


class SessionLogger:
    """Callable logger with turn-aware file routing.

    Manages two sets of loggers:

    - **cross_turn_loggers**: Always write to the same location, never receive
      ``group``.  For session-level logs that should not be split by turn.
    - **turn_aware_loggers**: Receive a ``group`` kwarg (e.g. ``'turn_001'``)
      for turn-based file routing.  Loggers like ``JsonLogger`` map
      ``group -> subfolder`` so the output file lands in a turn subdirectory.

    If no cross-turn loggers are configured, turn-aware loggers serve both
    roles (without ``group`` for pre-turn entries).

    Usage::

        from python_utils.io_utils.json_io import JsonLogger

        sl = SessionLogger(
            base_log_dir=Path('logs'),
            session_id='sess_001',
            session_type='DefaultAgent',
            turn_aware_loggers=[
                JsonLogger(file_path='logs/session.jsonl', append=True,
                           parts_key_paths=['item'], parts_min_size=2000),
            ],
        )

        # Pass as logger to any Debuggable:
        component = MyComponent(logger=sl, ...)
        # component.log_info(...) calls sl(log_data, **kwargs) automatically.
    """

    def __init__(
        self,
        base_log_dir: Path,
        session_id: str,
        session_type: str,
        turn_aware_loggers: Optional[List[Callable]] = None,
        cross_turn_loggers: Optional[List[Callable]] = None,
        new_turn_log_type: str = 'AgentState',
        manifest_filename: str = 'manifest.json',
        session_log_filename: str = 'session.jsonl',
    ):
        """Create session directory with timestamp, initialize manifest.

        Args:
            base_log_dir: Parent directory where session directories are created.
            session_id: Unique identifier for the session.
            session_type: Type/variant of session running.
            turn_aware_loggers: Loggers that receive ``group`` for turn routing.
            cross_turn_loggers: Loggers that never receive ``group``.
            new_turn_log_type: log_data['type'] value that triggers a new turn.
            manifest_filename: Name of the manifest file written to session dir.
            session_log_filename: Name of the session log file (stored in manifest).
        """
        self._lock = threading.RLock()
        self._session_id = session_id
        self._session_type = session_type
        self._new_turn_log_type = new_turn_log_type
        self._manifest_filename = manifest_filename

        # --- Directory setup (collision-safe) ---
        now = datetime.now()
        timestamp_str = now.strftime("%Y%m%d_%H%M%S")
        creation_timestamp = now.strftime("%Y-%m-%dT%H:%M:%S")

        base_log_dir = Path(base_log_dir)
        base_log_dir.mkdir(parents=True, exist_ok=True)

        dir_name = f"{session_id}_{timestamp_str}"
        session_dir = base_log_dir / dir_name

        if session_dir.exists():
            n = 2
            while True:
                dir_name = f"{session_id}_{timestamp_str}_{n}"
                session_dir = base_log_dir / dir_name
                if not session_dir.exists():
                    break
                n += 1

        session_dir.mkdir(parents=True, exist_ok=True)
        self._session_dir = session_dir

        # --- Manifest ---
        self._manifest = SessionManifest(
            session_id=session_id,
            creation_timestamp=creation_timestamp,
            session_type=session_type,
            status="running",
            session_dir=str(session_dir),
            session_log_file=session_log_filename,
        )
        self.write_manifest()

        # --- Logger sets ---
        self._turn_aware_loggers: List[Callable] = list(turn_aware_loggers or [])
        self._cross_turn_loggers: List[Callable] = list(cross_turn_loggers or [])

        # --- Turn tracking ---
        self._current_turn_number = 0
        self._turn_step_counter = 0

    # ------------------------------------------------------------------
    # Logger management
    # ------------------------------------------------------------------

    def add_turn_aware_logger(self, logger: Callable) -> None:
        """Add a turn-aware logger (receives ``group`` for turn routing)."""
        self._turn_aware_loggers.append(logger)

    def add_cross_turn_logger(self, logger: Callable) -> None:
        """Add a cross-turn logger (never receives ``group``)."""
        self._cross_turn_loggers.append(logger)

    # ------------------------------------------------------------------
    # Callable logger interface
    # ------------------------------------------------------------------

    def __call__(self, log_data, **kwargs):
        """Callable logger interface for Debuggable integration.

        Detects turn boundaries, injects ``group`` for turn-aware loggers,
        and delegates to the configured logger sets.

        Returns the result from the first turn-aware logger (typically
        ``JsonLogger`` → ``write_json``), which is the post-parts-extraction
        version of the data.  This enables the Debuggable pipeline:
        ``SessionLogger`` with ``pass_output=True`` feeds slimmed-down data
        to a downstream ``print`` logger with ``use_processed=True``.

        Special kwargs consumed (not forwarded to loggers):
            is_cross_turn (bool): If True, route only to cross-turn loggers
                (or turn-aware loggers without ``group`` as fallback).
        """
        is_cross_turn = kwargs.pop('is_cross_turn', False)

        log_type = log_data.get('type', '') if isinstance(log_data, dict) else ''

        # Detect turn boundary
        if log_type == self._new_turn_log_type:
            self._advance_turn()

        result = None

        if is_cross_turn:
            # Cross-turn: use cross_turn_loggers, fallback to turn_aware (no group)
            for logger in (self._cross_turn_loggers or self._turn_aware_loggers):
                r = logger(log_data, **kwargs)
                if result is None and r is not None:
                    result = r
        else:
            # Turn-aware: inject group if a turn is active
            if self._current_turn_number > 0:
                kwargs.setdefault('group', f'turn_{self._current_turn_number:03d}')
            for logger in self._turn_aware_loggers:
                r = logger(log_data, **kwargs)
                if result is None and r is not None:
                    result = r
            # Also write to cross-turn loggers (without group) if they exist
            if self._cross_turn_loggers:
                cross_kwargs = {k: v for k, v in kwargs.items() if k != 'group'}
                for logger in self._cross_turn_loggers:
                    logger(log_data, **cross_kwargs)

        return result

    # ------------------------------------------------------------------
    # Properties for Debuggable integration
    # ------------------------------------------------------------------

    @property
    def file_path(self) -> Optional[str]:
        """First available file path from loggers."""
        for logger in (*self._turn_aware_loggers, *self._cross_turn_loggers):
            fp = getattr(logger, 'file_path', None)
            if fp:
                return fp
        return None

    @property
    def keywords(self) -> dict:
        """Empty dict — no baked-in params to exclude.

        ``Debuggable.log()`` checks ``getattr(_logger, 'keywords', {}).keys()``
        to avoid passing duplicate kwargs to ``functools.partial`` loggers.
        ``SessionLogger`` is not a partial, so nothing should be excluded.
        """
        return {}

    # ------------------------------------------------------------------
    # Directory / manifest properties
    # ------------------------------------------------------------------

    @property
    def session_dir(self) -> Path:
        """Return the timestamped session directory path."""
        return self._session_dir

    # ------------------------------------------------------------------
    # Turn management
    # ------------------------------------------------------------------

    def start_turn(self, turn_number=None) -> None:
        """Advance to the next turn.

        This is the public API for explicit turn advancement. The ``__call__``
        method auto-detects turns via ``new_turn_log_type``, but callers may
        advance turns explicitly.

        Args:
            turn_number: Ignored (turn numbers are auto-incremented).
        """
        self._advance_turn()

    def _advance_turn(self) -> None:
        """Advance to the next turn: update manifest, reset step counter."""
        with self._lock:
            if self._current_turn_number > 0 and self._manifest.turns:
                self._manifest.turns[-1].end_timestamp = (
                    datetime.now().strftime("%Y-%m-%dT%H:%M:%S")
                )
            self._current_turn_number += 1
            self._turn_step_counter = 0

            now = datetime.now()
            start_timestamp = now.strftime("%Y-%m-%dT%H:%M:%S")

            turn_entry = TurnEntry(
                turn_number=self._current_turn_number,
                start_timestamp=start_timestamp,
                log_file=f'turn_{self._current_turn_number:03d}',
            )
            self._manifest.turns.append(turn_entry)

    # ------------------------------------------------------------------
    # Manifest operations
    # ------------------------------------------------------------------

    def get_manifest(self) -> dict:
        """Return the current manifest as a dictionary."""
        return self._manifest.to_dict()

    def write_manifest(self) -> None:
        """Write the manifest to the session directory (thread-safe)."""
        with self._lock:
            manifest_path = self._session_dir / self._manifest_filename
            manifest_path.write_text(
                json.dumps(self._manifest.to_dict(), indent=2, sort_keys=True) + "\n"
            )

    def finalize(self, status: str) -> None:
        """Write final session status and end timestamp to manifest (thread-safe).

        Idempotent: if already finalized (end_timestamp is set), this is a no-op.

        Args:
            status: Final session status (e.g., "completed", "error").
        """
        with self._lock:
            if self._manifest.end_timestamp is not None:
                return

            now = datetime.now().strftime("%Y-%m-%dT%H:%M:%S")
            self._manifest.end_timestamp = now
            self._manifest.status = status

            if self._manifest.turns and self._manifest.turns[-1].end_timestamp is None:
                self._manifest.turns[-1].end_timestamp = now

        self.write_manifest()


class SessionLogReader:
    """Read-side counterpart to :class:`SessionLogger`.

    Loads the session manifest and provides iteration over cross-turn
    and per-turn log entries.  Each iteration method returns a fresh
    iterator backed by :func:`~python_utils.io_utils.json_io.iter_json_objs`.

    Args:
        session_dir: Path to the timestamped session directory
            (e.g. ``logs/sess_001_20260101_120000/``).
        manifest_filename: Name of the manifest file. Default ``'manifest.json'``.
        resolve_parts: Resolve parts references when reading log entries.
            Default ``True``.
        parts_suffix: Parts directory suffix. Default ``'.parts'``.

    Examples:
        >>> reader = SessionLogReader('logs/sess_001_20260101_120000')
        >>> reader.manifest.session_id
        'sess_001'
        >>> for obj in reader.iter_cross_turn():
        ...     print(obj.get('type'))
        >>> for obj in reader.iter_turn(1):
        ...     print(obj.get('type'))
    """

    def __init__(
        self,
        session_dir,
        manifest_filename='manifest.json',
        resolve_parts=True,
        parts_suffix='.parts',
    ):
        self._session_dir = Path(session_dir)
        self._resolve_parts = resolve_parts
        self._parts_suffix = parts_suffix

        manifest_path = self._session_dir / manifest_filename
        manifest_text = manifest_path.read_text(encoding='utf-8')
        self._manifest = SessionManifest.from_json(manifest_text)

    @property
    def manifest(self):
        """The loaded :class:`SessionManifest`."""
        return self._manifest

    @property
    def session_dir(self):
        """Path to the session directory."""
        return self._session_dir

    @property
    def turns(self):
        """List of :class:`TurnEntry` from the manifest."""
        return self._manifest.turns

    def _iter_log_file(self, log_file_path):
        """Iterate JSON objects from a single log file, if it exists."""
        path_str = str(log_file_path)
        if not log_file_path.exists():
            return iter(())
        return iter_json_objs(
            path_str,
            resolve_parts=self._resolve_parts,
            parts_suffix=self._parts_suffix,
            use_tqdm=False,
            verbose=False,
        )

    def iter_cross_turn(self):
        """Iterate over cross-turn (session-level) log entries.

        Reads from ``{session_dir}/{session_log_file}``.
        """
        log_path = self._session_dir / self._manifest.session_log_file
        return self._iter_log_file(log_path)

    def iter_turn(self, turn_number):
        """Iterate over log entries for a specific turn.

        Args:
            turn_number (int): 1-based turn number.

        Reads from ``{session_dir}/{turn.log_file}/{session_log_file}``
        (e.g. ``session_dir/turn_001/session.jsonl``).
        """
        for turn in self._manifest.turns:
            if turn.turn_number == turn_number:
                log_path = (self._session_dir / turn.log_file
                            / self._manifest.session_log_file)
                return self._iter_log_file(log_path)
        return iter(())

    def __iter__(self):
        """Iterate over ALL log entries: cross-turn first, then each turn."""
        yield from self.iter_cross_turn()
        for turn in self._manifest.turns:
            log_path = (self._session_dir / turn.log_file
                        / self._manifest.session_log_file)
            yield from self._iter_log_file(log_path)

    def __repr__(self):
        return (f'SessionLogReader(session_dir={str(self._session_dir)!r}, '
                f'session_id={self._manifest.session_id!r}, '
                f'turns={len(self._manifest.turns)})')
