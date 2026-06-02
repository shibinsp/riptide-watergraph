"""Live MCP stdio smoke test — runs only when RIPTIDE_TEST_MCP_CMD is set (skipped in CI).

    pip install -e ".[mcp]"
    # a real MCP server, e.g. the reference filesystem server (needs Node/npx):
    export RIPTIDE_TEST_MCP_CMD='npx -y @modelcontextprotocol/server-filesystem .'
    pytest tests/test_mcp_stdio_live.py

CI has no server, so this is skipped there; StdioMcpClient is covered offline by
tests/test_mcp_stdio.py (faked SDK).
"""

from __future__ import annotations

import os
import shlex

import pytest

from riptide_watergraph.mcp.stdio import StdioMcpClient

pytestmark = pytest.mark.skipif(
    not os.getenv("RIPTIDE_TEST_MCP_CMD"),
    reason="set RIPTIDE_TEST_MCP_CMD='<command> <args...>' (and install [mcp] + the server) to run",
)


async def test_live_list_tools():
    parts = shlex.split(os.environ["RIPTIDE_TEST_MCP_CMD"])
    client = StdioMcpClient(parts[0], parts[1:])
    tools = await client.list_tools()
    assert isinstance(tools, list)
    if tools:
        assert tools[0].name
