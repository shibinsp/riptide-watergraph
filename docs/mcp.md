# MCP interop

Tools from external [Model Context Protocol](https://modelcontextprotocol.io) servers plug straight into
the registry — once registered they are ordinary `ToolSpec`s the worker/swarm call with no graph changes.

The core is dependency-free and testable offline via `FakeMcpClient`; the real stdio transport
(`StdioMcpClient`) needs the `[mcp]` extra.

## Register from code

```python
from riptide_watergraph import register_mcp_tools, default_registry
from riptide_watergraph.mcp.stdio import StdioMcpClient   # pip install "riptide-watergraph[mcp]"

registry = default_registry()
client = StdioMcpClient(command="npx",
                        args=["-y", "@modelcontextprotocol/server-filesystem", "/data"])
await register_mcp_tools(registry, client, prefix="fs.")   # fs.read_file, fs.write_file, ...
```

Read-only MCP tools run inline (and in parallel in swarm mode); the rest are `side_effecting` and route
through the human-approval gate. The prefix namespaces them so they never collide with local tools.

## Connect from the Studio (gated + allowlisted)

The Studio's **MCP Servers** view turns the catalog into live tools without code — but only when
`RIPTIDE_ENABLE_MCP_CONNECT=1` **and** the target server is pre-declared in the allowlist. The browser
can never launch an arbitrary command.

```bash
export RIPTIDE_ENABLE_MCP_CONNECT=1
export RIPTIDE_MCP_SERVERS='[{"name":"fs","command":"npx",
  "args":["-y","@modelcontextprotocol/server-filesystem","."],"prefix":"fs."}]'
riptide serve        # MCP Servers > Connect → fs.* tools appear everywhere; Disconnect removes them
```

Connected tools join a **dynamic-spec store** that `default_registry()` appends, so they persist across
Chat, Playground, Workflows and the Tool Runner.

| Endpoint | Purpose |
|----------|---------|
| `GET /api/mcp` | list allowlist entries + connection state |
| `POST /api/mcp/connect {name}` | connect (403 if gate off, 404 if not allowlisted) |
| `POST /api/mcp/disconnect {name}` | disconnect + unregister the tools |

See [`examples/mcp_connect.py`](https://github.com/shibinsp/riptide-watergraph/blob/main/examples/mcp_connect.py)
for an offline end-to-end demo with `FakeMcpClient`.
