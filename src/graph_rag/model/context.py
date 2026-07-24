from __future__ import annotations

from datetime import datetime
from typing import Annotated

from pydantic import (
    Field,
    BeforeValidator,
    model_validator
)

from graph_rag.model.base import (
    Answerability,
    PlanStepStatus,
    ReasoningImpact,
    NonEmptyStr,
    ContractModel
)
from graph_rag.model.iteration import (
    IterationRecordBuilder
)
from graph_rag.model.plan import Plan
from graph_rag.model.supporting_data import EvidenceRecord
from graph_rag.model.tool_operations import AvailableTool
from graph_rag.model.workflow import WorkflowEvaluation
from graph_rag.utils import scalar_to_list


def _validate_plan_evidence_references(
        plan: Plan,
        available_evidence_ids: set[str],
) -> None:
    """Validate evidence references contained by a plan.

    Args:
        plan: Plan whose findings and unresolved items are being validated.
        available_evidence_ids: Evidence identifiers available in the enclosing
            record or working context.

    Raises:
        ValueError: If a finding or unresolved item references missing evidence.
    """

    for step in plan.steps:
        for finding in step.supported_findings:
            missing = set(finding.evidence_record_ids) - available_evidence_ids
            if missing:
                raise ValueError(
                    f"finding {finding.id!r} references missing evidence: "
                    f"{sorted(missing)!r}"
                )

        for unresolved in step.unresolved_items:
            missing = set(unresolved.evidence_record_ids) - available_evidence_ids
            if missing:
                raise ValueError(
                    f"unresolved item {unresolved.id!r} references missing "
                    f"evidence: {sorted(missing)!r}"
                )


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
        list[EvidenceRecord],
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
# CURRENT WORKING CONTEXT
#
# WorkingContext is the prompt-oriented snapshot carried into the next
# iteration. It contains stable graph context, the current plan revision, compact
# evidence summaries, and the latest evaluation. Raw tool results remain only in
# IterationRecord.
# =============================================================================


class WorkingContext(ContractModel):
    """Represent the latest coherent snapshot used by the next iteration.

    Attributes:
        iteration_number: Iteration number of the current iteration.
            Incremented by one for each iteration.
        question: The text of the question to be answered by the workflow.
        iteration_start_time: Time at which the current iteration started, or
            ``None`` before an iteration is active.
        iteration_purpose: Purpose of the current iteration, or ``None`` before
            an iteration is active.
        graph_context: Stable initialized graph context, including schema,
            sample data, and available tools.
        plan: Current progress-bearing plan revision.
        evidence_records: Accumulated prompt-friendly evidence summaries.
        latest_evaluation: Most recent assessment of the current plan revision.
    """

    iteration_number: int = Field(
        default=0,
        description=(
            "Iteration number of the current iteration. Incremented by one for "
            "each iteration."
        ),
    )
    question: NonEmptyStr = Field(
        description=(
            "Question to be answered by the workflow."
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
    graph_context: GraphContext = Field(
        description=(
            "Stable initialized profile, schema, sample data, and available-tool "
            "catalog."
        ),
    )
    plan: Plan = Field(
        description=(
            "Current revision of the evolving progress-bearing plan. Findings and "
            "unresolved items in this snapshot must reference evidence carried by this "
            "context."
        ),
    )
    iteration_record_builder: IterationRecordBuilder | None = Field(
        default=None,
        description=(
            "Record builder for the actions and their results during the current "
            "iteration, or null before an iteration is active."
        ),
    )
    evidence_records: Annotated[
        list[EvidenceRecord],
        BeforeValidator(scalar_to_list),
    ] = Field(
        default_factory=list,
        description=(
            "Accumulated compact EvidenceRecord summaries available for future prompts "
            "and reasoning. Do not include raw tool-result data here."
        ),
    )
    latest_evaluation: WorkflowEvaluation | None = Field(
        default=None,
        description=(
            "Most recent evaluation of the current plan revision, or null before any "
            "evaluation."
        ),
    )

    @model_validator(mode="after")
    def validate_context_references(self) -> WorkingContext:
        """Validate plan and evaluation references against current evidence."""

        evidence_ids = [record.id for record in self.evidence_records]
        if len(evidence_ids) != len(set(evidence_ids)):
            raise ValueError("working-context evidence ids must be unique")
        available_evidence = set(evidence_ids)
        step_ids = {step.id for step in self.plan.steps}

        _validate_plan_evidence_references(self.plan, available_evidence)

        evaluation = self.latest_evaluation
        if evaluation is None:
            return self

        evaluation_evidence_ids = [record.id for record in evaluation.evidence_records]
        if len(evaluation_evidence_ids) != len(set(evaluation_evidence_ids)):
            raise ValueError("latest evaluation evidence ids must be unique")

        missing_evaluation_evidence = set(evaluation_evidence_ids) - available_evidence
        if missing_evaluation_evidence:
            raise ValueError(
                "latest evaluation references missing evidence: "
                f"{sorted(missing_evaluation_evidence)!r}"
            )

        for assumption in evaluation.assumptions:
            missing_evidence = (
                    set(assumption.evidence_record_ids) - available_evidence
            )
            if missing_evidence:
                raise ValueError(
                    f"assumption {assumption.id!r} references missing evidence: "
                    f"{sorted(missing_evidence)!r}"
                )
            unknown_steps = set(assumption.affected_step_ids) - step_ids
            if unknown_steps:
                raise ValueError(
                    f"assumption {assumption.id!r} references unknown steps: "
                    f"{sorted(unknown_steps)!r}"
                )

        for contradiction in evaluation.contradictions:
            missing_evidence = (
                    set(contradiction.evidence_record_ids) - available_evidence
            )
            if missing_evidence:
                raise ValueError(
                    f"contradiction {contradiction.id!r} references missing "
                    f"evidence: {sorted(missing_evidence)!r}"
                )
            unknown_steps = set(contradiction.affected_step_ids) - step_ids
            if unknown_steps:
                raise ValueError(
                    f"contradiction {contradiction.id!r} references unknown steps: "
                    f"{sorted(unknown_steps)!r}"
                )

        if evaluation.answerability == Answerability.COMPLETE:
            incomplete_required = [
                step.id
                for step in self.plan.steps
                if step.required and step.status != PlanStepStatus.COMPLETE
            ]
            if incomplete_required:
                raise ValueError(
                    "complete answerability requires all required plan steps to "
                    f"be complete: {incomplete_required!r}"
                )

            blocking_reasoning = [
                item.id
                for item in [*evaluation.assumptions, *evaluation.contradictions]
                if item.impact == ReasoningImpact.BLOCKING
            ]
            if blocking_reasoning:
                raise ValueError(
                    "complete answerability cannot retain blocking assumptions or "
                    f"contradictions: {blocking_reasoning!r}"
                )

        return self
