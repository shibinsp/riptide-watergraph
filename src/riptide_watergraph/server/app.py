"""FastAPI service exposing the agent graph over HTTP.

Endpoints:
- ``GET  /healthz``                  — liveness check.
- ``POST /run``                      — run a task, return a structured result.
- ``GET  /run/stream``               — same, streamed as Server-Sent Events.
- ``POST /sessions/{sid}/messages``  — multi-turn: runs with the session's history.
- ``GET  /sessions/{sid}``           — the session's turns.

Endpoints are sync ``def`` on purpose: the graph runs synchronously (each node drives
async work via ``asyncio.run``), so FastAPI executes them in its threadpool where a fresh
event loop is available. Over-budget tenants get HTTP 402.
"""

from __future__ import annotations

import json

from fastapi import FastAPI, HTTPException
from fastapi.responses import StreamingResponse
from pydantic import BaseModel

from ..observability.cost import BudgetExceeded
from ..service import RunResult, SessionStore, run_task

_sessions = SessionStore()


class RunRequest(BaseModel):
    task: str
    tenant_id: str = "default"
    offline: bool = False
    memory: bool = True
    llm_composer: bool = False
    single: bool = False


class MessageRequest(BaseModel):
    task: str
    tenant_id: str = "default"
    offline: bool = False


def _sse(obj: dict) -> str:
    return f"data: {json.dumps(obj)}\n\n"


def create_app() -> FastAPI:
    app = FastAPI(title="riptide-watergraph", version="0.1.0")

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

    return app


app = create_app()
