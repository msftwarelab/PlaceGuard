"""PlaceGuard Agent - Production ReAct agent for VOYGR place validation."""

__version__ = "0.1.0"
__author__ = "VOYGR Team"

# Lazy imports to avoid circular dependency issues during test collection.
# Import directly from submodules when needed:
#   from agent.schemas import PlaceQuery
#   from agent.graph import build_agent_graph

__all__ = [
    "build_agent_graph",
    "PlaceQuery",
    "ValidationResult",
    "PlaceDetails",
    "ValidationIssue",
    "LLMProvider",
]
