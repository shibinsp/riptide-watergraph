"""Coverage for the offline DemoGateway's scripted behavior."""

from __future__ import annotations

import json

from riptide_watergraph.gateway import DemoGateway
from riptide_watergraph.interfaces.gateway import Message


def _complete(gw: DemoGateway, system: str, user: str, tools=None):
    import asyncio

    return asyncio.run(
        gw.complete(
            model="demo",
            messages=[Message(role="system", content=system),
                      Message(role="user", content=user)],
            tools=tools,
        )
    )


def test_plan_splits_on_connectives():
    gw = DemoGateway()
    r = _complete(gw, "You are a planning orchestrator.", "a and b then c")
    assert json.loads(r.content) == ["a", "b", "c"]


def test_compose_then_is_sequential_and_is_parallel():
    gw = DemoGateway()
    r = _complete(gw, "You are a planning composer.", "x and y then z")
    data = json.loads(r.content)
    assert data["mode"] == "swarm"
    tasks = [s["task"] for s in data["subtasks"]]
    assert tasks == ["x", "y", "z"]
    # z (after 'then') depends on x and y; x, y are independent
    assert data["subtasks"][2]["depends_on"] == [0, 1]
    assert data["subtasks"][0]["depends_on"] == []


def test_worker_picks_offered_tool():
    gw = DemoGateway()
    tools = [{"type": "function", "function": {"name": "calculator"}}]
    r = _complete(gw, "You are a worker.", "compute 2 + 2", tools=tools)
    assert r.tool_calls and r.tool_calls[0]["function"]["name"] == "calculator"


def test_worker_falls_back_to_direct_answer():
    gw = DemoGateway()
    # No tools offered and not a recognized verb -> direct content answer.
    r = _complete(gw, "You are a worker.", "ponder the meaning of life", tools=[])
    assert r.content and not r.tool_calls


def test_reflect_returns_lesson_json():
    gw = DemoGateway()
    r = _complete(gw, "You are a reflection module.", "Task: compute 2 + 2\nOutcome: SUCCESS")
    data = json.loads(r.content)
    assert "lesson" in data


def test_word_count_and_uppercase_and_search_branches():
    gw = DemoGateway()
    everything = [{"type": "function", "function": {"name": n}}
                  for n in ("word_count", "uppercase", "web_search")]
    assert _complete(gw, "You are a worker.", "count the words", everything).tool_calls[0]["function"]["name"] == "word_count"
    assert _complete(gw, "You are a worker.", "uppercase this", everything).tool_calls[0]["function"]["name"] == "uppercase"
    assert _complete(gw, "You are a worker.", "search for cats", everything).tool_calls[0]["function"]["name"] == "web_search"
