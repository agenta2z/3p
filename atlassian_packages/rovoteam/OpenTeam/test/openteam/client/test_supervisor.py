"""TIER-1 tests for openteam.client.supervisor — discover-or-launch."""
from __future__ import annotations

import asyncio
import json
import os
import subprocess
import sys
import time
from dataclasses import asdict
from pathlib import Path

import pytest

from openteam.client.discovery import ServerHandle, compute_server_id
from openteam.client.supervisor import (
    NoServerAvailable,
    _pick_free_port,
    auto_launch_server,
    ensure_server,
)


# ── _pick_free_port ──────────────────────────────────────────────────────────
class TestPickFreePort:
    def test_returns_int_from_range(self):
        p = _pick_free_port("127.0.0.1", candidates=range(50000, 50010))
        assert 50000 <= p < 50010

    def test_raises_when_all_taken(self, monkeypatch):
        # Force every bind to fail
        import socket

        class _ExplodeSocket(socket.socket):
            def bind(self, *args):
                raise OSError("simulated bind failure")

        monkeypatch.setattr(socket, "socket", lambda *a, **kw: _ExplodeSocket(*a, **kw))
        with pytest.raises(RuntimeError, match="no free port"):
            _pick_free_port("127.0.0.1", candidates=[50000])


# ── ensure_server: existing live server (no launch) ──────────────────────────
def _write_live_entry(reg_dir: Path, *, runtime_root: Path, host: str = "127.0.0.1",
                     port: int = 8000) -> Path:
    """Write a registry entry whose pid is our own — passes pid_alive."""
    sid = compute_server_id(runtime_root, host, port)
    handle = ServerHandle(
        server_id=sid, pid=os.getpid(), host=host, port=port,
        runtime_root=str(runtime_root.resolve()), server_dir_name="server_test",
        started_at="2026-05-18T00:00:00.000Z", version="0.1.0",
    )
    target = reg_dir / f"{sid}.json"
    target.write_text(json.dumps(asdict(handle)))
    return target


class TestEnsureServerNoLaunch:
    """When auto_launch=False, just look up; raise if not found."""

    @pytest.mark.asyncio
    async def test_raises_no_server_when_empty(self, isolated_registry, tmp_path):
        with pytest.raises(NoServerAvailable):
            await ensure_server(
                runtime_root=tmp_path, host="127.0.0.1", port=8000,
                auto_launch=False,
            )

    @pytest.mark.asyncio
    async def test_returns_live_handle_when_present(
        self, isolated_registry, tmp_path, monkeypatch,
    ):
        # Bypass the actual /api/health roundtrip in is_alive(); the test
        # is about the discovery path, not the network call.
        from openteam.client import discovery as disc
        monkeypatch.setattr(disc, "health_check", lambda *a, **kw: True)

        _write_live_entry(isolated_registry, runtime_root=tmp_path, port=8000)
        handle = await ensure_server(
            runtime_root=tmp_path, host="127.0.0.1", port=8000,
            auto_launch=False,
        )
        assert handle.port == 8000


# ── ensure_server: fork-bomb guard (I17) ─────────────────────────────────────
class TestForkBombGuard:
    @pytest.mark.asyncio
    async def test_refuses_recursion_when_env_set(
        self, isolated_registry, tmp_path, monkeypatch,
    ):
        # Simulate being a server-spawned subprocess that accidentally
        # imports openteam.client and calls ensure_server.
        monkeypatch.setenv("OPENTEAM_AUTO_LAUNCH", "0")
        with pytest.raises(NoServerAvailable, match="OPENTEAM_AUTO_LAUNCH=0"):
            await ensure_server(
                runtime_root=tmp_path, host="127.0.0.1", port=8000,
                auto_launch=True,
            )


# ── auto_launch_server: O_EXCL file lock (I13) ───────────────────────────────
class TestFileLock:
    """If the lock file exists, auto_launch waits for the registry entry."""

    def test_existing_lock_with_live_registry_returns_handle(
        self, isolated_registry, tmp_path, monkeypatch,
    ):
        # Pre-write the lock + a live registry entry, simulating "another
        # process is mid-launch and has just registered".
        (isolated_registry / ".launch.lock").touch()
        _write_live_entry(isolated_registry, runtime_root=tmp_path, port=8042)
        from openteam.client import discovery as disc
        monkeypatch.setattr(disc, "health_check", lambda *a, **kw: True)

        handle = auto_launch_server(
            runtime_root=tmp_path, host="127.0.0.1", port=8042,
            wait_timeout_s=2.0, poll_interval_s=0.05,
        )
        assert handle.port == 8042

    def test_existing_lock_no_entry_times_out(
        self, isolated_registry, tmp_path,
    ):
        # Lock present, no registry entry, no entry ever arrives — timeout.
        (isolated_registry / ".launch.lock").touch()
        with pytest.raises(RuntimeError, match="another auto-launch holds"):
            auto_launch_server(
                runtime_root=tmp_path, host="127.0.0.1", port=8043,
                wait_timeout_s=0.3, poll_interval_s=0.05,
            )


# ── auto_launch_server: I17 fork-bomb env propagation ────────────────────────
class TestNoRecursiveLaunch:
    """The spawned subprocess sees OPENTEAM_AUTO_LAUNCH=0 in its env (I17)."""

    def test_spawn_env_includes_no_autolaunch(
        self, isolated_registry, tmp_path, monkeypatch,
    ):
        # Capture the env Popen receives without actually launching the server.
        captured_env: dict = {}
        captured_cmd: list = []

        class _FakeProc:
            pid = 12345
            returncode = 0

            def poll(self):
                # Simulate "still running" so the registry-poll loop runs once
                # and then we make it succeed.
                return None

        def _fake_popen(cmd, env=None, **kwargs):
            captured_cmd[:] = cmd
            captured_env.update(env or {})
            return _FakeProc()

        monkeypatch.setattr(subprocess, "Popen", _fake_popen)

        # Make find_server return a "live" handle on second call so the
        # registration loop exits quickly. We patch find_server inside the
        # supervisor module namespace (where it's imported).
        from openteam.client import supervisor as sup

        call_count = {"n": 0}

        def _fake_find(*, runtime_root, host, port=None):
            call_count["n"] += 1
            if call_count["n"] >= 2:  # first call (re-check) returns None; second returns handle
                sid = compute_server_id(runtime_root, host, port or 8044)
                return ServerHandle(
                    server_id=sid, pid=os.getpid(), host=host, port=port or 8044,
                    runtime_root=str(Path(runtime_root).resolve()),
                    server_dir_name="x", started_at="x", version="x",
                )
            return None

        monkeypatch.setattr(sup, "find_server", _fake_find)
        monkeypatch.setattr(
            "openteam.client.discovery.health_check",
            lambda *a, **kw: True,
        )

        handle = auto_launch_server(
            runtime_root=tmp_path, host="127.0.0.1", port=8044,
            wait_timeout_s=2.0, poll_interval_s=0.05,
        )
        assert handle.port == 8044
        # I17: spawned child sees OPENTEAM_AUTO_LAUNCH=0
        assert captured_env.get("OPENTEAM_AUTO_LAUNCH") == "0", (
            "I17 fork-bomb guard not propagated to spawned child"
        )

    def test_spawn_cmd_has_runtime_root_flag(
        self, isolated_registry, tmp_path, monkeypatch,
    ):
        """Spawned cmd must include --runtime-root for proper isolation."""
        captured_cmd: list = []

        class _FakeProc:
            pid = 12345
            returncode = 0

            def poll(self):
                return None

        def _fake_popen(cmd, env=None, **kwargs):
            captured_cmd[:] = cmd
            return _FakeProc()

        monkeypatch.setattr(subprocess, "Popen", _fake_popen)
        from openteam.client import supervisor as sup

        call_count = {"n": 0}

        def _fake_find(*, runtime_root, host, port=None):
            call_count["n"] += 1
            if call_count["n"] >= 2:
                sid = compute_server_id(runtime_root, host, port or 8045)
                return ServerHandle(
                    server_id=sid, pid=os.getpid(), host=host, port=port or 8045,
                    runtime_root=str(Path(runtime_root).resolve()),
                    server_dir_name="x", started_at="x", version="x",
                )
            return None

        monkeypatch.setattr(sup, "find_server", _fake_find)
        monkeypatch.setattr(
            "openteam.client.discovery.health_check",
            lambda *a, **kw: True,
        )

        auto_launch_server(
            runtime_root=tmp_path, host="127.0.0.1", port=8045,
            wait_timeout_s=2.0, poll_interval_s=0.05,
        )
        assert "--runtime-root" in captured_cmd
        rt_idx = captured_cmd.index("--runtime-root")
        assert captured_cmd[rt_idx + 1] == str(tmp_path)


# ── auto_launch_server: early subprocess exit ────────────────────────────────
class TestEarlyExit:
    def test_raises_when_subprocess_exits(
        self, isolated_registry, tmp_path, monkeypatch,
    ):
        class _DeadProc:
            pid = 12345
            returncode = 1

            def poll(self):
                return 1  # already exited

        monkeypatch.setattr(subprocess, "Popen", lambda *a, **kw: _DeadProc())

        from openteam.client import supervisor as sup
        monkeypatch.setattr(sup, "find_server", lambda **kw: None)

        with pytest.raises(RuntimeError, match="exited prematurely"):
            auto_launch_server(
                runtime_root=tmp_path, host="127.0.0.1", port=8046,
                wait_timeout_s=1.0, poll_interval_s=0.05,
            )
