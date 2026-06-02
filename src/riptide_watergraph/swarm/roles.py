"""Agent roles — heterogeneous specialists instead of one generic worker.

Each role carries a specialized system prompt and an optional **tool allow-list** that
scopes on-demand tool retrieval (least privilege per agent). The composer/orchestrator
assigns a role per subtask. Every prompt keeps the "You are a worker" phrasing so the
rest of the graph (and scripted gateways) treats a specialist as a worker.
"""

from __future__ import annotations

from pydantic import BaseModel, Field


class AgentRole(BaseModel):
    name: str
    system_prompt: str
    tools: list[str] | None = None  # None => all tools allowed (generalist)
    category: str = "general"  # grouping for the Studio role gallery
    description: str = ""  # short human-readable summary of the role
    tags: list[str] = Field(default_factory=list)  # free-form labels for search/filter


_GENERALIST = AgentRole(
    name="generalist",
    system_prompt=(
        "You are a worker. Accomplish the subtask. Use a tool if helpful; otherwise "
        "answer directly and concisely."
    ),
    tools=None,
    category="general",
    description="A capable all-rounder with access to every tool.",
)

DEFAULT_ROLES: dict[str, AgentRole] = {
    "generalist": _GENERALIST,
    "researcher": AgentRole(
        name="researcher",
        system_prompt=(
            "You are a worker acting as a researcher. Find and report the relevant "
            "facts concisely; prefer the search tool."
        ),
        tools=["web_search"],
        category="research",
        description="Finds and reports relevant facts.",
    ),
    "analyst": AgentRole(
        name="analyst",
        system_prompt=(
            "You are a worker acting as an analyst. Compute and reason about quantities "
            "precisely; prefer the calculator tool."
        ),
        tools=["calculator"],
        category="data",
        description="Computes and reasons about quantities.",
    ),
    "scribe": AgentRole(
        name="scribe",
        system_prompt=(
            "You are a worker acting as a scribe. Summarize, format, and record text; "
            "use the text tools."
        ),
        tools=["word_count", "uppercase", "reverse_text", "write_note"],
        category="writing",
        description="Summarizes, formats, and records text.",
    ),
    "coder": AgentRole(
        name="coder",
        system_prompt=(
            "You are a worker acting as a software engineer. Inspect and modify code in "
            "the workspace to implement features or fix bugs: read files, search the code, "
            "apply precise edits, and (when enabled) run code or tests to verify. Make the "
            "smallest change that solves the subtask."
        ),
        tools=[
            "read_file", "list_dir", "find_files", "search_code",
            "write_file", "apply_edit",
            "run_python", "run_command", "run_tests",
        ],
        category="engineering",
        description="Inspects and edits code to implement features or fix bugs.",
    ),
}

# Substring stems per role, checked in order. Stems (not whole words) so "compute"
# matches "comput"; curated to avoid collisions (e.g. analyst omits "sum" so it doesn't
# swallow "summary", which belongs to the scribe).
# ``coder`` is checked first so coding intent wins over generic "write"/"find" stems; its
# stems are specific enough not to swallow research/analyst/scribe tasks.
_ROLE_STEMS: list[tuple[str, tuple[str, ...]]] = [
    ("coder", ("code", "coding", "bug", "debug", "refactor", "implement", "fix", "patch",
               "pytest", "unit test", "function", "module", "compile", "syntax",
               "exception", "stack trace", "traceback")),
    ("sql_developer", ("sql", "query the", "database query", "select ", "join ")),
    ("data_analyst", ("dataset", "dataframe", "data analy", "analyze the data", "csv", "statistic")),
    ("devops_engineer", ("devops", "deploy", "kubernetes", "docker", "ci/cd", "pipeline",
                         "provision", "infrastructure")),
    ("security_analyst", ("security", "vulnerab", "exploit", "pentest", "threat", "encrypt",
                          "hash the", "cve")),
    ("qa_engineer", ("test plan", "test case", "quality assur", "qa ", " qa")),
    ("technical_writer", ("document", "readme", "changelog", "release note", "user guide")),
    ("product_manager", ("roadmap", "requirement", "user story", "backlog", "prioriti")),
    ("researcher", ("search", "find", "research", "investigat", "look up", "lookup")),
    ("analyst", ("comput", "calculat", "arithmetic", "multipl", "divid", "math", "product")),
    ("scribe", ("writ", "note", "save", "summar", "format", "uppercase", "reverse",
                "report", "draft", "word", "count", "text")),
]


def role_for(subtask: str) -> str:
    """Pick a role for a subtask by keyword stem; falls back to ``generalist``."""
    low = subtask.lower()
    for name, stems in _ROLE_STEMS:
        if any(stem in low for stem in stems):
            return name
    return "generalist"


def get_role(name: str) -> AgentRole:
    """Resolve a role from the full catalog (curated core + domain specialists)."""
    from .role_library import ROLE_CATALOG  # lazy import to avoid a cycle
    return ROLE_CATALOG.get(name, _GENERALIST)


def all_roles() -> list[AgentRole]:
    """Every role in the catalog (curated core + domain specialists)."""
    from .role_library import ROLE_CATALOG  # lazy import to avoid a cycle
    return list(ROLE_CATALOG.values())
