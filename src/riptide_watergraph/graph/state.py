"""Typed state for the orchestrator-worker graph.

LangGraph state uses a ``TypedDict`` with reducer annotations (the idiomatic choice
over pydantic for graph state). ``Annotated[list, add]`` channels are appended to by
nodes rather than overwritten.
"""

from __future__ import annotations

from operator import add
from typing import Annotated, Any, TypedDict


class WorkerResult(TypedDict):
    """Output of a single worker step on one subtask."""

    subtask: str
    output: str
    tool_calls: list[dict[str, Any]]


class OrchestratorState(TypedDict, total=False):
    """Shared state threaded through the graph.

    Channels annotated with ``add`` accumulate; the rest are last-write-wins.
    """

    task: str  # the user's task
    plan: list[str]  # subtasks produced by the orchestrator
    cursor: int  # index of the next subtask the worker will handle
    results: Annotated[list[WorkerResult], add]  # appended by workers
    pending_action: dict[str, Any] | None  # the side-effecting call awaiting approval
    approval: dict[str, Any] | None  # resume payload from the human
    final_answer: str | None
    messages: Annotated[list[dict[str, Any]], add]  # running transcript
    metrics: dict[str, Any]  # tool-call validity counters, etc.

    # --- Stage 2: memory + self-learning ---
    session_id: str  # identifies this run for reflection
    recalled_lessons: list[str]  # lessons retrieved from memory, injected into prompts
    success: bool  # outcome judged at reflection time
    stored_lessons: list[str]  # lessons written back to memory this run

    # --- Stage 3 / Phase C: dynamic swarm composition + dependency DAG ---
    swarm_decision: dict[str, Any]  # the composer's single-vs-swarm decision
    dependencies: list[list[int]]  # dependencies[i] = prerequisite subtask indices
    blackboard: dict[int, str]  # subtask index -> output, shared across waves

    # --- Multi-agent enhancement (roles / critic / supervisor / handoff) ---
    roles: list[str]  # role name per subtask (parallel to plan)
    verdicts: list[dict[str, Any]]  # critic verdict per result
    round: int  # supervisor re-planning round counter
    handoffs: dict[int, int]  # subtask index -> handoff count (cap enforcement)

    # --- Stage 4: guardrails + multi-tenancy ---
    tenant_id: str  # tenant this run belongs to (isolation + cost attribution)
    blocked: bool  # set by guard_input when the request is refused
    guard_violations: list[str]  # input-side guardrail findings
    guard_violations_out: list[str]  # output-side guardrail findings
