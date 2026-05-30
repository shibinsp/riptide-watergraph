# Examples

Runnable, offline (no API key) demonstrations of the library API.

```bash
pip install -e ".[dev]"
python examples/quickstart.py     # drive the full graph as a library
python examples/custom_tool.py    # register a custom tool + custom gateway
python examples/mcp_tools.py      # plug external MCP tools into the registry
```

- **quickstart.py** — `build_graph(...)` with registry + memory + composer + guardrails, run a task end-to-end with the deterministic `DemoGateway`.
- **custom_tool.py** — implement two seams at once: a custom `ToolSpec` and a scripted `ModelGateway` that calls it.
- **mcp_tools.py** — register tools from an (offline) MCP server via `FakeMcpClient`; swap in `StdioMcpClient` for a real one.

For a real model, install `.[litellm]`, set `OPENAI_API_KEY`, and replace `DemoGateway()` with `LiteLLMGateway(default_model="gpt-4o-mini")`.
