# Contributing to riptide-watergraph

Thanks for your interest! This is a layered, "like water" multi-agent framework — every
layer sits behind an interface in `src/riptide_watergraph/interfaces/`, so most
contributions are a new implementation of an existing seam (a gateway, memory backend,
composer, guardrail, reranker, embedding provider, tool, or MCP client).

## Dev setup

```bash
python -m pip install -e ".[dev]"   # core + test/lint/type tooling
```

Optional extras: `.[litellm]` (real models), `.[server]` (HTTP API), `.[mcp]` (MCP stdio),
`.[observability]` (Langfuse/OTEL), `.[pgvector]` (Postgres memory), or `.[all]`.

## Checks (must pass before a PR)

```bash
ruff check src tests examples     # lint
mypy src                          # type check
pytest -q                         # tests
riptide eval --offline            # behavioral regression gate
```

Everything runs **offline** with the deterministic `DemoGateway` — no API key needed.

Optionally install the git hooks to run ruff + mypy before each commit:

```bash
pip install pre-commit && pre-commit install
```

## Adding a feature

1. Add or implement an interface in `interfaces/` (keep new heavy deps in an optional
   extra and import them lazily — the core stays dependency-light).
2. Wire it additively: `build_graph(...)` takes optional layers, so existing behavior is
   unchanged when your layer isn't passed.
3. Add a test (mirror the existing `tests/` patterns; use `MockGateway` from
   `tests/conftest.py` for graph tests).
4. Update the README / CHANGELOG.

## Commit conventions (enforced by review)

See [`CLAUDE.md`](CLAUDE.md). In short:

- **Granular commits** — one logical change per commit (ideally one file).
- **Conventional Commits** — `type(scope): summary` (`feat`, `fix`, `docs`, `test`,
  `build`, `chore`, `refactor`).
- **No AI watermark** — no `Co-Authored-By` / "Generated with…" footers.
- Branch off `main`; open a PR; CI (3.11–3.13) must be green.
