# Changelog

All notable changes to this project are documented here. The format is based on
[Keep a Changelog](https://keepachangelog.com/), and this project adheres to
[Semantic Versioning](https://semver.org/).

## [Unreleased]

## [0.17.0] - 2026-06-07

### Added
- **Deliberate reasoning (verified best-of-N + confidence)** — track 3 of the AGI-direction roadmap. A
  new `riptide_watergraph.reasoning` package: a `Verifier` seam (`HeuristicVerifier` offline /
  `LLMVerifier`) and `deliberate(...)`, which generates several candidates from *diverse* reasoning
  styles, scores each, and returns the best with a calibrated **confidence** (verifier score blended with
  candidate agreement) — a metacognition signal for "escalate when unsure." `service.deliberate_task` +
  `riptide deliberate "<task>"`. Additive (no graph-path change), pure-Python, offline-testable. Docs:
  [Deliberate reasoning](docs/deliberation.md).

## [0.16.0] - 2026-06-07

### Added
- **Cognitive memory (knowledge graph + consolidation)** — track 2 of the AGI-direction roadmap. A
  semantic-memory store of `(subject, predicate, object)` facts (`KnowledgeGraph`, merge-on-add with a
  recurrence `weight`) behind a `TripleExtractor` seam (`RuleTripleExtractor` offline / `LLMTripleExtractor`),
  plus a **consolidation "sleep" cycle** (`consolidate_memory` + `riptide consolidate`) that distils
  accumulated **episodic** memory into the graph and writes **SEMANTIC** facts back into the store. The
  existing `recall` node already injects semantic records, so consolidated knowledge is surfaced into
  prompts on future runs **with no graph change** — per-tenant, pure-Python, offline-testable. Docs:
  [Cognitive memory](docs/cognitive-memory.md).

## [0.15.0] - 2026-06-07

### Added
- **Self-authored skills (SkillForge)** — track 1 of the AGI-direction roadmap. The agent distills a
  successful run into a reusable, parameterized **skill** (a prompt-program), verifies it, persists it,
  and registers it as a `skill.<name>` tool so future runs invoke it directly — capability acquisition,
  à la Voyager. New `riptide_watergraph.skills` package behind ABCs (`SkillSynthesizer`, `SkillStore`)
  with `LLMSkillSynthesizer`, `JsonFileSkillStore`, `skill_to_spec`, `verify_skill`; a gated `skill_forge`
  graph node; `RunResult.learned_skills`; CLI `riptide run --learn-skills` and `riptide skills`.
  **Off by default** (`--learn-skills` / `RIPTIDE_ENABLE_SKILLS=1`), verified before registration,
  per-tenant, and code-execution-free (safe by construction). Docs: [Self-authored skills](docs/skills.md).

## [0.14.0] - 2026-06-06

### Added
- **OpenAI-compatible API.** A `POST /v1/chat/completions` endpoint that speaks the OpenAI
  chat-completions wire format — point any OpenAI SDK / LangChain / OpenWebUI / `curl` client at
  `<base>/v1` and the full agentic graph (memory, swarm, tools, guardrails) answers. The last message
  is the task; earlier `user`/`assistant` messages become history. `stream=true` returns
  `chat.completion.chunk` SSE deltas terminated by `data: [DONE]`; otherwise a single `chat.completion`.
  A riptide-specific `"offline": true` field runs the deterministic gateway (no API key). Over-budget
  tenants get HTTP 402; empty `messages` gets 400. Docs: [OpenAI-compatible API](docs/openai-api.md).

## [0.13.0] - 2026-06-06

### Added
- **Documentation site.** A [mkdocs-material](https://squidfunk.github.io/mkdocs-material/) site under
  `docs/` (install, quickstart, studio, streaming & HITL, tools & roles, workflows, MCP, evaluation,
  monitoring, architecture, HTTP API, deploy, demo) published to **GitHub Pages** by a new
  `.github/workflows/docs.yml` on push to `main`. A `docs` extra (`mkdocs-material`) builds it locally.
- **Docker Compose.** A `docker-compose.yml` runs the Studio with a persistent `DATA_DIR` volume, plus a
  `docs/deploy.md` covering Docker, Compose, hosting, and the full env-var reference.

### Changed
- `[project.urls] Documentation` now points at the hosted docs site; README links to it.

## [0.12.0] - 2026-06-06

### Added
- **Real-model proof path.** `examples/real_model_chat.py` runs one task through the library against a
  live LLM (`run_task(offline=False)`), and `tests/test_eval_real_smoke.py` is a skip-guarded smoke test
  that runs the full eval suite end-to-end when `OPENAI_API_KEY`/`ANTHROPIC_API_KEY` is set (skipped in
  CI). The real-model wiring (`EvalRunner(offline=False)` → `ResilientGateway(LiteLLMGateway)`) stays
  covered offline against a faked boundary.

### Fixed
- Replaced the stale `AGENTIC_WATER_MODEL` env-var name (a rename leftover) with `RIPTIDE_WATERGRAPH_MODEL`
  in `examples/real_model_eval.py` and the `riptide eval` real-model error hint.

## [0.11.0] - 2026-06-03

### Added
- **Real token-by-token chat streaming.** `service.stream_chat_tokens` + `GET /api/chat/stream` (SSE)
  stream the model's output deltas through `gateway.stream()` (single-agent, no graph) — the offline
  `DemoGateway` yields once, a live LiteLLM gateway yields real tokens. The Studio Chat has a **"Direct
  token stream"** toggle for a type-as-you-read experience.
- **Interactive in-browser HITL approval.** `service.run_interactive` / `resume_interactive` +
  `POST /api/run/interactive` and `POST /api/run/{thread_id}/resume` pause a run at a side-effecting tool
  (`auto_approve=False`), return a `PendingApproval` with the thread id + action, and resume over the
  durable `SqliteSaver` thread. The Studio Chat has an **"Ask before running tools"** toggle that renders
  an **approval card** (tool + arguments + subtask) with Approve/Deny.

### Changed
- **Studio redesign** — a Microsoft Fluent / Azure-portal look (Segoe UI, communication-blue accent,
  warm-neutral grays, 4px corners, left-bar nav selection, subtle elevation; light + dark), a **colorful
  🌊 wave** logo (top-bar + chat hero + favicon), and an **Azure-Foundry-style Chat empty-state**
  (centered, a 2-column prompt-card grid) with a clean rounded **composer box**.
- **README modernized** — centered hero, an **About** section, a features grid, and collapsible deep-dives.
- **Test coverage at 100%**, enforced in CI (`--cov-fail-under=100`). Previously-untested paths now run
  under test — `cli.py`, the `litellm`/`psycopg`/MCP-stdio/OTEL boundaries (faked modules execute them in
  CI), and server SSE/error branches — plus `skipif`-guarded **live** tests for local runs with real
  credentials. Only genuinely non-executable lines are excluded via `exclude_lines` / `# pragma: no cover`.

## [0.10.0] - 2026-06-03

### Added
- **Real MCP connectors (gated + allowlisted).** A Studio "MCP Servers" view and
  `GET/POST /api/mcp[/connect|/disconnect]` let an operator attach an external Model Context
  Protocol server so its tools become real, runnable tools across Chat, Playground, Workflows and
  the Tool Runner. The feature is **off by default** — it works only when
  `RIPTIDE_ENABLE_MCP_CONNECT=1` **and** the target server is pre-declared in the
  `RIPTIDE_MCP_SERVERS` allowlist (`McpServerConfig`); the browser never supplies an arbitrary
  command. Read-only MCP tools run inline; mutating ones stay HITL-gated.
- A **dynamic-spec store** in `tools/examples.py` (`register_dynamic_spec` / `remove_dynamic_specs` /
  `clear_dynamic_specs` / `dynamic_specs`) that `default_registry()` appends, so runtime-registered
  tools persist into every subsequent run/eval/HTTP request (previously a fresh registry was built
  per call). `GET /api/meta` now reports an `mcp` summary (`enabled`, `connected`).
- `examples/mcp_connect.py` — offline end-to-end demo (via `FakeMcpClient`) of the connect flow.

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
