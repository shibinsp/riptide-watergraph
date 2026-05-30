# Changelog

All notable changes to this project are documented here. The format is based on
[Keep a Changelog](https://keepachangelog.com/), and this project adheres to
[Semantic Versioning](https://semver.org/).

## [Unreleased]

## [0.2.0] - 2026-05-30

### Added
- `LICENSE` (MIT), `CONTRIBUTING.md`, `CHANGELOG.md`, and runnable `examples/`
  (`quickstart`, `custom_tool`, `mcp_tools`, `real_model_eval`).
- `PgVectorMemory` — Postgres + pgvector backend (dense cosine search), a drop-in for
  `JsonFileMemory` at scale (lazy `psycopg` import; `[pgvector]` extra).

### Changed
- `EvalRunner(offline=False)` now uses the configured model wrapped in `ResilientGateway`
  (previously a placeholder); `riptide eval` prints a setup hint on failure.
- CI now runs **blocking** `mypy`, lints `examples/`, and gates coverage at `--cov-fail-under=80`.

### Fixed
- Type errors across the gateway/composer/cli so `mypy src` passes cleanly.

## [0.1.0] - 2026-05-30

### Added
- **Orchestration spine** — LangGraph orchestrator→worker→finalize with a durable
  `SqliteSaver` checkpointer and a human-in-the-loop approval `interrupt()`.
- **Self-learning memory** — `recall` + `reflect` loop; hybrid retrieval (BM25 + dense
  embeddings fused by RRF) with reranking, episodic trajectory storage, consolidation
  /decay, and a lesson quality gate. Persistent `JsonFileMemory`.
- **Dynamic swarm** — cost-aware `HeuristicSwarmComposer` and `LLMSwarmComposer`;
  dependency-ordered wave execution with a shared blackboard; per-role model routing.
- **Tools** — versioned `StaticToolRegistry` with on-demand BM25 retrieval; MCP interop
  (`FakeMcpClient`, `register_mcp_tools`, `StdioMcpClient`).
- **Production hardening** — `ResilientGateway` (timeouts + retries), tool-error
  isolation, real token-usage cost accounting, guardrails (prompt-injection block + PII
  redaction), multi-tenancy with per-tenant cost dashboard and budget enforcement.
- **Service** — FastAPI app (`riptide serve`): `POST /run`, SSE `/run/stream`, multi-turn
  session endpoints.
- **Quality** — offline evaluation suite as a CI regression gate; ruff + mypy + coverage;
  CI green on Python 3.11–3.13.

[Unreleased]: https://github.com/shibinsp/riptide-watergraph/compare/v0.2.0...HEAD
[0.2.0]: https://github.com/shibinsp/riptide-watergraph/compare/v0.1.0...v0.2.0
[0.1.0]: https://github.com/shibinsp/riptide-watergraph/releases/tag/v0.1.0
