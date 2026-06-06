# Install

Riptide-Watergraph is on PyPI. The core is dependency-light; heavier integrations are optional extras
imported lazily.

## Core

```bash
pip install riptide-watergraph
```

This gives you the graph engine, the 238-tool registry, the 219-role catalog, memory, guardrails, the
swarm composer, the eval harness, and the `riptide` CLI — all runnable offline with the deterministic
`DemoGateway`.

## Extras

| Extra | Installs | For |
|-------|----------|-----|
| `[server]` | FastAPI + uvicorn | `riptide serve` + the Like Water Studio web UI |
| `[litellm]` | litellm | running against a real LLM (any OpenAI-compatible provider) |
| `[mcp]` | mcp SDK | the real MCP stdio transport (`StdioMcpClient`) |
| `[observability]` | OpenTelemetry + Langfuse | per-LLM-call tracing spans |
| `[pgvector]` | langchain-postgres + psycopg | the Postgres/pgvector memory backend |
| `[all]` | litellm + observability + mcp + server | everything for a real-model, traced, served run |
| `[dev]` | pytest, ruff, mypy, httpx | contributing |

```bash
pip install "riptide-watergraph[server]"     # web UI
pip install "riptide-watergraph[all]"        # the lot
```

## From source

```bash
git clone https://github.com/shibinsp/riptide-watergraph.git
cd riptide-watergraph
pip install -e ".[dev,server]"
```

## Verify

```bash
riptide run "What is 21 * 2?" --offline
riptide eval --offline          # 4/4 = 100%
```

## Docker

```bash
docker build -t riptide-watergraph .
docker run -p 8000:8000 riptide-watergraph     # then open http://localhost:8000/
```

See [Deploy](deploy.md) for Docker Compose and hosting notes.
