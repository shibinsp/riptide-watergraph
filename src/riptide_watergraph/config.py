"""Runtime configuration via pydantic-settings (reads from env / .env)."""

from __future__ import annotations

from pydantic import BaseModel, Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class McpServerConfig(BaseModel):
    """One entry in the MCP-server allowlist.

    The Studio can only connect to servers declared here (and only when
    ``RIPTIDE_ENABLE_MCP_CONNECT=1``) — the browser never supplies an arbitrary command.
    ``prefix`` namespaces the registered tool names (e.g. ``"fs."``) to avoid collisions.
    """

    name: str
    command: str
    args: list[str] = Field(default_factory=list)
    env: dict[str, str] = Field(default_factory=dict)
    prefix: str = ""
    description: str = ""


class Settings(BaseSettings):
    """Framework settings. All fields overridable by environment variables."""

    model_config = SettingsConfigDict(
        env_file=".env",
        env_prefix="",
        extra="ignore",
        case_sensitive=False,
    )

    # Default model string passed to LiteLLM (orchestrator/worker/finalizer).
    riptide_watergraph_model: str = "gpt-4o-mini"
    # Optional per-role model routing (Phase C). Empty => use the default model.
    planner_model: str = ""  # orchestrator + finalize (the "thinking" steps)
    worker_model: str = ""  # workers (often a cheaper model)

    # Checkpoint database path for the LangGraph SqliteSaver.
    checkpoint_path: str = ".riptide_watergraph/checkpoints.sqlite"

    # Persistent long-term memory store (Stage 2: lessons accumulate here across runs).
    memory_path: str = ".riptide_watergraph/memory.json"

    # Stage 4: multi-tenancy + cost attribution.
    tenant_id: str = "default"
    data_dir: str = ".riptide_watergraph"  # base dir for per-tenant memory + usage log

    # Sandbox root the agentic developer tools (read_file/write_file/run_*) are confined to.
    # All file paths are resolved under this dir; ``..``/absolute escapes are refused.
    workspace_dir: str = ".riptide_watergraph/workspace"
    # Phase D: per-tenant spend ceiling in USD (0 = unlimited). Runs are refused once a
    # tenant's accumulated cost reaches this.
    tenant_budget_usd: float = 0.0

    # MCP-server allowlist (Track v0.10.0). The Studio can connect only to servers listed
    # here, and only when ``RIPTIDE_ENABLE_MCP_CONNECT=1``. Supply as a JSON array via the
    # ``RIPTIDE_MCP_SERVERS`` env var, e.g.
    #   RIPTIDE_MCP_SERVERS='[{"name":"fs","command":"npx",
    #     "args":["-y","@modelcontextprotocol/server-filesystem","."],"prefix":"fs."}]'
    riptide_mcp_servers: list[McpServerConfig] = Field(default_factory=list)

    def tenant_memory_path(self, tenant_id: str) -> str:
        """Per-tenant memory namespace so lessons never leak across tenants."""
        return f"{self.data_dir}/tenants/{tenant_id}/memory.json"

    @property
    def usage_log_path(self) -> str:
        return f"{self.data_dir}/usage.jsonl"

    # Observability
    langfuse_public_key: str | None = None
    langfuse_secret_key: str | None = None
    langfuse_host: str = "https://cloud.langfuse.com"
    riptide_watergraph_disable_tracing: bool = False


def get_settings() -> Settings:
    """Load settings from environment / .env."""
    return Settings()
