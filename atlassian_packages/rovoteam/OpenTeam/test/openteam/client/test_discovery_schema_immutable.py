"""CI preflight: ``SCHEMA_VERSION`` and ``ServerHandle`` field set are locked.

Any change to either side requires explicit edit of this test. This prevents
silent schema drift that would break older clients reading newer registry
files (or vice versa).

To bump the schema:
  1. Update SCHEMA_VERSION in openteam/client/discovery.py.
  2. Update _EXPECTED_FIELDS below to match the new field set.
  3. Document the migration in docs/SERVER_DISCOVERY.md.
"""
from __future__ import annotations

from openteam.client.discovery import SCHEMA_VERSION, SERVICE_NAME, ServerHandle


# ── Schema version sentinel ─────────────────────────────────────────────────
def test_schema_version_is_locked():
    assert SCHEMA_VERSION == 1, (
        "SCHEMA_VERSION bumped without updating this preflight. "
        "See docstring for migration steps."
    )


def test_service_name_is_openteam():
    """I11 defensive marker — clients assert this against /api/health response."""
    assert SERVICE_NAME == "openteam"


# ── ServerHandle field set sentinel ─────────────────────────────────────────
_EXPECTED_FIELDS: set[str] = {
    "server_id",
    "pid",
    "host",
    "port",
    "runtime_root",
    "server_dir_name",
    "started_at",
    "version",
    "schema_version",
    "service",
    "process_command",
}


def test_server_handle_fields_are_locked():
    actual = set(ServerHandle.__dataclass_fields__)
    extra = actual - _EXPECTED_FIELDS
    missing = _EXPECTED_FIELDS - actual
    assert not extra and not missing, (
        "ServerHandle field set drift detected.\n"
        f"  extra:   {sorted(extra)}\n"
        f"  missing: {sorted(missing)}\n"
        "Update _EXPECTED_FIELDS in this preflight after bumping SCHEMA_VERSION "
        "and documenting the migration in docs/SERVER_DISCOVERY.md."
    )
