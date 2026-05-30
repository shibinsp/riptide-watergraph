"""Real stdio MCP transport over the official ``mcp`` SDK (optional ``[mcp]`` extra).

The SDK is imported lazily so the package imports without it. This reference client
opens a fresh connection per operation, which is simple and correct but launches the
server subprocess on each call — for production, hold a persistent session (e.g. a
background event loop) and pool it. Verify SDK symbol names against your installed
``mcp`` version.
"""

from __future__ import annotations

from typing import Any

from .client import McpToolInfo


class StdioMcpClient:
    """``McpClient`` that talks to an MCP server launched as a subprocess via stdio."""

    def __init__(self, command: str, args: list[str] | None = None,
                 env: dict[str, str] | None = None) -> None:
        self.command = command
        self.args = args or []
        self.env = env

    def _server_params(self):
        from mcp import StdioServerParameters  # lazy

        return StdioServerParameters(command=self.command, args=self.args, env=self.env)

    async def _session(self):
        # Returns an async context manager yielding an initialized ClientSession.
        from contextlib import asynccontextmanager

        from mcp import ClientSession
        from mcp.client.stdio import stdio_client

        params = self._server_params()

        @asynccontextmanager
        async def _ctx():
            async with stdio_client(params) as (read, write):
                async with ClientSession(read, write) as session:
                    await session.initialize()
                    yield session

        return _ctx()

    async def list_tools(self) -> list[McpToolInfo]:
        ctx = await self._session()
        async with ctx as session:
            result = await session.list_tools()
            infos: list[McpToolInfo] = []
            for tool in result.tools:
                annotations = getattr(tool, "annotations", None)
                read_only = bool(getattr(annotations, "readOnlyHint", False))
                infos.append(
                    McpToolInfo(
                        name=tool.name,
                        description=getattr(tool, "description", "") or "",
                        input_schema=getattr(tool, "inputSchema", {}) or {},
                        read_only=read_only,
                    )
                )
            return infos

    async def call_tool(self, name: str, arguments: dict[str, Any]) -> str:
        ctx = await self._session()
        async with ctx as session:
            result = await session.call_tool(name, arguments)
            return _flatten_content(getattr(result, "content", []))


def _flatten_content(content: list[Any]) -> str:
    """Join the text of an MCP CallToolResult's content blocks."""
    parts: list[str] = []
    for block in content or []:
        text = getattr(block, "text", None)
        if text is not None:
            parts.append(text)
        elif isinstance(block, dict) and "text" in block:
            parts.append(block["text"])
    return "\n".join(parts)
