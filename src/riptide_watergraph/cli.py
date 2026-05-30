"""Command-line entrypoint.

``riptide run "<task>"`` runs a task end-to-end (guardrails -> recall -> orchestrate ->
worker/swarm -> approval -> finalize -> reflect -> output), attributing usage to a
tenant. ``riptide costs`` prints the per-tenant cost dashboard.
"""

from __future__ import annotations

import argparse
import sys
import time
import uuid
from pathlib import Path
from typing import Any

from langgraph.checkpoint.sqlite import SqliteSaver
from langgraph.types import Command

from .config import get_settings
from .evaluation import EvalRunner
from .gateway import DemoGateway, LiteLLMGateway
from .graph import build_graph
from .guardrails import default_guardrails
from .memory import JsonFileMemory
from .memory.reflection import LLMReflector
from .observability.cost import CostTracker, UsageRecord, estimate_tokens
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
    tenant_id: str = "default",
    guardrails_on: bool = True,
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

    # Stage 2 + 4: per-tenant persistent memory (lessons never leak across tenants).
    memory = (
        JsonFileMemory(settings.tenant_memory_path(tenant_id)) if memory_on else None
    )
    reflector = (
        LLMReflector(gateway, model=settings.riptide_watergraph_model)
        if memory_on
        else None
    )
    guardrails = default_guardrails() if guardrails_on else None

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
            guardrails=guardrails,
        )

        print(f" tenant={tenant_id} thread={thread_id}")
        result = graph.invoke(
            {"task": task, "session_id": thread_id, "tenant_id": tenant_id}, config
        )

        # Resume loop: handle one or more approval interrupts.
        while "__interrupt__" in result:
            payload = result["__interrupt__"][0].value
            approved = True if auto_approve else _prompt_approval(payload)
            if auto_approve:
                print(f" auto-approved: {payload.get('tool')}")
            result = graph.invoke(Command(resume={"approved": approved}), config)

        _print_result(result, memory_on=memory_on, memory=memory)
        _record_usage(settings, tenant_id, task, result)
    return 0


def _print_result(result: dict, *, memory_on: bool, memory) -> None:
    if result.get("blocked"):
        print(f" BLOCKED by guardrails: {', '.join(result.get('guard_violations') or [])}")
        print("\n FINAL ANSWER\n" + (result.get("final_answer") or "(none)"))
        return

    decision = result.get("swarm_decision") or {}
    if decision:
        print(f" composition: {decision.get('mode')} "
              f"(parallelism={decision.get('parallelism')}) - {decision.get('rationale')}")

    for tag in ("guard_violations", "guard_violations_out"):
        if result.get(tag):
            print(f" guardrails ({tag}): {', '.join(result[tag])}")

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
        print(f"\n tool-call validity: {valid}/{total} = {valid / total:.0%}")

    if memory_on and memory is not None:
        stored = result.get("stored_lessons") or []
        outcome = "success" if result.get("success") else "needs-improvement"
        print(f" outcome: {outcome}; learned {len(stored)} lesson(s) "
              f"(memory now holds {len(memory)})")


def _record_usage(settings, tenant_id: str, task: str, result: dict) -> None:
    decision = result.get("swarm_decision") or {}
    blob = (
        task
        + " ".join(r.get("output", "") for r in (result.get("results") or []))
        + (result.get("final_answer") or "")
    )
    tracker = CostTracker(settings.usage_log_path)
    tracker.record(
        UsageRecord(
            tenant_id=tenant_id,
            task=task,
            mode=decision.get("mode", "single"),
            est_tokens=estimate_tokens(blob),
            cost_usd=float(decision.get("estimated_cost_usd", 0.0)),
            blocked=bool(result.get("blocked")),
            ts=time.time(),
        )
    )


def _show_costs() -> int:
    settings = get_settings()
    totals = CostTracker(settings.usage_log_path).by_tenant()
    if not totals:
        print("no usage recorded yet.")
        return 0
    print(f"{'tenant':<16}{'runs':>6}{'tokens':>10}{'cost_usd':>12}{'blocked':>9}")
    print("-" * 53)
    for t in sorted(totals.values(), key=lambda x: x.cost_usd, reverse=True):
        print(f"{t.tenant_id:<16}{t.runs:>6}{t.est_tokens:>10}"
              f"{t.cost_usd:>12.6f}{t.blocked:>9}")
    return 0


def _run_eval(offline: bool) -> int:
    report = EvalRunner(offline=offline).run()
    print(f"{'task':<14}{'pass':>6}{'mode':>10}{'tool_valid':>12}  notes")
    print("-" * 60)
    for r in report.results:
        rate = "-" if r.tool_valid_rate is None else f"{r.tool_valid_rate:.0%}"
        mark = "PASS" if r.passed else "FAIL"
        print(f"{r.task_id:<14}{mark:>6}{r.mode:>10}{rate:>12}  {r.notes}")
    print("-" * 60)
    print(f" pass rate: {report.n_passed}/{report.n_total} = {report.pass_rate:.0%}")
    print(f" routing: {report.modes}; blocked: {report.blocked}; "
          f"self-learning recall: {report.learning_recall}")
    return 0 if report.pass_rate == 1.0 else 1


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="riptide-watergraph")
    sub = parser.add_subparsers(dest="command", required=True)

    run_p = sub.add_parser("run", help="Run a task end-to-end.")
    run_p.add_argument("task", help="The task for the agent to perform.")
    run_p.add_argument("--auto-approve", action="store_true",
                       help="Approve side-effecting tools without prompting (for CI).")
    run_p.add_argument("--offline", action="store_true",
                       help="Use the deterministic offline gateway (no API key).")
    run_p.add_argument("--no-memory", action="store_true",
                       help="Disable long-term memory recall + reflection.")
    run_p.add_argument("--single", action="store_true",
                       help="Force a single agent (skip the swarm composer).")
    run_p.add_argument("--tenant", default="default",
                       help="Tenant id for memory isolation + cost attribution.")
    run_p.add_argument("--no-guardrails", action="store_true",
                       help="Disable input/output guardrails for this run.")

    sub.add_parser("costs", help="Show the per-tenant cost dashboard.")

    eval_p = sub.add_parser("eval", help="Run the evaluation suite and report metrics.")
    eval_p.add_argument("--offline", action="store_true",
                        help="Evaluate with the deterministic offline gateway.")

    args = parser.parse_args(argv)
    if args.command == "run":
        return _run_task(
            args.task,
            auto_approve=args.auto_approve,
            offline=args.offline,
            memory_on=not args.no_memory,
            single=args.single,
            tenant_id=args.tenant,
            guardrails_on=not args.no_guardrails,
        )
    if args.command == "costs":
        return _show_costs()
    if args.command == "eval":
        return _run_eval(args.offline)
    parser.print_help()
    return 1


if __name__ == "__main__":
    sys.exit(main())
