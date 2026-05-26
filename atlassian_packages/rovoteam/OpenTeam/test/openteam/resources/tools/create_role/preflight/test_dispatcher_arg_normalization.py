"""Preflight: CLI dispatcher argument normalization (Option D fix).

Verifies CLI argument dashes are normalized to underscores by the dispatcher,
with NO dash-prefixed keys lingering in the arguments dict.

Regression test for the Option D fix in:
  * ``tool_cli.run_cli`` (argparse → normalized dict)
  * ``manager_websocket_routes._parse_slash_args`` (slash command parser)

Runtime: ~2s, no LLM cost.
"""

from __future__ import annotations


def test_dispatcher_arg_normalization():
    """Verify all CLI args reach the executor as canonical underscore keys."""
    # Capture the arguments dict the executor receives
    captured = {}

    def stub_execute(arguments, session_context=None):
        captured.update(arguments)

    import openteam.server.resources.tools.create_role.executor as cr_exec
    real_execute = cr_exec.execute
    cr_exec.execute = stub_execute
    try:
        from openteam.server.resources.tools.create_role.cli import (
            main as create_role_main,
        )

        # Run with argparse-style CLI args (mixed dash + positional)
        # Note: --output-path was removed 2026-05-18; canonical deliverable
        # now surfaces inside the workspace as final_deliverables/role_document.md
        argv = [
            "--max-facets", "3",
            "Senior Engineer",  # role_description (positional)
        ]
        try:
            create_role_main(argv)
        except SystemExit:
            pass  # CLI may sys.exit; we only care about captured args

        # Verify canonical underscore keys present
        assert "max_facets" in captured, (
            f"max_facets missing from arguments. "
            f"Got keys: {list(captured.keys())}"
        )
        assert captured.get("max_facets") in (3, "3"), (
            f"max_facets should be 3, got {captured.get('max_facets')!r}"
        )
        assert "role_description" in captured, (
            f"role_description missing. Got keys: {list(captured.keys())}"
        )
        assert captured.get("role_description") == "Senior Engineer", (
            f"role_description mismatch: {captured.get('role_description')!r}"
        )

        # CRITICAL: verify NO dash-prefixed keys lingering
        dash_keys = [
            k for k in captured.keys() if k.startswith("-") or "-" in k
        ]
        assert not dash_keys, (
            f"Dash-prefixed/dashed keys must not appear in arguments dict. "
            f"Got: {dash_keys}. All keys: {list(captured.keys())}"
        )
    finally:
        cr_exec.execute = real_execute
