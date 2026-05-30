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

    # Checkpoint database path for the LangGraph SqliteSaver.
    checkpoint_path: str = ".riptide_watergraph/checkpoints.sqlite"

    # Persistent long-term memory store (Stage 2: lessons accumulate here across runs).
    memory_path: str = ".riptide_watergraph/memory.json"

    # Observability
    langfuse_public_key: str | None = None
    langfuse_secret_key: str | None = None
    langfuse_host: str = "https://cloud.langfuse.com"
    riptide_watergraph_disable_tracing: bool = False


def get_settings() -> Settings:
    """Load settings from environment / .env."""
    return Settings()
