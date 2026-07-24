from __future__ import annotations

from datetime import datetime
from typing import (
    Annotated,
    Literal,
    TypeAlias
)

from pydantic import (
    BeforeValidator,
    Field,
    model_validator,
)

from graph_rag.model.base import (
    ContractModel,
    WorkflowStatus,
    ActionOutcome,
    NonEmptyStr
)
from graph_rag.model.tool_operations import ToolCallRequest
from graph_rag.utils import (
    new_id,
    scalar_to_list,
    utc_now
)


# =============================================================================
# SELECTED ACTIONS AND EXECUTED ACTION RESULTS
#
# The action node selects one WorkflowAction after EvaluationResult has been
# applied to the working context and current plan. Plan updates are part of
# evaluation application and are not workflow actions.
#
# An action may rely only on evidence already incorporated into the working
# context before action selection.
# =============================================================================


class ActionBase(ContractModel):
    """Define fields shared by all selected workflow actions.

    Attributes:
        id: Stable identifier for the selected action.
        rationale: Explanation of why the action is appropriate now.
        evidence_record_ids: Evidence records supporting the action decision.
    """

    id: str = Field(
        default_factory=lambda: new_id("action"),
        description=(
            "Stable identifier for the selected action, normally generated automatically. "
            "The corresponding action result must copy this exact ID."
        ),
    )
    rationale: NonEmptyStr = Field(
        description=(
            "Explain why this action is the best next step given the current plan, "
            "evidence, assumptions, contradictions, limits, and latest evaluation."
        ),
    )
    evidence_record_ids: Annotated[
        list[NonEmptyStr],
        BeforeValidator(scalar_to_list),
    ] = Field(
        default_factory=list,
        description=(
            "Exact EvidenceRecord IDs from the updated working context that "
            "materially justify this action. Do not reference evidence produced "
            "later during the same iteration."
        ),
    )


class CallToolAction(ActionBase):
    """Select one exact tool invocation for execution.

    Attributes:
        id: Action identifier inherited from ActionBase.
        rationale: Reason the tool call is the appropriate next action.
        evidence_record_ids: Evidence supporting the action selection.
        type: Discriminator identifying a tool-call action.
        request: Exact validated tool invocation to execute.
    """

    type: Literal["call_tool"] = Field(
        default="call_tool",
        description=(
            "Discriminator for a tool-execution action. Always use the exact literal "
            "\"call_tool\" for this model."
        ),
    )
    request: ToolCallRequest = Field(
        description=(
            "Complete exact ToolCallRequest to execute. The request must select an "
            "available tool, supply schema-valid arguments, and explain how the call "
            "advances the plan."
        ),
    )


class FinalizeAction(ActionBase):
    """Route the workflow to final response creation.

    Attributes:
        id: Action identifier inherited from ActionBase.
        rationale: Reason the investigation should terminate now.
        evidence_record_ids: Evidence supporting finalization.
        type: Discriminator identifying a finalization action.
        status: Terminal status the final response should represent.
    """

    type: Literal["finalize"] = Field(
        default="finalize",
        description=(
            "Discriminator for a finalization action. Always use the exact literal "
            "\"finalize\" for this model."
        ),
    )
    status: Literal[
        WorkflowStatus.COMPLETE,
        WorkflowStatus.PARTIAL,
        WorkflowStatus.FAILED,
    ] = Field(
        description=(
            "Terminal status to use when producing the answer. It must agree with the "
            "latest evaluation’s answerability and the actual completeness of required "
            "plan steps."
        ),
    )


class RequestClarificationAction(ActionBase):
    """Route the workflow to request additional user information.

    Attributes:
        id: Action identifier inherited from ActionBase.
        rationale: Reason user clarification is necessary.
        evidence_record_ids: Evidence supporting the clarification decision.
        type: Discriminator identifying a clarification request.
        question: Specific question to present to the user.
    """

    type: Literal["request_clarification"] = Field(
        default="request_clarification",
        description=(
            "Discriminator for a clarification action. Always use the exact literal "
            "\"request_clarification\" for this model."
        ),
    )
    question: NonEmptyStr = Field(
        description=(
            "Specific concise question asking for the minimum user information needed to "
            "resolve the blocking ambiguity. Do not ask for information already present "
            "in the question, working context, evidence, or iteration history."
        ),
    )


WorkflowAction: TypeAlias = Annotated[
    CallToolAction
    | FinalizeAction
    | RequestClarificationAction,
    Field(discriminator="type"),
]


class ActionResultBase(ContractModel):
    """Define fields shared by executable action results.

    Attributes:
        action_id: ID of the selected action that produced this result.
        outcome: Operational outcome of the action.
        completed_at: UTC timestamp at which action execution completed.
        error: Error explanation for failed or rejected actions.
    """

    action_id: NonEmptyStr = Field(
        description=(
            "Exact ID of the selected action whose execution produced this result. Copy "
            "the action ID; do not generate a new value."
        ),
    )
    outcome: ActionOutcome = Field(
        description=(
            "Actual operational outcome of executing the action. Distinguish execution "
            "success from whether the returned information was conclusive."
        ),
    )
    completed_at: datetime = Field(
        default_factory=utc_now,
        description=(
            "UTC timestamp generated when action execution completed. It is supplied by "
            "the workflow runtime rather than invented by the reasoning model."
        ),
    )
    error: NonEmptyStr | None = Field(
        default=None,
        description=(
            "Error explanation for FAILED or REJECTED outcomes; otherwise null. Record "
            "the actual failure without speculative diagnosis."
        ),
    )

    @model_validator(mode="after")
    def validate_outcome(self) -> ActionResultBase:
        """Validate the relationship between outcome and error information."""

        if self.outcome == ActionOutcome.SUCCEEDED and self.error is not None:
            raise ValueError("successful action results cannot contain an error")
        if self.outcome in {ActionOutcome.FAILED, ActionOutcome.REJECTED}:
            if self.error is None:
                raise ValueError("failed or rejected actions require an error")
        return self


class CallToolActionResult(ActionResultBase):
    """Record execution of a CallToolAction.

    Attributes:
        action_id: ID of the CallToolAction that was executed.
        outcome: Operational outcome of the action.
        completed_at: UTC timestamp at which action execution completed.
        error: Error explanation for a failed or rejected action.
        type: Discriminator identifying a tool-call action result.
        tool_result_id: Retained raw tool-result identifier.
    """

    type: Literal["call_tool"] = Field(
        default="call_tool",
        description=(
            "Discriminator for a tool-call action result. Always use the exact literal "
            "\"call_tool\" for this model."
        ),
    )
    tool_result_id: NonEmptyStr = Field(
        description=(
            "Exact retained ToolCallResult.id produced by this action. Do not use the "
            "request ID or embed the raw result here."
        ),
    )


ExecutedActionResult: TypeAlias = Annotated[
    CallToolActionResult,
    Field(discriminator="type"),
]
