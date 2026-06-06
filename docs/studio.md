# Like Water Studio

A dependency-free, vanilla-JS single-page app served by the FastAPI server. No Node build step — the
assets ship inside the wheel.

```bash
pip install "riptide-watergraph[server]"
riptide serve        # open http://127.0.0.1:8000/
```

## The 11 views

| Group | View | What it does |
|-------|------|--------------|
| **Workspace** | Chat | Conversational runs with token streaming, interactive approval, agent attribution |
| | Playground | Single task with every knob (critic, supervisor, ReAct, voting, structured output) |
| | Workflows | Drag-and-drop DAG builder — nodes are role-assigned steps, edges are dependencies |
| | History | Replay past runs from local storage |
| **Library** | Tools | Searchable, category-filtered gallery of all registered tools |
| | Roles | The role catalog with prompts + tool allow-lists |
| | Tool Runner | One-click invoke of any read-only tool |
| **Insights** | Monitoring | KPI cards, runs/cost-over-time chart, recent runs ([details](monitoring.md)) |
| | Eval | Run the eval suite and see the scored report |
| | Costs | Per-tenant usage dashboard |
| **System** | Connections | Set the AI provider / API key at runtime (in-memory, masked) |
| | MCP Servers | Connect gated, allowlisted MCP servers ([details](mcp.md)) |

## Design

Microsoft Fluent / Azure-portal look — Segoe UI, communication-blue accent, warm-neutral grays, 4px
corners, left-bar nav selection, light + dark. A colorful 🌊 wave logo and a Foundry-style Chat
empty-state with a prompt-card grid.

## Gated features

Some capabilities are **off by default** and enabled per-process via env flags (never togglable from the
browser):

| Flag | Unlocks |
|------|---------|
| `RIPTIDE_ENABLE_ENTERPRISE=1` | ~518 enterprise connector tools (~750 total in the gallery) |
| `RIPTIDE_ENABLE_EXEC=1` | code-execution dev tools (`run_python`, `run_command`, `run_tests`) |
| `RIPTIDE_ENABLE_NETWORK=1` | network utility tools (HTTP GET/HEAD, DNS, …) |
| `RIPTIDE_ENABLE_MCP_CONNECT=1` | the MCP Servers connect flow (requires an allowlist) |

## Security note

The server binds `127.0.0.1` by default and the API is unauthenticated — it is meant for local/trusted
use. Connection keys are held in memory only and masked in GET responses. Put an auth proxy in front
before exposing it.
