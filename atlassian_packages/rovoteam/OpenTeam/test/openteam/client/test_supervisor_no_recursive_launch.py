"""CI preflight (I17): auto-launched server cannot recursively auto-launch.

Two enforcement points (BOTH must hold):

1. ``auto_launch_server`` MUST set ``OPENTEAM_AUTO_LAUNCH=0`` in the spawned
   subprocess's env. (Tested via subprocess.Popen capture.)

2. ``ensure_server`` MUST refuse to auto-launch when it sees
   ``OPENTEAM_AUTO_LAUNCH=0`` in its own env. (Tested directly.)

Together these form an in-depth defense against accidental fork bombs if a
future server-side helper ever imports ``openteam.client``.
"""
from __future__ import annotations

import os
import subprocess
from pathlib import Path

import pytest

from openteam.client.discovery import ServerHandle, compute_server_id
from openteam.client.supervisor import (
    NoServerAvailable,
    auto_launch_server,
    ensure_server,
)


def test_spawned_child_env_includes_no_autolaunch(tmp_path, monkeypatch):
    """Enforcement #1: spawned env explicitly sets the guard."""
    monkeypatch.setenv("OPENTEAM_REGISTRY_DIR", str(tmp_path / "registry"))

    captured_env: dict = {}

    class _FakeProc:
        pid = 12345
        returncode = 0

        def poll(self):
            return None

    def _fake_popen(cmd, env=None, **kwargs):
        captured_env.update(env or {})
        return _FakeProc()

    monkeypatch.setattr(subprocess, "Popen", _fake_popen)

    # Mock find_server so the wait loop exits on second iteration
    from openteam.client import supervisor as sup
    call_count = {"n": 0}

    def _fake_find(*, runtime_root, host, port=None):
        call_count["n"] += 1
        if call_count["n"] >= 2:
            sid = compute_server_id(runtime_root, host, port or 8099)
            return ServerHandle(
                server_id=sid, pid=os.getpid(), host=host, port=port or 8099,
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
        runtime_root=tmp_path, host="127.0.0.1", port=8099,
        wait_timeout_s=2.0, poll_interval_s=0.05,
    )
    assert captured_env.get("OPENTEAM_AUTO_LAUNCH") == "0", (
        "FORK-BOMB GUARD MISSING: auto_launch_server did NOT set "
        "OPENTEAM_AUTO_LAUNCH=0 in the spawned subprocess env. "
        "This violates Invariant I17."
    )


@pytest.mark.asyncio
async def test_ensure_server_refuses_when_guard_set(tmp_path, monkeypatch):
    """Enforcement #2: ensure_server refuses to auto-launch if guard is set."""
    monkeypatch.setenv("OPENTEAM_REGISTRY_DIR", str(tmp_path / "registry"))
    monkeypatch.setenv("OPENTEAM_AUTO_LAUNCH", "0")
    with pytest.raises(NoServerAvailable, match="OPENTEAM_AUTO_LAUNCH=0"):
        await ensure_server(
            runtime_root=tmp_path, host="127.0.0.1", port=8000,
            auto_launch=True,
        )
