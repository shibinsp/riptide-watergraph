# Tools & roles

## Tools

The registry ships **230+ read-only, stdlib-only tools** (`tools/library.py`) across text, regex,
JSON/CSV, encoding, hashing, math/stats, datetime, units, collections, random, extract, code, color, and
validation — **238 tools out of the box**. Each is a `ToolSpec` with a JSON schema, a category, and tags.

On-demand **BM25 retrieval** (`tool_k=4`) means a worker only ever sees the handful of tools relevant to
its subtask — so the registry can grow without bloating any prompt.

```python
from riptide_watergraph import default_registry

reg = default_registry()
print(len(reg.all_specs()))                 # 238
print([s.name for s in reg.retrieve("hash a string")][:3])
result = await reg.invoke("sha256", {"text": "water"})
```

### Custom tools

A tool is just a `ToolSpec` with a handler (sync or async). Read-only tools run inline; side-effecting
tools route through the human-approval gate.

```python
from riptide_watergraph.interfaces.tools import ToolSpec

ToolSpec(
    name="shout", description="Upper-case with emphasis.",
    json_schema={"type": "object", "properties": {"text": {"type": "string"}},
                 "required": ["text"], "additionalProperties": False},
    side_effecting=False, handler=lambda text: text.upper() + "!",
)
```

### Enterprise connectors (opt-in)

`RIPTIDE_ENABLE_ENTERPRISE=1` registers **~518 connector tools** for ~37 vendors (Salesforce, Jira,
GitHub, ServiceNow, Slack, Snowflake, Stripe, …) — **~750 tools** in the gallery. Offline they are
**deterministic stubs**; bind a real [MCP](mcp.md) server for a vendor to make them execute. Write
actions are `side_effecting` (human-approval gated) and stay inert until bound.

## Roles

A **219-role catalog** (`swarm/role_library.py`) of domain specialists across engineering, data,
devops/SRE, security, QA, product, writing, research, finance, ops, design, and enterprise
functions/verticals. Each role carries a focused system prompt and a category-scoped **tool allow-list**,
so retrieval stays small no matter how large the registry is.

```python
from riptide_watergraph.swarm.roles import role_for, get_role

role_for("fix the bug in app.py")     # -> "coder"
get_role("analyst").tools             # the analyst's allowed tools
```

The composer assigns a role per subtask (`SwarmDecision.roles`), or `role_for` routes by keyword for the
common ones. The rest are selectable in the Studio and via the composer.
