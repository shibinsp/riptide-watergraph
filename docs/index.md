# 🌊 Riptide-Watergraph

A reusable, **"like water"** multi-agent framework built as a thin layer on
[LangGraph](https://langchain-ai.github.io/langgraph/). Pure Python, lean core, every layer swappable
behind a thin ABC.

[![PyPI](https://img.shields.io/pypi/v/riptide-watergraph.svg)](https://pypi.org/project/riptide-watergraph/)
[![Python](https://img.shields.io/pypi/pyversions/riptide-watergraph.svg)](https://pypi.org/project/riptide-watergraph/)
[![Coverage](https://img.shields.io/badge/coverage-100%25-brightgreen.svg)](https://github.com/shibinsp/riptide-watergraph)
[![License](https://img.shields.io/badge/license-MIT-blue.svg)](https://github.com/shibinsp/riptide-watergraph/blob/main/LICENSE)

## What is it?

Riptide-Watergraph is an enterprise-grade multi-agent framework — *like AutoGen*, but built as a **thin
layer on LangGraph** so it inherits durable execution, checkpointing, and human-in-the-loop interrupts
instead of re-authoring orchestration. The **"like water"** philosophy: every layer (gateway, memory,
tools, swarm composer, guardrails) sits behind a small interface, so you can pour in your own
implementation without touching the engine.

## What's in the box

<div class="grid cards" markdown>

- :material-brain: **Self-learning memory** — persistent lessons, recall-injection, hybrid (BM25 + dense) retrieval, reflection
- :material-account-group: **Dynamic swarm** — cost-aware composer, dependency-wave execution, a shared blackboard
- :material-tools: **238 tools out of the box** (750+ with the enterprise pack) and a **219-role catalog**
- :material-shield-check: **Guardrails** — prompt-injection blocking + PII redaction, defense in depth
- :material-account-multiple: **Multi-tenancy** — isolated memory namespaces + per-tenant cost tracking and budgets
- :material-monitor-dashboard: **Like Water Studio** — a dependency-free web UI for chat, workflows, tools, monitoring
- :material-keyboard: **Streaming & interactive HITL** — token-by-token chat + in-browser approve/deny
- :material-connection: **MCP interop** — plug external Model Context Protocol tool servers straight in

</div>

## Status

**v0.12.0** · on [PyPI](https://pypi.org/project/riptide-watergraph/) · Stages 1–4 + Studio · **100% test
coverage** · MIT licensed.

## Next steps

- [Install](install.md) the package and extras
- Follow the [Quickstart](quickstart.md) (offline, no API key)
- Launch the [Like Water Studio](studio.md)
- Read the [Architecture](architecture.md)
