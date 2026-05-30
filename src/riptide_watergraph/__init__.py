"""Riptide-Watergraph — a 'like water', layered multi-agent framework on LangGraph.

Public surface (Stage 1):

    from riptide_watergraph import build_graph, LiteLLMGateway, InMemoryMemory
    from riptide_watergraph import default_registry, SingleAgentComposer
"""

from __future__ import annotations

__version__ = "0.1.0"

from .gateway import LiteLLMGateway
from .graph import build_graph
from .interfaces import (
    Agent,
    CompletionResult,
    Memory,
    Message,
    ModelGateway,
    SwarmComposer,
    SwarmDecision,
    ToolRegistry,
    ToolSpec,
)
from .memory import InMemoryMemory
from .swarm import SingleAgentComposer
from .tools import StaticToolRegistry, default_registry

__all__ = [
    "__version__",
    "build_graph",
    "LiteLLMGateway",
    "InMemoryMemory",
    "StaticToolRegistry",
    "default_registry",
    "SingleAgentComposer",
    # interfaces
    "Agent",
    "ModelGateway",
    "Message",
    "CompletionResult",
    "Memory",
    "ToolRegistry",
    "ToolSpec",
    "SwarmComposer",
    "SwarmDecision",
]
