# Monitoring

Every run appends a `UsageRecord` to a per-tenant usage log
(`.riptide_watergraph/usage.jsonl`) with tenant, mode, tokens, cost, latency, success, tool-call counts,
and a timestamp.

## In the Studio

`riptide serve` → **Monitoring** aggregates the log into:

- **KPI cards** — runs, success rate, avg latency, tokens, cost, tool-call validity, blocked
- a **runs / cost-over-time** chart (inline SVG, no libraries)
- a **recent-runs** table

served by `GET /api/monitoring` (`totals`, `by_mode`, `by_tenant`, `recent`, `daily`).

## Costs

```bash
riptide costs
```

prints the per-tenant dashboard (runs, tokens, cost, blocked). Per-tenant **budget ceilings** reject
over-budget runs with HTTP 402.

## Deeper tracing

The optional `[observability]` extra adds per-LLM-call spans via OpenTelemetry + Langfuse. Tracing is
**opt-in** and off by default (`RIPTIDE_WATERGRAPH_DISABLE_TRACING=1` in the Docker image).

```bash
pip install "riptide-watergraph[observability]"
```
