"""Per-tenant usage + cost tracking.

Each run appends a ``UsageRecord`` to a JSONL log, attributed to a tenant. The
``costs`` CLI subcommand aggregates the log into a per-tenant dashboard. Token/cost
figures are estimates (real models also report ``usage``, which can be wired in here);
the point is attribution and visibility, tracked from day one.
"""

from __future__ import annotations

import json
from pathlib import Path

from pydantic import BaseModel, Field


def estimate_tokens(text: str) -> int:
    """Rough token estimate (~4 chars/token)."""
    return max(0, len(text) // 4)


class UsageRecord(BaseModel):
    """One run's usage, attributed to a tenant."""

    tenant_id: str
    task: str
    mode: str = "single"  # single | swarm
    est_tokens: int = 0
    cost_usd: float = 0.0
    blocked: bool = False
    ts: float = 0.0


class TenantTotals(BaseModel):
    """Aggregated usage for one tenant."""

    tenant_id: str
    runs: int = 0
    est_tokens: int = 0
    cost_usd: float = 0.0
    blocked: int = 0


class CostTracker:
    """Append-only JSONL usage log with per-tenant aggregation."""

    def __init__(self, path: str | Path) -> None:
        self.path = Path(path)

    def record(self, rec: UsageRecord) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        with self.path.open("a", encoding="utf-8") as fh:
            fh.write(json.dumps(rec.model_dump()) + "\n")

    def load(self) -> list[UsageRecord]:
        if not self.path.exists():
            return []
        records: list[UsageRecord] = []
        for line in self.path.read_text(encoding="utf-8").splitlines():
            line = line.strip()
            if line:
                records.append(UsageRecord(**json.loads(line)))
        return records

    def by_tenant(self) -> dict[str, TenantTotals]:
        totals: dict[str, TenantTotals] = {}
        for rec in self.load():
            t = totals.setdefault(rec.tenant_id, TenantTotals(tenant_id=rec.tenant_id))
            t.runs += 1
            t.est_tokens += rec.est_tokens
            t.cost_usd = round(t.cost_usd + rec.cost_usd, 6)
            if rec.blocked:
                t.blocked += 1
        return totals
