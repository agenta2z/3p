"""TIER-1 tests for openteam.mcp_server.server.create_openteam_server."""
from __future__ import annotations

import asyncio

import pytest

from openteam.mcp_server.server import create_openteam_server


def _count_tools(server) -> int:
    return len(asyncio.run(server._local_provider.list_tools()))


class TestCreateOpenteamServer:
    def test_default_registers_all_four(self):
        server = create_openteam_server()
        assert _count_tools(server) == 4

    def test_subset_works(self):
        server = create_openteam_server(tool_names=["openteam_task"])
        assert _count_tools(server) == 1

    def test_invalid_name_raises(self):
        with pytest.raises(ValueError, match="Unknown tool names"):
            create_openteam_server(tool_names=["nonexistent"])
