"""Abstract storage boundaries for completed workflows and checkpoints."""

from __future__ import annotations

from abc import ABC, abstractmethod

from graph_rag.model.rag_state import GraphRagState


class WorkflowRepository(ABC):
    """Store and retrieve terminal workflow audit packages."""

    @abstractmethod
    async def save(self, record: object) -> None:
        """Store one completed workflow package by its workflow ID."""

    @abstractmethod
    async def get(self, workflow_id: str) -> object | None:
        """Retrieve one completed workflow package when it exists."""


class WorkflowCheckpointRepository(ABC):
    """Store restartable in-process state separately from completed records."""

    @abstractmethod
    async def save(self, state: GraphRagState) -> None:
        """Store the latest restartable state for one active workflow."""

    @abstractmethod
    async def get(self, workflow_id: str) -> GraphRagState | None:
        """Retrieve the latest active checkpoint when it exists."""

    @abstractmethod
    async def delete(self, workflow_id: str) -> None:
        """Remove the active checkpoint for a terminal workflow."""


class NoOpWorkflowRepository(WorkflowRepository):
    """Discard completed workflow packages while satisfying the boundary."""

    async def save(self, record: object) -> None:
        """Discard one completed workflow package."""

    async def get(self, workflow_id: str) -> object | None:
        """Return no completed workflow package."""

        return None


class NoOpCheckpointRepository(WorkflowCheckpointRepository):
    """Disable active-workflow checkpoint persistence."""

    async def save(self, state: GraphRagState) -> None:
        """Discard one active workflow checkpoint."""

    async def get(self, workflow_id: str) -> GraphRagState | None:
        """Return no active workflow checkpoint."""

        return None

    async def delete(self, workflow_id: str) -> None:
        """Ignore deletion of an active workflow checkpoint."""
