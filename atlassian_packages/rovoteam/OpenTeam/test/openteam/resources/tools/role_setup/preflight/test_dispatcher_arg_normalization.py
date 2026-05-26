"""Preflight: CLI dispatcher argument normalization (Option D fix).

Verifies CLI argument dashes are normalized to underscores by the dispatcher,
with NO dash-prefixed keys lingering in the arguments dict.

Regression test for the Option D fix in:
  * ``tool_cli.run_cli`` (argparse → normalized dict)
  * ``manager_websocket_routes._parse_slash_args`` (slash command parser)

Critical for role_setup: ``--max-facets`` and ``--max-inner-facets`` MUST
arrive as ``max_facets`` and ``max_inner_facets`` (the executor reads them
in canonical underscore form to pass to the outer + inner BTAs).

Runtime: ~2s, no LLM cost.
"""

from __future__ import annotations


def test_dispatcher_arg_normalization(tmp_path):
    """Verify all CLI args reach the executor as canonical underscore keys."""
    # Capture the arguments dict the executor receives
    captured = {}

    def stub_execute(arguments, session_context=None):
        captured.update(arguments)

    import openteam.server.resources.tools.role_setup.executor as rs_exec
    real_execute = rs_exec.execute
    rs_exec.execute = stub_execute
    try:
        from openteam.server.resources.tools.role_setup.cli import (
            main as role_setup_main,
        )

        # Create a fake role document for the positional arg
        fake_role_doc = tmp_path / "fake_role.md"
        fake_role_doc.write_text("# Senior Engineer\nFake role document for arg-normalization test.\n")

        # Run with argparse-style CLI args (mixed dash + positional)
        argv = [
            "--max-facets", "8",
            "--max-inner-facets", "5",
            str(fake_role_doc),  # role_document_path (positional)
        ]
        try:
            role_setup_main(argv)
        except SystemExit:
            pass  # CLI may sys.exit; we only care about captured args

        # Verify canonical underscore keys present
        for expected_key, expected_value in [
            ("max_facets", 8),
            ("max_inner_facets", 5),
            ("role_document_path", str(fake_role_doc)),
        ]:
            assert expected_key in captured, (
                f"{expected_key} missing from arguments. "
                f"Got keys: {list(captured.keys())}"
            )
            actual = captured.get(expected_key)
            # int args might arrive as int or str depending on dispatcher
            if isinstance(expected_value, int):
                assert actual in (expected_value, str(expected_value)), (
                    f"{expected_key} should be {expected_value}, got {actual!r}"
                )
            else:
                assert actual == expected_value, (
                    f"{expected_key} mismatch: {actual!r}"
                )

        # CRITICAL: verify NO dash-prefixed/dashed keys lingering
        dash_keys = [
            k for k in captured.keys() if k.startswith("-") or "-" in k
        ]
        assert not dash_keys, (
            f"Dash-prefixed/dashed keys must not appear in arguments dict. "
            f"Got: {dash_keys}. All keys: {list(captured.keys())}"
        )
    finally:
        rs_exec.execute = real_execute
