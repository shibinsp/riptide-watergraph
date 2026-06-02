"""FastAPI service exposing the agent graph over HTTP, plus the "Like Water Studio" UI.

Endpoints:
- ``GET  /``                         — the Studio single-page app (static).
- ``GET  /healthz``                  — liveness check.
- ``POST /run``                      — run a task, return a structured result.
- ``GET  /run/stream``               — same, streamed as Server-Sent Events.
- ``POST /sessions/{sid}/messages``  — multi-turn: runs with the session's history.
- ``GET  /sessions/{sid}``           — the session's turns.
- ``GET  /api/meta``                 — defaults + models + counts to drive the UI controls.
- ``GET  /api/tools``                — the registered tool catalog.
- ``GET  /api/roles``                — the built-in agent roles.
- ``POST /api/eval``                 — run the evaluation suite, return the report.
- ``GET  /api/costs``                — per-tenant usage/cost dashboard.

Endpoints are sync ``def`` on purpose: the graph runs synchronously (each node drives
async work via ``asyncio.run``), so FastAPI executes them in its threadpool where a fresh
event loop is available. Over-budget tenants get HTTP 402.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from fastapi import FastAPI, HTTPException
from fastapi.responses import FileResponse, StreamingResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel

from ..config import get_settings
from ..evaluation import EvalReport, EvalRunner
from ..observability.cost import BudgetExceeded, CostTracker, TenantTotals, _PRICE_PER_1K
from ..service import RunResult, SessionStore, run_task
from ..swarm.roles import DEFAULT_ROLES, AgentRole
from ..tools import default_registry

_VERSION = "0.3.0"
_STATIC = Path(__file__).parent / "static"
_sessions = SessionStore()


class RunRequest(BaseModel):
    task: str
    tenant_id: str = "default"
    offline: bool = False
    memory: bool = True
    llm_composer: bool = False
    single: bool = False
    guardrails: bool = True
    critic: bool = False
    supervisor: bool = False
    react_steps: int = 1
    vote_k: int = 1
    final_schema: dict[str, Any] | None = None


class MessageRequest(BaseModel):
    task: str
    tenant_id: str = "default"
    offline: bool = False


class EvalRequest(BaseModel):
    offline: bool = True


class ToolInfo(BaseModel):
    name: str
    version: str
    description: str
    side_effecting: bool
    json_schema: dict[str, Any]


class MetaResponse(BaseModel):
    version: str
    defaults: dict[str, Any]
    models: list[str]
    current_model: str
    tool_count: int
    role_names: list[str]


def _sse(obj: dict) -> str:
    return f"data: {json.dumps(obj)}\n\n"


def create_app() -> FastAPI:
    app = FastAPI(title="riptide-watergraph", version=_VERSION)

    @app.get("/healthz")
    def healthz() -> dict:
        return {"status": "ok"}

    @app.post("/run", response_model=RunResult)
    def run(req: RunRequest) -> RunResult:
        try:
            return run_task(
                req.task,
                tenant_id=req.tenant_id,
                offline=req.offline,
                memory_on=req.memory,
                llm_composer=req.llm_composer,
                single=req.single,
                guardrails_on=req.guardrails,
                critic=req.critic,
                supervisor=req.supervisor,
                react_steps=req.react_steps,
                vote_k=req.vote_k,
                final_schema=req.final_schema,
            )
        except BudgetExceeded as exc:
            raise HTTPException(status_code=402, detail=str(exc)) from exc

    @app.get("/run/stream")
    def run_stream(task: str, tenant_id: str = "default", offline: bool = True):
        def gen():
            try:
                result = run_task(task, tenant_id=tenant_id, offline=offline)
            except BudgetExceeded as exc:
                yield _sse({"event": "error", "detail": str(exc)})
                return
            yield _sse({"event": "composition", "mode": result.mode,
                        "blocked": result.blocked})
            for word in (result.final_answer or "").split():
                yield _sse({"event": "token", "text": word})
            yield _sse({"event": "final", "answer": result.final_answer})

        return StreamingResponse(gen(), media_type="text/event-stream")

    @app.post("/sessions/{session_id}/messages", response_model=RunResult)
    def post_message(session_id: str, req: MessageRequest) -> RunResult:
        try:
            result = run_task(
                req.task,
                tenant_id=req.tenant_id,
                offline=req.offline,
                history=_sessions.history(session_id),
            )
        except BudgetExceeded as exc:
            raise HTTPException(status_code=402, detail=str(exc)) from exc
        _sessions.append(session_id, req.task, result.final_answer or "")
        return result

    @app.get("/sessions/{session_id}")
    def get_session(session_id: str) -> dict:
        return {"session_id": session_id, "turns": _sessions.turns(session_id)}

    # --- Studio data endpoints (read-only, offline-safe) ---

    @app.get("/api/meta", response_model=MetaResponse)
    def api_meta() -> MetaResponse:
        settings = get_settings()
        return MetaResponse(
            version=_VERSION,
            defaults={
                "tenant_id": settings.tenant_id,
                "offline": False,
                "memory": True,
                "guardrails": True,
                "single": False,
                "llm_composer": False,
                "critic": False,
                "supervisor": False,
                "react_steps": 1,
                "vote_k": 1,
            },
            models=list(_PRICE_PER_1K),
            current_model=settings.riptide_watergraph_model,
            tool_count=len(default_registry().all_specs()),
            role_names=list(DEFAULT_ROLES),
        )

    @app.get("/api/tools", response_model=list[ToolInfo])
    def api_tools() -> list[ToolInfo]:
        return [ToolInfo(**spec.model_dump()) for spec in default_registry().all_specs()]

    @app.get("/api/roles", response_model=list[AgentRole])
    def api_roles() -> list[AgentRole]:
        return list(DEFAULT_ROLES.values())

    @app.post("/api/eval", response_model=EvalReport)
    def api_eval(req: EvalRequest) -> EvalReport:
        return EvalRunner(offline=req.offline).run()

    @app.get("/api/costs", response_model=dict[str, TenantTotals])
    def api_costs() -> dict[str, TenantTotals]:
        return CostTracker(get_settings().usage_log_path).by_tenant()

    # --- Studio SPA (registered AFTER all routes so it never shadows them) ---

    @app.get("/", include_in_schema=False)
    def index() -> FileResponse:
        return FileResponse(_STATIC / "index.html")

    app.mount("/static", StaticFiles(directory=str(_STATIC)), name="static")

    return app


app = create_app()
