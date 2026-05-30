"""Adapt MCP tools into the local tool registry.

Once registered, an MCP-backed tool is an ordinary ``ToolSpec`` — the worker/swarm
call it through ``StaticToolRegistry`` exactly like a local tool. No graph changes.
"""

from __future__ import annotations

from typing import Any

import jsonschema

from ..interfaces.tools import ToolSpec
from ..tools.registry import StaticToolRegistry
from .client import McpClient, McpToolInfo


def _make_handler(client: McpClient, server_name: str, schema: dict[str, Any]):
    """Handler that delegates to the MCP server using the tool's ORIGINAL name.

    Validates arguments against the server-declared schema first, so a malformed call
    is rejected before it reaches the server (defense-in-depth even if invoked outside
    the registry, which also validates).
    """

    async def handler(**arguments: Any) -> str:
        if schema:
            jsonschema.validate(instance=arguments, schema=schema)
        return await client.call_tool(server_name, arguments)

    return handler


def mcp_tool_to_spec(
    info: McpToolInfo, client: McpClient, *, prefix: str = ""
) -> ToolSpec:
    """Map an ``McpToolInfo`` to a ``ToolSpec`` backed by ``client``.

    ``prefix`` namespaces the registered name (e.g. ``"fs."``) to avoid collisions;
    the handler still calls the server with the unprefixed name. MCP tools are
    treated as side-effecting (=> HITL approval) unless the server marks them
    read-only.
    """
    schema = info.input_schema or {"type": "object", "properties": {}}
    return ToolSpec(
        name=f"{prefix}{info.name}",
        description=info.description,
        json_schema=schema,
        side_effecting=not info.read_only,
        handler=_make_handler(client, info.name, schema),
    )


async def register_mcp_tools(
    registry: StaticToolRegistry, client: McpClient, *, prefix: str = ""
) -> list[str]:
    """Discover the client's tools, adapt them, and register them.

    Returns the registered (possibly prefixed) tool names.
    """
    names: list[str] = []
    for info in await client.list_tools():
        spec = mcp_tool_to_spec(info, client, prefix=prefix)
        registry.register(spec)
        names.append(spec.name)
    return names
