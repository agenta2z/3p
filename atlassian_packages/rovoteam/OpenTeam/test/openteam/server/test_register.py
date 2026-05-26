"""TIER-1 tests for openteam.server._register — discovery write hook."""
from __future__ import annotations

import json
import os
import signal
import subprocess
import sys
import time
from pathlib import Path

import pytest

from openteam.server._register import (
    ConflictError,
    register_server,
    unregister_server,
)


@pytest.fixture
def isolated_registry(tmp_path, monkeypatch):
    reg = tmp_path / "registry"
    reg.mkdir(parents=True, exist_ok=True)
    monkeypatch.setenv("OPENTEAM_REGISTRY_DIR", str(reg))
    return reg


class TestRegisterServer:
    def test_writes_atomic_file(self, isolated_registry, tmp_path):
        handle = register_server(
            runtime_root=tmp_path,
            host="127.0.0.1",
            port=8000,
            server_dir_name="server_test",
            version="0.1.0",
            process_command=["openteam-server", "--port", "8000"],
        )
        target = isolated_registry / f"{handle.server_id}.json"
        assert target.is_file()
        data = json.loads(target.read_text())
        assert data["pid"] == os.getpid()
        assert data["host"] == "127.0.0.1"
        assert data["port"] == 8000
        assert data["server_dir_name"] == "server_test"
        assert data["service"] == "openteam"
        assert data["schema_version"] == 1
        assert data["process_command"] == ["openteam-server", "--port", "8000"]

    def test_no_tmp_files_left_behind(self, isolated_registry, tmp_path):
        register_server(
            runtime_root=tmp_path, host="127.0.0.1", port=8000,
            server_dir_name="server_x", process_command=["x"],
        )
        leftovers = list(isolated_registry.glob("*.tmp"))
        assert leftovers == [], f"tmp files leaked: {leftovers}"

    def test_overwrites_stale_pid_entry(self, isolated_registry, tmp_path):
        # Pre-write an entry with a dead PID
        sid_file = isolated_registry / "server_zzz.json"
        sid_file.write_text(json.dumps({
            "server_id": "server_zzz",
            "pid": 99999999,  # dead
            "host": "127.0.0.1", "port": 8000,
            "runtime_root": str(tmp_path), "server_dir_name": "x",
            "started_at": "x", "version": "x",
            "schema_version": 1, "service": "openteam",
            "process_command": [],
        }))
        # New registration on the same (rt,host,port) — different server_id since
        # the deterministic id is based on the triple. Compute it ourselves
        # to verify overwrite.
        handle = register_server(
            runtime_root=tmp_path, host="127.0.0.1", port=8000,
            server_dir_name="server_alive",
            process_command=["x"],
        )
        # The conflict check is keyed by handle.registry_file (a path based
        # on handle.server_id). To exercise the overwrite-stale path we must
        # pre-write a stale entry at THAT exact filename:
        sid_file.unlink()  # clean up our distractor
        stale_target = handle.registry_file
        stale_target.write_text(json.dumps({
            "server_id": handle.server_id, "pid": 99999999,
            "host": "127.0.0.1", "port": 8000,
            "runtime_root": str(tmp_path), "server_dir_name": "old",
            "started_at": "old", "version": "old",
            "schema_version": 1, "service": "openteam",
            "process_command": [],
        }))
        # Re-register — should overwrite, not raise
        handle2 = register_server(
            runtime_root=tmp_path, host="127.0.0.1", port=8000,
            server_dir_name="server_alive",
            process_command=["x"],
        )
        data = json.loads(handle2.registry_file.read_text())
        assert data["pid"] == os.getpid()  # ours, not the stale 99999999

    def test_overwrites_corrupt_entry(self, isolated_registry, tmp_path):
        # Compute the deterministic id first
        from openteam.client.discovery import compute_server_id
        sid = compute_server_id(tmp_path, "127.0.0.1", 8000)
        (isolated_registry / f"{sid}.json").write_text("not json{{{")
        # Should NOT raise; should overwrite
        handle = register_server(
            runtime_root=tmp_path, host="127.0.0.1", port=8000,
            server_dir_name="server_x", process_command=["x"],
        )
        data = json.loads(handle.registry_file.read_text())
        assert data["pid"] == os.getpid()

    def test_raises_on_conflict_with_live_pid(self, isolated_registry, tmp_path):
        # Use our own pid → triggers "same pid" branch (no conflict). Use a
        # *different* live pid to actually trigger ConflictError.
        # We can't easily reserve another live pid without spawning, so spawn
        # a sleep subprocess.
        sleeper = subprocess.Popen([sys.executable, "-c", "import time; time.sleep(30)"])
        try:
            # Pre-write registry entry claiming the sleeper owns this triple.
            from openteam.client.discovery import compute_server_id
            sid = compute_server_id(tmp_path, "127.0.0.1", 8000)
            (isolated_registry / f"{sid}.json").write_text(json.dumps({
                "server_id": sid, "pid": sleeper.pid,
                "host": "127.0.0.1", "port": 8000,
                "runtime_root": str(tmp_path), "server_dir_name": "x",
                "started_at": "x", "version": "x",
                "schema_version": 1, "service": "openteam",
                "process_command": [],
            }))
            with pytest.raises(ConflictError, match="already registered"):
                register_server(
                    runtime_root=tmp_path, host="127.0.0.1", port=8000,
                    server_dir_name="server_y", process_command=["x"],
                )
        finally:
            sleeper.terminate()
            sleeper.wait(timeout=2)


class TestUnregisterServer:
    def test_idempotent(self, isolated_registry, tmp_path):
        h = register_server(
            runtime_root=tmp_path, host="127.0.0.1", port=8002,
            server_dir_name="x", process_command=["x"],
        )
        unregister_server(h.registry_file)
        assert not h.registry_file.exists()
        # Second call should not raise
        unregister_server(h.registry_file)


class TestSignalHandlerCleanup:
    """SIGTERM / SIGINT handler removes the registry file on shutdown.

    Spawns a subprocess that registers, sleeps, then receives SIGTERM. Verifies
    the registry file is gone afterwards.
    """

    def test_sigterm_removes_registry(self, tmp_path):
        reg = tmp_path / "registry"
        reg.mkdir(parents=True, exist_ok=True)
        rt = tmp_path / "rt"
        rt.mkdir()
        child_script = f"""
import os, signal, sys, time
os.environ["OPENTEAM_REGISTRY_DIR"] = {str(reg)!r}
sys.path.insert(0, {str(Path(__file__).parent.parent.parent.parent.parent / 'src')!r})
from openteam.server._register import register_server
h = register_server(
    runtime_root={str(rt)!r}, host="127.0.0.1", port=8123,
    server_dir_name="server_smoke", process_command=["smoke"],
)
print(str(h.registry_file), flush=True)
time.sleep(30)
"""
        proc = subprocess.Popen(
            [sys.executable, "-c", child_script],
            stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True,
        )
        try:
            # Wait for the child to print its registry path (signals it's ready)
            registry_path = ""
            deadline = time.monotonic() + 5.0
            while time.monotonic() < deadline:
                line = proc.stdout.readline()
                if line:
                    registry_path = line.strip()
                    break
                time.sleep(0.05)
            assert registry_path, "child did not print registry path"
            assert Path(registry_path).is_file(), f"registry file not created: {registry_path}"

            # Send SIGTERM
            proc.send_signal(signal.SIGTERM)
            try:
                proc.wait(timeout=3)
            except subprocess.TimeoutExpired:
                proc.kill()
                pytest.fail("child did not exit within 3s of SIGTERM")

            # Registry file should be gone (signal handler cleaned up)
            assert not Path(registry_path).exists(), (
                f"registry file still present after SIGTERM: {registry_path}"
            )
        finally:
            if proc.poll() is None:
                proc.kill()
                proc.wait()
