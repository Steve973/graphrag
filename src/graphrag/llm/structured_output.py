"""Schema-validated output through one forced LangChain tool call."""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from typing import Any, Protocol, TypeVar

from langchain_core.messages import AIMessage, BaseMessage
from langchain_core.tools import BaseTool, StructuredTool
from pydantic import BaseModel, ValidationError

StructuredModel = TypeVar("StructuredModel", bound=BaseModel)
ToolDefinition = BaseTool | dict[str, Any] | type[BaseModel]
_OUTPUT_TOOL_NAME = "return_structured_output"


class StructuredOutputError(ValueError):
    """Raised when an LLM does not return one valid forced output tool call."""


class ChatCompletionClient(Protocol):
    """Native LangChain transport contract used by the structured-output adapter."""

    async def complete(
        self,
        *,
        messages: Sequence[Mapping[str, Any] | BaseMessage],
        tools: Sequence[ToolDefinition] | None = None,
        tool_choice: str | None = None,
        parallel_tool_calls: bool | None = None,
    ) -> AIMessage: ...


class LangChainStructuredOutput:
    """Preserve the workflow's single forced call and Pydantic validation.

    The synthetic StructuredTool specifies the output format. It is not executed;
    its arguments are validated against the caller's existing response model.
    Native model/provider exceptions propagate to the workflow retry policy.
    """

    def __init__(self, client: ChatCompletionClient) -> None:
        self._client = client

    async def complete(
        self,
        *,
        messages: Sequence[Mapping[str, Any] | BaseMessage],
        response_model: type[StructuredModel],
    ) -> StructuredModel:
        response = await self._client.complete(
            messages=list(messages),
            tools=[
                StructuredTool(
                    name=_OUTPUT_TOOL_NAME,
                    description="Return the complete response exactly once with every required field.",
                    # Keep the full schema: class-based tool conversion drops extra="forbid".
                    args_schema=response_model.model_json_schema(),
                )
            ],
            tool_choice=_OUTPUT_TOOL_NAME,
            parallel_tool_calls=False,
        )
        if response.invalid_tool_calls:
            raise StructuredOutputError("Model returned malformed tool arguments")
        if len(response.tool_calls) != 1:
            raise StructuredOutputError(
                f"Model returned {len(response.tool_calls)} tool calls; expected exactly one"
            )
        output_call = response.tool_calls[0]
        if output_call["name"] != _OUTPUT_TOOL_NAME:
            raise StructuredOutputError(
                f"Model called {output_call['name']!r}; expected {_OUTPUT_TOOL_NAME!r}"
            )
        try:
            return response_model.model_validate(output_call["args"])
        except ValidationError as error:
            raise StructuredOutputError(
                f"{response_model.__name__} tool arguments failed validation: {error}"
            ) from error
