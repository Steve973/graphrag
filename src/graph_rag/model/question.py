from __future__ import annotations

from datetime import datetime
from typing import TypeAlias, Literal

from pydantic import (
    Field,
)

from graph_rag.model.base import (
    ContractModel,
    WorkflowStatus,
    WorkflowLimitsMode,
    NonEmptyStr
)
from graph_rag.utils import (
    new_id,
    utc_now
)


# =============================================================================
# QUESTION AND EXECUTION LIMITS
#
# Question identifies one workflow execution and carries the user text plus
# request-level limits. profile_id is an optional explicit profile selection;
# when omitted, initialization uses the configured GraphDataProfile.
# =============================================================================


class WorkflowLimits(ContractModel):
    """Specify request-level bounds for workflow execution.

    Attributes:
        max_iterations: Maximum number of investigation iterations allowed.
        max_elapsed_seconds: Maximum intended wall-clock duration in seconds.
        mode: Rule used to apply the configured limits.
    """

    max_iterations: int = Field(
        default=8,
        ge=1,
        description=(
            "Maximum number of investigation iterations permitted for this workflow. "
            "Treat this as an execution constraint supplied by the caller; copy it "
            "unchanged rather than choosing a new value."
        ),
    )
    max_elapsed_seconds: int = Field(
        default=120,
        ge=1,
        description=(
            "Maximum intended wall-clock duration, in seconds, for this workflow. Treat "
            "this as a caller-supplied execution constraint and do not revise it."
        ),
    )
    mode: WorkflowLimitsMode = Field(
        default=WorkflowLimitsMode.FIRST,
        description=(
            "Rule for deciding when configured limits stop execution. Use the exact "
            "supplied enum value and apply its documented semantics consistently."
        ),
    )


class ClarificationRequest(ContractModel):
    rationale: NonEmptyStr = Field(
        description=(
            "Rationale for requesting clarification. This should explain the need for "
            "clarification from the user. E.g., why is the question too broad, what is "
            "specifically ambiguous or missing, or what conditions have arisen that "
            "prohibit deterministic and accurate progression of the workflow?"
        )
    )
    user_message: NonEmptyStr = Field(
        description=(
            "A message to the user that prompts for the specific clarification needed "
            "to resolve the uncertainty. This message should ideally include suggestions "
            "or examples of the type of information that the LLM needs to resolve the "
            "uncertainty in order to proceed."
        )
    )


class UserClarificationResponse(ContractModel):
    response: NonEmptyStr = Field(
        description=(
            "User response to a clarification request. This should be requested when "
            "the LLM needs to clarify something that may be ambiguous or too broad as "
            "phrased in the question, or when accumulated evidence shows that "
            "proceeding without further clarification is difficult or may stray from "
            "the original question."
        )
    )


class UserClarificationEvaluationResult(ContractModel):
    resolved: bool = Field(
        description=(
            "Whether the user clarification response resolved the uncertainty. A "
            "value of 'False' requires an accompanying explanation in the "
            "'remaining_information_needed' field. Both 'True' and 'False' values "
            "require an accompanying rationale that explains this determination in "
            "that field."
        )
    )
    rationale: NonEmptyStr = Field(
        description=(
            "Rationale for the user clarification response. This explains why the "
            "user clarification response either resolved, or failed to resolve, the "
            "uncertainty."
        )
    )
    remaining_information_needed: str | None = Field(
        default=None,
        description=(
            "Additional information needed to resolve the uncertainty. This field is "
            "required when the 'resolved' field is 'False'."
        )
    )


class Question(ContractModel):
    """Represent the complete user request accepted by the workflow.

    Attributes:
        id: Stable identifier shared by the question and workflow execution.
        text: Natural-language question the workflow must answer.
        profile_id: Optional explicit graph-data profile identifier. When absent,
            initialization uses the process configuration.
        limits: Request-specific execution bounds and limit-resolution mode.
        submitted_at: UTC timestamp at which the question was created.
    """

    id: str = Field(
        default_factory=lambda: new_id("workflow"),
        description=(
            "Stable workflow identifier. It is normally generated by the application; "
            "omit it when creating a new question unless an existing workflow ID was "
            "explicitly supplied. Reuse this exact value throughout the workflow."
        ),
    )
    text: NonEmptyStr = Field(
        description=(
            "The original natural-language request to solve. Preserve the user’s meaning "
            "exactly; do not replace this field with an answer, summary, plan, or "
            "rewritten request."
        ),
    )
    profile_id: NonEmptyStr | None = Field(
        default=None,
        description=(
            "Optional exact graph-data profile identifier selected for this workflow, for "
            "example \"gtd/v1\". Use only a configured profile ID; do not invent one. Leave "
            "null when initialization should use the configured default profile."
        ),
    )
    limits: WorkflowLimits = Field(
        default_factory=WorkflowLimits,
        description=(
            "Caller-supplied workflow execution limits. Carry this object forward "
            "unchanged; it is not part of the investigation reasoning."
        ),
    )
    submitted_at: datetime = Field(
        default_factory=utc_now,
        description=(
            "UTC submission timestamp generated by the application. Omit it when creating "
            "a new question unless the exact timestamp is already known."
        ),
    )

    def simple_string(self) -> str:
        return f"Question: {self.text}"


FinalAnswerStatus: TypeAlias = Literal[
    WorkflowStatus.COMPLETE,
    WorkflowStatus.PARTIAL,
    WorkflowStatus.FAILED,
]


class FinalAnswer(ContractModel):
    """Represent the public terminal response.

    Attributes:
        workflow_id: Identifier used to retrieve the persisted workflow record.
        status: Terminal workflow status represented by the response.
        answer: User-facing answer or clarification request.
        confidence: Confidence in the answer.
    """

    workflow_id: NonEmptyStr = Field(
        description=(
            "Exact workflow/question ID used to retrieve the persisted plan, evidence, "
            "raw results, and iteration trace. Copy it from GraphRagState.workflow_id."
        ),
    )
    status: FinalAnswerStatus = Field(
        description=(
            "Terminal workflow status. It must agree with the final action and latest "
            "evaluation; use COMPLETE only for a fully supported answer."
        ),
    )
    answer: NonEmptyStr = Field(
        description=(
            "Direct user-facing answer. Base factual claims on the accepted findings "
            "and evidence carried by the workflow, but do not expose internal IDs or "
            "raw trace data."
        ),
    )
    confidence: float = Field(
        ge=0.0,
        le=1.0,
        description=(
            "Confidence in the answer, on a scale from 0 to 1. 0 means the answer is "
            "completely uncertain, while 1 means the answer is completely certain."
        ),
    )
