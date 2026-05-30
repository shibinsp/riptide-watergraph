"""Transport-agnostic MCP client seam.

An ``McpClient`` is anything that can list and call tools on an MCP (Model Context
Protocol) server. The framework only depends on this protocol; concrete transports
(stdio over the official ``mcp`` SDK, or an in-memory fake for tests) implement it.
"""

from __future__ import annotations

from typing import Any, Awaitable, Callable, Protocol, runtime_checkable

from pydantic import BaseModel, Field


class McpToolInfo(BaseModel):
    """A tool as advertised by an MCP server."""

    name: str
    description: str = ""
    input_schema: dict[str, Any] = Field(default_factory=dict)
    # MCP `readOnlyHint`. False (the safe default) => the tool needs human approval.
    read_only: bool = False


@runtime_checkable
class McpClient(Protocol):
    """Minimal MCP client surface the adapter needs."""

    async def list_tools(self) -> list[McpToolInfo]: ...

    async def call_tool(self, name: str, arguments: dict[str, Any]) -> str: ...


class FakeMcpClient:
    """In-memory MCP client — proves pluggability without a running server.

    Built from ``{name: (McpToolInfo, handler)}`` where ``handler(**arguments)``
    returns the tool result (sync or awaitable). Used by tests and demos.
    """

    def __init__(
        self,
        tools: dict[str, tuple[McpToolInfo, Callable[..., Any | Awaitable[Any]]]],
    ) -> None:
        self._tools = tools

    async def list_tools(self) -> list[McpToolInfo]:
        return [info for info, _ in self._tools.values()]

    async def call_tool(self, name: str, arguments: dict[str, Any]) -> str:
        if name not in self._tools:
            raise KeyError(f"unknown MCP tool: {name!r}")
        _, handler = self._tools[name]
        result = handler(**arguments)
        if hasattr(result, "__await__"):
            result = await result
        return str(result)
