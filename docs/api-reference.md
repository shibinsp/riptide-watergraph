# HTTP API

The FastAPI server (`riptide serve`, the `[server]` extra) exposes the routes below. It binds
`127.0.0.1:8000` by default and serves the Studio SPA at `/`. Interactive OpenAPI docs are at `/docs`.

!!! warning
    The API is unauthenticated and meant for local/trusted use. Put an auth proxy in front before
    exposing it.

## Core run

| Method | Path | Purpose |
|--------|------|---------|
| `GET` | `/healthz` | liveness probe |
| `POST` | `/run` | run a task → `RunResult` (all knobs: critic, supervisor, react_steps, vote_k, sampling, final_schema) |
| `GET` | `/run/stream` | SSE — stream the final answer word-by-word |
| `GET` | `/api/run/trace` | SSE — live node trace then the final `RunResult` |

## Streaming & interactive HITL

| Method | Path | Purpose |
|--------|------|---------|
| `GET` | `/api/chat/stream` | SSE — token-by-token chat (`stream_chat_tokens`) |
| `POST` | `/api/run/interactive` | run with `auto_approve=False`; returns `pending_approval` or a `RunResult` |
| `POST` | `/api/run/{thread_id}/resume` | approve/deny (or answer a clarification) and continue |

## Sessions

| Method | Path | Purpose |
|--------|------|---------|
| `POST` | `/sessions/{id}/messages` | append a turn; run with the session's history |
| `GET` | `/sessions/{id}` | the transcript |
| `GET` | `/api/sessions/{id}/messages/stream` | SSE — node trace; appends the turn on completion |
| `DELETE` | `/sessions/{id}` | clear the session |

## Catalog & insights

| Method | Path | Purpose |
|--------|------|---------|
| `GET` | `/api/meta` | version, knob defaults, models, tool/role counts, connection + mcp summary |
| `GET` | `/api/tools` · `/api/roles` | the tool / role catalogs |
| `POST` | `/api/tools/{name}/invoke` | run a **read-only** tool (side-effecting → 400) |
| `POST` | `/api/eval` | run the eval suite → `EvalReport` |
| `GET` | `/api/costs` · `/api/monitoring` | per-tenant costs / aggregated monitoring |

## Connections

| Method | Path | Purpose |
|--------|------|---------|
| `GET` | `/api/connection` | provider/model/status (key masked, never echoed) |
| `POST` | `/api/connection` | set provider + model + key (in-memory; mirrors to env) |
| `POST` | `/api/connection/test` | ping the configured gateway |

## MCP

| Method | Path | Purpose |
|--------|------|---------|
| `GET` | `/api/mcp` | allowlist entries + connection state |
| `POST` | `/api/mcp/connect` · `/api/mcp/disconnect` | connect/disconnect a gated, allowlisted server |

## Workflows

| Method | Path | Purpose |
|--------|------|---------|
| `GET`/`POST` | `/api/workflows` | list / save (upsert) |
| `GET`/`DELETE` | `/api/workflows/{name}` | load / delete |
| `POST` | `/api/workflows/run` | run a spec → `RunResult` |
| `GET` | `/api/workflows/run/stream` | run with an SSE node trace |

## Status codes

- `402` — a per-tenant budget ceiling was exceeded (`BudgetExceeded`)
- `422` — invalid workflow spec (cycle, dangling edge, …) or request body
- `400` — bad tool args / a side-effecting tool on the read-only invoke path / a resume error
- `404` — unknown tool / workflow / MCP server
- `403` — MCP connect with the gate off
