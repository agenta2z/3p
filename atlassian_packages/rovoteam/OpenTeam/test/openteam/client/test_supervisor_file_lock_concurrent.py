"""CI preflight (I13): O_EXCL file lock serialises concurrent auto-launches.

Two threads call ``auto_launch_server`` simultaneously. Only ONE physically
spawns a subprocess; the other waits for the registry entry and returns the
same ``ServerHandle``.

We test this by counting how many times ``subprocess.Popen`` is invoked
across two parallel ``auto_launch_server`` calls. Expected: exactly 1.
"""
from __future__ import annotations

import os
import subprocess
import threading
import time
from dataclasses import asdict
from pathlib import Path

from openteam.client.discovery import ServerHandle, compute_server_id
from openteam.client.supervisor import auto_launch_server


def test_two_concurrent_launches_only_spawn_one_subprocess(tmp_path, monkeypatch):
    monkeypatch.setenv("OPENTEAM_REGISTRY_DIR", str(tmp_path / "registry"))

    spawn_count = {"n": 0}
    spawn_lock = threading.Lock()
    spawned_event = threading.Event()

    class _FakeProc:
        pid = 12345
        returncode = 0

        def poll(self):
            return None

    def _fake_popen(cmd, env=None, **kwargs):
        with spawn_lock:
            spawn_count["n"] += 1
        spawned_event.set()
        # Write the registry entry on first spawn so the wait loop in BOTH
        # threads can find it.
        import json
        reg_dir = Path(tmp_path / "registry")
        sid = compute_server_id(tmp_path, "127.0.0.1", 8100)
        handle = ServerHandle(
            server_id=sid, pid=os.getpid(), host="127.0.0.1", port=8100,
            runtime_root=str(tmp_path.resolve()),
            server_dir_name="server_test",
            started_at="2026-05-18T00:00:00.000Z", version="0.1.0",
        )
        (reg_dir / f"{sid}.json").write_text(json.dumps(asdict(handle)))
        return _FakeProc()

    monkeypatch.setattr(subprocess, "Popen", _fake_popen)
    monkeypatch.setattr(
        "openteam.client.discovery.health_check",
        lambda *a, **kw: True,
    )

    results: list[ServerHandle] = []
    errors: list[Exception] = []

    def _worker():
        try:
            h = auto_launch_server(
                runtime_root=tmp_path, host="127.0.0.1", port=8100,
                wait_timeout_s=5.0, poll_interval_s=0.05,
            )
            results.append(h)
        except Exception as e:
            errors.append(e)

    t1 = threading.Thread(target=_worker)
    t2 = threading.Thread(target=_worker)
    t1.start()
    # Stagger slightly so one is more likely to grab the lock first;
    # either order is correct (only one should spawn).
    time.sleep(0.02)
    t2.start()
    t1.join(timeout=10)
    t2.join(timeout=10)

    assert not errors, f"workers raised: {errors}"
    assert len(results) == 2
    # I13: Only ONE subprocess spawned across both calls
    assert spawn_count["n"] == 1, (
        f"FILE LOCK FAILED: {spawn_count['n']} subprocesses spawned for "
        f"concurrent ensure_server calls; expected exactly 1 (I13 violation)."
    )
    # Both calls converged on the same server_id
    assert results[0].server_id == results[1].server_id
