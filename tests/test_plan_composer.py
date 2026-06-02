"""StaticPlanComposer replays a fixed plan/roles/dependencies as a SwarmDecision."""

from __future__ import annotations

import asyncio

from riptide_watergraph.swarm import StaticPlanComposer


def _decide(**kw):
    return asyncio.run(StaticPlanComposer(**kw).decide("ignored task"))


def test_propagates_plan_roles_deps_and_swarm_mode():
    d = _decide(plan=["a", "b", "c"], roles=["researcher", "analyst", "scribe"],
                dependencies=[[], [0], [1]], model="m")
    assert d.mode == "swarm"
    assert d.plan == ["a", "b", "c"]
    assert d.roles == ["researcher", "analyst", "scribe"]
    assert d.dependencies == [[], [0], [1]]
    assert d.estimated_cost_usd > 0  # not $0 (offline usage log relies on this)
    assert [m.role for m in d.members] == ["researcher", "analyst", "scribe"]


def test_single_node_is_single_mode():
    d = _decide(plan=["only"], roles=["generalist"], dependencies=[[]], model="m")
    assert d.mode == "single"


def test_explicit_mode_override():
    d = _decide(plan=["a", "b"], roles=["x", "y"], dependencies=[[], []], model="m", mode="single")
    assert d.mode == "single"
