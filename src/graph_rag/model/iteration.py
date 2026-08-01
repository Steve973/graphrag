from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from typing import Annotated, Self

from pydantic import (
    BeforeValidator,
    Field,
    model_validator
)

from graph_rag.model.action import (
    ExecutedActionResult,
    WorkflowAction,
    FinalizeAction,
    RequestClarificationAction,
    CallToolAction,
    CallToolActionResult,
)
from graph_rag.model.base import (
    ActionOutcome,
    NonEmptyStr,
    ContractModel, Answerability
)
from graph_rag.model.plan import Plan
from graph_rag.model.supporting_data import EvidenceRecord
from graph_rag.model.tool_operations import (
    ToolCallResult,
    ToolResultStatus
)
from graph_rag.model.workflow import (
    WorkflowError,
    EvaluationResult
)
from graph_rag.utils import scalar_to_list, utc_now


# =============================================================================
# ITERATION FORENSICS
#
# IterationRecord captures exactly what happened: evaluation,
# action, retained raw result, evidence summaries, and errors.
# =============================================================================


class IterationRecord(ContractModel):
    """Retain the complete forensic record of one finished iteration.

    Attributes:
        iteration_number: One-based position in workflow history.
        purpose: Immediate investigation objective of the iteration.
        action: Single action selected for the iteration.
        action_result: Result of an executable action, when applicable.
        tool_results: Complete raw tool results produced by the action.
        evidence_records: New evidence summaries are created from retained results.
        errors: Structured errors encountered during the iteration.
        started_at: UTC timestamp at which the iteration began.
        completed_at: UTC timestamp at which the iteration was committed.
    """

    iteration_number: int = Field(
        ge=1,
        description=(
            "One-based sequence number of this committed iteration. It must equal its "
            "position in the persisted iteration history."
        ),
    )
    purpose: NonEmptyStr = Field(
        description=(
            "Specific immediate objective pursued during this iteration."
        ),
    )
    plan: Plan = Field(
        description=(
            "Plan revision that was current for this iteration after any "
            "plan-evaluation update was applied."
        ),
    )
    evaluation_result: EvaluationResult = Field(
        description=(
            "Evaluation result applied to the working context before action selection. "
            "It does not evaluate the action or results produced later in the "
            "iteration."
        ),
    )
    action: WorkflowAction = Field(
        description=(
            "Single action selected and attempted during this iteration, including its "
            "rationale and evidence links."
        ),
    )
    action_result: ExecutedActionResult | None = Field(
        default=None,
        description=(
            "Execution result for the selected executable action, or null for terminal "
            "finalization and clarification actions."
        ),
    )
    tool_results: Annotated[
        list[ToolCallResult],
        BeforeValidator(scalar_to_list),
    ] = Field(
        default_factory=list,
        description=(
            "Complete retained raw tool results produced during this iteration. Each "
            "result must reference a request represented by the selected action."
        ),
    )
    evidence_records: Annotated[
        list[EvidenceRecord],
        BeforeValidator(scalar_to_list),
    ] = Field(
        default_factory=list,
        description=(
            "New compact evidence summaries produced during this iteration. Each must "
            "cite retained tool-result IDs from this record."
        ),
    )
    errors: Annotated[
        list[WorkflowError],
        BeforeValidator(scalar_to_list),
    ] = Field(
        default_factory=list,
        description=(
            "Structured errors encountered during this iteration, including recoverable "
            "errors retained for forensic traceability."
        ),
    )
    started_at: datetime = Field(
        description=(
            "Actual UTC timestamp at which this iteration began."
        ),
    )
    completed_at: datetime = Field(
        description=(
            "Actual UTC timestamp at which this iteration record was committed. It must "
            "not precede started_at."
        ),
    )

    @model_validator(mode="after")
    def validate_iteration_trace(self) -> IterationRecord:
        """Validate the completed iteration's evaluation, action, and artifacts."""

        if self.completed_at < self.started_at:
            raise ValueError("completed_at cannot precede started_at")

        result_ids = [result.id for result in self.tool_results]
        if len(result_ids) != len(set(result_ids)):
            raise ValueError("iteration tool result ids must be unique")

        evidence_ids = [record.id for record in self.evidence_records]
        if len(evidence_ids) != len(set(evidence_ids)):
            raise ValueError("iteration evidence ids must be unique")

        error_ids = [error.id for error in self.errors]
        if len(error_ids) != len(set(error_ids)):
            raise ValueError("iteration error ids must be unique")

        retained_result_ids = set(result_ids)
        for evidence in self.evidence_records:
            missing_result_ids = (
                    set(evidence.evidence_data_ids) - retained_result_ids
            )
            if missing_result_ids:
                raise ValueError(
                    f"evidence record {evidence.id!r} references tool results "
                    f"not retained by this iteration: "
                    f"{sorted(missing_result_ids)!r}"
                )

        # Terminal actions are selected because of this iteration's context
        # evaluation, but they do not execute or produce tool artifacts.
        if isinstance(self.action, FinalizeAction):
            if self.action_result is not None:
                raise ValueError(
                    "finalize actions cannot have an execution result"
                )
            if self.tool_results:
                raise ValueError(
                    "finalize actions cannot produce tool results"
                )
            if self.evidence_records:
                raise ValueError(
                    "finalize actions cannot produce evidence records"
                )
            return self

        if isinstance(self.action, RequestClarificationAction):
            if self.action_result is not None:
                raise ValueError(
                    "clarification actions cannot have an execution result"
                )
            if self.tool_results:
                raise ValueError(
                    "clarification actions cannot produce tool results"
                )
            if self.evidence_records:
                raise ValueError(
                    "clarification actions cannot produce evidence records"
                )
            return self

        # Every remaining action is executable.
        if self.action_result is None:
            raise ValueError(
                "executable actions require an action result"
            )
        if self.action_result.action_id != self.action.id:
            raise ValueError(
                "action result must reference the selected action"
            )
        if self.action_result.type != self.action.type:
            raise ValueError(
                "action and action-result types must match"
            )

        if isinstance(self.action, CallToolAction):
            if not isinstance(
                    self.action_result,
                    CallToolActionResult,
            ):
                raise ValueError(
                    "call-tool actions require call-tool action results"
                )

            # CallToolAction represents one exact invocation, so the iteration
            # must retain exactly one raw result for that request.
            if len(self.tool_results) != 1:
                raise ValueError(
                    "call-tool actions require exactly one tool result"
                )

            tool_result = self.tool_results[0]

            if tool_result.request_id != self.action.request.id:
                raise ValueError(
                    "tool result must reference the selected tool request"
                )
            if self.action_result.tool_result_id != tool_result.id:
                raise ValueError(
                    "action result must reference the retained tool result"
                )

            if tool_result.status == ToolResultStatus.SUCCESS:
                if self.action_result.outcome not in {
                    ActionOutcome.SUCCEEDED,
                    ActionOutcome.INCONCLUSIVE,
                }:
                    raise ValueError(
                        "successful tool results require a succeeded or "
                        "inconclusive action outcome"
                    )

                if not self.evidence_records:
                    raise ValueError(
                        "successful tool calls require at least one "
                        "evidence record"
                    )

                unrelated_evidence = [
                    evidence.id
                    for evidence in self.evidence_records
                    if tool_result.id not in evidence.evidence_data_ids
                ]
                if unrelated_evidence:
                    raise ValueError(
                        "evidence produced by a successful tool action must "
                        "reference that action's tool result: "
                        f"{unrelated_evidence!r}"
                    )

            elif tool_result.status == ToolResultStatus.ERROR:
                if self.action_result.outcome != ActionOutcome.FAILED:
                    raise ValueError(
                        "tool execution errors require a failed action outcome"
                    )
                if self.evidence_records:
                    raise ValueError(
                        "failed tool calls cannot produce evidence records"
                    )

            elif tool_result.status == ToolResultStatus.REJECTED:
                if self.action_result.outcome != ActionOutcome.REJECTED:
                    raise ValueError(
                        "rejected tool calls require a rejected action outcome"
                    )
                if self.evidence_records:
                    raise ValueError(
                        "rejected tool calls cannot produce evidence records"
                    )

            return self

        raise ValueError(
            f"unsupported workflow action type: "
            f"{type(self.action).__name__}"
        )


@dataclass(slots=True)
class IterationRecordBuilder:
    """Assemble the forensic record for the iteration currently in progress."""

    iteration_number: int = 0
    started_at: datetime = field(default_factory=utc_now)
    purpose: str = "Unspecified"
    plan: Plan = field(default_factory=Plan)
    evaluation_result: EvaluationResult = field(
        default_factory=lambda: EvaluationResult(
            answerability=Answerability.NOT_READY,
            iteration_purpose="Unspecified",
            rationale="Unspecified",
        )
    )
    action: WorkflowAction | None = None
    action_result: ExecutedActionResult | None = None
    tool_results: list[ToolCallResult] = field(default_factory=list)
    evidence_records: list[EvidenceRecord] = field(default_factory=list)
    errors: list[WorkflowError] = field(default_factory=list)

    def set_plan(self, plan: Plan) -> Self:
        """Record the plan that was current for this iteration."""

        self.plan = plan
        return self

    def set_evaluation_result(
        self,
        evaluation_result: EvaluationResult,
    ) -> Self:
        """Record the evaluation result applied to the working context."""

        self.evaluation_result = evaluation_result
        return self

    def set_action(
        self,
        action: WorkflowAction,
    ) -> Self:
        """Record the single action selected for this iteration."""

        self.action = action
        return self

    def set_action_result(
        self,
        action_result: ExecutedActionResult,
    ) -> Self:
        """Record the execution result for the selected action."""

        self.action_result = action_result
        return self

    def add_tool_result(
        self,
        tool_result: ToolCallResult,
    ) -> Self:
        """Retain one raw tool result produced during this iteration."""

        self.tool_results.append(tool_result)
        return self

    def add_evidence_record(
        self,
        evidence_record: EvidenceRecord,
    ) -> Self:
        """Retain one evidence record produced during this iteration."""

        self.evidence_records.append(evidence_record)
        return self

    def add_error(
        self,
        error: WorkflowError,
    ) -> Self:
        """Retain one structured error encountered during this iteration."""

        self.errors.append(error)
        return self

    def build(
        self,
        completed_at: datetime | None = None,
    ) -> IterationRecord:
        """Create the complete immutable and validated iteration record."""

        if self.action is None:
            raise ValueError(
                "an iteration record requires a selected action"
            )

        record = IterationRecord(
            iteration_number=self.iteration_number,
            purpose=self.purpose,
            plan=self.plan,
            evaluation_result=self.evaluation_result,
            action=self.action,
            action_result=self.action_result,
            tool_results=list(self.tool_results),
            evidence_records=list(self.evidence_records),
            errors=list(self.errors),
            started_at=self.started_at,
            completed_at=completed_at or utc_now(),
        )

        return record
