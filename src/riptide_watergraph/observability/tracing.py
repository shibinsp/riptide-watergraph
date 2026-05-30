"""Tracing setup.

We standardize on OpenTelemetry for our own graph spans (orchestrator/worker/approval/
finalize) and route LiteLLM generations to Langfuse via its OTEL-native callback. This
keeps the framework backend-swappable: instrument once, change backends freely.

Tracing is best-effort: if no exporter or keys are configured, it degrades to a no-op
so the skeleton runs fully offline.
"""

from __future__ import annotations

from contextlib import contextmanager
from typing import Iterator

from ..config import Settings, get_settings

_INITIALIZED = False
_TRACER = None


def init_tracing(settings: Settings | None = None) -> None:
    """Initialize OTEL + Langfuse. Idempotent and never raises."""
    global _INITIALIZED, _TRACER
    if _INITIALIZED:
        return
    settings = settings or get_settings()
    _INITIALIZED = True

    if settings.riptide_watergraph_disable_tracing:
        return

    # Route LiteLLM generations to Langfuse if keys are present.
    if settings.langfuse_public_key and settings.langfuse_secret_key:
        try:
            import litellm

            callbacks = list(getattr(litellm, "callbacks", []) or [])
            if "langfuse_otel" not in callbacks:
                callbacks.append("langfuse_otel")
            litellm.callbacks = callbacks
        except Exception:
            pass  # best-effort; never block a run on tracing

    # Set up an OTEL tracer for our own graph spans.
    try:
        from opentelemetry import trace
        from opentelemetry.sdk.resources import Resource
        from opentelemetry.sdk.trace import TracerProvider

        provider = TracerProvider(
            resource=Resource.create({"service.name": "riptide-watergraph"})
        )
        trace.set_tracer_provider(provider)
        _TRACER = trace.get_tracer("riptide_watergraph")
    except Exception:
        _TRACER = None


def get_tracer():  # type: ignore[no-untyped-def]
    """Return the OTEL tracer (or None if tracing is disabled/unavailable)."""
    return _TRACER


@contextmanager
def span(name: str, **attributes: object) -> Iterator[None]:
    """Context manager that opens an OTEL span if tracing is active, else no-op."""
    tracer = get_tracer()
    if tracer is None:
        yield
        return
    with tracer.start_as_current_span(name) as s:
        for k, v in attributes.items():
            try:
                s.set_attribute(k, v)  # type: ignore[arg-type]
            except Exception:
                pass
        yield
