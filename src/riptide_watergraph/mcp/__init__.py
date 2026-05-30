"""MCP (Model Context Protocol) tool interop.

Adapt tools from external MCP servers into the local registry so the worker/swarm call
them like any other tool. The dependency-free pieces are exported here; the real stdio
transport (``StdioMcpClient``) lives in ``.stdio`` and needs the optional ``[mcp]``
extra, so it is imported on demand rather than at package import.
"""

from .adapter import mcp_tool_to_spec, register_mcp_tools
from .client import FakeMcpClient, McpClient, McpToolInfo

__all__ = [
    "McpClient",
    "McpToolInfo",
    "FakeMcpClient",
    "register_mcp_tools",
    "mcp_tool_to_spec",
]
