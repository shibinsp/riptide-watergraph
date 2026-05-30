"""MCP tool interop: adapt external MCP tools into the registry and the graph."""

from __future__ import annotations

import json

from langgraph.checkpoint.sqlite import SqliteSaver
from langgraph.types import Command

from riptide_watergraph import (
    FakeMcpClient,
    McpToolInfo,
    SingleAgentComposer,
    build_graph,
    register_mcp_tools,
)
from riptide_watergraph.interfaces.gateway import CompletionResult
from riptide_watergraph.tools.registry import StaticToolRegistry

from .conftest import MockGateway, tool_call


def _fake_server() -> FakeMcpClient:
    return FakeMcpClient(
        {
            "echo": (
                McpToolInfo(
                    name="echo",
                    description="Echo back the provided text",
                    input_schema={
                        "type": "object",
                        "properties": {"text": {"type": "string"}},
                        "required": ["text"],
                        "additionalProperties": False,
                    },
                    read_only=True,
                ),
                lambda text: f"echo: {text}",
            ),
            "delete_thing": (
                McpToolInfo(
                    name="delete_thing",
                    description="Delete a thing (mutating)",
                    input_schema={
                        "type": "object",
                        "properties": {"id": {"type": "string"}},
                        "required": ["id"],
                        "additionalProperties": False,
                    },
                    read_only=False,
                ),
                lambda id: f"deleted {id}",
            ),
        }
    )


async def test_register_and_invoke_mcp_tool():
    reg = StaticToolRegistry()
    names = await register_mcp_tools(reg, _fake_server())
    assert set(names) == {"echo", "delete_thing"}
    # Invocation routes through the registry to the fake server.
    assert await reg.invoke("echo", {"text": "hi"}) == "echo: hi"


async def test_read_only_maps_to_non_side_effecting():
    reg = StaticToolRegistry()
    await register_mcp_tools(reg, _fake_server())
    assert reg.get("echo").side_effecting is False
    assert reg.get("delete_thing").side_effecting is True  # conservative default


async def test_prefix_namespacing_keeps_server_name():
    reg = StaticToolRegistry()
    names = await register_mcp_tools(reg, _fake_server(), prefix="mcp.")
    assert "mcp.echo" in names
    # Registered under the prefixed name, but the call reaches the server's real name.
    assert await reg.invoke("mcp.echo", {"text": "x"}) == "echo: x"


async def test_mcp_tool_is_retrievable():
    reg = StaticToolRegistry()
    await register_mcp_tools(reg, _fake_server())
    hits = await reg.retrieve("echo back text", k=1)
    assert hits[0].name == "echo"


def test_readonly_mcp_tool_runs_in_graph():
    async def setup(reg):
        await register_mcp_tools(reg, _fake_server())

    import asyncio

    reg = StaticToolRegistry()
    asyncio.run(setup(reg))

    def responder(system: str, user: str) -> CompletionResult:
        if "planning orchestrator" in system:
            return CompletionResult(content=json.dumps(["echo the greeting"]))
        if "You are a worker" in system:
            return CompletionResult(tool_calls=[tool_call("echo", {"text": "hello"})])
        return CompletionResult(content="final")

    with SqliteSaver.from_conn_string(":memory:") as cp:
        graph = build_graph(
            gateway=MockGateway(responder),
            registry=reg,
            composer=SingleAgentComposer(model="mock"),
            model="mock",
            checkpointer=cp,
        )
        result = graph.invoke({"task": "echo"}, {"configurable": {"thread_id": "mcp"}})

    assert "__interrupt__" not in result  # read-only -> no approval needed
    assert any("echo: hello" in r["output"] for r in result["results"])


def test_side_effecting_mcp_tool_requires_approval():
    async def setup(reg):
        await register_mcp_tools(reg, _fake_server())

    import asyncio

    reg = StaticToolRegistry()
    asyncio.run(setup(reg))

    def responder(system: str, user: str) -> CompletionResult:
        if "planning orchestrator" in system:
            return CompletionResult(content=json.dumps(["delete the thing"]))
        if "You are a worker" in system:
            return CompletionResult(
                tool_calls=[tool_call("delete_thing", {"id": "42"})]
            )
        return CompletionResult(content="final")

    with SqliteSaver.from_conn_string(":memory:") as cp:
        graph = build_graph(
            gateway=MockGateway(responder),
            registry=reg,
            composer=SingleAgentComposer(model="mock"),
            model="mock",
            checkpointer=cp,
        )
        cfg = {"configurable": {"thread_id": "mcp-se"}}
        result = graph.invoke({"task": "delete"}, cfg)
        assert "__interrupt__" in result  # mutating MCP tool -> HITL gate
        result = graph.invoke(Command(resume={"approved": True}), cfg)

    assert any("deleted 42" in r["output"] for r in result["results"])
