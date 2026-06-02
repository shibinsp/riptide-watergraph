# Changelog

All notable changes to this project are documented here. The format is based on
[Keep a Changelog](https://keepachangelog.com/), and this project adheres to
[Semantic Versioning](https://semver.org/).

## [Unreleased]

## [0.5.0] - 2026-06-02

### Added
- **100+ stdlib tools** (`tools/library.py`): ~150 read-only, dependency-free tools across
  text, regex, JSON/CSV, encoding, hashing, math/stats, datetime, units, collections, random,
  extract, code, and color categories. A gated **network** pack (`RIPTIDE_ENABLE_NETWORK=1`)
  adds read-only HTTP/DNS tools; extra exec tools (`run_node`, `lint_python`, `format_python`)
  join the existing `RIPTIDE_ENABLE_EXEC=1` set.
- **100+ role catalog** (`swarm/role_library.py`): ~120 domain specialists (engineering, data,
  devops/SRE, security, QA, product, writing, research, finance, ops, design) with focused
  prompts, category-scoped tool allow-lists, and descriptions. `role_for` routes the
  highest-traffic specialists; `get_role`/`all_roles` resolve the full catalog.
- `ToolSpec` and `AgentRole` gain `category`/`tags` (and role `description`) for grouping.
- **Studio Tool Runner** (`POST /api/tools/{name}/invoke`, read-only tools only) and a UI view
  to invoke a single tool with a schema-built form.
- **Live execution trace** (`GET /api/run/trace` SSE + `service.stream_task`) streamed
  node-by-node into the Playground.
- Studio **search + category filters** on the Tools and Roles galleries, and a local
  **run history** view with replay.

## [0.4.0] - 2026-06-02

### Added
- **Agentic developer tools** for coding & bug-fixing, all confined to a **workspace sandbox**
  (`Settings.workspace_dir`): `read_file`, `list_dir`, `find_files`, `search_code` (read-only),
  `write_file`, `apply_edit` (side-effecting). Code-execution tools `run_python`, `run_command`,
  `run_tests` are **opt-in** — registered only when `RIPTIDE_ENABLE_EXEC=1`.
- A **`coder`** agent role (with the dev-tool allow-list); `role_for` now routes code/bug/fix/
  refactor/debug subtasks to it.
- **Studio Connections panel** + `GET/POST /api/connection` and `POST /api/connection/test`:
  set the AI provider (OpenAI / Anthropic / Custom OpenAI-compatible) + model + API key at
  runtime. The key is held **in memory only** (never written to disk) and **masked** in responses;
  it is mirrored to the environment so the next run connects with no restart.
- **Modern enterprise UI redesign** of the Studio: a design system with **light + dark themes**
  (toggle persisted in `localStorage`), an app shell (top bar with connection-status pill,
  grouped sidebar), toast notifications, toggle switches, segmented controls, and copy-to-clipboard
  JSON — all still dependency-free vanilla JS/CSS.

### Security
- File tools reject `..`/absolute paths that escape the workspace sandbox; code-execution tools
  are off by default. The Studio API is unauthenticated and binds `127.0.0.1` — do not expose it
  publicly.

## [0.3.0] - 2026-06-02

### Added
- **Like Water Studio** — a dependency-free web UI (vanilla-JS SPA, no build step) served by
  `riptide serve` at `/`: Playground with a full run inspector, Sessions, Tools, Roles, Eval,
  and Costs views.
- Read-only studio API: `GET /api/meta`, `/api/tools`, `/api/roles`, `/api/costs`, and
  `POST /api/eval`.
- `RunResult` now carries run detail (`plan`, `roles`, `results`, `verdicts`,
  `swarm_decision`, `metrics`, `guard_violations`, `guard_violations_out`, `clarifications`)
  for inspection; `RunRequest` exposes `guardrails`, `critic`, `supervisor`, `react_steps`,
  `vote_k`, and `final_schema`.

### Fixed
- `service.run_task` now forwards `critic`/`supervisor`/`react_steps`/`vote_k` to
  `build_graph` (previously only the CLI could use these — the HTTP API silently ignored them).

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
