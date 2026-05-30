"""Command-line entrypoint: ``riptide-watergraph run "<task>"``.

Runs a task end-to-end through the orchestrator-worker graph, pausing at the
human-approval interrupt for any side-effecting tool, then resuming to finalize.
"""

from __future__ import annotations

import argparse
import sys
import uuid
from pathlib import Path
from typing import Any

from langgraph.checkpoint.sqlite import SqliteSaver
from langgraph.types import Command

from .config import get_settings
from .gateway import DemoGateway, LiteLLMGateway
from .graph import build_graph
from .memory import JsonFileMemory
from .memory.reflection import LLMReflector
from .observability.tracing import init_tracing
from .swarm import HeuristicSwarmComposer, SingleAgentComposer
from .tools import default_registry


def _prompt_approval(payload: dict[str, Any]) -> bool:
    """Ask the operator to approve a pending side-effecting action."""
    print("\n  HUMAN APPROVAL REQUIRED")
    print(f"   tool:      {payload.get('tool')}")
    print(f"   arguments: {payload.get('arguments')}")
    print(f"   subtask:   {payload.get('subtask')}")
    reply = input("   Approve? [y/N] ").strip().lower()
    return reply in ("y", "yes")


def _run_task(
    task: str,
    *,
    auto_approve: bool,
    offline: bool = False,
    memory_on: bool = True,
    single: bool = False,
) -> int:
    settings = get_settings()
    init_tracing(settings)

    Path(settings.checkpoint_path).parent.mkdir(parents=True, exist_ok=True)

    gateway = (
        DemoGateway()
        if offline
        else LiteLLMGateway(default_model=settings.riptide_watergraph_model)
    )
    registry = default_registry()
    composer = (
        SingleAgentComposer(model=settings.riptide_watergraph_model)
        if single
        else HeuristicSwarmComposer(model=settings.riptide_watergraph_model)
    )

    # Stage 2: persistent memory + reflection (lessons accumulate across runs).
    memory = JsonFileMemory(settings.memory_path) if memory_on else None
    reflector = (
        LLMReflector(gateway, model=settings.riptide_watergraph_model)
        if memory_on
        else None
    )

    thread_id = str(uuid.uuid4())
    config = {"configurable": {"thread_id": thread_id}}

    with SqliteSaver.from_conn_string(settings.checkpoint_path) as checkpointer:
        graph = build_graph(
            gateway=gateway,
            registry=registry,
            composer=composer,
            model=settings.riptide_watergraph_model,
            checkpointer=checkpointer,
            memory=memory,
            reflector=reflector,
        )

        print(f" thread={thread_id}")
        result = graph.invoke({"task": task, "session_id": thread_id}, config)

        decision = result.get("swarm_decision") or {}
        if decision:
            print(f" composition: {decision.get('mode')} "
                  f"(parallelism={decision.get('parallelism')}) - {decision.get('rationale')}")

        # Resume loop: handle one or more approval interrupts.
        while "__interrupt__" in result:
            payload = result["__interrupt__"][0].value
            approved = True if auto_approve else _prompt_approval(payload)
            if auto_approve:
                print(f" auto-approved: {payload.get('tool')}")
            result = graph.invoke(Command(resume={"approved": approved}), config)

        recalled = result.get("recalled_lessons") or []
        if recalled:
            print(f"\n recalled {len(recalled)} lesson(s):")
            for ln in recalled:
                print(f"   - {ln}")

        print("\n FINAL ANSWER\n" + (result.get("final_answer") or "(none)"))

        metrics = result.get("metrics") or {}
        total = metrics.get("tool_calls_total", 0)
        valid = metrics.get("tool_calls_valid", 0)
        if total:
            rate = valid / total
            print(f"\n tool-call validity: {valid}/{total} = {rate:.0%}")

        if memory_on:
            stored = result.get("stored_lessons") or []
            outcome = "success" if result.get("success") else "needs-improvement"
            print(f" outcome: {outcome}; learned {len(stored)} lesson(s) "
                  f"(memory now holds {len(memory)})")
    return 0


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="riptide-watergraph")
    sub = parser.add_subparsers(dest="command", required=True)

    run_p = sub.add_parser("run", help="Run a task end-to-end.")
    run_p.add_argument("task", help="The task for the agent to perform.")
    run_p.add_argument(
        "--auto-approve",
        action="store_true",
        help="Approve side-effecting tools without prompting (for CI).",
    )
    run_p.add_argument(
        "--offline",
        action="store_true",
        help="Use the deterministic offline gateway (no API key / network needed).",
    )
    run_p.add_argument(
        "--no-memory",
        action="store_true",
        help="Disable long-term memory recall + reflection for this run.",
    )
    run_p.add_argument(
        "--single",
        action="store_true",
        help="Force a single agent (skip the cost-aware swarm composer).",
    )

    args = parser.parse_args(argv)
    if args.command == "run":
        return _run_task(
            args.task,
            auto_approve=args.auto_approve,
            offline=args.offline,
            memory_on=not args.no_memory,
            single=args.single,
        )
    parser.print_help()
    return 1


if __name__ == "__main__":
    sys.exit(main())
