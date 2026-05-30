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

    # --- Stage 3: dynamic swarm composition ---
    swarm_decision: dict[str, Any]  # the composer's single-vs-swarm decision
