"""Targeted coverage for the long tail of small modules — edge branches that the
behavioral suites don't reach. Kept together so the intent (close specific gaps) is clear.
"""

from __future__ import annotations

import sys
import types

import pytest

from riptide_watergraph.interfaces.gateway import CompletionResult, Message
from riptide_watergraph.interfaces.memory import MemoryRecord, RetrievedItem
from riptide_watergraph.interfaces.tools import ToolSpec

from .conftest import MockGateway


# ---------- tools/examples.py ----------

def test_calculator_unary_and_reverse():
    from riptide_watergraph.tools.examples import calculator, reverse_text
    assert calculator("-(3) + 4") == "1.0"          # UnaryOp branch
    assert reverse_text("abc") == "cba"


# ---------- tools/enterprise.py ----------

def test_enterprise_stub_handles_unserializable_args():
    from riptide_watergraph.tools.enterprise import _stub
    circular: dict = {}
    circular["self"] = circular                       # json.dumps -> ValueError -> str(kwargs)
    out = _stub("salesforce.get")(payload=circular)
    assert out.startswith("(stub) salesforce.get(")


# ---------- workflows.py ----------

def test_workflow_store_list_empty_and_delete_missing(tmp_path):
    from riptide_watergraph.workflows import WorkflowStore
    store = WorkflowStore(str(tmp_path / "wf"))
    assert store.list() == []                         # dir doesn't exist yet
    assert store.delete("nope") is False


# ---------- swarm/role_library.py ----------

def test_role_library_skips_curated_core(monkeypatch):
    from riptide_watergraph.swarm import role_library as rl
    name = rl._ROLE_DATA[0][0]
    monkeypatch.setattr(rl, "DEFAULT_ROLES", {**rl.DEFAULT_ROLES, name: object()})
    catalog = rl._build()
    assert name not in catalog                        # curated core takes precedence (continue)


# ---------- memory/reflection.py ----------

def test_parse_lesson_empty_and_fenced():
    from riptide_watergraph.memory.reflection import _parse_lesson
    assert _parse_lesson(None, "t") == ("", [])
    lesson, tags = _parse_lesson('```json\n{"lesson": "prefer X", "tags": ["a"]}\n```', "t")
    assert lesson == "prefer X" and tags == ["a"]


# ---------- memory/ranking.py ----------

def test_cosine_edges():
    from riptide_watergraph.memory.ranking import _cosine
    assert _cosine([], [1.0]) == 0.0                  # empty / length mismatch
    assert _cosine([0.0, 0.0], [0.0, 0.0]) == 0.0     # zero-norm


# ---------- memory/rerank.py ----------

def test_reranker_empty_query_overlap():
    from riptide_watergraph.memory.rerank import LexicalOverlapReranker
    item = RetrievedItem(record=MemoryRecord(id="a", text="water rivers"), score=1.0)
    assert LexicalOverlapReranker().rerank("", [item], k=1) == [item]  # overlap -> 0.0 path


# ---------- memory/inmemory.py + jsonfile.py ----------

async def test_inmemory_reflect_noop():
    from riptide_watergraph.memory import InMemoryMemory
    assert await InMemoryMemory().reflect("s") == []


async def test_jsonfile_reflect_and_consolidate_text_dupe(tmp_path):
    from riptide_watergraph.memory import JsonFileMemory
    mem = JsonFileMemory(str(tmp_path / "m.json"))
    assert await mem.reflect("s") == []
    # Two embedding-less records with identical text -> text-equality dedupe branch.
    mem._records = {
        "a": MemoryRecord(id="a", text="same lesson"),
        "b": MemoryRecord(id="b", text="same lesson"),
    }
    assert mem.consolidate() >= 1


def test_jsonfile_load_ignores_corrupt(tmp_path):
    from riptide_watergraph.memory import JsonFileMemory
    p = tmp_path / "m.json"
    p.write_text("{ not json", encoding="utf-8")
    mem = JsonFileMemory(str(p))                       # _load swallows JSONDecodeError
    assert len(mem) == 0


# ---------- memory/embedding.py (LiteLLMEmbedding via fake litellm) ----------

def test_litellm_embedding_dict_and_object(monkeypatch):
    from riptide_watergraph.memory.embedding import LiteLLMEmbedding
    fake = types.ModuleType("litellm")
    fake.embedding = lambda model, input: {"data": [{"embedding": [0.1, 0.2]} for _ in input]}
    monkeypatch.setitem(sys.modules, "litellm", fake)
    assert LiteLLMEmbedding().embed(["x"]) == [[0.1, 0.2]]

    fake.embedding = lambda model, input: types.SimpleNamespace(
        data=[types.SimpleNamespace(embedding=[0.3]) for _ in input])
    assert LiteLLMEmbedding().embed(["x", "y"]) == [[0.3], [0.3]]


# ---------- gateway/demo_gateway.py + resilient.py ----------

async def test_demo_gateway_branches():
    from riptide_watergraph.gateway import DemoGateway
    gw = DemoGateway()
    sup = await gw.complete(model="m", messages=[Message(role="system", content="You are a supervisor")])
    assert sup.content == "[]"
    worker = await gw.complete(model="m", messages=[
        Message(role="system", content="You are a worker acting as x"),
        Message(role="user", content="do"),
        Message(role="tool", content="OBS"),
    ])
    assert "OBS" in (worker.content or "")
    assert [c async for c in gw.stream(model="m", messages=[Message(role="user", content="hi")])]


async def test_resilient_stream_passthrough():
    from riptide_watergraph.gateway import DemoGateway, ResilientGateway
    gw = ResilientGateway(DemoGateway())
    out = [c async for c in gw.stream(model="m", messages=[Message(role="user", content="hi")])]
    assert out  # passthrough yields the inner gateway's chunks


# ---------- swarm/llm_composer.py ----------

async def test_llm_composer_budget_forces_single():
    plan_json = '{"mode": "swarm", "subtasks": [{"task": "a"}, {"task": "b"}]}'
    gw = MockGateway(lambda system, user: CompletionResult(content=plan_json))
    from riptide_watergraph.swarm.llm_composer import LLMSwarmComposer
    decision = await LLMSwarmComposer(gw, model="m").decide("do stuff", budget_usd=0.0)
    assert decision.mode == "single"  # 2 subtasks, but swarm cost > tiny budget -> single


def test_llm_composer_parse_fenced():
    from riptide_watergraph.swarm.llm_composer import _parse
    plan, deps, mode = _parse(
        '```json\n{"mode": "swarm", "subtasks": [{"task": "a"}, {"task": "b", "depends_on": [0]}]}\n```',
        "task")
    assert plan == ["a", "b"] and mode == "swarm"


# ---------- evaluation/runner.py (_score branches) ----------

def test_eval_score_branches():
    from riptide_watergraph.evaluation.runner import EvalRunner
    from riptide_watergraph.evaluation.suite import EvalTask
    assert EvalRunner._score(EvalTask(id="x", prompt="p"), {}, True, "single")[0] is False
    bad_mode = EvalRunner._score(EvalTask(id="x", prompt="p", expect_mode="swarm"), {}, False, "single")
    assert bad_mode[0] is False
    miss = EvalRunner._score(
        EvalTask(id="x", prompt="p", expect_substring="zzz"),
        {"results": [], "final_answer": ""}, False, "single")
    assert miss[0] is False


# ---------- tools/registry.py ----------

async def test_registry_edges():
    from riptide_watergraph.tools import default_registry
    from riptide_watergraph.tools.registry import StaticToolRegistry, ToolValidationError

    reg = StaticToolRegistry()
    reg.register(ToolSpec(name="beta_tool", version="beta", description="d",
                          json_schema={"type": "object"}, side_effecting=False,
                          handler=lambda **k: "ok"))          # non-numeric version key
    assert reg.get("beta_tool").version == "beta"
    with pytest.raises(ToolValidationError):
        reg.list_versions("nope")                              # unknown tool

    assert default_registry().openai_schemas(["calculator"])   # names-filtered branch
    assert await default_registry().retrieve("x", k=0) == []   # k<=0 short-circuit

    reg.register(ToolSpec(name="no_handler", description="d", json_schema={"type": "object"},
                          side_effecting=False, handler=None))
    with pytest.raises(ToolValidationError):
        await reg.invoke("no_handler", {})                     # no_handler branch


# ---------- mcp/client.py ----------

async def test_fake_mcp_client_unknown_and_async_handler():
    from riptide_watergraph.mcp import FakeMcpClient, McpToolInfo

    async def _async_handler(**kwargs):
        return "async-result"

    client = FakeMcpClient({"t": (McpToolInfo(name="t"), _async_handler)})
    assert await client.call_tool("t", {}) == "async-result"   # awaitable result branch
    with pytest.raises(KeyError):
        await client.call_tool("nope", {})                     # unknown tool
