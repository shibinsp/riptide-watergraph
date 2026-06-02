"""StdioMcpClient coverage with a fake `mcp` SDK (no subprocess, no [mcp] extra).

The SDK is imported lazily inside the client, so fake `mcp` / `mcp.client.stdio` modules
in `sys.modules` let `list_tools()` / `call_tool()` run their session logic end-to-end.
`_flatten_content` is unit-tested directly.
"""

from __future__ import annotations

import contextlib
import sys
import types

import pytest

from riptide_watergraph.mcp.stdio import StdioMcpClient, _flatten_content


class _FakeSession:
    async def initialize(self):
        return None

    async def list_tools(self):
        tool = types.SimpleNamespace(
            name="echo", description="Echo text", inputSchema={"type": "object"},
            annotations=types.SimpleNamespace(readOnlyHint=True),
        )
        return types.SimpleNamespace(tools=[tool])

    async def call_tool(self, name, arguments):
        return types.SimpleNamespace(content=[types.SimpleNamespace(text="result")])


class _FakeClientSession:
    def __init__(self, read, write):
        self._read, self._write = read, write

    async def __aenter__(self):
        return _FakeSession()

    async def __aexit__(self, *exc):
        return False


@contextlib.asynccontextmanager
async def _fake_stdio_client(params):
    yield ("read", "write")


@pytest.fixture
def fake_mcp(monkeypatch):
    mcp_mod = types.ModuleType("mcp")
    mcp_mod.StdioServerParameters = lambda **kw: types.SimpleNamespace(**kw)
    mcp_mod.ClientSession = _FakeClientSession
    client_mod = types.ModuleType("mcp.client")
    stdio_mod = types.ModuleType("mcp.client.stdio")
    stdio_mod.stdio_client = _fake_stdio_client
    monkeypatch.setitem(sys.modules, "mcp", mcp_mod)
    monkeypatch.setitem(sys.modules, "mcp.client", client_mod)
    monkeypatch.setitem(sys.modules, "mcp.client.stdio", stdio_mod)


async def test_list_tools_maps_readonly(fake_mcp):
    client = StdioMcpClient("npx", ["server"], {"E": "1"})
    infos = await client.list_tools()
    assert len(infos) == 1
    assert infos[0].name == "echo" and infos[0].read_only is True
    assert infos[0].input_schema == {"type": "object"}


async def test_call_tool_flattens_content(fake_mcp):
    client = StdioMcpClient("npx")
    assert await client.call_tool("echo", {"text": "hi"}) == "result"


def test_flatten_content_object_and_dict_blocks():
    blocks = [
        types.SimpleNamespace(text="a"),
        {"text": "b"},
        types.SimpleNamespace(text=None),  # skipped
        {"other": "c"},                    # skipped
    ]
    assert _flatten_content(blocks) == "a\nb"
    assert _flatten_content([]) == ""
