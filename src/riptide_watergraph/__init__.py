"""Riptide-Watergraph — a 'like water', layered multi-agent framework on LangGraph.

Public surface (Stage 1):

    from riptide_watergraph import build_graph, LiteLLMGateway, InMemoryMemory
    from riptide_watergraph import default_registry, SingleAgentComposer
"""

from __future__ import annotations

__version__ = "0.1.0"

from .gateway import DemoGateway, LiteLLMGateway, ResilientGateway
from .graph import build_graph
from .guardrails import (
    GuardrailPipeline,
    PiiGuardrail,
    PromptInjectionGuardrail,
    default_guardrails,
)
from .interfaces import (
    Agent,
    CompletionResult,
    Guardrail,
    GuardrailResult,
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
from .mcp import FakeMcpClient, McpToolInfo, register_mcp_tools
from .memory import InMemoryMemory, JsonFileMemory, LLMReflector, MemoryType
from .observability import CostTracker, UsageRecord
from .swarm import HeuristicSwarmComposer, LLMSwarmComposer, SingleAgentComposer
from .tools import StaticToolRegistry, default_registry

__all__ = [
    "__version__",
    "build_graph",
    "LiteLLMGateway",
    "DemoGateway",
    "ResilientGateway",
    "InMemoryMemory",
    "JsonFileMemory",
    "LLMReflector",
    "MemoryType",
    "StaticToolRegistry",
    "default_registry",
    "SingleAgentComposer",
    "HeuristicSwarmComposer",
    "LLMSwarmComposer",
    # guardrails + observability (Stage 4)
    "GuardrailPipeline",
    "default_guardrails",
    "PiiGuardrail",
    "PromptInjectionGuardrail",
    "Guardrail",
    "GuardrailResult",
    "CostTracker",
    "UsageRecord",
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
    # MCP tool interop
    "register_mcp_tools",
    "FakeMcpClient",
    "McpToolInfo",
]
