"""Observability: OpenTelemetry graph spans + Langfuse for LLM generations."""

from .tracing import get_tracer, init_tracing

__all__ = ["init_tracing", "get_tracer"]
