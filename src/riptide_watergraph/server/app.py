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
- ``POST /api/tools/{name}/invoke``  — run a single read-only tool (Tool Runner).
- ``GET  /api/run/trace``            — stream node-by-node execution as Server-Sent Events.
- ``GET  /api/connection``           — current AI connection (provider/model, masked key).
- ``POST /api/connection``           — set the AI provider/model/key at runtime (in-memory).
- ``POST /api/connection/test``      — ping the configured gateway to validate the connection.
- ``GET/POST/DELETE /api/workflows`` — CRUD for saved visual workflow specs.
- ``POST /api/workflows/run`` + ``GET /api/workflows/run/stream`` — run a workflow DAG (SSE).

Endpoints are sync ``def`` on purpose: the graph runs synchronously (each node drives
async work via ``asyncio.run``), so FastAPI executes them in its threadpool where a fresh
event loop is available. Over-budget tenants get HTTP 402.
"""

from __future__ import annotations

import asyncio
import json
import os
import threading
import time
from pathlib import Path
from typing import Any, Literal

from fastapi import FastAPI, HTTPException
from fastapi.responses import FileResponse, StreamingResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, ValidationError

from ..config import get_settings
from ..evaluation import EvalReport, EvalRunner
from ..gateway import DemoGateway, LiteLLMGateway, ResilientGateway
from ..interfaces.gateway import Message
from ..observability.cost import BudgetExceeded, CostTracker, TenantTotals, _PRICE_PER_1K
from ..service import (
    RunResult,
    SessionStore,
    run_task,
    run_workflow,
    stream_task,
    stream_workflow,
)
from ..swarm.roles import AgentRole, all_roles
from ..tools import default_registry
from ..tools.registry import ToolValidationError
from ..workflows import WorkflowSpec, WorkflowStore, WorkflowValidationError, validate_spec

_VERSION = "0.8.0"
_STATIC = Path(__file__).parent / "static"
_sessions = SessionStore()
_workflows = WorkflowStore()


def _sampling(temperature: float | None, top_p: float | None,
              max_tokens: int | None) -> dict[str, Any] | None:
    """Collect set sampling params into a dict litellm understands (None => model default)."""
    s: dict[str, Any] = {}
    if temperature is not None:
        s["temperature"] = temperature
    if top_p is not None:
        s["top_p"] = top_p
    if max_tokens is not None:
        s["max_tokens"] = max_tokens
    return s or None

# --- runtime AI connection (in-memory; key never persisted to disk) ----------
# Maps a provider to the env var litellm reads. Mirrored to os.environ on change so the
# next run() picks it up (get_settings() is not cached; litellm reads keys per call).
_PROVIDER_KEY_ENV = {"openai": "OPENAI_API_KEY", "anthropic": "ANTHROPIC_API_KEY",
                     "custom": "OPENAI_API_KEY"}
_conn_lock = threading.Lock()
_connection: dict[str, str] = {"provider": "offline", "model": "", "api_base": "", "api_key": ""}


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
    temperature: float | None = None
    top_p: float | None = None
    max_tokens: int | None = None


class MessageRequest(BaseModel):
    task: str
    tenant_id: str = "default"
    offline: bool = False
    memory: bool = True
    guardrails: bool = True
    single: bool = False
    llm_composer: bool = False
    critic: bool = False
    supervisor: bool = False
    react_steps: int = 1
    vote_k: int = 1
    temperature: float | None = None
    top_p: float | None = None
    max_tokens: int | None = None


class EvalRequest(BaseModel):
    offline: bool = True


class WorkflowRunRequest(BaseModel):
    spec: WorkflowSpec
    tenant_id: str = "default"
    offline: bool = False
    memory: bool = True
    guardrails: bool = True
    critic: bool = False
    supervisor: bool = False


class ToolInfo(BaseModel):
    name: str
    version: str
    description: str
    side_effecting: bool
    category: str = "general"
    tags: list[str] = []
    json_schema: dict[str, Any]


class ToolInvokeRequest(BaseModel):
    arguments: dict[str, Any] = {}


class ToolInvokeResult(BaseModel):
    name: str
    result: str


class ConnectionRequest(BaseModel):
    provider: Literal["offline", "openai", "anthropic", "custom"] = "offline"
    model: str = ""
    api_key: str | None = None  # omitted => keep the existing key
    api_base: str | None = None


class ConnectionStatus(BaseModel):
    provider: str
    model: str
    api_base: str
    key_set: bool
    key_masked: str | None
    configured: bool


class ConnectionTestResult(BaseModel):
    ok: bool
    model: str
    latency_ms: int
    detail: str


class MetaResponse(BaseModel):
    version: str
    defaults: dict[str, Any]
    models: list[str]
    current_model: str
    tool_count: int
    role_count: int
    role_names: list[str]
    tool_categories: list[str]
    role_categories: list[str]
    connection: ConnectionStatus


def _sse(obj: dict) -> str:
    return f"data: {json.dumps(obj)}\n\n"


def _mask(key: str) -> str | None:
    """Mask an API key for display — never return the raw secret."""
    if not key:
        return None
    return ("•" * 4) + key[-4:] if len(key) > 4 else "•" * len(key)


def _connection_status() -> ConnectionStatus:
    with _conn_lock:
        c = dict(_connection)
    key = c["api_key"]
    return ConnectionStatus(
        provider=c["provider"], model=c["model"], api_base=c["api_base"],
        key_set=bool(key), key_masked=_mask(key),
        configured=c["provider"] != "offline" and bool(c["model"]),
    )


def _apply_connection() -> None:
    """Mirror the in-memory connection to os.environ so the next run/litellm call uses it."""
    with _conn_lock:
        c = dict(_connection)
    if c["model"]:
        os.environ["RIPTIDE_WATERGRAPH_MODEL"] = c["model"]
    if c["provider"] in _PROVIDER_KEY_ENV and c["api_key"]:
        os.environ[_PROVIDER_KEY_ENV[c["provider"]]] = c["api_key"]
    if c["api_base"]:
        os.environ["OPENAI_API_BASE"] = c["api_base"]


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
                sampling=_sampling(req.temperature, req.top_p, req.max_tokens),
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

    @app.get("/api/run/trace")
    def api_run_trace(task: str, tenant_id: str = "default", offline: bool = True):
        def gen():
            try:
                for kind, payload in stream_task(task, tenant_id=tenant_id, offline=offline):
                    if kind == "node":
                        yield _sse({"event": "node", "name": payload})
                    else:
                        yield _sse({"event": "result", "result": payload.model_dump()})
            except BudgetExceeded as exc:
                yield _sse({"event": "error", "detail": str(exc)})

        return StreamingResponse(gen(), media_type="text/event-stream")

    def _message_run_kwargs(session_id: str, req: MessageRequest) -> dict[str, Any]:
        return dict(
            tenant_id=req.tenant_id, offline=req.offline, memory_on=req.memory,
            guardrails_on=req.guardrails, single=req.single, llm_composer=req.llm_composer,
            critic=req.critic, supervisor=req.supervisor, react_steps=req.react_steps,
            vote_k=req.vote_k, sampling=_sampling(req.temperature, req.top_p, req.max_tokens),
            history=_sessions.history(session_id),
        )

    @app.post("/sessions/{session_id}/messages", response_model=RunResult)
    def post_message(session_id: str, req: MessageRequest) -> RunResult:
        try:
            result = run_task(req.task, **_message_run_kwargs(session_id, req))
        except BudgetExceeded as exc:
            raise HTTPException(status_code=402, detail=str(exc)) from exc
        _sessions.append(session_id, req.task, result)
        return result

    @app.get("/api/sessions/{session_id}/messages/stream")
    def stream_message(session_id: str, task: str, tenant_id: str = "default",
                       offline: bool = True, memory: bool = True, guardrails: bool = True,
                       single: bool = False, llm_composer: bool = False, critic: bool = False,
                       supervisor: bool = False, react_steps: int = 1, vote_k: int = 1,
                       temperature: float | None = None, top_p: float | None = None,
                       max_tokens: int | None = None):
        def gen():
            try:
                stream = stream_task(
                    task, tenant_id=tenant_id, offline=offline, memory_on=memory,
                    guardrails_on=guardrails, single=single, llm_composer=llm_composer,
                    critic=critic, supervisor=supervisor, react_steps=react_steps, vote_k=vote_k,
                    sampling=_sampling(temperature, top_p, max_tokens),
                    history=_sessions.history(session_id),
                )
                for kind, payload in stream:
                    if kind == "node":
                        yield _sse({"event": "node", "name": payload})
                    else:
                        _sessions.append(session_id, task, payload)
                        yield _sse({"event": "result", "result": payload.model_dump()})
            except BudgetExceeded as exc:
                yield _sse({"event": "error", "detail": str(exc)})

        return StreamingResponse(gen(), media_type="text/event-stream")

    @app.get("/sessions/{session_id}")
    def get_session(session_id: str) -> dict:
        return {"session_id": session_id, "turns": _sessions.turns(session_id)}

    @app.delete("/sessions/{session_id}")
    def delete_session(session_id: str) -> dict:
        _sessions.clear(session_id)
        return {"status": "cleared", "session_id": session_id}

    # --- Studio data endpoints (read-only, offline-safe) ---

    @app.get("/api/meta", response_model=MetaResponse)
    def api_meta() -> MetaResponse:
        settings = get_settings()
        specs = default_registry().all_specs()
        roles = all_roles()
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
            tool_count=len(specs),
            role_count=len(roles),
            role_names=[r.name for r in roles],
            tool_categories=sorted({s.category for s in specs}),
            role_categories=sorted({r.category for r in roles}),
            connection=_connection_status(),
        )

    @app.get("/api/tools", response_model=list[ToolInfo])
    def api_tools() -> list[ToolInfo]:
        return [ToolInfo(**spec.model_dump()) for spec in default_registry().all_specs()]

    @app.get("/api/roles", response_model=list[AgentRole])
    def api_roles() -> list[AgentRole]:
        return all_roles()

    @app.post("/api/tools/{name}/invoke", response_model=ToolInvokeResult)
    def api_invoke_tool(name: str, req: ToolInvokeRequest) -> ToolInvokeResult:
        registry = default_registry()
        try:
            spec = registry.get(name)
        except (KeyError, ToolValidationError) as exc:
            raise HTTPException(status_code=404, detail=f"unknown tool: {name}") from exc
        if spec.side_effecting:
            raise HTTPException(
                status_code=400,
                detail="refusing to run a side-effecting tool from the Tool Runner",
            )
        try:
            result = asyncio.run(registry.invoke(name, req.arguments))
        except ToolValidationError as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc
        return ToolInvokeResult(name=name, result=str(result))

    @app.post("/api/eval", response_model=EvalReport)
    def api_eval(req: EvalRequest) -> EvalReport:
        return EvalRunner(offline=req.offline).run()

    @app.get("/api/costs", response_model=dict[str, TenantTotals])
    def api_costs() -> dict[str, TenantTotals]:
        return CostTracker(get_settings().usage_log_path).by_tenant()

    # --- AI connection (runtime, in-memory key; masked in responses) ---

    @app.get("/api/connection", response_model=ConnectionStatus)
    def api_get_connection() -> ConnectionStatus:
        return _connection_status()

    @app.post("/api/connection", response_model=ConnectionStatus)
    def api_set_connection(req: ConnectionRequest) -> ConnectionStatus:
        if req.provider != "offline" and not req.model:
            raise HTTPException(status_code=400, detail="model is required")
        if req.provider == "custom" and not (req.api_base or _connection["api_base"]):
            raise HTTPException(status_code=400, detail="api_base is required for a custom provider")
        with _conn_lock:
            _connection["provider"] = req.provider
            _connection["model"] = req.model
            _connection["api_base"] = req.api_base if req.api_base is not None else (
                _connection["api_base"] if req.provider == "custom" else "")
            if req.api_key is not None:  # omitted => keep the existing key
                _connection["api_key"] = req.api_key
            if req.provider in ("openai", "anthropic", "custom") and not _connection["api_key"]:
                raise HTTPException(status_code=400, detail="api_key is required for this provider")
        _apply_connection()
        return _connection_status()

    @app.post("/api/connection/test", response_model=ConnectionTestResult)
    def api_test_connection(req: ConnectionRequest) -> ConnectionTestResult:
        offline = req.provider == "offline"
        model = req.model or get_settings().riptide_watergraph_model
        if not offline:
            _apply_connection()  # ensure litellm sees the saved key/base
        try:
            if offline:
                gateway: Any = DemoGateway()
            else:
                gateway = ResilientGateway(
                    LiteLLMGateway(default_model=model), max_attempts=1, timeout_s=20.0)
            start = time.perf_counter()
            asyncio.run(gateway.complete(model=model, messages=[Message(role="user", content="ping")]))
            latency = int((time.perf_counter() - start) * 1000)
            return ConnectionTestResult(ok=True, model=model, latency_ms=latency,
                                        detail="offline (DemoGateway)" if offline else "connected")
        except ImportError:
            return ConnectionTestResult(ok=False, model=model, latency_ms=0,
                                        detail='litellm not installed — pip install -e ".[litellm]"')
        except Exception as exc:  # noqa: BLE001 - report any failure, never crash
            return ConnectionTestResult(ok=False, model=model, latency_ms=0,
                                        detail=f"{type(exc).__name__}: {exc}")

    # --- Workflow builder (canvas DAG -> StaticPlanComposer -> swarm run) ---

    def _wf_messages(exc: Exception) -> list[str]:
        return exc.messages if isinstance(exc, WorkflowValidationError) else [str(exc)]

    @app.get("/api/workflows", response_model=list[str])
    def api_list_workflows() -> list[str]:
        return _workflows.list()

    @app.post("/api/workflows", response_model=WorkflowSpec)
    def api_save_workflow(spec: WorkflowSpec) -> WorkflowSpec:
        try:
            validate_spec(spec)
        except WorkflowValidationError as exc:
            raise HTTPException(status_code=422, detail=exc.messages) from exc
        _workflows.save(spec)
        return spec

    @app.get("/api/workflows/{name}", response_model=WorkflowSpec)
    def api_get_workflow(name: str) -> WorkflowSpec:
        spec = _workflows.get(name)
        if spec is None:
            raise HTTPException(status_code=404, detail=f"no workflow: {name}")
        return spec

    @app.delete("/api/workflows/{name}")
    def api_delete_workflow(name: str) -> dict:
        if not _workflows.delete(name):
            raise HTTPException(status_code=404, detail=f"no workflow: {name}")
        return {"status": "deleted", "name": name}

    @app.post("/api/workflows/run", response_model=RunResult)
    def api_run_workflow(req: WorkflowRunRequest) -> RunResult:
        try:
            return run_workflow(
                req.spec, tenant_id=req.tenant_id, offline=req.offline,
                memory_on=req.memory, guardrails_on=req.guardrails,
                critic=req.critic, supervisor=req.supervisor,
            )
        except WorkflowValidationError as exc:
            raise HTTPException(status_code=422, detail=exc.messages) from exc
        except BudgetExceeded as exc:
            raise HTTPException(status_code=402, detail=str(exc)) from exc

    @app.get("/api/workflows/run/stream")
    def api_run_workflow_stream(spec: str, tenant_id: str = "default", offline: bool = True,
                                memory: bool = True, guardrails: bool = True,
                                critic: bool = False, supervisor: bool = False):
        def gen():
            try:
                parsed = WorkflowSpec.model_validate_json(spec)
                validate_spec(parsed)
            except (ValidationError, WorkflowValidationError) as exc:
                yield _sse({"event": "error", "detail": _wf_messages(exc)})
                return
            try:
                for kind, payload in stream_workflow(
                    parsed, tenant_id=tenant_id, offline=offline, memory_on=memory,
                    guardrails_on=guardrails, critic=critic, supervisor=supervisor,
                ):
                    if kind == "node":
                        yield _sse({"event": "node", "name": payload})
                    else:
                        yield _sse({"event": "result", "result": payload.model_dump()})
            except BudgetExceeded as exc:
                yield _sse({"event": "error", "detail": str(exc)})

        return StreamingResponse(gen(), media_type="text/event-stream")

    # --- Studio SPA (registered AFTER all routes so it never shadows them) ---

    @app.get("/", include_in_schema=False)
    def index() -> FileResponse:
        return FileResponse(_STATIC / "index.html")

    app.mount("/static", StaticFiles(directory=str(_STATIC)), name="static")

    return app


app = create_app()
