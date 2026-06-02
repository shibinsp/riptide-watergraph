"""Monitoring: enriched usage records + the /api/monitoring aggregation (offline)."""

from __future__ import annotations

import pytest

from riptide_watergraph.observability.cost import CostTracker, UsageRecord

pytest.importorskip("fastapi")
from fastapi.testclient import TestClient  # noqa: E402

from riptide_watergraph.config import get_settings  # noqa: E402
from riptide_watergraph.server import app  # noqa: E402


@pytest.fixture
def client(tmp_path, monkeypatch):
    monkeypatch.setenv("DATA_DIR", str(tmp_path))
    monkeypatch.setenv("CHECKPOINT_PATH", str(tmp_path / "cp.sqlite"))
    monkeypatch.setenv("RIPTIDE_WATERGRAPH_DISABLE_TRACING", "1")
    return TestClient(app)


def test_usage_record_new_fields_default():
    r = UsageRecord(tenant_id="t", task="x")
    assert r.latency_ms == 0 and r.success is None
    assert r.tool_calls_total == 0 and r.tool_calls_valid == 0 and r.n_subtasks == 0


def test_run_records_latency_and_success(client):
    client.post("/run", json={"task": "compute 21 * 2", "offline": True, "memory": True})
    records = CostTracker(get_settings().usage_log_path).load()
    assert records
    last = records[-1]
    assert last.ts > 0
    assert last.latency_ms >= 0
    assert last.success is not None  # memory on -> reflection sets success


def test_monitoring_aggregates(client):
    client.post("/run", json={"task": "compute 21 * 2", "offline": True, "memory": False})
    client.post("/run", json={
        "task": "search cats and count the words and uppercase the title",
        "offline": True, "memory": False})
    m = client.get("/api/monitoring").json()
    assert m["totals"]["runs"] == 2
    assert set(m["by_mode"]) <= {"single", "swarm"}
    assert m["daily"] and "runs" in m["daily"][0]
    assert len(m["recent"]) == 2
    assert {"ts", "task", "mode", "latency_ms", "tokens", "cost_usd", "blocked"} <= set(m["recent"][0])


def test_monitoring_empty_when_no_usage(client):
    m = client.get("/api/monitoring").json()
    assert m["totals"]["runs"] == 0
    assert m["recent"] == []
