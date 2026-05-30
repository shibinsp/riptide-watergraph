# Riptide-Watergraph

A reusable, enterprise-grade multi-agent framework — conceptually *like AutoGen*, but built as a **thin layer on [LangGraph](https://github.com/langchain-ai/langgraph)** rather than re-authoring the orchestration runtime. The design goal is to be **"like water"**: a layered, modular substrate where every layer is swappable behind a thin interface.

> **Stages 1–2 implemented.** Stage 1: the runnable spine — orchestrator decomposes a task → worker calls a
> tool → human-approval interrupt → resume → finalize, with tracing. **Stage 2: memory + self-learning** —
> a `recall` step injects relevant past lessons into prompts, and a `reflect` step distills new lessons into
> persistent memory after each run. The remaining differentiators (dynamic **swarm composer**, on-demand
> **tool registry**) are interface-stubbed seams for Stages 3–4.

## Why this shape

The framework consumes what LangGraph already does well (durable graph execution, checkpointing, human-in-the-loop interrupts) and concentrates custom engineering on the three things no framework ships off the shelf:

1. **Memory + self-learning** — model-agnostic, consolidating long-term memory with reflection loops.
2. **Dynamic swarm composer** — a runtime policy that decides single-agent-vs-swarm and team composition per task, with a cost-aware gate.
3. **Tool/skill registry** — a reusable, versioned, MCP-compatible catalog with on-demand tool retrieval.

Pure Python, one toolchain. The retrieval-ranking core (**BM25** lexical scoring + **Reciprocal Rank Fusion, k=60**) lives in [`memory/ranking.py`](src/riptide_watergraph/memory/ranking.py) behind a small, stable signature — if profiling ever shows it's a hot path at scale, those two functions can be swapped for a native implementation without touching the rest of the framework.

## Layers (Stage 1 surface)

| Layer | Stage-1 implementation | Later-stage seam |
|---|---|---|
| Model gateway | `LiteLLMGateway` (API-first, OpenAI-compatible) | local vLLM endpoint |
| Agent core | thin `Agent` over the gateway | typed agent core |
| Orchestration | LangGraph orchestrator-worker graph + `SqliteSaver` | richer graphs |
| Memory | `JsonFileMemory` (persistent) + `LLMReflector`; BM25+RRF recall, distilled lessons | Letta/Mem0 + pgvector at scale |
| Swarm composer | `SingleAgentComposer` (cost-aware gate stubbed) | runtime team formation |
| Tool registry | `StaticToolRegistry`; MCP seam noted | versioned + on-demand retrieval |
| HITL | LangGraph `interrupt()` approval gate | escalation queues |
| Observability | Langfuse via OTEL + own graph spans | eval/regression gates |

## Quickstart

Prerequisites: Python 3.11+. No compiler or other toolchain needed.

```bash
# 1. Install (editable) with dev deps
pip install -e ".[dev]"

# 2. Verify everything
pytest                           # graph e2e + ranking + tool-call gate

# 3. Run a task end-to-end, fully offline (no API key / network):
#    orchestrate -> worker -> approval interrupt -> resume -> finalize
riptide-watergraph run "Save a note about water" --offline --auto-approve
riptide-watergraph run "What is 21 * 2?" --offline      # read-only: no interrupt

# Self-learning: run the same task twice — the 2nd run recalls the lesson the 1st stored.
riptide run "compute 21 * 2" --offline      # learns a lesson
riptide run "compute 21 * 2" --offline      # "recalled 1 lesson(s): ..."
riptide run "compute 21 * 2" --offline --no-memory   # disable recall + reflection

# 4. Use a real model (installs the LiteLLM gateway + tracing extras)
pip install -e ".[all]"
cp .env.example .env             # fill OPENAI_API_KEY / model + (optional) Langfuse keys
riptide-watergraph run "Summarize and save a note about water"   # drop --offline
```

## Repository layout

```
Riptide-Watergraph/
├── pyproject.toml               # setuptools build, src layout
└── src/riptide_watergraph/
    ├── interfaces/              # ABCs = the swappable seams (incl. Reflector)
    ├── gateway/                 # LiteLLMGateway + DemoGateway (offline)
    ├── memory/                  # JsonFileMemory, ranking, reflection, types
    ├── tools/                   # StaticToolRegistry + example tools
    ├── swarm/                   # SingleAgentComposer (stub)
    ├── graph/                   # state, nodes (recall/reflect), builder (LangGraph)
    ├── observability/           # OTEL + Langfuse tracing
    ├── config.py                # pydantic-settings
    └── cli.py                   # `riptide-watergraph run`
```

## Self-learning loop (Stage 2)

After each task the graph runs a **`reflect`** step: it judges success/failure, asks the
model to distill one reusable lesson, and writes it to persistent memory (`JsonFileMemory`,
deduped by content hash, capped to bound growth). At the start of the next task a **`recall`**
step retrieves the most relevant lessons (BM25 + RRF) and injects them into the orchestrator
and worker prompts. Over repeated runs the lesson store grows and is reused — improvement
**without any fine-tuning** (the Reflexion / ReasoningBank pattern). See
[`test_self_learning.py`](tests/test_self_learning.py) for a deterministic proof that success
rises across runs purely from recall + reflection.

## Roadmap

- **Stage 2 ✅** — memory + reflection: persistent lessons, recall-injection, end-of-task reflection (done).
- **Stage 3** — dynamic swarm composer + tool registry with on-demand retrieval (must beat single-agent *net of token cost*).
- **Stage 4** — guardrails, multi-tenancy, per-tenant cost dashboards, optional Temporal + SGLang; swap `JsonFileMemory` → pgvector at scale.

## License

MIT
