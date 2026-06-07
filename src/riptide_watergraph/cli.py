"""Command-line entrypoint.

``riptide run "<task>"`` runs a task end-to-end (guardrails -> recall -> orchestrate ->
worker/swarm -> approval -> finalize -> reflect -> output), attributing usage to a
tenant. ``riptide costs`` prints the per-tenant cost dashboard.
"""

from __future__ import annotations

import argparse
import json
import os
import sys
import time
import uuid
from pathlib import Path
from typing import Any

from langgraph.checkpoint.sqlite import SqliteSaver
from langgraph.types import Command

from .config import get_settings
from .evaluation import EvalRunner
from .gateway import DemoGateway, LiteLLMGateway, ResilientGateway
from .graph import build_graph
from .guardrails import default_guardrails
from .memory import (
    HashingEmbedding,
    JsonFileMemory,
    LexicalOverlapReranker,
    RuleTripleExtractor,
    consolidate_memory,
)
from .memory.reflection import LLMReflector
from .observability.cost import (
    BudgetExceeded,
    CostTracker,
    UsageRecord,
    cost_from_usage,
    estimate_tokens,
)
from .observability.tracing import init_tracing
from .service import deliberate_task, enforce_budget
from .skills import JsonFileSkillStore, LLMSkillSynthesizer, skill_to_spec
from .interfaces import SwarmComposer
from .swarm import HeuristicSwarmComposer, LLMSwarmComposer, SingleAgentComposer
from .tools import default_registry


def _prompt_approval(payload: dict[str, Any]) -> bool:
    """Ask the operator to approve a pending side-effecting action."""
    print("\n  HUMAN APPROVAL REQUIRED")
    print(f"   tool:      {payload.get('tool')}")
    print(f"   arguments: {payload.get('arguments')}")
    print(f"   subtask:   {payload.get('subtask')}")
    reply = input("   Approve? [y/N] ").strip().lower()
    return reply in ("y", "yes")


def _prompt_clarification(payload: dict[str, Any]) -> str:
    """Ask the operator to answer a worker's clarifying question."""
    print("\n  CLARIFICATION REQUESTED")
    print(f"   subtask:  {payload.get('subtask')}")
    print(f"   question: {payload.get('question')}")
    return input("   Your answer: ").strip()


def _run_task(
    task: str,
    *,
    auto_approve: bool,
    offline: bool = False,
    memory_on: bool = True,
    single: bool = False,
    tenant_id: str = "default",
    guardrails_on: bool = True,
    llm_composer: bool = False,
    critic: bool = False,
    supervisor: bool = False,
    react_steps: int = 1,
    vote_k: int = 1,
    final_schema: dict[str, Any] | None = None,
    learn_skills: bool = False,
) -> int:
    settings = get_settings()
    init_tracing(settings)
    Path(settings.checkpoint_path).parent.mkdir(parents=True, exist_ok=True)

    try:
        enforce_budget(settings, tenant_id)
    except BudgetExceeded as exc:
        print(f" BUDGET EXCEEDED: {exc}")
        return 2

    model = settings.riptide_watergraph_model
    planner_model = settings.planner_model or model
    worker_model = settings.worker_model or model

    base_gateway = DemoGateway() if offline else LiteLLMGateway(default_model=model)
    # Wrap with timeout + retry so transient API failures don't crash the run.
    gateway = ResilientGateway(base_gateway)
    registry = default_registry()
    composer: SwarmComposer
    if single:
        composer = SingleAgentComposer(model=planner_model)
    elif llm_composer:
        composer = LLMSwarmComposer(gateway, model=planner_model)
    else:
        composer = HeuristicSwarmComposer(model=planner_model)

    # Stage 2 + 4: per-tenant persistent memory (lessons never leak across tenants),
    # with hybrid dense+lexical retrieval (offline embedder) and reranking.
    memory = (
        JsonFileMemory(
            settings.tenant_memory_path(tenant_id),
            embedding=HashingEmbedding(),
            reranker=LexicalOverlapReranker(),
        )
        if memory_on
        else None
    )
    reflector = LLMReflector(gateway, model=planner_model) if memory_on else None
    guardrails = default_guardrails() if guardrails_on else None

    # SkillForge: load previously-learned skills as tools, and (when on) distill new ones.
    skill_store = None
    skill_synthesizer = None
    if learn_skills or os.getenv("RIPTIDE_ENABLE_SKILLS") == "1":
        skill_store = JsonFileSkillStore(settings.tenant_skills_dir(tenant_id))
        skill_synthesizer = LLMSkillSynthesizer(gateway, model=planner_model)
        for sk in skill_store.load_all():
            registry.register(skill_to_spec(sk, gateway=gateway, model=planner_model))

    thread_id = str(uuid.uuid4())
    config = {"configurable": {"thread_id": thread_id}}

    with SqliteSaver.from_conn_string(settings.checkpoint_path) as checkpointer:
        graph = build_graph(
            gateway=gateway,
            registry=registry,
            composer=composer,
            model=model,
            checkpointer=checkpointer,
            memory=memory,
            reflector=reflector,
            skill_synthesizer=skill_synthesizer,
            skill_store=skill_store,
            guardrails=guardrails,
            planner_model=planner_model,
            worker_model=worker_model,
            enable_critic=critic,
            enable_supervisor=supervisor,
            max_steps=react_steps,
            vote_k=vote_k,
            final_schema=final_schema,
        )

        print(f" tenant={tenant_id} thread={thread_id}")
        result = graph.invoke(
            {"task": task, "session_id": thread_id, "tenant_id": tenant_id}, config
        )

        # Resume loop: handle approval and clarification interrupts.
        while "__interrupt__" in result:
            payload = result["__interrupt__"][0].value
            if isinstance(payload, dict) and payload.get("type") == "clarification":
                if auto_approve:
                    answer = "(no clarification available; proceed with your best assumption)"
                    print(f" auto-clarify: {payload.get('question')}")
                else:
                    answer = _prompt_clarification(payload)
                result = graph.invoke(Command(resume={"answer": answer}), config)
            else:
                approved = True if auto_approve else _prompt_approval(payload)
                if auto_approve:
                    print(f" auto-approved: {payload.get('tool')}")
                result = graph.invoke(Command(resume={"approved": approved}), config)

        _print_result(result, memory_on=memory_on, memory=memory)
        learned = result.get("learned_skills") or []
        if learned:
            print(f" learned {len(learned)} skill(s): {', '.join(learned)}")
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
    roles = result.get("roles") or []
    plan = result.get("plan") or []
    if roles:
        print(" roles: " + ", ".join(
            f"{plan[i] if i < len(plan) else '?'} -> {roles[i]}" for i in range(len(roles))
        ))
    verdicts = result.get("verdicts") or []
    if verdicts:
        n_pass = sum(1 for v in verdicts if v.get("verdict") == "pass")
        print(f" critic: {n_pass}/{len(verdicts)} subtasks verified")

    for tag in ("guard_violations", "guard_violations_out"):
        if result.get(tag):
            print(f" guardrails ({tag}): {', '.join(result[tag])}")

    recalled = result.get("recalled_lessons") or []
    if recalled:
        print(f"\n recalled {len(recalled)} lesson(s):")
        for ln in recalled:
            print(f"   - {ln}")

    print("\n FINAL ANSWER\n" + (result.get("final_answer") or "(none)"))

    structured = result.get("structured_output")
    if structured:
        print("\n STRUCTURED OUTPUT\n" + json.dumps(structured, indent=2))

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
    # Prefer real token usage from the gateway; fall back to the composer estimate.
    usage = (result.get("metrics") or {}).get("usage") or {}
    actual_total = int(usage.get("total_tokens", 0) or 0)
    if actual_total > 0:
        cost = cost_from_usage(settings.riptide_watergraph_model, usage)
    else:
        cost = float(decision.get("estimated_cost_usd", 0.0))
    tracker = CostTracker(settings.usage_log_path)
    tracker.record(
        UsageRecord(
            tenant_id=tenant_id,
            task=task,
            mode=decision.get("mode", "single"),
            est_tokens=estimate_tokens(blob),
            actual_tokens=actual_total,
            cost_usd=cost,
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


def _show_skills(tenant_id: str) -> int:
    """List the skills the agent has authored for this tenant (SkillForge)."""
    settings = get_settings()
    skills = JsonFileSkillStore(settings.tenant_skills_dir(tenant_id)).load_all()
    if not skills:
        print("no learned skills yet (run with --learn-skills to author some).")
        return 0
    print(f"{'skill':<28}description")
    print("-" * 60)
    for sk in skills:
        print(f"{'skill.' + sk.name:<28}{sk.description}")
    return 0


def _deliberate(task: str, samples: int, offline: bool) -> int:
    """Verified best-of-N deliberation: print the ranked candidates + the best + confidence."""
    result = deliberate_task(task, samples=samples, offline=offline)
    print(f" deliberation ({len(result.candidates)} candidates)")
    for c in result.candidates:
        print(f"   [{c.score:.2f}] {c.style:<12} {c.answer[:72]}")
    print(f"\n BEST (score {result.score:.2f}, confidence {result.confidence:.2f})")
    print(result.answer or "(none)")
    if not result.confident():
        print("\n low confidence — consider escalating or asking a human.")
    return 0


def _consolidate(tenant_id: str) -> int:
    """Run the consolidation 'sleep' cycle: episodic memory -> knowledge graph + facts."""
    settings = get_settings()
    memory = JsonFileMemory(
        settings.tenant_memory_path(tenant_id),
        embedding=HashingEmbedding(),
        reranker=LexicalOverlapReranker(),
    )
    report = consolidate_memory(
        memory, extractor=RuleTripleExtractor(),
        kg_path=settings.tenant_kg_path(tenant_id),
    )
    print(f" consolidated tenant={tenant_id}")
    print(f"   scanned {report.records_scanned} records "
          f"({report.episodic_scanned} episodic)")
    print(f"   knowledge graph: {report.triples} facts; "
          f"wrote {report.facts_written} semantic record(s); pruned {report.pruned}")
    return 0


def _run_eval(offline: bool) -> int:
    try:
        report = EvalRunner(offline=offline).run()
    except Exception as exc:  # noqa: BLE001 - surface a friendly hint for real runs
        if not offline:
            print(f" real-model eval failed: {exc}")
            print(' hint: pip install -e ".[litellm]", set OPENAI_API_KEY and '
                  "RIPTIDE_WATERGRAPH_MODEL, or use --offline.")
            return 1
        raise
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
    run_p.add_argument("--llm-composer", action="store_true",
                       help="Use the LLM swarm composer (plan + dependencies) instead "
                            "of the heuristic one.")
    run_p.add_argument("--critic", action="store_true",
                       help="Add a critic agent that verifies each subtask result.")
    run_p.add_argument("--supervisor", action="store_true",
                       help="Add a supervisor that re-plans corrective subtasks (implies "
                            "--critic).")
    run_p.add_argument("--react", type=int, default=1, metavar="N",
                       help="Max think->act->observe steps per subtask (default 1).")
    run_p.add_argument("--vote", type=int, default=1, metavar="K",
                       help="Self-consistency samples for direct answers (default 1).")
    run_p.add_argument("--schema", metavar="PATH",
                       help="Path to a JSON Schema file; finalize emits a validated "
                            "structured output matching it.")
    run_p.add_argument("--learn-skills", action="store_true",
                       help="SkillForge: distill a reusable skill from a successful run and "
                            "register it for future runs (also loads previously-learned skills).")

    sub.add_parser("costs", help="Show the per-tenant cost dashboard.")

    skills_p = sub.add_parser("skills", help="List the agent's self-authored skills.")
    skills_p.add_argument("--tenant", default="default",
                          help="Tenant id whose learned skills to list.")

    consolidate_p = sub.add_parser(
        "consolidate",
        help="Run the memory 'sleep' cycle: distill episodic memory into a knowledge graph.")
    consolidate_p.add_argument("--tenant", default="default",
                               help="Tenant id whose memory to consolidate.")

    deliberate_p = sub.add_parser(
        "deliberate",
        help="Verified best-of-N deliberation over diverse reasoning candidates.")
    deliberate_p.add_argument("task", help="The task to deliberate on.")
    deliberate_p.add_argument("--samples", type=int, default=3, metavar="N",
                              help="Number of diverse candidates to generate + score.")
    deliberate_p.add_argument("--offline", action="store_true",
                              help="Use the deterministic offline gateway + verifier.")

    eval_p = sub.add_parser("eval", help="Run the evaluation suite and report metrics.")
    eval_p.add_argument("--offline", action="store_true",
                        help="Evaluate with the deterministic offline gateway.")

    serve_p = sub.add_parser("serve", help="Run the HTTP service (needs the [server] extra).")
    serve_p.add_argument("--host", default="127.0.0.1")
    serve_p.add_argument("--port", type=int, default=8000)

    args = parser.parse_args(argv)
    if args.command == "run":
        final_schema = json.loads(Path(args.schema).read_text()) if args.schema else None
        return _run_task(
            args.task,
            auto_approve=args.auto_approve,
            offline=args.offline,
            memory_on=not args.no_memory,
            single=args.single,
            tenant_id=args.tenant,
            guardrails_on=not args.no_guardrails,
            llm_composer=args.llm_composer,
            critic=args.critic,
            supervisor=args.supervisor,
            react_steps=args.react,
            vote_k=args.vote,
            final_schema=final_schema,
            learn_skills=args.learn_skills,
        )
    if args.command == "costs":
        return _show_costs()
    if args.command == "skills":
        return _show_skills(args.tenant)
    if args.command == "consolidate":
        return _consolidate(args.tenant)
    if args.command == "deliberate":
        return _deliberate(args.task, args.samples, args.offline)
    if args.command == "eval":
        return _run_eval(args.offline)
    if args.command == "serve":
        return _serve(args.host, args.port)
    parser.print_help()  # pragma: no cover - unreachable: subparser is required=True
    return 1  # pragma: no cover


def _serve(host: str, port: int) -> int:
    try:
        import uvicorn
    except ImportError:
        print('the HTTP server needs the [server] extra: pip install -e ".[server]"')
        return 1
    print(f" serving riptide-watergraph on http://{host}:{port}")
    uvicorn.run("riptide_watergraph.server:app", host=host, port=port)
    return 0


if __name__ == "__main__":
    sys.exit(main())
