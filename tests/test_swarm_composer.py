"""Cost-aware swarm composer gate: single vs swarm decisions."""

from __future__ import annotations

from riptide_watergraph.swarm import HeuristicSwarmComposer


async def test_simple_task_stays_single():
    composer = HeuristicSwarmComposer(model="m")
    d = await composer.decide("compute 2 + 2")
    assert d.mode == "single"
    assert d.parallelism == 1


async def test_decomposable_task_goes_swarm():
    composer = HeuristicSwarmComposer(model="m")
    d = await composer.decide("search cats and count words and uppercase the title")
    assert d.mode == "swarm"
    assert d.parallelism == 3
    assert len(d.members) == 3
    # The swarm costs more in tokens than a single agent would — the gate accepts
    # that because the work genuinely parallelizes.
    assert d.estimated_cost_usd > d.single_cost_usd


async def test_side_effecting_task_stays_single():
    composer = HeuristicSwarmComposer(model="m")
    d = await composer.decide("research three vendors and save a report and email it")
    assert d.mode == "single"  # needs human-approved side effects -> serial


async def test_budget_ceiling_forces_single():
    composer = HeuristicSwarmComposer(model="m")
    d = await composer.decide(
        "alpha and beta and gamma and delta", budget_usd=0.0
    )
    assert d.mode == "single"  # swarm would exceed a zero budget


async def test_parallelism_capped_by_max():
    composer = HeuristicSwarmComposer(model="m", max_parallelism=2)
    d = await composer.decide("a and b and c and d and e")
    assert d.mode == "swarm"
    assert d.parallelism == 2  # capped
