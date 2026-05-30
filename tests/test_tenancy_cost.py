"""Multi-tenancy isolation + per-tenant cost aggregation."""

from __future__ import annotations

from riptide_watergraph.memory import JsonFileMemory
from riptide_watergraph.memory.types import lesson_record
from riptide_watergraph.observability.cost import (
    CostTracker,
    UsageRecord,
    estimate_tokens,
)


async def test_tenant_memory_is_isolated(tmp_path):
    a = JsonFileMemory(tmp_path / "tenants" / "a" / "mem.json")
    b = JsonFileMemory(tmp_path / "tenants" / "b" / "mem.json")
    await a.write([lesson_record("tenant A private strategy for billing")])

    assert len(a) == 1 and len(b) == 0
    # Tenant B retrieves nothing from tenant A's namespace.
    assert await b.retrieve("strategy", k=5) == []


def test_cost_tracker_aggregates_by_tenant(tmp_path):
    tracker = CostTracker(tmp_path / "usage.jsonl")
    tracker.record(UsageRecord(tenant_id="acme", task="t1", est_tokens=100, cost_usd=0.001))
    tracker.record(
        UsageRecord(tenant_id="acme", task="t2", est_tokens=50, cost_usd=0.0005, blocked=True)
    )
    tracker.record(UsageRecord(tenant_id="globex", task="t3", est_tokens=200, cost_usd=0.002))

    totals = tracker.by_tenant()
    assert totals["acme"].runs == 2
    assert totals["acme"].est_tokens == 150
    assert abs(totals["acme"].cost_usd - 0.0015) < 1e-9
    assert totals["acme"].blocked == 1
    assert totals["globex"].runs == 1


def test_estimate_tokens():
    assert estimate_tokens("") == 0
    assert estimate_tokens("a" * 40) == 10
