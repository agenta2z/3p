"""Discover-or-launch the OpenTeam server. Idempotent under concurrency.

Public entry point: :func:`ensure_server`. Caller passes a ``runtime_root``,
gets back a live :class:`ServerHandle` (auto-launching if no live server is
found and ``auto_launch`` is True).

Concurrency safety: O_EXCL launch lock at
``<discovery_dir>/.launch.lock`` (Invariant I13). After acquiring, re-check
the registry — another process may have just registered.

Fork-bomb safety: the spawned server inherits ``OPENTEAM_AUTO_LAUNCH=0``
(Invariant I17), so if its own startup code ever imports the connector it
will not recurse.
"""
from __future__ import annotations

import asyncio
import contextlib
import logging
import os
import socket
import subprocess
import sys
import time
from pathlib import Path
from typing import Optional, Union

from openteam.client.discovery import (
    DISCOVERY_DIR,
    ServerHandle,
    find_server,
)

_logger = logging.getLogger(__name__)


class NoServerAvailable(RuntimeError):
    """No live server, and ``auto_launch=False``."""


async def ensure_server(
    *,
    runtime_root: Path,
    host: str = "127.0.0.1",
    port: Optional[int] = None,
    auto_launch: bool = True,
    wait_timeout_s: float = 15.0,
) -> ServerHandle:
    """Return a live :class:`ServerHandle`, auto-launching if necessary.

    Always async so callers in event-loop contexts (Textual TUI startup)
    don't block the loop. The actual auto-launch happens in a thread pool
    via ``run_in_executor``.

    Raises:
        :class:`NoServerAvailable`: no live server AND ``auto_launch=False``.
        ``RuntimeError``: auto-launch attempted but failed (port range
            exhausted, server subprocess exited before registering,
            timeout waiting for registration, etc.).
    """
    handle = find_server(runtime_root=runtime_root, host=host, port=port)
    if handle is not None and handle.is_alive():
        return handle

    if not auto_launch:
        raise NoServerAvailable(
            f"No live OpenTeam server under runtime_root={runtime_root} host={host}. "
            f"Start one with `openteam-server` or pass auto_launch=True."
        )

    # Honor the fork-bomb guard (I17): if our process was itself spawned by
    # an earlier ensure_server, refuse to recurse.
    if os.environ.get("OPENTEAM_AUTO_LAUNCH") == "0":
        raise NoServerAvailable(
            "OPENTEAM_AUTO_LAUNCH=0 set in env; refusing to auto-launch. "
            "This guard prevents fork bombs when a server-side process "
            "transitively imports openteam.client."
        )

    loop = asyncio.get_running_loop()
    return await loop.run_in_executor(
        None,
        lambda: auto_launch_server(
            runtime_root=runtime_root,
            host=host,
            port=port,
            wait_timeout_s=wait_timeout_s,
        ),
    )


def auto_launch_server(
    *,
    runtime_root: Path,
    host: str = "127.0.0.1",
    port: Optional[int] = None,
    wait_timeout_s: float = 15.0,
    poll_interval_s: float = 0.25,
    extra_argv: Optional[list[str]] = None,
) -> ServerHandle:
    """Spawn an OpenTeam server. Mutex'd by O_EXCL file-lock (I13).

    Args:
        runtime_root: passed to the child as ``--runtime-root <path>``.
        host: passed as ``--host``.
        port: if None, ``_pick_free_port`` walks 8000-8010.
        wait_timeout_s: max seconds to wait for the child to register itself.
        poll_interval_s: how often to re-check the registry while waiting.
        extra_argv: optional extra args to pass to the server command (e.g.
            ``["--llm-backend", "rovodev"]``).

    Returns the registered :class:`ServerHandle`. Raises ``RuntimeError`` on
    timeout, subprocess crash, or port exhaustion.
    """
    reg_dir = DISCOVERY_DIR()
    reg_dir.mkdir(parents=True, exist_ok=True)
    lock_path = reg_dir / ".launch.lock"

    # O_EXCL acquires an atomic mutex via filesystem semantics. If another
    # process holds the lock, we wait for its registry entry to appear.
    try:
        lock_fd = os.open(str(lock_path), os.O_CREAT | os.O_EXCL | os.O_WRONLY, 0o600)
    except FileExistsError:
        deadline = time.monotonic() + wait_timeout_s
        while time.monotonic() < deadline:
            time.sleep(poll_interval_s)
            handle = find_server(runtime_root=runtime_root, host=host, port=port)
            if handle is not None and handle.is_alive():
                return handle
            # Stale lock recovery: if the lock file is older than our
            # patience window, assume the holder died and try once.
            try:
                lock_age = time.time() - lock_path.stat().st_mtime
            except FileNotFoundError:
                continue  # holder finished and cleaned up
            if lock_age > wait_timeout_s:
                _logger.warning(
                    "[supervisor] lock %s appears stale (%.1fs old); removing",
                    lock_path,
                    lock_age,
                )
                with contextlib.suppress(FileNotFoundError, OSError):
                    lock_path.unlink()
                # Loop will retry the O_EXCL acquisition implicitly via
                # find_server; if no handle appears, we re-raise below.
        raise RuntimeError(
            f"another auto-launch holds {lock_path}; timed out after {wait_timeout_s}s"
        )

    try:
        # Re-check after lock acquisition: another process may have just
        # registered between our initial find_server in ensure_server and
        # the O_EXCL open above.
        handle = find_server(runtime_root=runtime_root, host=host, port=port)
        if handle is not None and handle.is_alive():
            return handle

        actual_port = port if port is not None else _pick_free_port(host)

        env = dict(os.environ)
        env["OPENTEAM_AUTO_LAUNCH"] = "0"  # I17: prevent fork bomb in child

        # Prefer the installed console script so the child has a clean argv
        # (matters for ``process_command`` in the discovery file). Fall back
        # to ``python -m openteam.server.run_server`` when the script isn't
        # on PATH (dev mode, pre-install testing).
        console_script = _find_executable("openteam-server")
        if console_script is not None:
            cmd: list[str] = [console_script]
        else:
            cmd = [sys.executable, "-m", "openteam.server.run_server"]
        cmd += [
            "--host", host,
            "--port", str(actual_port),
            "--runtime-root", str(runtime_root),
            # --real-sessions is preserved for backward compatibility with
            # call sites that haven't migrated to --runtime-root yet; the
            # server treats either as equivalent (I21).
            "--real-sessions", str(runtime_root),
        ]
        if extra_argv:
            cmd += list(extra_argv)

        _logger.info("[supervisor] auto-launching: %s", " ".join(cmd))
        proc = subprocess.Popen(
            cmd,
            env=env,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            start_new_session=True,   # detach from caller's process group
        )

        deadline = time.monotonic() + wait_timeout_s
        while time.monotonic() < deadline:
            time.sleep(poll_interval_s)
            if proc.poll() is not None:
                raise RuntimeError(
                    f"auto-launched server exited prematurely (rc={proc.returncode}). "
                    f"Run `{' '.join(cmd)}` manually to see the error."
                )
            handle = find_server(runtime_root=runtime_root, host=host, port=actual_port)
            if handle is not None and handle.is_alive():
                return handle
        raise RuntimeError(
            f"auto-launched server did not register within {wait_timeout_s}s "
            f"(pid={proc.pid}); kill it manually with `kill {proc.pid}`"
        )
    finally:
        try:
            os.close(lock_fd)
        except OSError:
            pass
        with contextlib.suppress(FileNotFoundError, OSError):
            lock_path.unlink()


def _find_executable(name: str) -> Optional[str]:
    """Locate an executable on PATH. Used by auto_launch to find ``openteam-server``."""
    import shutil
    return shutil.which(name)


def _pick_free_port(host: str, *, candidates: Union[range, list[int]] = range(8000, 8011)) -> int:
    """Probe ``candidates`` until one binds successfully. Raise if all are taken.

    The probe binds momentarily then closes; the port is then available for
    the child to bind. This races with concurrent bind attempts but is the
    standard Unix idiom (no atomic "reserve and pass to child" exists for
    plain TCP).
    """
    for p in candidates:
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
            try:
                s.bind((host, p))
                return p
            except OSError:
                continue
    raise RuntimeError(
        f"no free port in {list(candidates)}; close some processes or pass port= explicitly"
    )
