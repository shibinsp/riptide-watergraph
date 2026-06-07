"""Riptide-Watergraph — a 'like water', layered multi-agent framework on LangGraph.

Public surface (Stage 1):

    from riptide_watergraph import build_graph, LiteLLMGateway, InMemoryMemory
    from riptide_watergraph import default_registry, SingleAgentComposer
"""

from __future__ import annotations

__version__ = "0.18.0"

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
    Triple,
    TripleExtractor,
)
from .mcp import FakeMcpClient, McpToolInfo, register_mcp_tools
from .memory import (
    InMemoryMemory,
    JsonFileMemory,
    KnowledgeGraph,
    LLMReflector,
    MemoryType,
    RuleTripleExtractor,
    consolidate_memory,
)
from .observability import CostTracker, UsageRecord
from .optimize import (
    Example,
    OptimizationResult,
    Scorer,
    SubstringScorer,
    TemplateProposer,
    optimize_prompt,
)
from .reasoning import (
    Candidate,
    DeliberationResult,
    HeuristicVerifier,
    LLMVerifier,
    Verdict,
    Verifier,
    deliberate,
)
from .skills import (
    JsonFileSkillStore,
    LLMSkillSynthesizer,
    Skill,
    SkillStore,
    SkillSynthesizer,
    skill_to_spec,
)
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
    # cognitive memory (knowledge graph + consolidation)
    "KnowledgeGraph",
    "RuleTripleExtractor",
    "consolidate_memory",
    "Triple",
    "TripleExtractor",
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
    # SkillForge (self-authored capabilities)
    "Skill",
    "SkillSynthesizer",
    "SkillStore",
    "LLMSkillSynthesizer",
    "JsonFileSkillStore",
    "skill_to_spec",
    # deliberate reasoning (verified best-of-N + confidence)
    "deliberate",
    "DeliberationResult",
    "Candidate",
    "Verdict",
    "Verifier",
    "HeuristicVerifier",
    "LLMVerifier",
    # self-improvement (measured prompt optimization)
    "optimize_prompt",
    "OptimizationResult",
    "Example",
    "Scorer",
    "SubstringScorer",
    "TemplateProposer",
]
