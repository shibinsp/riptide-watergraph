# Deploy

The server is a pure-Python FastAPI app — no compiler, no Node build. The Studio assets ship inside the
wheel.

## Docker

A `Dockerfile` is included (installs `.[server]`, runs `riptide serve` on `0.0.0.0:8000`):

```bash
docker build -t riptide-watergraph .
docker run -p 8000:8000 riptide-watergraph        # http://localhost:8000/
```

For a real model, pass a key and install the extra (or extend the image):

```bash
docker run -e OPENAI_API_KEY=sk-... -e RIPTIDE_WATERGRAPH_MODEL=gpt-4o-mini \
  -p 8000:8000 riptide-watergraph
```

## Docker Compose

A `docker-compose.yml` mounts a named volume for `DATA_DIR` (so memory + the usage log persist) and reads
env from your shell or a `.env` file:

```bash
docker compose up --build        # http://localhost:8000/
```

```yaml
services:
  studio:
    build: .
    ports: ["8000:8000"]
    environment:
      RIPTIDE_WATERGRAPH_DISABLE_TRACING: "1"
      DATA_DIR: "/data"
      # OPENAI_API_KEY / RIPTIDE_WATERGRAPH_MODEL for a real model
    volumes:
      - riptide-data:/data
volumes:
  riptide-data:
```

## Other hosts

- **Render / Railway / Fly.io** — deploy the Docker image; expose port 8000; set env vars in the
  dashboard; attach a persistent volume at your `DATA_DIR` if you want memory to survive restarts.
- **Any container platform** — the image is a standard `python:3.13-slim` + `riptide serve`.

Bind the public listener behind an auth proxy — the API is unauthenticated.

## Configuration reference

All settings are environment variables (pydantic-settings; a `.env` file also works).

| Variable | Default | Purpose |
|----------|---------|---------|
| `RIPTIDE_WATERGRAPH_MODEL` | `gpt-4o-mini` | default LiteLLM model string |
| `PLANNER_MODEL` / `WORKER_MODEL` | (model) | optional per-role model routing |
| `DATA_DIR` | `.riptide_watergraph` | base dir for per-tenant memory + usage log |
| `CHECKPOINT_PATH` | `.riptide_watergraph/checkpoints.sqlite` | LangGraph SqliteSaver DB |
| `MEMORY_PATH` | `.riptide_watergraph/memory.json` | persistent lesson store |
| `WORKSPACE_DIR` | `.riptide_watergraph/workspace` | sandbox for the dev/file tools |
| `TENANT_ID` | `default` | active tenant |
| `TENANT_BUDGET_USD` | `0` (unlimited) | per-tenant spend ceiling (→ HTTP 402) |
| `RIPTIDE_MCP_SERVERS` | `[]` | JSON array — the MCP-connect allowlist |
| `RIPTIDE_WATERGRAPH_DISABLE_TRACING` | `false` | turn off OTEL/Langfuse spans |
| `LANGFUSE_PUBLIC_KEY` / `LANGFUSE_SECRET_KEY` / `LANGFUSE_HOST` | — | tracing backend |

Gated feature flags (off by default): `RIPTIDE_ENABLE_ENTERPRISE`, `RIPTIDE_ENABLE_EXEC`,
`RIPTIDE_ENABLE_NETWORK`, `RIPTIDE_ENABLE_MCP_CONNECT`.

## API keys

Keys (`OPENAI_API_KEY`, `ANTHROPIC_API_KEY`, …) are read by LiteLLM from the environment per call, or set
at runtime via the Studio **Connections** view (in-memory, masked, never written to disk).
