# Changelog

All notable changes to this project are documented here. The format is based on
[Keep a Changelog](https://keepachangelog.com/), and this project adheres to
[Semantic Versioning](https://semver.org/).

## [Unreleased]

## [0.9.0] - 2026-06-02

### Added
- **Monitoring dashboard** — a Studio "Monitoring" view + `GET /api/monitoring` that aggregate the
  per-run usage log into KPIs (runs, success rate, avg latency, tokens, cost, tool-call validity,
  blocked), runs/cost-over-time charts (inline SVG), by-mode breakdown, and a recent-runs table.
- `UsageRecord` now captures `latency_ms`, `success`, `tool_calls_total/valid`, `n_subtasks`, and a
  real `ts` (set at record time); `run_task`/`stream_task` measure end-to-end latency.
- **PyPI release pipeline** — `.github/workflows/publish.yml` builds + publishes on a `vX.Y.Z` tag
  via PyPI Trusted Publishing (OIDC, no stored token). Added `[project.urls]` + classifiers and
  documented `pip install riptide-watergraph` (+ the `git+https` install that works pre-release).

## [0.8.0] - 2026-06-02

### Added
- **Enterprise connector catalog** (`tools/enterprise.py`): ~518 data-driven integration tool
  specs (≈37 vendors × actions across CRM, ITSM, DevOps, SCM, cloud, storage, data, comms, docs,
  HR, finance, support) — properly schema'd, categorized by domain, searchable, role-assignable.
  Offline they are **deterministic stubs**; they become real when bound to an **MCP server**
  (`register_mcp_tools`). **Opt-in** via `RIPTIDE_ENABLE_ENTERPRISE=1` (off by default). Read
  actions are read-only/inline; write actions are `side_effecting` (HITL-gated, inert until bound).
- **~70 more real stdlib utilities** in `tools/library.py` (string distance/LCS, validation &
  format checks, more stats/math/finance, geo/haversine, color, datetime, encoding) — the default
  registry now ships ~238 always-on tools (756 with the enterprise pack enabled).
- **~100 more roles** in `swarm/role_library.py` — enterprise functions (sales, marketing,
  support, HR, finance, legal, compliance, operations, IT, analytics) and industry verticals
  (healthcare, fintech, insurance, retail, manufacturing, logistics, telecom, energy). ~219 total.
- **AutoGen-Studio-style chat redesign**: a 3-pane layout — left **conversation list**
  (new/switch/delete), center thread with an **empty-state + clickable sample prompts**, **agent
  name + avatar attribution**, per-message **timestamps + copy**, a **Stop** button to cancel a
  streaming run and **Regenerate**; cleaner modern styling.

## [0.7.0] - 2026-06-02

### Added
- **Workflow builder** — a drag-and-drop canvas in the Studio (Workspace → Workflows) to compose
  a multi-agent workflow: drag roles onto the canvas as **step nodes** (role + instruction),
  connect them into a **dependency DAG**, then Run with a live node-by-node trace and per-node
  results. Save/load named workflows and Clear.
- `StaticPlanComposer` (`swarm/plan_composer.py`) — replays a user-authored plan/roles/dependencies
  as a `SwarmDecision`, so a hand-drawn DAG runs on the existing swarm engine with **no graph
  changes**.
- `workflows.py` — `WorkflowSpec` models, `validate_spec` (rejects cycles/dups/dangling/self/empty
  via Kahn), `spec_to_plan` (topo-sort → plan/roles/dependencies), and a slug-safe `WorkflowStore`.
- `service.run_workflow` / `stream_workflow` + a `composer` override on `build_components`/
  `run_task`/`stream_task`.
- Endpoints: `GET/POST/GET{name}/DELETE /api/workflows`, `POST /api/workflows/run`, and
  `GET /api/workflows/run/stream` (SSE).

### Notes
- Per-node model/tool overrides are not exposed: the swarm worker uses one global
  `worker_model`/`sampling`; nodes carry role + instruction, tool scope comes from the role.
  Side-effecting tools stay inert on the workflow (swarm) path.

## [0.6.0] - 2026-06-02

### Added
- **Chat playground** (replaces the basic Sessions view): an AutoGen-Studio-style conversation
  with message bubbles, a model-settings side panel, **live "thinking" trace** streaming (graph
  nodes appear as they run, then the answer), collapsible **agent attribution + details** per
  reply (plan↔roles, agent steps + tool calls, critic verdicts, metrics), and **export / clear**.
- **Model sampling controls** threaded end-to-end (`temperature`, `top_p`, `max_tokens`) via a
  `sampling` dict on `GraphContext` spread into every gateway call; exposed on `RunRequest`,
  `MessageRequest`, and the chat UI (with Precise/Balanced/Creative presets). This also makes
  self-consistency voting (`vote_k>1`) produce diverse samples (voting now defaults to
  `temperature=0.7` when none is set).
- Per-turn composition knobs in chat (memory, guardrails, critic, supervisor, single/swarm,
  llm_composer, ReAct steps, vote k).
- Backend: `service.stream_task` generalized to all knobs + history; `SessionStore` turns enriched
  with plan/roles/results/verdicts/metrics + a `clear()`; new `GET
  /api/sessions/{id}/messages/stream` (SSE) and `DELETE /sessions/{id}`.

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
