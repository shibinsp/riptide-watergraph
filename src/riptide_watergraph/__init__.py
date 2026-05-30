"""Riptide-Watergraph — a 'like water', layered multi-agent framework on LangGraph.

Public surface (Stage 1):

    from riptide_watergraph import build_graph, LiteLLMGateway, InMemoryMemory
    from riptide_watergraph import default_registry, SingleAgentComposer
"""

from __future__ import annotations

__version__ = "0.1.0"

from .gateway import DemoGateway, LiteLLMGateway
from .graph import build_graph
from .interfaces import (
    Agent,
    CompletionResult,
    Memory,
    Message,
    ModelGateway,
    Reflector,
    SwarmComposer,
    SwarmDecision,
    ToolRegistry,
    ToolSpec,
    Trajectory,
)
from .memory import InMemoryMemory, JsonFileMemory, LLMReflector, MemoryType
from .swarm import SingleAgentComposer
from .tools import StaticToolRegistry, default_registry

__all__ = [
    "__version__",
    "build_graph",
    "LiteLLMGateway",
    "DemoGateway",
    "InMemoryMemory",
    "JsonFileMemory",
    "LLMReflector",
    "MemoryType",
    "StaticToolRegistry",
    "default_registry",
    "SingleAgentComposer",
    # interfaces
    "Agent",
    "ModelGateway",
    "Message",
    "CompletionResult",
    "Memory",
    "Reflector",
    "Trajectory",
    "ToolRegistry",
    "ToolSpec",
    "SwarmComposer",
    "SwarmDecision",
]
