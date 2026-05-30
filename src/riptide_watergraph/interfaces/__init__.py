"""The swappable seams of Riptide-Watergraph.

Every layer is defined here as an abstract base class so concrete implementations
can be swapped without touching callers. Stage-1 implementations live in sibling
packages (``gateway``, ``memory``, ``tools``, ``swarm``).
"""

from .agent import Agent
from .gateway import CompletionResult, Message, ModelGateway
from .memory import Memory, MemoryRecord, RetrievedItem
from .reflector import Reflector, Trajectory
from .swarm import SwarmComposer, SwarmDecision, TeamMember
from .tools import ToolRegistry, ToolSpec

__all__ = [
    "Agent",
    "ModelGateway",
    "Message",
    "CompletionResult",
    "Memory",
    "MemoryRecord",
    "RetrievedItem",
    "Reflector",
    "Trajectory",
    "ToolRegistry",
    "ToolSpec",
    "SwarmComposer",
    "SwarmDecision",
    "TeamMember",
]
