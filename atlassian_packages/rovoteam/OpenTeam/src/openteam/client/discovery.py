"""Server discovery: read-side helpers + schema authority.

This module is the **schema authority** for the discovery file format.
``openteam.server._register`` imports schema constants from here — the only
allowed client→server reverse import per Invariant I14.

The discovery directory is a Jupyter-style per-server JSON registry under
``~/.openteam/_runtime/registry/`` (default). A live server writes its own
``<server_id>.json`` on startup; clients reap stale entries on every read.

Atomic writes use ``tempfile.mkstemp + os.replace`` (POSIX-atomic rename).
Readers never see torn JSON.
"""
from __future__ import annotations

import contextlib
import errno
import hashlib
import json
import logging
import os
from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional
from urllib.error import URLError
from urllib.request import urlopen

_logger = logging.getLogger(__name__)

# ── Schema constants ─────────────────────────────────────────────────────────
SCHEMA_VERSION = 1
SERVICE_NAME = "openteam"  # I11: assert /api/health["service"] matches

# Default discovery directory. Overridable via the ``OPENTEAM_REGISTRY_DIR``
# env var for test isolation, multi-user systems, and sandboxed environments.
# Co-located under ~/.openteam/_runtime/ so all OpenTeam state lives under one
# user-home tree by default, while remaining INDEPENDENT of any per-server
# runtime_root (so one registry sees N servers with N runtime roots).
_DEFAULT_REGISTRY_REL = Path(".openteam") / "_runtime" / "registry"


def DISCOVERY_DIR() -> Path:
    """Where discovery files live. Overridable via ``OPENTEAM_REGISTRY_DIR``.

    Returned as a function (not a module-level constant) so test fixtures
    using ``monkeypatch.setenv`` take effect even when the module was imported
    before the test set the env var.
    """
    base = os.environ.get("OPENTEAM_REGISTRY_DIR")
    if base:
        return Path(base).expanduser().resolve()
    return Path.home() / _DEFAULT_REGISTRY_REL


def compute_server_id(runtime_root: str | Path, host: str, port: int) -> str:
    """Deterministic id from ``(runtime_root, host, port)`` — Invariant I16.

    Triple-keyed: dev (port 8000) + staging (port 8001) on the same host get
    distinct ids; different OpenTeam checkouts get distinct ids regardless
    of port. Returns ``"server_<12 hex chars>"``.
    """
    key = f"{Path(runtime_root).resolve()}|{host}|{port}"
    return f"server_{hashlib.sha256(key.encode()).hexdigest()[:12]}"


def pid_alive(pid: int | None) -> bool:
    """Cross-platform PID liveness via ``os.kill(pid, 0)``.

    Returns False for None/0/negative pids (defensive: malformed registry
    entries shouldn't raise). Returns True on ``EPERM`` — the process exists
    but we don't have permission to signal it (multi-user / Docker case).
    """
    if not isinstance(pid, int) or pid <= 0:
        return False
    try:
        os.kill(pid, 0)
        return True
    except OSError as e:
        # EPERM ⇒ process exists, we just can't signal it.
        return e.errno == errno.EPERM


def health_check(host: str, port: int, *, timeout_s: float = 0.2) -> bool:
    """``GET /api/health``; return True iff HTTP 200 AND ``service: openteam`` (I11).

    Hard-coded to ``http://`` because v1 is loopback-only (POST-4 covers
    multi-host federation with TLS).
    """
    url = f"http://{host}:{port}/api/health"
    try:
        with urlopen(url, timeout=timeout_s) as resp:
            if not (200 <= resp.status < 300):
                return False
            body = json.loads(resp.read())
            return body.get("service") == SERVICE_NAME
    except (URLError, OSError, TimeoutError, json.JSONDecodeError):
        return False


# ── ServerHandle dataclass = wire format ─────────────────────────────────────
@dataclass(frozen=True)
class ServerHandle:
    """Live-server descriptor. Also the on-disk wire format via ``asdict``.

    The dataclass fields are the *complete* set of fields written to / read
    from ``<discovery_dir>/<server_id>.json``. ``test_discovery_schema_immutable``
    asserts this field set is unchanged across releases without an explicit
    SCHEMA_VERSION bump.
    """
    server_id: str
    pid: int
    host: str
    port: int
    runtime_root: str          # absolute path on the server's filesystem
    server_dir_name: str       # basename (movable across runtime_root reorgs)
    started_at: str            # ISO 8601 UTC with milliseconds
    version: str               # OpenTeam package version
    schema_version: int = SCHEMA_VERSION
    service: str = SERVICE_NAME
    # ``process_command`` (sys.argv at register time) supports a future
    # ``openteam-server stop <server_id>`` (POST-2) without re-parsing config.
    # Round-7 M3 fix.
    process_command: list[str] = field(default_factory=list)

    @property
    def server_dir(self) -> Path:
        return Path(self.runtime_root) / "servers" / self.server_dir_name

    @property
    def http_endpoint(self) -> str:
        return f"http://{self.host}:{self.port}"

    @property
    def ws_endpoint(self) -> str:
        return f"ws://{self.host}:{self.port}/ws/manager"

    @property
    def registry_file(self) -> Path:
        return DISCOVERY_DIR() / f"{self.server_id}.json"

    def is_alive(self, *, timeout_s: float = 0.2) -> bool:
        """Triple check (I11): pid + health endpoint + service marker."""
        if not pid_alive(self.pid):
            return False
        return health_check(self.host, self.port, timeout_s=timeout_s)


# ── Read-side helpers ────────────────────────────────────────────────────────
def discover_servers(
    *,
    runtime_root: Optional[Path] = None,
    host: Optional[str] = None,
    reap_stale: bool = True,
) -> list[ServerHandle]:
    """Read all registry files; reap stale; filter; return live entries only.

    Args:
        runtime_root: if given, only return servers whose ``runtime_root``
            resolves to the same absolute path.
        host: if given, only return servers whose ``host`` matches.
        reap_stale: if True (default), delete corrupt or dead-PID entries
            from disk during the scan. Disable in read-only / dry-run flows.

    Returns servers in arbitrary order — callers that want a single result
    should use :func:`find_server`.
    """
    reg = DISCOVERY_DIR()
    if not reg.exists():
        return []

    out: list[ServerHandle] = []
    for f in reg.glob("server_*.json"):
        try:
            data = json.loads(f.read_text(encoding="utf-8"))
            # Schema-version forward compat: silently skip newer-than-known
            # entries so an upgraded server doesn't crash older clients.
            if data.get("schema_version", 0) > SCHEMA_VERSION:
                continue
            # Filter to known fields so unknown fields from newer schemas
            # don't trip ``__init__`` with unexpected kwargs.
            handle = ServerHandle(**{
                k: v for k, v in data.items()
                if k in ServerHandle.__dataclass_fields__
            })
        except (json.JSONDecodeError, TypeError, ValueError, OSError):
            _logger.warning("[discovery] corrupt registry file: %s", f)
            if reap_stale:
                with contextlib.suppress(FileNotFoundError, OSError):
                    f.unlink()
            continue

        if not pid_alive(handle.pid):
            if reap_stale:
                with contextlib.suppress(FileNotFoundError, OSError):
                    f.unlink()
            continue

        if runtime_root and Path(handle.runtime_root).resolve() != Path(runtime_root).resolve():
            continue
        if host and handle.host != host:
            continue
        out.append(handle)
    return out


def find_server(
    runtime_root: Optional[Path] = None,
    host: str = "127.0.0.1",
    port: Optional[int] = None,
) -> Optional[ServerHandle]:
    """Return the first matching live server, or None.

    Composes ``discover_servers`` + a port filter. Does NOT call
    ``handle.is_alive()`` — that's the caller's job (``discover_servers``
    already validated PID liveness; HTTP+service-marker check is the
    expensive part and is gated by the caller's use case).
    """
    handles = discover_servers(runtime_root=runtime_root, host=host)
    if port is not None:
        handles = [h for h in handles if h.port == port]
    return handles[0] if handles else None
