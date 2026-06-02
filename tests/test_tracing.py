"""observability.tracing coverage via faked optional backends.

Fake `litellm` + `opentelemetry.*` modules let `init_tracing` run its Langfuse-callback and
OTEL-provider setup offline; `span()` is exercised with an active tracer (success + the
set_attribute error swallow) and with no tracer (no-op).
"""

from __future__ import annotations

import sys
import types

from riptide_watergraph.config import Settings
from riptide_watergraph.observability import tracing


def _install_fake_otel(monkeypatch):
    ot = types.ModuleType("opentelemetry")
    trace_mod = types.ModuleType("opentelemetry.trace")

    class _Span:
        def __enter__(self):
            return self

        def __exit__(self, *exc):
            return False

        def set_attribute(self, k, v):
            return None

    class _Tracer:
        def start_as_current_span(self, name):
            return _Span()

    trace_mod.set_tracer_provider = lambda provider: None
    trace_mod.get_tracer = lambda name: _Tracer()
    ot.trace = trace_mod
    sdk = types.ModuleType("opentelemetry.sdk")
    res_mod = types.ModuleType("opentelemetry.sdk.resources")
    res_mod.Resource = types.SimpleNamespace(create=lambda d: d)
    trace_sdk = types.ModuleType("opentelemetry.sdk.trace")
    trace_sdk.TracerProvider = lambda resource=None: object()
    for name, mod in [
        ("opentelemetry", ot), ("opentelemetry.trace", trace_mod),
        ("opentelemetry.sdk", sdk), ("opentelemetry.sdk.resources", res_mod),
        ("opentelemetry.sdk.trace", trace_sdk),
    ]:
        monkeypatch.setitem(sys.modules, name, mod)


def test_init_tracing_full_setup(monkeypatch):
    monkeypatch.setattr(tracing, "_INITIALIZED", False)
    monkeypatch.setattr(tracing, "_TRACER", None)
    fake_litellm = types.ModuleType("litellm")
    fake_litellm.callbacks = []
    monkeypatch.setitem(sys.modules, "litellm", fake_litellm)
    _install_fake_otel(monkeypatch)

    tracing.init_tracing(Settings(
        langfuse_public_key="pk", langfuse_secret_key="sk",
        riptide_watergraph_disable_tracing=False,
    ))
    assert "langfuse_otel" in fake_litellm.callbacks  # Langfuse callback registered
    assert tracing.get_tracer() is not None           # OTEL tracer created


def test_init_tracing_import_failures(monkeypatch):
    monkeypatch.setattr(tracing, "_INITIALIZED", False)
    monkeypatch.setattr(tracing, "_TRACER", None)
    monkeypatch.setitem(sys.modules, "litellm", None)        # import litellm -> ImportError
    monkeypatch.setitem(sys.modules, "opentelemetry", None)  # from opentelemetry ... -> ImportError
    tracing.init_tracing(Settings(
        langfuse_public_key="pk", langfuse_secret_key="sk",
        riptide_watergraph_disable_tracing=False,
    ))
    assert tracing.get_tracer() is None  # both setups failed gracefully


def test_init_tracing_idempotent(monkeypatch):
    monkeypatch.setattr(tracing, "_INITIALIZED", True)
    tracing.init_tracing(Settings(riptide_watergraph_disable_tracing=False))  # returns immediately


def test_init_tracing_disabled(monkeypatch):
    monkeypatch.setattr(tracing, "_INITIALIZED", False)
    monkeypatch.setattr(tracing, "_TRACER", None)
    tracing.init_tracing(Settings(riptide_watergraph_disable_tracing=True))
    assert tracing.get_tracer() is None


def test_span_active_tracer_and_error_swallow(monkeypatch):
    class _Span:
        def __enter__(self):
            return self

        def __exit__(self, *exc):
            return False

        def set_attribute(self, k, v):
            raise ValueError("boom")  # exercise the swallow

    class _Tracer:
        def start_as_current_span(self, name):
            return _Span()

    monkeypatch.setattr(tracing, "_TRACER", _Tracer())
    with tracing.span("op", attr=1):
        pass  # must not raise even though set_attribute throws


def test_span_noop_without_tracer(monkeypatch):
    monkeypatch.setattr(tracing, "_TRACER", None)
    with tracing.span("op", attr=1):
        pass
