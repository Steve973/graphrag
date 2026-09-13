"""Application service for running the GraphRAG workflow."""

from dataclasses import dataclass
from typing import Any, Mapping

from langchain_core.runnables import RunnableConfig
from langgraph.checkpoint.base import BaseCheckpointSaver
from langgraph.types import Command, Interrupt

from graph_rag.config.graph_rag_config import GraphRagSettings
from graph_rag.graph_store.provider import GraphProvider
from graph_rag.langgraph.graph import build_graph_rag_graph
from graph_rag.langgraph.node_runner import GraphRagNodeRunner
from graph_rag.model.base import WorkflowStatus
from graph_rag.model.question import Question, UserClarificationResponse
from graph_rag.model.rag_state import GraphRagState, create_initial_state
from graph_rag.persistence.repository import NoOpWorkflowRepository, WorkflowRepository
from graph_rag.service.checkpointer import create_checkpointer


@dataclass(frozen=True)
class GraphRagExecutionResult:
    """Return validated state alongside any pending user-facing interrupts."""

    state: GraphRagState
    interrupts: tuple[Interrupt, ...] = ()

    @property
    def interrupted(self) -> bool:
        """Return whether this execution paused for external input."""

        return bool(self.interrupts)


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

    async def answer(self, question: Question) -> GraphRagExecutionResult:
        """Run a new workflow until it terminates or pauses for user input."""

        result = await self._graph.ainvoke(
            create_initial_state(question),
            config=self._config(question.id, question.limits.max_iterations),
        )
        return await self._finalize_result(result)

    async def resume(
        self,
        workflow_id: str,
        response: UserClarificationResponse,
    ) -> GraphRagExecutionResult:
        """Resume one interrupted workflow using its existing checkpoint thread."""

        checkpoint_config = RunnableConfig(configurable={"thread_id": workflow_id})
        snapshot = await self._graph.aget_state(checkpoint_config)
        if not snapshot.values:
            raise ValueError(f"no checkpoint exists for workflow {workflow_id!r}")
        checkpoint_state = GraphRagState.model_validate(snapshot.values)
        result = await self._graph.ainvoke(
            Command(resume=response.model_dump(mode="json")),
            config=self._config(
                workflow_id,
                checkpoint_state.question.limits.max_iterations,
            ),
        )
        return await self._finalize_result(result)

    @staticmethod
    def _config(workflow_id: str, max_iterations: int) -> RunnableConfig:
        """Create the typed checkpoint and superstep configuration for one run."""

        return RunnableConfig(
            configurable={"thread_id": workflow_id},
            recursion_limit=20 + (12 * max_iterations),
        )

    async def _finalize_result(
        self,
        result: Mapping[str, Any],
    ) -> GraphRagExecutionResult:
        """Separate LangGraph control metadata from strict workflow state."""

        state_values = dict(result)
        raw_interrupts = state_values.pop("__interrupt__", ())
        interrupts = tuple(raw_interrupts)
        state = GraphRagState.model_validate(state_values)
        if state.status in {
            WorkflowStatus.COMPLETE,
            WorkflowStatus.PARTIAL,
            WorkflowStatus.FAILED,
        }:
            await self._repository.save(state)
        return GraphRagExecutionResult(state=state, interrupts=interrupts)
