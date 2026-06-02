"""Connect an MCP server so its tools persist into *every* later run (offline demo).

This mirrors what the Studio's "MCP Servers > Connect" button does: it discovers a
server's tools and registers them in the dynamic-spec store, so they show up in every
subsequent ``default_registry()`` — i.e. across Chat, Playground, Workflows and the Tool
Runner — not just a one-off registry instance.

Swap ``FakeMcpClient`` for ``StdioMcpClient`` (needs the ``[mcp]`` extra) to talk to a
real server, e.g. ``StdioMcpClient("npx", ["-y", "@modelcontextprotocol/server-filesystem", "."])``.

Run: python examples/mcp_connect.py
"""

from __future__ import annotations

import asyncio

from riptide_watergraph import FakeMcpClient, McpToolInfo, register_mcp_tools
from riptide_watergraph.tools import (
    clear_dynamic_specs,
    default_registry,
    register_dynamic_spec,
    remove_dynamic_specs,
)
from riptide_watergraph.tools.registry import StaticToolRegistry


def main() -> None:
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

    before = len(default_registry().all_specs())

    # "Connect": discover the server's tools and persist them in the dynamic store.
    tmp = StaticToolRegistry()
    names = asyncio.run(register_mcp_tools(tmp, client, prefix="fs."))
    for spec in tmp.all_specs():
        register_dynamic_spec(spec)
    print("connected - registered:", names)

    # A brand-new registry (as the next run would build) now includes the MCP tools.
    fresh = default_registry()
    print(f"tool count: {before} -> {len(fresh.all_specs())}")
    print("invoke fs.echo:", asyncio.run(fresh.invoke("fs.echo", {"text": "hello"})))

    # "Disconnect": remove them again.
    remove_dynamic_specs(names)
    print("after disconnect:", len(default_registry().all_specs()))
    clear_dynamic_specs()


if __name__ == "__main__":
    main()
