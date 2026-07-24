from __future__ import annotations

from enum import StrEnum
from typing import (
    TypeAlias,
    Annotated
)

from pydantic import (
    StringConstraints,
    BaseModel,
    ConfigDict
)

NonEmptyStr: TypeAlias = Annotated[
    str,
    StringConstraints(strip_whitespace=True, min_length=1),
]


class WorkflowLimitsMode(StrEnum):
    """Define how iteration and elapsed-time limits control termination.

    Attributes:
        FIRST: Stop when the first configured limit is reached.
        ALL: Stop only after all configured limits have been reached.
        ITERATION: Treat the iteration limit as controlling and elapsed time as
            advisory.
        ELAPSED: Treat elapsed time as controlling and the iteration limit as
            advisory.
    """

    FIRST = "first"
    ALL = "all"
    ITERATION = "iteration"
    ELAPSED = "elapsed"


class WorkflowStatus(StrEnum):
    """Describe the lifecycle or terminal status of a workflow execution.

    Attributes:
        INITIALIZING: Graph context and the initial plan are being prepared.
        RUNNING: The controlled investigation loop is active.
        COMPLETE: The workflow produced a fully supported answer.
        PARTIAL: The workflow produced a supported but incomplete answer.
        NEEDS_CLARIFICATION: User input is required before work can continue.
        FAILED: A non-recoverable error prevented a usable answer.
    """

    INITIALIZING = "initializing"
    RUNNING = "running"
    COMPLETE = "complete"
    PARTIAL = "partial"
    NEEDS_CLARIFICATION = "needs_clarification"
    FAILED = "failed"


class Answerability(StrEnum):
    """Express whether the current plan can support a response.

    Attributes:
        NOT_READY: More investigation is required before answering.
        COMPLETE: All required plan work supports a complete answer.
        PARTIAL: Available evidence supports a useful but incomplete answer.
        NEEDS_CLARIFICATION: Missing user input prevents a supported answer.
    """

    NOT_READY = "not_ready"
    COMPLETE = "complete"
    PARTIAL = "partial"
    NEEDS_CLARIFICATION = "needs_clarification"


class ActionOutcome(StrEnum):
    """Describe the operational outcome of an executable action.

    Attributes:
        SUCCEEDED: The action completed as requested.
        FAILED: The action encountered an execution failure.
        REJECTED: Validation or policy intentionally blocked the action.
        INCONCLUSIVE: The action completed but did not resolve its purpose.
    """

    SUCCEEDED = "succeeded"
    FAILED = "failed"
    REJECTED = "rejected"
    INCONCLUSIVE = "inconclusive"


class ErrorCategory(StrEnum):
    """Classify errors retained in initialization or iteration history.

    Attributes:
        LLM_VALIDATION: Model output failed structured validation or repair.
        LLM_PROVIDER: The configured model provider returned an operational
            error.
        TOOL_VALIDATION: A selected tool or its arguments failed validation.
        TOOL_EXECUTION: A validated tool call failed while running.
        MCP_CONNECTION: Communication with the MCP service failed.
        QUERY_REJECTED: A graph query was rejected by safety controls.
        WORKFLOW_LIMIT: Execution stopped because a configured limit applied.
        INTERNAL: An uncategorized application failure occurred.
    """

    LLM_VALIDATION = "llm_validation"
    LLM_PROVIDER = "llm_provider"
    TOOL_VALIDATION = "tool_validation"
    TOOL_EXECUTION = "tool_execution"
    MCP_CONNECTION = "mcp_connection"
    QUERY_REJECTED = "query_rejected"
    WORKFLOW_LIMIT = "workflow_limit"
    INTERNAL = "internal"


class ReasoningImpact(StrEnum):
    """Describe how an unresolved reasoning issue affects answer completion.

    Attributes:
        BLOCKING: A complete answer is not justified until the issue is resolved.
        MATERIAL: The issue materially affects interpretation but may permit a
            partial answer.
        SUPPORTING: Resolving the issue would improve the answer but is not
            required for completion.
        MINOR: The issue has little effect on the resulting answer.
    """

    BLOCKING = "blocking"
    MATERIAL = "material"
    SUPPORTING = "supporting"
    MINOR = "minor"


class SupportStrength(StrEnum):
    """Describe the qualitative strength of evidence supporting a finding.

    Attributes:
        DIRECT: The finding is explicitly present in the cited evidence.
        STRONG: The finding follows with little interpretive uncertainty.
        MODERATE: The finding is supported but requires meaningful inference.
        TENTATIVE: The finding is plausible but remains weakly supported.
    """

    DIRECT = "direct"
    STRONG = "strong"
    MODERATE = "moderate"
    TENTATIVE = "tentative"


class PlanStepStatus(StrEnum):
    """Describe the current progress of one plan step.

    Attributes:
        PENDING: Work on the step has not started.
        IN_PROGRESS: The step is actively being investigated.
        COMPLETE: The step's completion criteria are satisfied.
        BLOCKED: The step cannot currently advance because of an unresolved
            blocking item or an incomplete dependency.
        SKIPPED: The step was intentionally omitted after plan evaluation.
    """

    PENDING = "pending"
    IN_PROGRESS = "in_progress"
    COMPLETE = "complete"
    BLOCKED = "blocked"
    SKIPPED = "skipped"


# =============================================================================
# SHARED CONTRACT BEHAVIOR
#
# Pydantic contract objects are strict and frozen after validation. Workflow
# state may still carry mutable runtime containers, but retained model snapshots
# are replaced with newly validated instances rather than mutated in place.
# Unknown fields are rejected so malformed provider output cannot silently expand
# the workflow state.
# =============================================================================


class ContractModel(BaseModel):
    """Base class for strict, frozen workflow contracts.

    Attributes:
        model_config: Shared Pydantic configuration that rejects unknown fields,
            freezes validated instances, and validates default values.
    """

    model_config = ConfigDict(
        extra="forbid",
        frozen=True,
        validate_default=True,
    )
