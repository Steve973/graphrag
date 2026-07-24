from __future__ import annotations

from datetime import datetime
from typing import Annotated, Literal

from pydantic import (
    Field,
    BeforeValidator,
    model_validator,
    JsonValue
)

from graph_rag.model.base import (
    ContractModel,
    Answerability,
    ErrorCategory,
    ReasoningImpact,
    NonEmptyStr
)
from graph_rag.model.supporting_data import (
    Assumption,
    Contradiction, EvidenceRecord
)
from graph_rag.utils import (
    new_id,
    scalar_to_list,
    utc_now
)


# =============================================================================
# EVALUATION OF THE CURRENT WORKING CONTEXT
#
# WorkflowEvaluation assesses the current plan revision and all evidence available
# at the beginning of an iteration.
#
# The evaluation retained in the iteration record therefore documents both the
# state examined and the changes that prepared the working context for action
# selection.
# =============================================================================


class EvaluationFailureDisposition(ContractModel):
    """Record why evaluation determined that the workflow must fail.

    Attributes:
        error_ids: WorkflowError IDs that caused the non-recoverable failure.
        rationale: Explanation of why the cited errors prevent continuation.
    """

    error_ids: Annotated[
        list[NonEmptyStr],
        BeforeValidator(scalar_to_list),
    ] = Field(
        min_length=1,
        description=(
            "WorkflowError IDs that caused the non-recoverable failure. Cite retained "
            "error records from the current or immediately preceding iteration context."
        ),
    )
    rationale: NonEmptyStr = Field(
        description=(
            "Explain why the cited errors are non-recoverable and require workflow "
            "failure rather than another action or partial answer."
        ),
    )

    @model_validator(mode="after")
    def validate_failure_disposition(
        self,
    ) -> EvaluationFailureDisposition:
        """Reject duplicate referenced error IDs."""

        if len(self.error_ids) != len(set(self.error_ids)):
            raise ValueError("failure disposition error ids must be unique")
        return self


class BaseEvaluationContent(ContractModel):
    """Describes the context evaluation content.

    Attributes:
        answerability: Current ability to answer based on the evaluated plan and evidence: COMPLETE
            only when all required steps are complete and no blocking issue remains;
            PARTIAL when useful supported content exists but material gaps remain;
            NEEDS_CLARIFICATION when user input is required; otherwise NOT_READY.
        iteration_purpose: Immediate goal for the current iteration, derived from what is now
            known, what remains unresolved, and what progress would most directly
            advance the investigation.
        rationale: Integrated explanation for the evaluation’s answerability, plan disposition,
            assumptions, contradictions, and recommended focus. Ground all factual
            claims in the evidence IDs listed by this evaluation.
        failure: Details of any evaluation failure, including related error identifiers
            and a rationale for the failure.
    """

    answerability: Answerability = Field(
        description=(
            "Current ability to answer based on the evaluated plan and evidence: COMPLETE "
            "only when all required steps are complete and no blocking issue remains; "
            "PARTIAL when useful supported content exists but material gaps remain; "
            "NEEDS_CLARIFICATION when user input is required; otherwise NOT_READY."
        ),
    )
    iteration_purpose: NonEmptyStr = Field(
        description=(
            "Immediate goal for the current iteration, derived from what is now "
            "known, what remains unresolved, and what progress would most directly "
            "advance the investigation."
        ),
    )
    rationale: NonEmptyStr = Field(
        description=(
            "Integrated explanation for the evaluation’s answerability, plan disposition, "
            "assumptions, contradictions, and recommended focus. Ground all factual "
            "claims in the evidence IDs listed by this evaluation."
        ),
    )
    failure: EvaluationFailureDisposition | None = Field(
        default=None,
        description=(
            "Details of an evaluation-determined workflow failure. Use only for "
            "non-recoverable operational or workflow errors, not evidence insufficiency."
        )
    )

    @model_validator(mode="after")
    def validate_failure_answerability(self) -> BaseEvaluationContent:
        """Keep failure disposition distinct from complete answerability."""

        if self.failure is not None and self.answerability == Answerability.COMPLETE:
            raise ValueError(
                "evaluation failure cannot be combined with complete answerability"
            )
        return self


class WorkflowEvaluation(BaseEvaluationContent):
    """Assess the cumulative workflow state at the beginning of an iteration.

    The evaluation considers the current plan, all evidence already available
    in the working context, and the completed record from the immediately
    preceding iteration when one exists. It determines what is currently known,
    what remains unresolved, whether a supported answer can be produced, and
    the purpose that should guide the current iteration.

    This model records the evaluator's conclusions. It does not describe the
    updates that must be applied to the working context or plan. Those
    instructions are carried separately by EvaluationResult.

    The evaluation retained in an IterationRecord is the evaluation used to
    prepare the context and choose that iteration's action. It does not assess
    the action or results produced later in the same iteration.

    Attributes:
        id: Stable evaluation identifier.
        iteration_number: Iteration for which the evaluation was produced.
        evidence_records: Accumulated evidence to be materially considered.
        assumptions: Current assumptions affecting the investigation.
        contradictions: Current contradictions affecting the investigation.
        answerability: Current ability to produce a supported response.
        iteration_purpose: Immediate goal that should guide this iteration.
        rationale: Explanation supporting the evaluation's conclusions.
        created_at: UTC timestamp at which the evaluation was produced.
    """

    id: str = Field(
        default_factory=lambda: new_id("evaluation"),
        description=(
            "Stable identifier for this evaluation, normally generated automatically. "
            "Omit it when producing a new evaluation."
        ),
    )
    iteration_number: int = Field(
        ge=1,
        description=(
            "One-based number of the iteration being evaluated. Copy the current "
            "iteration number exactly; do not derive a different count from IDs or plan "
            "revisions."
        ),
    )
    created_at: datetime = Field(
        default_factory=utc_now,
        description=(
            "UTC timestamp generated when the evaluation is created. Omit it unless the "
            "application explicitly supplies the timestamp."
        ),
    )
    assumptions: Annotated[
        list[Assumption],
        BeforeValidator(scalar_to_list),
    ] = Field(
        default_factory=list,
        description=(
            "Current assumptions discovered or still relevant while evaluating this plan. "
            "Include only assumptions that affect reasoning or completion, with explicit "
            "impact and evidence links where applicable."
        ),
    )
    contradictions: Annotated[
        list[Contradiction],
        BeforeValidator(scalar_to_list),
    ] = Field(
        default_factory=list,
        description=(
            "Current unresolved contradictions discovered or still relevant to this plan. "
            "Each must explain the conflict, impact, affected steps, and supporting "
            "evidence."
        ),
    )
    evidence_records: list[EvidenceRecord] = Field(
        default_factory=list,
        description=(
            "Accumulated evidence in the working context that is materially "
            "considered by this evaluation."
        ),
    )

    @model_validator(mode="after")
    def validate_evaluation(self) -> WorkflowEvaluation:
        """Validate identifier uniqueness and compatible evaluation decisions."""

        evidence_ids = [record.id for record in self.evidence_records]
        if len(evidence_ids) != len(set(evidence_ids)):
            raise ValueError("evaluation evidence records must be unique")
        available_evidence = set(evidence_ids)

        assumption_ids = [item.id for item in self.assumptions]
        if len(assumption_ids) != len(set(assumption_ids)):
            raise ValueError("assumption ids must be unique within an evaluation")

        contradiction_ids = [item.id for item in self.contradictions]
        if len(contradiction_ids) != len(set(contradiction_ids)):
            raise ValueError("contradiction ids must be unique within an evaluation")

        for assumption in self.assumptions:
            if len(assumption.evidence_record_ids) != len(
                    set(assumption.evidence_record_ids)
            ):
                raise ValueError(
                    f"assumption {assumption.id!r} has duplicate evidence ids"
                )
            missing_evidence = (
                    set(assumption.evidence_record_ids) - available_evidence
            )
            if missing_evidence:
                raise ValueError(
                    f"assumption {assumption.id!r} references missing evidence: "
                    f"{sorted(missing_evidence)!r}"
                )

        for contradiction in self.contradictions:
            if len(contradiction.evidence_record_ids) != len(
                    set(contradiction.evidence_record_ids)
            ):
                raise ValueError(
                    f"contradiction {contradiction.id!r} has duplicate evidence ids"
                )
            missing_evidence = (
                    set(contradiction.evidence_record_ids) - available_evidence
            )
            if missing_evidence:
                raise ValueError(
                    f"contradiction {contradiction.id!r} references missing "
                    f"evidence: {sorted(missing_evidence)!r}"
                )

        if self.answerability == Answerability.COMPLETE:
            blocking_reasoning = [
                item.id
                for item in [*self.assumptions, *self.contradictions]
                if item.impact == ReasoningImpact.BLOCKING
            ]
            if blocking_reasoning:
                raise ValueError(
                    "complete answerability cannot retain blocking assumptions "
                    f"or contradictions: {blocking_reasoning!r}"
                )

        return self


class AssumptionsUpdate(ContractModel):
    """
    Represents an update operation for handling assumptions associated with a plan.

    This class allows modifications to the existing list of assumptions using a specified
    update type. The supported update types include replacing all existing assumptions,
    removing specific ones, or appending new assumptions to the list. Each assumption should
    be explicitly defined where possible and linked with its impact and evidence.

    Attributes:
        type: Update type for assumptions. 'replace' replaces all existing assumptions
            with the provided list. 'remove' removes the specified assumptions from
            the existing list. 'append' adds the provided assumptions to the existing
            list.
        assumptions: A list of assumptions to update the existing list of assumptions.
    """

    type: Literal["replace", "remove", "append"] = Field(
        default="append",
        description=(
            "Update type for assumptions. 'replace' replaces all existing assumptions "
            "with the provided list. 'remove' removes the specified assumptions from "
            "the existing list. 'append' adds the provided assumptions to the existing "
            "list."
        ),
    )
    assumptions: Annotated[
        list[Assumption],
        BeforeValidator(scalar_to_list),
    ] = Field(
        default_factory=list,
        description=(
            "Current assumptions discovered or still relevant while evaluating this plan. "
            "Include only assumptions that affect reasoning or completion, with explicit "
            "impact and evidence links where applicable."
        ),
    )


class ContradictionsUpdate(ContractModel):
    """
    Represents an update model to manage contradictions in a plan.

    This class defines how contradictions within a plan should be updated. Users can
    either replace, remove, or append to the existing list of contradictions. The
    contradictions represent unresolved conflicts that are either newly discovered or
    still applicable to the plan. Each contradiction must include details about the
    conflict, its impact, the steps it affects, and supporting evidence.

    Attributes:
        type: Update type for contradictions. 'replace' replaces all existing contradictions
            with the provided list. 'remove' removes the specified contradictions from
            the existing list. 'append' adds the provided contradictions to the existing
            list.
        contradictions: A list of contradictions to update the existing list of contradictions.
    """

    type: Literal["replace", "remove", "append"] = Field(
        default="append",
        description=(
            "Update type for contradictions. 'replace' replaces all existing contradictions "
            "with the provided list. 'remove' removes the specified contradictions from "
            "the existing list. 'append' adds the provided contradictions to the existing "
            "list."
        ),
    )
    contradictions: Annotated[
        list[Contradiction],
        BeforeValidator(scalar_to_list),
    ] = Field(
        default_factory=list,
        description=(
            "Current unresolved contradictions discovered or still relevant to this plan. "
            "Each must explain the conflict, impact, affected steps, and supporting "
            "evidence."
        ),
    )


class EvaluationResult(BaseEvaluationContent):
    """Describe the updates to apply before action selection. The LLM returns instances of
    this class for subsequent application.

    Attributes:
        id: Stable identifier for this evaluation result, normally generated automatically.
            Omit it when producing a new evaluation result.
        assumptions_updates: Updates to assumptions discovered or still relevant while evaluating this plan.
            Include only assumptions that affect reasoning or completion, with explicit
            impact and evidence links where applicable.
        contradictions_updates: Updates to contradictions discovered or still relevant while evaluating this plan.
            Each must explain the conflict, impact, affected steps, and supporting
            evidence.
        new_evidence_records: Evidence from the preceding iteration to
            incorporate into the cumulative working context.
        answerability: Current ability to answer based on the evaluated plan and evidence: COMPLETE
            only when all required steps are complete and no blocking issue remains;
            PARTIAL when useful supported content exists but material gaps remain;
            NEEDS_CLARIFICATION when user input is required; otherwise NOT_READY.
        iteration_purpose: Immediate goal for the current iteration, derived from what is now
            known, what remains unresolved, and what progress would most directly
            advance the investigation.
        rationale: Integrated explanation for the evaluation’s answerability, plan disposition,
            assumptions, contradictions, and recommended focus. Ground all factual
            claims in the evidence IDs listed by this evaluation.
    """

    id: str = Field(
        default_factory=lambda: new_id("evaluation_result"),
        description=(
            "Stable identifier for this evaluation result, normally generated automatically. "
            "Omit it when producing a new evaluation result."
        ),
    )
    assumptions_updates: Annotated[
        list[AssumptionsUpdate],
        BeforeValidator(scalar_to_list),
    ] = Field(
        default_factory=list,
        description=(
            "Assumptions updates to be applied, in order, to the list of assumptions."
        ),
    )
    contradictions_updates: Annotated[
        list[ContradictionsUpdate],
        BeforeValidator(scalar_to_list),
    ] = Field(
        default_factory=list,
        description=(
            "Contradictions updates to be applied, in order, to the list of contradictions."
        ),
    )
    new_evidence_records: list[EvidenceRecord] = Field(
        default_factory=list,
        description=(
            "Evidence from the preceding iteration to incorporate into the "
            "cumulative working context."
        ),
    )


class WorkflowError(ContractModel):
    """Capture a structured error in initialization or an iteration.

    Attributes:
        id: Stable error-record identifier.
        category: Stable classification of the failure.
        message: Human-readable explanation of the error.
        recoverable: Whether the workflow may choose another action and continue.
        details: Additional JSON-compatible diagnostic information.
        created_at: UTC timestamp at which the error was recorded.
    """

    id: str = Field(
        default_factory=lambda: new_id("error"),
        description=(
            "Stable identifier for this error record, normally generated automatically."
        ),
    )
    category: ErrorCategory = Field(
        description=(
            "Most specific available classification of the actual error. Choose based on "
            "where and why the failure occurred, not on its effect on the final answer."
        ),
    )
    message: NonEmptyStr = Field(
        description=(
            "Concise human-readable description of what failed. Preserve actionable "
            "details and avoid unsupported diagnosis."
        ),
    )
    recoverable: bool = Field(
        description=(
            "Whether the workflow can reasonably select another action and continue "
            "without user intervention or loss of correctness."
        ),
    )
    details: dict[str, JsonValue] = Field(
        default_factory=dict,
        description=(
            "Optional structured JSON-compatible diagnostics useful for tracing the "
            "error. Do not place secrets or arbitrary prose dumps here."
        ),
    )
    created_at: datetime = Field(
        default_factory=utc_now,
        description=(
            "UTC timestamp generated when the error is recorded."
        ),
    )
