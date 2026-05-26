"""Phase 5 — end-to-end real-LLM verification for claude_cli backend.

Boots a server with --llm-backend claude_cli, creates a session, connects
to /ws/manager (mirroring the React UI), sends a single short message,
and validates that real Claude streams a response containing the answer.

Run directly (not via pytest — pytest swallows the spawned server logs):
    python -m test.openteam.server.backends.test_e2e_claude_cli

Cost: ~$0.005 (haiku-style single short message via claude_cli sonnet).

Pre-requisites:
  - claude.exe on PATH (verified via shutil.which)
  - PYTHONPATH includes OpenTeam/src + AgentFoundation/src + PythonUtils/src
"""

from __future__ import annotations

import asyncio
import json
import os
import shutil
import socket
import subprocess
import sys
import time
from pathlib import Path

import requests
import websockets

# Bootstrap sys.path
_HERE = Path(__file__).resolve()
_OPENSTARTUP = _HERE.parents[4]
_REPO_ROOT = _OPENSTARTUP.parent
for _dep in [
    _OPENSTARTUP / "src",
    _REPO_ROOT / "AgentFoundation" / "src",
    _REPO_ROOT / "PythonUtils" / "src",
]:
    p = str(_dep)
    if p not in sys.path:
        sys.path.insert(0, p)


def _free_port() -> int:
    s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    s.bind(("127.0.0.1", 0))
    port = s.getsockname()[1]
    s.close()
    return port


def _wait_for_health(port: int, timeout: float = 30.0) -> None:
    url = f"http://127.0.0.1:{port}/api/health"
    deadline = time.time() + timeout
    while time.time() < deadline:
        try:
            r = requests.get(url, timeout=1.0)
            if r.status_code == 200:
                return
        except Exception:
            pass
        time.sleep(0.4)
    raise RuntimeError(f"Server on :{port} never became healthy within {timeout}s")


async def _drive_chat(port: int, session_id: str, message: str, timeout: float = 120.0) -> str:
    """Connect to /ws/manager and send a single message; return assembled response.

    The WebSocket protocol mirrors useManagerChat.js:
      - Client first message: {"type":"connect","session_id":"..."} (per route impl)
      - Client follow-up: {"type":"message","content":"..."}
      - Server streams back a sequence of {"type":"token", "content":"..."}
        chunks, finally a {"type":"message_end", ...}.
    """
    url = f"ws://127.0.0.1:{port}/ws/manager"
    pieces: list[str] = []
    final_content = ""
    async with websockets.connect(url, max_size=8 * 1024 * 1024) as ws:
        # Handshake — init with session_id (verified at manager_websocket_routes.py:509).
        await ws.send(json.dumps({"type": "init", "session_id": session_id}))
        # Wait for session_init ack.
        ack_raw = await asyncio.wait_for(ws.recv(), timeout=10.0)
        ack = json.loads(ack_raw)
        if ack.get("type") != "session_init":
            raise RuntimeError(f"expected session_init, got {ack}")
        await ws.send(json.dumps({"type": "message", "content": message}))
        try:
            async with asyncio.timeout(timeout):
                async for raw in ws:
                    try:
                        evt = json.loads(raw)
                    except json.JSONDecodeError:
                        continue
                    et = evt.get("type")
                    if et == "token":
                        chunk = evt.get("content", "")
                        if chunk:
                            pieces.append(chunk)
                    elif et == "message_end":
                        # Server sends {"type":"message_end", "final_content":...}
                        final_content = evt.get("final_content") or "".join(pieces)
                        return final_content
                    elif et == "error":
                        raise RuntimeError(f"server error: {evt.get('message')}")
                    # ignore other event types (task_status, message_start, heartbeat, etc.)
        except TimeoutError:
            raise RuntimeError(
                f"timed out after {timeout}s waiting for message_end. "
                f"Partial content: {''.join(pieces)[:300]!r}"
            )
    return final_content or "".join(pieces)


def main() -> int:
    if shutil.which("claude") is None:
        print("SKIP: claude binary not on PATH; phase 5 requires Claude Code CLI.")
        return 77  # standard "test skipped" exit

    runtime_dir = Path("C:/temp/openstartup_e2e_runtime")
    runtime_dir.mkdir(parents=True, exist_ok=True)

    port = _free_port()
    server_dir = _OPENSTARTUP / "src" / "openteam" / "server"
    env = os.environ.copy()
    env["PYTHONPATH"] = os.pathsep.join([
        str(_OPENSTARTUP / "src"),
        str(_REPO_ROOT / "AgentFoundation" / "src"),
        str(_REPO_ROOT / "PythonUtils" / "src"),
        env.get("PYTHONPATH", ""),
    ])
    cmd = [
        sys.executable,
        "run_server.py",
        "--host", "127.0.0.1",
        "--port", str(port),
        "--real-sessions", str(runtime_dir),
        "--llm-backend", "claude_cli",
        "--llm-model", "sonnet",
    ]
    print(f"[boot] {cmd}", flush=True)
    proc = subprocess.Popen(
        cmd,
        cwd=str(server_dir),
        env=env,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
    )

    try:
        _wait_for_health(port)
        print(f"[ok] server up on :{port}", flush=True)

        # 1. Create a session
        r = requests.post(
            f"http://127.0.0.1:{port}/api/sessions",
            json={"title": "phase5-e2e"},
            timeout=10.0,
        )
        r.raise_for_status()
        body = r.json()
        sess = body.get("data") or body
        sid = sess["id"]
        print(f"[ok] session created: {sid}", flush=True)

        # 2. Set backend to claude_cli (also exercise the meta route)
        r = requests.post(
            f"http://127.0.0.1:{port}/api/sessions/{sid}/backend",
            json={"backend": "claude_cli", "model": "sonnet"},
            timeout=10.0,
        )
        r.raise_for_status()
        print(f"[ok] backend set: {r.json()}", flush=True)

        # 3. Drive a single chat turn via WebSocket
        question = "What is 2+2? Reply with only the digit, nothing else."
        print(f"[chat] sending: {question!r}", flush=True)
        t0 = time.time()
        response = asyncio.run(_drive_chat(port, sid, question, timeout=180.0))
        elapsed = time.time() - t0
        print(f"[chat] received {len(response)}B in {elapsed:.1f}s", flush=True)
        print(f"[chat] response: {response[:500]!r}", flush=True)

        # 4. Assert the answer is in there
        # Be lenient — any of "4", "four" satisfies the test
        lower = response.lower()
        if "4" not in response and "four" not in lower:
            print(
                f"FAIL: expected '4' or 'four' in response, got: {response[:300]!r}",
                file=sys.stderr,
            )
            return 1
        print("[ok] response contains the expected answer", flush=True)
        return 0

    finally:
        print("[teardown] stopping server...", flush=True)
        proc.terminate()
        try:
            proc.wait(timeout=5)
        except subprocess.TimeoutExpired:
            proc.kill()


if __name__ == "__main__":
    sys.exit(main())
