"""Typed contracts for the controlled GraphRAG workflow."""

from __future__ import annotations

import operator
from datetime import datetime
from typing import (
    Annotated,
)

from pydantic import Field, BeforeValidator, model_validator

from graph_rag.model.base import WorkflowStatus, ContractModel, NonEmptyStr
from graph_rag.model.iteration import IterationRecord, IterationRecordBuilder
from graph_rag.model.plan import Plan
from graph_rag.model.question import (
    Question,
    FinalAnswer
)
from graph_rag.model.supporting_data import EvidenceSummary, EvidenceData
from graph_rag.model.tool_operations import AvailableTool
from graph_rag.model.workflow import WorkflowEvaluation
from graph_rag.utils import scalar_to_list


# =============================================================================
# INITIALIZED GRAPH CONTEXT
#
# GraphContext contains stable profile, schema, sample-data, and tool-catalog
# information established during initialization.
# =============================================================================


class GraphContext(ContractModel):
    """Contain stable dataset and tool knowledge established at initialization.

    Attributes:
        profile_id: Stable graph-data profile identifier, such as ``gtd/v1``.
        domain_description: Optional guidance for interpreting the selected
            graph dataset.
        schema_ddl: DDL schema of the graph database used to initialize this
            workflow.
        sample_data: Sample data summaries from initialization.
        available_tools: Unified catalog of tools and tool-specific
            capabilities exposed to the workflow.
    """

    profile_id: NonEmptyStr = Field(
        description=(
            "Exact stable ID of the graph-data profile used to initialize this "
            "workflow. Copy it from configuration and carry it unchanged."
        ),
    )
    domain_description: NonEmptyStr | None = Field(
        default=None,
        description=(
            "Optional domain-specific guidance for interpreting graph data and forming "
            "queries. Use it as context, but do not treat it as retrieved evidence."
        ),
    )
    schema_ddl: str = Field(
        description=(
            "DDL schema of the graph database used to initialize this workflow."
        ),
    )
    sample_data: Annotated[
        list[EvidenceSummary],
        BeforeValidator(scalar_to_list),
    ] = Field(
        default_factory=list,
        description=(
            "Sample data summaries from the graph database."
        ),
    )
    available_tools: Annotated[
        list[AvailableTool],
        BeforeValidator(scalar_to_list),
    ] = Field(
        default_factory=list,
        description=(
            "Complete unified catalog of callable tools available to this workflow. "
            "Select tools only from this list and use their exact references "
            "and schemas. Tool-specific capability catalogs, such as supported "
            "GDS procedures, belong on the relevant AvailableTool entry."
        ),
    )

    @model_validator(mode="after")
    def validate_tool_catalog(self) -> GraphContext:
        """Ensure that every available tool has a unique reference."""

        references = [
            (tool.reference.namespace, tool.reference.name)
            for tool in self.available_tools
        ]
        if len(references) != len(set(references)):
            raise ValueError("available tool references must be unique")
        return self


# =============================================================================
# FINAL RESPONSE AND LANGGRAPH STATE
#
# FinalAnswer is intentionally small: callers receive the workflow ID, terminal
# status, user-facing answer, and confidence. Detailed evidence and raw results
# are retrieved separately by workflow ID. GraphRagState contains one append-only
# iteration history; iteration counts and evaluation history are derived from
# those records.
# =============================================================================


class GraphRagState(ContractModel):
    """Define the LangGraph state exchanged through workflow nodes.

    TODO: Decide on validation.

    Attributes:
        workflow_id: Identifier shared by the question and persisted workflow.
        question: Original request and execution limits.
        graph_context: Stable initialized graph context, including schema,
            sample data, and available tools.
        plan: Current progress-bearing plan revision.
        current_iteration: Current progress-bearing iteration revision.
        iteration_purpose: Purpose of the current iteration, or ``None`` before
            an iteration is active.
        iteration_start_time: Time at which the current iteration started, or
            ``None`` before an iteration is active.
        iterations: Append-only completed iteration history.
        latest_evaluation: Most recent assessment of the current plan revision.
        evidence_summaries: Accumulated prompt-friendly evidence summaries.
        status: Current workflow lifecycle status.
        final_answer: Public terminal response after finalization.
    """

    workflow_id: str
    question: Question
    graph_context: GraphContext | None = Field(
        default=None,
        description=(
            "Stable initialized profile, schema, sample data, and available-tool "
            "catalog."
        ),
    )
    plan: Plan | None = Field(
        default=None,
        description=(
            "Current revision of the evolving progress-bearing plan. Findings and "
            "unresolved items in this snapshot must reference evidence carried by this "
            "context."
        ),
    )
    current_iteration: IterationRecordBuilder | None = Field(
        default=None,
        description=(
            "Current iteration record builder, or null before an iteration is "
            "active. Findings and unresolved items in this snapshot must reference "
            "evidence carried by this context."
        ),
    )
    iteration_purpose: NonEmptyStr | None = Field(
        default=None,
        description=(
            "Purpose of the current iteration, or null before an iteration is "
            "active. Start-iteration node validation should require it once an "
            "iteration has begun."
        ),
    )
    iteration_start_time: datetime | None = Field(
        default=None,
        description=(
            "Time at which the current iteration started, or null before an "
            "iteration is active."
        ),
    )
    iterations: Annotated[list[IterationRecord], operator.add] = Field(
        default_factory=list,
        description=(
            "List of iteration records, in order of iteration."
        ),
    )
    latest_evaluation: WorkflowEvaluation | None = Field(
        default=None,
        description=(
            "Most recent evaluation of the current plan revision, or null before any "
            "evaluation."
        ),
    )
    evidence_data: Annotated[
        list[EvidenceData],
        BeforeValidator(scalar_to_list),
    ] = Field(
        default_factory=list,
        description=(
            "Raw data from tool calls that generated evidence."
        ),
    )
    evidence_summaries: Annotated[
        list[EvidenceSummary],
        BeforeValidator(scalar_to_list),
    ] = Field(
        default_factory=list,
        description=(
            "Accumulated compact evidence summaries available for future prompts "
            "and reasoning. Do not include raw tool-result data here."
        ),
    )
    status: WorkflowStatus
    final_answer: FinalAnswer | None

    @property
    def iteration_number(self) -> int:
        return len(self.iterations) + 1


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
        graph_context=None,
        iterations=[],
        status=WorkflowStatus.INITIALIZING,
        final_answer=None,
    )
