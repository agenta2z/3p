"""Server-side registration (write hook for the discovery registry).

Imports schema constants from :mod:`openteam.client.discovery` — the one
allowed client→server reverse import per Invariant I14. This keeps the
ServerHandle dataclass as the single source of truth for the wire format
(``asdict(handle)`` is what we write; the same shape is what clients read).

Lifecycle:
1. ``register_server(...)`` writes ``<discovery_dir>/<server_id>.json`` atomically.
2. Installs ``atexit`` + SIGTERM/SIGINT signal handlers to remove the file
   on graceful shutdown (Invariant I12 — best-effort; clients also reap on read).
3. Conflict detection: if another live PID already owns the same
   ``(runtime_root, host, port)`` triple, raises :class:`ConflictError`.

Atomic write: ``tempfile.mkstemp`` in the registry dir + ``os.replace`` to
the final name. Readers never see torn JSON; the random-suffix temp name
also prevents collision if two callers somehow tried to register the same
``server_id`` simultaneously (the launch lock makes this impossible in
practice but defense in depth is cheap).
"""
from __future__ import annotations

import atexit
import contextlib
import json
import logging
import os
import signal
import sys
import tempfile
from dataclasses import asdict
from datetime import datetime, timezone
from pathlib import Path

from openteam.client.discovery import (
    DISCOVERY_DIR,
    SCHEMA_VERSION,
    SERVICE_NAME,
    ServerHandle,
    compute_server_id,
    pid_alive,
)

_logger = logging.getLogger(__name__)


class ConflictError(Exception):
    """Another live server already registered for this ``(runtime_root, host, port)``."""


def register_server(
    *,
    runtime_root: str | Path,
    host: str,
    port: int,
    server_dir_name: str,
    pid: int | None = None,
    version: str = "unknown",
    process_command: list[str] | None = None,
) -> ServerHandle:
    """Write the discovery file. Install ``atexit`` + SIGTERM/SIGINT cleanup.

    Args:
        runtime_root: absolute path to the server's runtime root.
        host: bind address (typically "127.0.0.1" for v1 loopback-only).
        port: bind port.
        server_dir_name: basename of the server's own dir under
            ``<runtime_root>/servers/`` (e.g., ``server_20260518_001234_abcd1234``).
        pid: process id (defaults to ``os.getpid()``).
        version: server package version (caller pulls from
            ``importlib.metadata`` if needed).
        process_command: argv used to launch the server (defaults to
            ``list(sys.argv)``). Recorded in the registry so a future
            ``openteam-server stop`` (POST-2) can locate the right process.

    Returns the registered :class:`ServerHandle`.

    Raises:
        :class:`ConflictError`: another live PID owns the same triple.
    """
    runtime_root_path = Path(runtime_root).resolve()
    sid = compute_server_id(runtime_root_path, host, port)
    pid = pid if pid is not None else os.getpid()
    started_at = (
        datetime.now(timezone.utc)
        .isoformat(timespec="milliseconds")
        .replace("+00:00", "Z")
    )
    # process_command from sys.argv — RHS of M3 fix in v6. Caller can override
    # for test isolation (avoid leaking pytest's argv into prod registry).
    cmd = list(process_command) if process_command is not None else list(sys.argv)

    handle = ServerHandle(
        server_id=sid,
        pid=pid,
        host=host,
        port=port,
        runtime_root=str(runtime_root_path),
        server_dir_name=server_dir_name,
        started_at=started_at,
        version=version,
        schema_version=SCHEMA_VERSION,
        service=SERVICE_NAME,
        process_command=cmd,
    )
    target = handle.registry_file
    target.parent.mkdir(parents=True, exist_ok=True)

    # Conflict check: refuse to clobber a live owner. Stale entries (dead PID,
    # corrupt JSON) are safe to overwrite.
    if target.exists():
        try:
            existing = json.loads(target.read_text(encoding="utf-8"))
            existing_pid = existing.get("pid")
            if existing_pid != pid and pid_alive(existing_pid):
                raise ConflictError(
                    f"server already registered at {target} (pid={existing_pid}); "
                    f"our pid={pid}. Stop the other server first."
                )
        except json.JSONDecodeError:
            pass  # corrupt — safe to overwrite

    _atomic_write_json(target, asdict(handle))
    _install_cleanup_handlers(target)
    _logger.info("[_register] registered: %s", target)
    return handle


def unregister_server(target: Path) -> None:
    """Remove the discovery file. Idempotent."""
    with contextlib.suppress(FileNotFoundError, OSError):
        target.unlink()
    _logger.info("[_register] unregistered: %s", target)


# ── Internal helpers ─────────────────────────────────────────────────────────
def _atomic_write_json(target: Path, data: dict) -> None:
    """``tempfile.mkstemp + os.replace`` in target's parent dir.

    POSIX-atomic on the rename; readers never see torn JSON. Random tmp name
    means concurrent writers (impossible in practice due to the launch lock,
    but defended in depth) don't collide.
    """
    fd, tmp_path = tempfile.mkstemp(
        dir=str(target.parent),
        prefix=f"{target.stem}.",
        suffix=".tmp",
    )
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=2, ensure_ascii=False)
            f.write("\n")
        os.replace(tmp_path, str(target))
    except Exception:
        with contextlib.suppress(OSError):
            os.unlink(tmp_path)
        raise


def _install_cleanup_handlers(target: Path) -> None:
    """Best-effort cleanup on graceful shutdown.

    ``atexit`` covers normal exit. SIGTERM/SIGINT handlers cover the most
    common kill signals; they chain to the previous handler so other
    library cleanup (FastAPI lifespan, etc.) still runs.

    NOT a substitute for stale-entry reaping — clients always reap on read
    (Invariant I12). This is just polite cleanup.
    """
    def _cleanup(*_args) -> None:
        unregister_server(target)

    atexit.register(_cleanup)

    for sig in (getattr(signal, "SIGTERM", None), getattr(signal, "SIGINT", None)):
        if sig is None:
            continue
        # signal.signal can fail in non-main threads or unusual environments;
        # cleanup-on-exit is best-effort by design.
        with contextlib.suppress(OSError, ValueError):
            prev = signal.getsignal(sig)

            def _handler(s: int, frame, _prev=prev) -> None:  # noqa: ARG001
                _cleanup()
                # Restore previous handler then re-raise so the original
                # signal semantics (e.g., SIGTERM → terminate) happen.
                signal.signal(s, _prev)
                signal.raise_signal(s)

            signal.signal(sig, _handler)
