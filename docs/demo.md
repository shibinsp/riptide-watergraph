# Demo walkthrough

A five-minute tour of the Like Water Studio, all offline (no API key).

```bash
pip install "riptide-watergraph[server]"
riptide serve            # open http://127.0.0.1:8000/
```

## 1. Chat

Open **Chat**. The empty-state shows a colorful 🌊 hero and a grid of prompt cards — click one, or type
your own and press **Enter**.

- Toggle **Direct token stream** to watch the answer type out token-by-token.
- Toggle **Ask before running tools**, then send *"save a note about water"*. The run pauses on an
  **approval card** showing the tool, its arguments, and the subtask. Click **Approve** to execute it
  once, or **Deny** to skip it.
- Each reply carries **agent attribution** (the role(s) that ran), a timestamp, and a copy button.

## 2. Playground

Open **Playground**, enter *"research water then compute 21 × 2 and summarize"*, and enable **Critic** +
**Live trace**. Run it: the node trace streams (`orchestrate → swarm_worker → critic → finalize`), then
the inspector shows the plan↔roles table, per-subtask results, the critic verdicts, and metrics.

## 3. Workflows

Open **Workflows**. Drag a `researcher`, an `analyst`, and a `scribe` onto the canvas. Connect
researcher → analyst → scribe (click an out-port, then an in-port). Set each node's instruction in the
inspector, then **Run** with the live trace — watch the wave execution and per-node results. **Save** it,
reload the page, and **Load** it back. (A cycle is refused on the canvas and by the API with 422.)

## 4. Tools & Tool Runner

Open **Tools** — search and filter the 238-tool gallery by category. Open **Tool Runner**, pick a
read-only tool like `sha256`, fill the auto-generated form, and **Run** to see the output. (Set
`RIPTIDE_ENABLE_ENTERPRISE=1` before `riptide serve` to surface ~750 tools.)

## 5. Monitoring & Eval

After a few runs, open **Monitoring** — KPI cards (runs, success rate, avg latency, tokens, cost), a
runs/cost-over-time chart, and a recent-runs table. Open **Eval** and **Run** to score the offline suite
(4/4 = 100%).

## 6. Connections & MCP

Open **Connections** to point the Studio at a real provider (OpenAI / Anthropic / Custom) — the key is
held in memory and masked. Open **MCP Servers** to connect a gated, allowlisted MCP server (needs
`RIPTIDE_ENABLE_MCP_CONNECT=1` + `RIPTIDE_MCP_SERVERS`); its tools then appear everywhere.

---

!!! tip "Screenshots"
    Want annotated screenshots of each view? They can be captured from a running instance and dropped
    into `docs/img/`. The walkthrough above mirrors the live UI step-for-step in the meantime.
