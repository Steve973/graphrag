"""Typed contracts for the controlled GraphRAG workflow."""

from __future__ import annotations

import operator
from typing import (
    Annotated,
    TypedDict
)

from graph_rag.model.base import WorkflowStatus
from graph_rag.model.context import WorkingContext
from graph_rag.model.iteration import IterationRecord
from graph_rag.model.question import (
    Question,
    FinalAnswer
)


# =============================================================================
# FINAL RESPONSE AND LANGGRAPH STATE
#
# FinalAnswer is intentionally small: callers receive the workflow ID, terminal
# status, user-facing answer, and confidence. Detailed evidence and raw results
# are retrieved separately by workflow ID. GraphRagState contains one append-only
# iteration history; iteration counts and evaluation history are derived from
# those records.
# =============================================================================


class GraphRagState(TypedDict):
    """Define the LangGraph state exchanged through workflow nodes.

    Attributes:
        workflow_id: Identifier shared by the question and persisted workflow.
        question: Original request and execution limits.
        iterations: Append-only completed iteration history.
        working_context: Latest prompt-oriented context, or ``None`` before
            initialization completes.
        status: Current workflow lifecycle status.
        final_answer: Public terminal response after finalization.
    """

    workflow_id: str
    question: Question
    iterations: Annotated[list[IterationRecord], operator.add]
    working_context: WorkingContext | None
    status: WorkflowStatus
    final_answer: FinalAnswer | None


def create_initial_state(question: Question) -> GraphRagState:
    """Create the complete state supplied to the workflow entry point.

    Args:
        question: Validated question that starts the workflow execution.

    Returns:
        A fully populated initial LangGraph state.
    """

    return GraphRagState(
        workflow_id=question.id,
        question=question,
        iterations=[],
        working_context=None,
        status=WorkflowStatus.INITIALIZING,
        final_answer=None,
    )
