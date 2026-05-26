"""TIER-1 tests for openteam.client.discovery — schema + read helpers."""
from __future__ import annotations

import json
import os
from dataclasses import asdict
from pathlib import Path

import pytest

from openteam.client.discovery import (
    DISCOVERY_DIR,
    SCHEMA_VERSION,
    SERVICE_NAME,
    ServerHandle,
    compute_server_id,
    discover_servers,
    find_server,
    health_check,
    pid_alive,
)


# ── Helper for crafting registry files ───────────────────────────────────────
def _write_registry_entry(reg_dir: Path, *, server_id: str, pid: int,
                          host: str = "127.0.0.1", port: int = 8000,
                          runtime_root: str = "/tmp/rt") -> Path:
    handle = ServerHandle(
        server_id=server_id, pid=pid, host=host, port=port,
        runtime_root=runtime_root, server_dir_name="server_test",
        started_at="2026-05-18T00:00:00.000Z", version="0.1.0",
        process_command=["openteam-server", "--port", str(port)],
    )
    target = reg_dir / f"{server_id}.json"
    target.write_text(json.dumps(asdict(handle)))
    return target


# ── compute_server_id (I16) ──────────────────────────────────────────────────
class TestComputeServerId:
    def test_stable_for_same_inputs(self, tmp_path):
        a = compute_server_id(tmp_path, "127.0.0.1", 8000)
        b = compute_server_id(tmp_path, "127.0.0.1", 8000)
        assert a == b

    def test_distinct_for_different_ports(self, tmp_path):
        a = compute_server_id(tmp_path, "127.0.0.1", 8000)
        b = compute_server_id(tmp_path, "127.0.0.1", 8001)
        assert a != b

    def test_distinct_for_different_runtime_roots(self, tmp_path):
        other = tmp_path / "other"
        other.mkdir()
        a = compute_server_id(tmp_path, "127.0.0.1", 8000)
        b = compute_server_id(other, "127.0.0.1", 8000)
        assert a != b

    def test_distinct_for_different_hosts(self, tmp_path):
        a = compute_server_id(tmp_path, "127.0.0.1", 8000)
        b = compute_server_id(tmp_path, "0.0.0.0", 8000)
        assert a != b

    def test_returns_server_prefixed_12hex(self, tmp_path):
        sid = compute_server_id(tmp_path, "127.0.0.1", 8000)
        assert sid.startswith("server_")
        # 12 hex chars after "server_"
        assert len(sid) == len("server_") + 12
        assert all(c in "0123456789abcdef" for c in sid[len("server_"):])


# ── pid_alive ────────────────────────────────────────────────────────────────
class TestPidAlive:
    def test_true_for_self(self):
        assert pid_alive(os.getpid()) is True

    def test_false_for_zero(self):
        assert pid_alive(0) is False

    def test_false_for_negative(self):
        assert pid_alive(-1) is False

    def test_false_for_none(self):
        # Defensive: malformed registry entries shouldn't crash discovery.
        assert pid_alive(None) is False

    def test_false_for_dead_pid(self):
        # PID 99999999 is essentially guaranteed to be unused.
        assert pid_alive(99999999) is False


# ── health_check (I11) ───────────────────────────────────────────────────────
class TestHealthCheck:
    def test_returns_false_when_no_server(self):
        # Pick a port unlikely to be in use.
        assert health_check("127.0.0.1", 1, timeout_s=0.05) is False

    def test_returns_false_on_wrong_service(self, monkeypatch):
        # If /api/health returns 200 but no "service: openteam" field, treat as
        # impostor (R5 mitigation). Verified by monkeypatching urlopen to a fake.
        from openteam.client import discovery as disc

        class _FakeResp:
            status = 200

            def read(self):
                return b'{"status": "ok"}'  # no service field

            def __enter__(self):
                return self

            def __exit__(self, *a):
                return False

        monkeypatch.setattr(disc, "urlopen", lambda *a, **kw: _FakeResp())
        assert disc.health_check("127.0.0.1", 9999) is False

    def test_returns_true_when_service_marker_matches(self, monkeypatch):
        from openteam.client import discovery as disc

        class _FakeResp:
            status = 200

            def read(self):
                return b'{"status": "ok", "service": "openteam"}'

            def __enter__(self):
                return self

            def __exit__(self, *a):
                return False

        monkeypatch.setattr(disc, "urlopen", lambda *a, **kw: _FakeResp())
        assert disc.health_check("127.0.0.1", 9999) is True


# ── ServerHandle properties ──────────────────────────────────────────────────
class TestServerHandle:
    def test_properties(self, tmp_path):
        h = ServerHandle(
            server_id="server_abc",
            pid=12345,
            host="127.0.0.1",
            port=8000,
            runtime_root=str(tmp_path),
            server_dir_name="server_X",
            started_at="2026-05-18T00:00:00.000Z",
            version="0.1.0",
        )
        assert h.http_endpoint == "http://127.0.0.1:8000"
        assert h.ws_endpoint == "ws://127.0.0.1:8000/ws/manager"
        assert h.server_dir == tmp_path / "servers" / "server_X"
        # schema_version + service have defaults
        assert h.schema_version == SCHEMA_VERSION
        assert h.service == SERVICE_NAME
        # process_command defaults to empty list — NOT same shared object
        a = ServerHandle(
            server_id="a", pid=1, host="x", port=1, runtime_root="/", server_dir_name="x",
            started_at="x", version="x",
        )
        b = ServerHandle(
            server_id="b", pid=2, host="y", port=2, runtime_root="/", server_dir_name="y",
            started_at="y", version="y",
        )
        a.process_command.append("a")
        assert b.process_command == []


# ── DISCOVERY_DIR ────────────────────────────────────────────────────────────
class TestDiscoveryDir:
    def test_default_under_user_home(self, monkeypatch):
        monkeypatch.delenv("OPENTEAM_REGISTRY_DIR", raising=False)
        d = DISCOVERY_DIR()
        # Default: ~/.openteam/_runtime/registry
        assert d == Path.home() / ".openteam" / "_runtime" / "registry"

    def test_env_var_override(self, tmp_path, monkeypatch):
        monkeypatch.setenv("OPENTEAM_REGISTRY_DIR", str(tmp_path / "custom"))
        d = DISCOVERY_DIR()
        assert d == (tmp_path / "custom").resolve()

    def test_env_var_expands_tilde(self, monkeypatch):
        monkeypatch.setenv("OPENTEAM_REGISTRY_DIR", "~/customreg")
        d = DISCOVERY_DIR()
        assert d == (Path.home() / "customreg").resolve()


# ── discover_servers ─────────────────────────────────────────────────────────
class TestDiscoverServers:
    def test_empty_when_no_dir(self, isolated_registry, monkeypatch):
        # Remove the registry dir entirely
        import shutil
        shutil.rmtree(isolated_registry)
        assert discover_servers() == []

    def test_returns_live_entries(self, isolated_registry):
        _write_registry_entry(isolated_registry, server_id="server_aaa", pid=os.getpid())
        handles = discover_servers()
        assert len(handles) == 1
        assert handles[0].server_id == "server_aaa"

    def test_reaps_stale_dead_pid(self, isolated_registry):
        target = _write_registry_entry(
            isolated_registry, server_id="server_dead", pid=99999999
        )
        assert target.exists()
        handles = discover_servers()
        assert handles == []
        # Reaped from disk by default
        assert not target.exists()

    def test_reap_disabled_keeps_file(self, isolated_registry):
        target = _write_registry_entry(
            isolated_registry, server_id="server_dead2", pid=99999999
        )
        handles = discover_servers(reap_stale=False)
        assert handles == []
        # File still there
        assert target.exists()

    def test_skips_corrupt_json(self, isolated_registry):
        (isolated_registry / "server_bad.json").write_text("not json{{{")
        # Should not raise; should reap
        assert discover_servers() == []
        assert not (isolated_registry / "server_bad.json").exists()

    def test_skips_newer_schema(self, isolated_registry):
        (isolated_registry / "server_future.json").write_text(json.dumps({
            "server_id": "server_future",
            "pid": os.getpid(),
            "host": "127.0.0.1", "port": 8000,
            "runtime_root": "/tmp", "server_dir_name": "x",
            "started_at": "x", "version": "x",
            "schema_version": SCHEMA_VERSION + 1,  # newer
            "service": "openteam",
        }))
        # Skipped silently (forward-compat), NOT reaped (live newer server)
        assert discover_servers() == []
        assert (isolated_registry / "server_future.json").exists()

    def test_filters_by_runtime_root(self, isolated_registry, tmp_path):
        rt1 = tmp_path / "rt1"
        rt1.mkdir()
        rt2 = tmp_path / "rt2"
        rt2.mkdir()
        _write_registry_entry(isolated_registry, server_id="server_1", pid=os.getpid(),
                              runtime_root=str(rt1))
        _write_registry_entry(isolated_registry, server_id="server_2", pid=os.getpid(),
                              runtime_root=str(rt2))
        only_rt1 = discover_servers(runtime_root=rt1)
        assert len(only_rt1) == 1
        assert only_rt1[0].server_id == "server_1"

    def test_filters_by_host(self, isolated_registry):
        _write_registry_entry(isolated_registry, server_id="server_a", pid=os.getpid(),
                              host="127.0.0.1")
        _write_registry_entry(isolated_registry, server_id="server_b", pid=os.getpid(),
                              host="0.0.0.0")
        only_loopback = discover_servers(host="127.0.0.1")
        assert len(only_loopback) == 1
        assert only_loopback[0].host == "127.0.0.1"


# ── find_server ──────────────────────────────────────────────────────────────
class TestFindServer:
    def test_none_when_empty(self, isolated_registry):
        assert find_server() is None

    def test_returns_first_matching(self, isolated_registry):
        _write_registry_entry(isolated_registry, server_id="server_p1", pid=os.getpid(),
                              port=8000)
        h = find_server(port=8000)
        assert h is not None
        assert h.port == 8000

    def test_port_filter(self, isolated_registry):
        _write_registry_entry(isolated_registry, server_id="server_p8000", pid=os.getpid(),
                              port=8000)
        _write_registry_entry(isolated_registry, server_id="server_p8001", pid=os.getpid(),
                              port=8001)
        h = find_server(port=8001)
        assert h is not None
        assert h.port == 8001
