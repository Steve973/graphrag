"""Typed inputs and conversion helpers for Ragas tool-call metrics."""

from __future__ import annotations

from typing import TYPE_CHECKING, Self

from pydantic import Field, JsonValue

from graphrag.model.base import ContractModel, NonEmptyStr

if TYPE_CHECKING:
    from graphrag.model.rag_state import GraphRagState
    from graphrag.model.tool_operations import ToolCallRequest


class ToolCallSpec(ContractModel):
    """One normalized actual or expected GraphRAG tool invocation."""

    name: NonEmptyStr
    arguments: dict[str, JsonValue] = Field(default_factory=dict)

    @classmethod
    def from_request(cls, request: ToolCallRequest) -> Self:
        """Normalize a project ``ToolCallRequest`` for Ragas evaluation."""

        name = (
            f"{request.tool.namespace}.{request.tool.name}"
            if request.tool.namespace
            else request.tool.name
        )
        return cls(name=name, arguments=request.arguments)


class ToolCallEvaluationInputs(ContractModel):
    """Actual and expected calls for deterministic tool-use evaluation."""

    user_input: NonEmptyStr
    actual_tool_calls: list[ToolCallSpec] = Field(default_factory=list)
    reference_tool_calls: list[ToolCallSpec] = Field(default_factory=list)

    @classmethod
    def from_state(
        cls,
        state: GraphRagState,
        *,
        reference_tool_calls: list[ToolCallSpec],
    ) -> Self:
        """Extract actual tool calls directly from completed workflow iterations."""

        from graphrag.model.action import CallToolAction

        actual = [
            ToolCallSpec.from_request(iteration.action.request)
            for iteration in state.iterations
            if isinstance(iteration.action, CallToolAction)
        ]
        return cls(
            user_input=state.question.text,
            actual_tool_calls=actual,
            reference_tool_calls=reference_tool_calls,
        )


def to_ragas_tool_inputs(inputs: ToolCallEvaluationInputs):
    """Convert project-owned contracts at the Ragas boundary."""

    from ragas.messages import AIMessage, HumanMessage, ToolCall

    actual = [
        ToolCall(name=call.name, args=call.arguments)
        for call in inputs.actual_tool_calls
    ]
    expected = [
        ToolCall(name=call.name, args=call.arguments)
        for call in inputs.reference_tool_calls
    ]
    messages = [
        HumanMessage(content=inputs.user_input),
        AIMessage(content="", tool_calls=actual),
    ]
    return messages, expected
