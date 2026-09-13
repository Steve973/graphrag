"""Application service for running the GraphRAG workflow."""
from langchain_core.runnables import RunnableConfig
from langgraph.checkpoint.base import BaseCheckpointSaver

from graph_rag.config.graph_rag_config import GraphRagSettings
from graph_rag.graph_store.provider import GraphProvider
from graph_rag.langgraph.graph import build_graph_rag_graph
from graph_rag.langgraph.node_runner import GraphRagNodeRunner
from graph_rag.model.base import WorkflowStatus
from graph_rag.model.question import Question
from graph_rag.model.rag_state import GraphRagState, create_initial_state
from graph_rag.persistence.repository import NoOpWorkflowRepository, WorkflowRepository
from graph_rag.service.checkpointer import create_checkpointer


class GraphRagService:
    """Create and run checkpointed GraphRAG question workflows."""

    def __init__(
        self,
        settings: GraphRagSettings,
        provider: GraphProvider,
        *,
        node_runner: GraphRagNodeRunner | None = None,
        checkpointer: BaseCheckpointSaver | None = None,
        repository: WorkflowRepository | None = None,
    ) -> None:
        """Build one reusable compiled workflow from application dependencies."""

        self._repository = repository or NoOpWorkflowRepository()
        self._graph = build_graph_rag_graph(
            settings,
            provider,
            node_runner=node_runner,
            checkpointer=checkpointer or create_checkpointer(settings),
        )

    async def answer(self, question: Question) -> GraphRagState:
        """Run a new question workflow and return its complete resulting state."""

        result = await self._graph.ainvoke(
            create_initial_state(question),
            config=RunnableConfig(
                configurable={"thread_id": question.id}
            ),
        )
        state = GraphRagState.model_validate(result)
        if state.status in {
            WorkflowStatus.COMPLETE,
            WorkflowStatus.PARTIAL,
            WorkflowStatus.FAILED,
        }:
            await self._repository.save(state)
        return state
