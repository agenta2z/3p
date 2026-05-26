"""TIER-2 E2E test: full server-launch → discovery → attach → tool round-trip.

Boots an OpenTeam server in a subprocess against a hermetic runtime root,
discovers it via the registry, POSTs ``/api/sessions/attach``, and verifies
the session lands at the right on-disk location. Validates the v6 unified
frontend protocol end-to-end without involving the TUI.

This is the closest thing to "would a real RovoDev TUI work against a real
OpenTeam server" that can run in CI.

SKIP CONDITIONS:
- The ``openteam-server`` console script must be installed in the venv. If
  not, the test SKIPs rather than failing (consoles scripts only land after
  ``pip install -e .``, which CI may not do for every workflow).
"""
from __future__ import annotations

import json
import os
import socket
import subprocess
import sys
import time
from pathlib import Path

import pytest

from openteam.client import (
    AttachFailed,
    attach_session_via_http,
    find_server,
)


def _pick_free_port() -> int:
    """Reserve a free port for the test server. Race-free per-test isolation."""
    with socket.socket() as s:
        s.bind(("127.0.0.1", 0))
        return s.getsockname()[1]


def _wait_for_registration(runtime_root: Path, port: int, timeout_s: float = 10.0):
    """Poll find_server() until the test server registers (or timeout)."""
    deadline = time.monotonic() + timeout_s
    while time.monotonic() < deadline:
        handle = find_server(runtime_root=runtime_root, port=port)
        if handle is not None and handle.is_alive():
            return handle
        time.sleep(0.1)
    return None


@pytest.fixture
def server_proc(tmp_path, monkeypatch):
    """Start an OpenTeam server as a subprocess; tear down on exit."""
    runtime_root = tmp_path / "rt"
    runtime_root.mkdir()
    registry_dir = tmp_path / "registry"
    registry_dir.mkdir()
    port = _pick_free_port()

    # Isolate the registry to tmp_path so we don't see any other dev server.
    env = dict(os.environ)
    env["OPENTEAM_REGISTRY_DIR"] = str(registry_dir)
    env["OPENTEAM_AUTO_LAUNCH"] = "0"  # I17 fork-bomb guard

    # Prefer the console script; fall back to python -m so the test works
    # whether or not the package was installed editable.
    import shutil
    cmd = shutil.which("openteam-server")
    if cmd is None:
        argv = [sys.executable, "-m", "openteam.server.run_server"]
    else:
        argv = [cmd]
    argv += [
        "--host", "127.0.0.1",
        "--port", str(port),
        "--runtime-root", str(runtime_root),
        "--real-sessions", str(runtime_root),
    ]

    log_file = tmp_path / "server.log"
    with open(log_file, "w") as logf:
        proc = subprocess.Popen(
            argv, env=env,
            stdout=logf, stderr=subprocess.STDOUT,
            start_new_session=True,
        )

    monkeypatch.setenv("OPENTEAM_REGISTRY_DIR", str(registry_dir))

    try:
        handle = _wait_for_registration(runtime_root, port, timeout_s=15.0)
        if handle is None:
            proc.terminate()
            log_content = log_file.read_text() if log_file.exists() else "(no log)"
            pytest.fail(
                f"server did not register within 15s. Server log:\n{log_content}"
            )
        yield {
            "proc": proc,
            "handle": handle,
            "runtime_root": runtime_root,
            "registry_dir": registry_dir,
            "port": port,
        }
    finally:
        if proc.poll() is None:
            proc.terminate()
            try:
                proc.wait(timeout=5)
            except subprocess.TimeoutExpired:
                proc.kill()
                proc.wait()


class TestUnifiedFrontendSessionE2E:
    def test_server_registers_and_health_check_passes(self, server_proc):
        handle = server_proc["handle"]
        # is_alive() checks both PID and /api/health[service]
        assert handle.is_alive() is True
        assert handle.host == "127.0.0.1"
        assert handle.port == server_proc["port"]
        # Registry file present with expected fields
        reg_file = handle.registry_file
        assert reg_file.is_file()
        data = json.loads(reg_file.read_text())
        assert data["service"] == "openteam"
        assert data["schema_version"] == 1
        # I17 fork-bomb guard was propagated (NOT to this server's own env,
        # since we set it ourselves above, but to verify the test setup is
        # consistent with what auto_launch_server would do).
        assert data["process_command"]  # non-empty

    def test_attach_creates_and_returns_session_root(self, server_proc):
        handle = server_proc["handle"]
        runtime_root = server_proc["runtime_root"]

        result = attach_session_via_http(
            handle,
            external_id="rovodev-e2e-1",
            frontend_id="rovodev",
            frontend_metadata={"workspace": "/tmp/test"},
        )
        assert result.session_id == "rovodev-e2e-1"
        assert result.created is True
        # session_root should be under runtime_root/servers/<server>/sessions/
        assert Path(result.session_root).is_dir()
        assert "rovodev-e2e-1" in result.session_root
        # And under the correct server dir
        assert handle.server_dir_name in result.session_root

    def test_attach_is_idempotent_over_http(self, server_proc):
        handle = server_proc["handle"]
        r1 = attach_session_via_http(
            handle, external_id="rovodev-e2e-idem", frontend_id="rovodev",
        )
        r2 = attach_session_via_http(
            handle, external_id="rovodev-e2e-idem", frontend_id="rovodev",
        )
        assert r1.created is True
        assert r2.created is False
        assert r1.session_id == r2.session_id
        assert r1.session_root == r2.session_root

    def test_invalid_prefix_returns_attach_failed(self, server_proc):
        handle = server_proc["handle"]
        with pytest.raises(AttachFailed):
            attach_session_via_http(
                handle, external_id="bogus-prefix-abc", frontend_id="bogus",
            )

    def test_registry_is_cleaned_on_graceful_shutdown(self, server_proc):
        """SIGTERM the server; verify the registry file disappears."""
        handle = server_proc["handle"]
        proc = server_proc["proc"]
        reg_file = handle.registry_file
        assert reg_file.is_file()
        proc.terminate()
        try:
            proc.wait(timeout=5)
        except subprocess.TimeoutExpired:
            proc.kill()
            proc.wait()
            pytest.fail("server did not shut down within 5s of SIGTERM")
        # Signal handler removed it
        assert not reg_file.exists()
