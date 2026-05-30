"""Plug external MCP tools into the registry (offline demo with a fake server).

Swap ``FakeMcpClient`` for ``StdioMcpClient`` (needs the ``[mcp]`` extra) to talk to a
real MCP server — the rest is identical.

Run: python examples/mcp_tools.py
"""

from __future__ import annotations

import asyncio

from riptide_watergraph import FakeMcpClient, McpToolInfo, register_mcp_tools
from riptide_watergraph.tools import default_registry


def main() -> None:
    registry = default_registry()

    client = FakeMcpClient(
        {
            "echo": (
                McpToolInfo(
                    name="echo",
                    description="Echo back the provided text.",
                    input_schema={
                        "type": "object",
                        "properties": {"text": {"type": "string"}},
                        "required": ["text"],
                        "additionalProperties": False,
                    },
                    read_only=True,  # read-only => runs inline (no approval gate)
                ),
                lambda text: f"echo: {text}",
            ),
        }
    )

    names = asyncio.run(register_mcp_tools(registry, client, prefix="mcp."))
    print("registered MCP tools:", names)
    print("invoke mcp.echo:", asyncio.run(registry.invoke("mcp.echo", {"text": "hello"})))


if __name__ == "__main__":
    main()
