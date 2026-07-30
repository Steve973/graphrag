from abc import ABC, abstractmethod

from graph_rag.model.context import GraphContext
from graph_rag.model.tool_operations import ToolCallRequest, ToolCallResult


class GraphProvider(ABC):
    """Base class for graph-backed data access providers."""

    @abstractmethod
    async def build_graph_context(
        self,
        profile_id: str,
    ) -> GraphContext:
        """Build graph context for a workflow."""

    @abstractmethod
    async def execute_graph_operation(
        self,
        request: ToolCallRequest,
    ) -> ToolCallResult:
        """Execute a graph-specific operation and return a normalized result."""