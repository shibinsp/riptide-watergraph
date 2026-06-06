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
- **mcp_connect.py** — end-to-end MCP connect/disconnect against a `FakeMcpClient` (the gated Studio flow, offline).

### Real-model examples (need an API key)

```bash
pip install -e ".[all]"
export OPENAI_API_KEY=sk-...                       # or ANTHROPIC_API_KEY
export RIPTIDE_WATERGRAPH_MODEL=gpt-4o-mini        # any LiteLLM model string
python examples/real_model_chat.py "What is the capital of France?"
python examples/real_model_eval.py                 # or: riptide eval
```

- **real_model_chat.py** — run one task through the library against a live LLM (`run_task(offline=False)`).
- **real_model_eval.py** — score the full eval suite against a live model (`EvalRunner(offline=False)`).
