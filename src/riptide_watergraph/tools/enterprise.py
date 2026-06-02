"""Enterprise connector catalog — a broad, data-driven set of integration tool specs.

These represent the **enterprise tool surface** (CRM, ITSM, DevOps, cloud, data warehouse,
comms, docs, HR, finance, …). Offline they are **deterministic stubs** (they echo the call,
they do not touch any network); a connector becomes real when the matching MCP server is
registered for it (``register_mcp_tools(registry, client, prefix="vendor.")`` —
see ``mcp/adapter.py``). The whole catalog is **opt-in**: it registers only when
``RIPTIDE_ENABLE_ENTERPRISE=1`` so the default Studio stays lean and safe.

Read actions (list/get/search/export/count) are ``side_effecting=False`` and run inline;
write actions (create/update/delete/…) are ``side_effecting=True`` and route through the
human-approval gate (and stay inert as stubs until MCP-bound).
"""

from __future__ import annotations

import json
import os
from typing import Any

from ..interfaces.tools import ToolSpec

_S = {"type": "string"}

# (action, side_effecting, properties, required)
_ACTIONS: list[tuple[str, bool, dict[str, Any], list[str]]] = [
    ("list", False, {"filter": _S}, []),
    ("get", False, {"id": _S}, ["id"]),
    ("search", False, {"query": _S}, ["query"]),
    ("export", False, {"format": _S}, []),
    ("count", False, {"filter": _S}, []),
    ("create", True, {"payload": _S}, ["payload"]),
    ("update", True, {"id": _S, "payload": _S}, ["id", "payload"]),
    ("delete", True, {"id": _S}, ["id"]),
    ("comment", True, {"id": _S, "text": _S}, ["id", "text"]),
    ("assign", True, {"id": _S, "assignee": _S}, ["id", "assignee"]),
    ("set_status", True, {"id": _S, "status": _S}, ["id", "status"]),
    ("tag", True, {"id": _S, "tag": _S}, ["id", "tag"]),
    ("share", True, {"id": _S, "target": _S}, ["id", "target"]),
    ("archive", True, {"id": _S}, ["id"]),
]

# (vendor, domain) — domain doubles as the tool category.
_VENDORS: list[tuple[str, str]] = [
    ("salesforce", "crm"), ("hubspot", "crm"), ("zoho_crm", "crm"),
    ("servicenow", "itsm"), ("freshservice", "itsm"),
    ("zendesk", "support"), ("intercom", "support"),
    ("jira", "project"), ("linear", "project"), ("asana", "project"),
    ("trello", "project"), ("monday", "project"),
    ("github", "scm"), ("gitlab", "scm"), ("bitbucket", "scm"),
    ("jenkins", "devops"), ("circleci", "devops"), ("argocd", "devops"),
    ("aws", "cloud"), ("gcp", "cloud"), ("azure", "cloud"),
    ("s3", "storage"), ("gcs", "storage"), ("dropbox", "storage"), ("box", "storage"),
    ("snowflake", "data"), ("bigquery", "data"), ("databricks", "data"),
    ("slack", "comms"), ("teams", "comms"), ("gmail", "comms"), ("outlook", "comms"),
    ("notion", "docs"), ("confluence", "docs"), ("gdrive", "docs"),
    ("workday", "hr"), ("stripe", "finance"),
]


def _stub(name: str):
    def handler(**kwargs: Any) -> str:
        try:
            args = json.dumps(kwargs, sort_keys=True, default=str)
        except (TypeError, ValueError):
            args = str(kwargs)
        return (f"(stub) {name}({args}) - connect an MCP server for this vendor "
                "(register_mcp_tools) to execute for real.")
    return handler


def _spec(vendor: str, domain: str, action: str, side_effecting: bool,
          props: dict[str, Any], required: list[str]) -> ToolSpec:
    name = f"{vendor}.{action}"
    verb = action.replace("_", " ")
    return ToolSpec(
        name=name,
        description=f"{verb.capitalize()} {vendor} {domain} records (enterprise connector).",
        json_schema={"type": "object", "properties": props, "required": required,
                     "additionalProperties": False},
        side_effecting=side_effecting,
        category=domain,
        tags=[vendor, domain, "enterprise"],
        handler=_stub(name),
    )


def enterprise_specs() -> list[ToolSpec]:
    """The enterprise connector catalog — only when ``RIPTIDE_ENABLE_ENTERPRISE=1``."""
    if os.getenv("RIPTIDE_ENABLE_ENTERPRISE") != "1":
        return []
    specs: list[ToolSpec] = []
    for vendor, domain in _VENDORS:
        for action, side_effecting, props, required in _ACTIONS:
            specs.append(_spec(vendor, domain, action, side_effecting, props, required))
    return specs
