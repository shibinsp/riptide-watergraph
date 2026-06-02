"""CLI coverage: subcommand dispatch, the interrupt/resume loop (approval +
clarification), result/usage/costs/eval printing, and the serve entry point.

The interrupt-loop branches are driven by a tiny fake graph (so we don't depend on the
offline gateway emitting interrupts); the offline ``main(["run", ...])`` tests exercise the
real graph end-to-end via the deterministic DemoGateway.
"""

from __future__ import annotations

import sys
import types

import pytest

from riptide_watergraph import cli
from riptide_watergraph.observability.cost import BudgetExceeded, CostTracker, UsageRecord


@pytest.fixture
def cli_env(tmp_path, monkeypatch):
    monkeypatch.setenv("DATA_DIR", str(tmp_path))
    monkeypatch.setenv("CHECKPOINT_PATH", str(tmp_path / "cp.sqlite"))
    monkeypatch.setenv("MEMORY_PATH", str(tmp_path / "mem.json"))
    monkeypatch.setenv("RIPTIDE_WATERGRAPH_DISABLE_TRACING", "1")
    return tmp_path


class _FakeGraph:
    """Returns scripted invoke() results in order (first call, then each resume)."""

    def __init__(self, scripted):
        self._scripted = list(scripted)
        self.invokes = 0

    def invoke(self, state, config):
        self.invokes += 1
        return self._scripted.pop(0)


def _interrupt(value):
    return {"__interrupt__": [types.SimpleNamespace(value=value)]}


# ---------- main() dispatch ----------

def test_main_run_offline_end_to_end(cli_env, capsys):
    rc = cli.main(["run", "compute 21 * 2", "--offline", "--no-memory"])
    assert rc == 0
    assert "FINAL ANSWER" in capsys.readouterr().out


def test_main_run_rich_flags_with_memory(cli_env, capsys):
    # --critic/--supervisor/--llm-composer + memory on exercises those gateway/graph branches.
    rc = cli.main([
        "run", "research water then compute 2+2 and summarize",
        "--offline", "--critic", "--supervisor", "--llm-composer",
    ])
    assert rc == 0
    assert "FINAL ANSWER" in capsys.readouterr().out


def test_main_run_with_schema(cli_env, tmp_path, capsys):
    schema = tmp_path / "s.json"
    schema.write_text('{"type":"object","properties":{"answer":{"type":"string"}}}')
    rc = cli.main(["run", "compute 21 * 2", "--offline", "--no-memory",
                   "--schema", str(schema)])
    assert rc == 0


def test_main_costs_and_eval(cli_env, capsys):
    assert cli.main(["costs"]) == 0  # empty dashboard
    assert "no usage" in capsys.readouterr().out.lower()
    assert cli.main(["eval", "--offline"]) == 0
    assert "pass rate" in capsys.readouterr().out


def test_main_run_single(cli_env, capsys):
    rc = cli.main(["run", "compute 21 * 2", "--offline", "--no-memory", "--single"])
    assert rc == 0


def test_main_run_budget_exceeded(cli_env, monkeypatch):
    def boom(settings, tenant_id):
        raise BudgetExceeded("default", 1.0, 0.5)
    monkeypatch.setattr(cli, "enforce_budget", boom)
    assert cli.main(["run", "x", "--offline", "--no-memory"]) == 2


# ---------- interrupt / resume loop ----------

def test_run_task_interactive_approval(cli_env, monkeypatch):
    graph = _FakeGraph([
        _interrupt({"type": "tool_approval", "tool": "write_note",
                    "arguments": {"path": "n"}, "subtask": "save"}),
        {"final_answer": "done", "metrics": {}},
    ])
    monkeypatch.setattr(cli, "build_graph", lambda **kw: graph)
    monkeypatch.setattr("builtins.input", lambda *_: "y")
    assert cli._run_task("save a note", auto_approve=False, offline=True, memory_on=False) == 0
    assert graph.invokes == 2


def test_run_task_interactive_clarification(cli_env, monkeypatch):
    graph = _FakeGraph([
        _interrupt({"type": "clarification", "question": "which color?", "subtask": "pick"}),
        {"final_answer": "blue", "metrics": {}},
    ])
    monkeypatch.setattr(cli, "build_graph", lambda **kw: graph)
    monkeypatch.setattr("builtins.input", lambda *_: "blue")
    assert cli._run_task("pick a color", auto_approve=False, offline=True, memory_on=False) == 0
    assert graph.invokes == 2


def test_run_task_auto_approve_and_clarify(cli_env, monkeypatch):
    graph = _FakeGraph([
        _interrupt({"type": "clarification", "question": "q", "subtask": "s"}),
        _interrupt({"type": "tool_approval", "tool": "write_note", "arguments": {}, "subtask": "s"}),
        {"final_answer": "ok", "metrics": {}},
    ])
    monkeypatch.setattr(cli, "build_graph", lambda **kw: graph)
    assert cli._run_task("x", auto_approve=True, offline=True, memory_on=False) == 0
    assert graph.invokes == 3


# ---------- _print_result branches ----------

def test_print_result_rich(capsys):
    cli._print_result(
        {
            "swarm_decision": {"mode": "swarm", "parallelism": 2, "rationale": "split"},
            "plan": ["a", "b"],
            "roles": ["researcher", "analyst"],
            "verdicts": [{"verdict": "pass"}, {"verdict": "fail"}],
            "guard_violations": ["pii"],
            "guard_violations_out": ["leak"],
            "recalled_lessons": ["prefer X"],
            "final_answer": "the answer",
            "structured_output": {"answer": "42"},
            "metrics": {"tool_calls_total": 2, "tool_calls_valid": 1},
            "success": True,
            "stored_lessons": ["learned Y"],
        },
        memory_on=True,
        memory=[1, 2, 3],
    )
    out = capsys.readouterr().out
    assert "composition: swarm" in out and "critic: 1/2" in out
    assert "STRUCTURED OUTPUT" in out and "tool-call validity: 1/2" in out
    assert "learned 1 lesson" in out


def test_print_result_blocked(capsys):
    cli._print_result(
        {"blocked": True, "guard_violations": ["injection"], "final_answer": "refused"},
        memory_on=False, memory=None,
    )
    assert "BLOCKED by guardrails: injection" in capsys.readouterr().out


# ---------- _record_usage (real-usage vs estimate) ----------

def test_record_usage_actual_and_estimate(cli_env):
    settings = cli.get_settings()
    cli._record_usage(settings, "t1", "task one",
                      {"metrics": {"usage": {"total_tokens": 100}},
                       "swarm_decision": {"mode": "single"}, "final_answer": "hi"})
    cli._record_usage(settings, "t2", "task two",
                      {"swarm_decision": {"mode": "swarm", "estimated_cost_usd": 0.5},
                       "results": [{"output": "x"}], "final_answer": "y"})
    totals = CostTracker(settings.usage_log_path).by_tenant()
    assert {"t1", "t2"} <= set(totals)
    assert totals["t2"].cost_usd == pytest.approx(0.5)


def test_show_costs_with_records(cli_env, capsys):
    settings = cli.get_settings()
    CostTracker(settings.usage_log_path).record(
        UsageRecord(tenant_id="acme", task="t", mode="single", est_tokens=10,
                    cost_usd=0.01, blocked=False))
    assert cli._show_costs() == 0
    assert "acme" in capsys.readouterr().out


# ---------- _run_eval real-model failure hint ----------

def test_run_eval_real_failure_hint(cli_env, monkeypatch, capsys):
    class _Boom:
        def __init__(self, *a, **k): ...
        def run(self):
            raise RuntimeError("no key")
    monkeypatch.setattr(cli, "EvalRunner", _Boom)
    assert cli._run_eval(offline=False) == 1
    assert "real-model eval failed" in capsys.readouterr().out


def test_run_eval_offline_reraises(cli_env, monkeypatch):
    class _Boom:
        def __init__(self, *a, **k): ...
        def run(self):
            raise RuntimeError("boom")
    monkeypatch.setattr(cli, "EvalRunner", _Boom)
    with pytest.raises(RuntimeError):
        cli._run_eval(offline=True)  # offline failures re-raise (a real bug, not a missing key)


# ---------- _serve (faked uvicorn + ImportError) ----------

def test_serve_success_via_main(monkeypatch, capsys):
    calls = {}
    fake = types.ModuleType("uvicorn")
    fake.run = lambda *a, **k: calls.setdefault("ran", (a, k))
    monkeypatch.setitem(sys.modules, "uvicorn", fake)
    assert cli.main(["serve", "--port", "8123"]) == 0  # exercises the serve dispatch too
    assert "ran" in calls


def test_serve_missing_uvicorn(monkeypatch, capsys):
    monkeypatch.setitem(sys.modules, "uvicorn", None)  # forces ImportError on `import uvicorn`
    assert cli._serve("127.0.0.1", 8000) == 1
    assert "[server] extra" in capsys.readouterr().out
