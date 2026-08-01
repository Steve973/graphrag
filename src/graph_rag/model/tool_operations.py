from __future__ import annotations

from datetime import datetime
from enum import StrEnum
from typing import Annotated

from pydantic import (
    Field,
    JsonValue,
    BeforeValidator,
    model_validator
)

from graph_rag.model.base import (
    ContractModel,
    NonEmptyStr
)
from graph_rag.utils import (
    scalar_to_list,
    new_id,
    utc_now
)


# =============================================================================
# TOOL CATALOG
#
# AvailableTool is the single catalog entry presented to the planner. Category,
# guidance, and constraints live on the same object as the callable tool schema,
# so additional tool types do not require parallel capability lists.
# ToolCallRequest records exactly what the workflow asked to execute and why.
# ToolCallResult retains the complete raw return and references the request by ID.
# =============================================================================


class ToolResultStatus(StrEnum):
    """Describe the execution status of a retained tool call.

    Attributes:
        SUCCESS: The tool completed without an execution error.
        ERROR: The tool invocation failed during execution.
        REJECTED: Validation or policy blocked the invocation.
    """

    SUCCESS = "success"
    ERROR = "error"
    REJECTED = "rejected"


class ToolReference(ContractModel):
    """Identify a tool independently of provider-specific tool classes.

    Attributes:
        name: Tool name exposed to the workflow.
        namespace: Optional namespace used to disambiguate equal names across
            MCP servers or tool groups.
    """

    name: NonEmptyStr = Field(
        description=(
            "Exact tool name copied from GraphContext.available_tools. Never invent, "
            "rename, normalize, or approximate a tool name."
        ),
    )
    namespace: NonEmptyStr | None = Field(
        default=None,
        description=(
            "Exact optional namespace copied from the selected available-tool entry. Use "
            "null when that entry has no namespace; do not infer one."
        ),
    )


class AvailableTool(ContractModel):
    """Describe one callable tool available to the workflow.

    Attributes:
        reference: Stable identity used in tool-call requests.
        category: Optional open-ended grouping used for filtering or prompt
            assembly.
        description: Human-readable explanation of the tool's behavior.
        input_schema: JSON schema describing accepted arguments.
        capability_catalog: Optional compact catalog of choices exposed through
            this callable tool, such as supported GDS procedures.
        capability_source_result_ids: Retained tool-result IDs used to build
            the capability catalog.
        usage_guidance: Guidance for deciding when the tool is appropriate.
        constraints: Known restrictions, safety rules, or limitations.
    """

    reference: ToolReference = Field(
        description=(
            "Stable callable identity for this tool. Requests must copy this exact "
            "reference so execution can resolve the catalog entry unambiguously."
        ),
    )
    category: NonEmptyStr | None = Field(
        default=None,
        description=(
            "Optional open-ended category used only to filter or group tools for prompt "
            "assembly. It does not replace the exact tool reference."
        ),
    )
    description: NonEmptyStr = Field(
        description=(
            "Authoritative explanation of what the tool does and what its result "
            "represents. Use this when deciding whether the tool can advance the plan."
        ),
    )
    input_schema: dict[str, JsonValue] = Field(
        default_factory=dict,
        description=(
            "Exact JSON Schema for accepted tool arguments. Any ToolCallRequest.arguments "
            "must conform to this schema and contain only supported fields and values."
        ),
    )
    capability_catalog: NonEmptyStr | None = Field(
        default=None,
        description=(
            "Optional compact prompt-friendly catalog of choices exposed through "
            "this callable tool. Use this for tool-specific choices such as "
            "supported GDS procedures, not as a separate GraphContext catalog."
        ),
    )
    capability_source_result_ids: Annotated[
        list[NonEmptyStr],
        BeforeValidator(scalar_to_list),
    ] = Field(
        default_factory=list,
        description=(
            "Retained ToolCallResult IDs used to build capability_catalog. These "
            "may come from initialization-only discovery calls, not from tools "
            "available for iteration action selection. Keep empty when the "
            "available tool has no retrieved capability catalog."
        ),
    )
    usage_guidance: Annotated[
        list[NonEmptyStr],
        BeforeValidator(scalar_to_list),
    ] = Field(
        default_factory=list,
        description=(
            "Specific guidance for situations in which this tool is useful. Apply these "
            "instructions when selecting among available tools."
        ),
    )
    constraints: Annotated[
        list[NonEmptyStr],
        BeforeValidator(scalar_to_list),
    ] = Field(
        default_factory=list,
        description=(
            "Known restrictions, safety rules, unsupported uses, or result limitations. A "
            "proposed invocation must honor every applicable constraint."
        ),
    )


class ToolCallRequest(ContractModel):
    """Represent one exact tool invocation requested by the workflow.

    Attributes:
        id: Stable identifier referenced by the corresponding result.
        tool: Tool selected from the initialized catalog.
        arguments: Exact arguments supplied to the tool.
        rationale: Why this invocation is relevant to the current plan.
        related_plan_step_ids: Plan steps the invocation is intended to advance.
        label: Optional semantic name such as ``schema`` or ``samples`` used to
            identify initialization or investigation results.
        created_at: UTC timestamp at which the request was created.
    """

    id: str = Field(
        default_factory=lambda: new_id("tool_request"),
        description=(
            "Stable identifier for this exact invocation request. It is normally "
            "generated automatically; omit it for a new request. The corresponding "
            "ToolCallResult.request_id must copy this exact ID."
        ),
    )
    tool: ToolReference = Field(
        description=(
            "Exact reference of the selected tool from GraphContext.available_tools. Do "
            "not invent a tool or use a category in place of the reference."
        ),
    )
    arguments: dict[str, JsonValue] = Field(
        default_factory=dict,
        description=(
            "Exact JSON-compatible arguments for the selected tool. They must conform to "
            "that tool’s input_schema, include every required argument, exclude "
            "unsupported arguments, and contain no markdown or explanatory text."
        ),
    )
    rationale: NonEmptyStr = Field(
        description=(
            "Explain why this specific invocation is the best next action and how its "
            "possible result would advance one or more current plan steps. Do not claim "
            "that the tool returned facts before it has executed."
        ),
    )
    related_plan_step_ids: Annotated[
        list[NonEmptyStr],
        BeforeValidator(scalar_to_list),
    ] = Field(
        default_factory=list,
        description=(
            "IDs of existing current-plan steps this invocation is intended to advance. "
            "Copy exact step IDs, include only materially related steps, and do not "
            "invent IDs."
        ),
    )
    label: NonEmptyStr | None = Field(
        default=None,
        description=(
            "Optional short semantic label for the requested result, such as \"schema\", "
            "\"samples\", or a concise investigation purpose. This aids trace inspection "
            "and does not replace the tool name or rationale."
        ),
    )
    created_at: datetime = Field(
        default_factory=utc_now,
        description=(
            "UTC timestamp generated when the request is created. Omit it for a new "
            "request unless the application explicitly supplies the timestamp."
        ),
    )

    @model_validator(mode="after")
    def validate_related_steps(self) -> ToolCallRequest:
        """Reject duplicate related plan-step identifiers."""

        if len(self.related_plan_step_ids) != len(set(self.related_plan_step_ids)):
            raise ValueError("related plan step ids must be unique")
        return self


class ToolCallResult(ContractModel):
    """Retain the complete raw result of one tool invocation.

    Attributes:
        id: Stable result identifier referenced by evidence records.
        request_id: Identifier of the request that produced this result.
        status: Whether execution succeeded, failed, or was rejected.
        data: Complete JSON-compatible data returned by the tool.
        error: Error explanation when execution did not succeed.
        started_at: UTC timestamp at which execution began.
        completed_at: UTC timestamp at which execution ended.
    """

    id: str = Field(
        default_factory=lambda: new_id("tool_result"),
        description=(
            "Stable identifier for this retained raw result. It is generated by the "
            "application and is the value EvidenceRecord.evidence_data_ids must cite."
        ),
    )
    request_id: NonEmptyStr = Field(
        description=(
            "Exact ToolCallRequest.id that produced this result. Copy the request ID; "
            "never use an action ID, evidence ID, tool name, or newly invented value."
        ),
    )
    status: ToolResultStatus = Field(
        description=(
            "Actual execution status reported by the tool boundary. Derive it from what "
            "happened during execution, not from whether the returned data was useful."
        ),
    )
    data: JsonValue | None = Field(
        default=None,
        description=(
            "Complete unmodified JSON-compatible payload returned by the tool. Preserve "
            "the raw shape and values exactly; do not summarize, reinterpret, redact, or "
            "wrap the result in prose here."
        ),
    )
    error: NonEmptyStr | None = Field(
        default=None,
        description=(
            "Execution or rejection message when status is ERROR or REJECTED. Use null "
            "for SUCCESS. Preserve useful diagnostic detail without fabricating causes."
        ),
    )
    started_at: datetime = Field(
        description=(
            "Actual UTC timestamp at which tool execution began, supplied by the "
            "execution layer rather than inferred by the reasoning model."
        ),
    )
    completed_at: datetime = Field(
        description=(
            "Actual UTC timestamp at which tool execution ended. It must not precede "
            "started_at and is supplied by the execution layer."
        ),
    )

    @model_validator(mode="after")
    def validate_execution_result(self) -> ToolCallResult:
        """Validate timestamps and status-specific result fields."""

        if self.completed_at < self.started_at:
            raise ValueError("completed_at cannot precede started_at")
        if self.status == ToolResultStatus.SUCCESS and self.error is not None:
            raise ValueError("successful tool results cannot contain an error")
        if self.status != ToolResultStatus.SUCCESS and self.error is None:
            raise ValueError("unsuccessful tool results require an error")
        return self
