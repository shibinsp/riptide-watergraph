"""Runtime configuration via pydantic-settings (reads from env / .env)."""

from __future__ import annotations

from pydantic_settings import BaseSettings, SettingsConfigDict


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
