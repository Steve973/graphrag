"""Provider-neutral structured LLM output through a forced tool call."""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from typing import Any, TypeVar

from pydantic import BaseModel, ValidationError

from graph_rag.llm.client import LiteLlmClient


StructuredModel = TypeVar("StructuredModel", bound=BaseModel)

_OUTPUT_TOOL_NAME = "return_structured_output"


class StructuredOutputError(ValueError):
    """Raised when an LLM does not return one valid forced output tool call."""


class LiteLlmStructuredOutput:
    """Request and validate structured output across LiteLLM providers.

    The response schema is exposed as the arguments of a single synthetic
    function tool. Selecting that function explicitly is stronger than asking
    for JSON in prompt text and works across providers that implement tool
    calling through LiteLLM's OpenAI-compatible interface.
    """

    def __init__(
        self,
        client: LiteLlmClient,
    ) -> None:
        self._client = client

    async def complete(
        self,
        *,
        messages: Sequence[Mapping[str, Any]],
        response_model: type[StructuredModel],
    ) -> StructuredModel:
        """Return one response validated against ``response_model``.

        Args:
            messages: OpenAI-compatible chat messages.
            response_model: Pydantic model defining the required response.

        Raises:
            StructuredOutputError: If the provider does not make exactly one
                matching tool call or its arguments fail model validation.
            Exception: Provider and transport exceptions from LiteLLM are
                intentionally allowed to propagate for separate classification.
        """

        response = await self._client.complete(
            messages=list(messages),
            tools=[self._output_tool(response_model)],
            tool_choice={
                "type": "function",
                "function": {"name": _OUTPUT_TOOL_NAME},
            },
            parallel_tool_calls=False,
        )

        arguments = self._extract_arguments(response)
        try:
            if isinstance(arguments, str):
                return response_model.model_validate_json(arguments)
            return response_model.model_validate(arguments)
        except ValidationError as error:
            raise StructuredOutputError(
                f"{response_model.__name__} tool arguments failed validation: {error}"
            ) from error

    @staticmethod
    def _output_tool(response_model: type[BaseModel]) -> dict[str, Any]:
        return {
            "type": "function",
            "function": {
                "name": _OUTPUT_TOOL_NAME,
                "description": (
                    "Return the complete response. You must call this function "
                    "exactly once and provide every required field."
                ),
                "parameters": response_model.model_json_schema(),
            },
        }

    @staticmethod
    def _extract_arguments(response: Any) -> str | Mapping[str, Any]:
        choices = _field(response, "choices")
        if not isinstance(choices, Sequence) or isinstance(choices, (str, bytes)):
            raise StructuredOutputError("provider response has no choices")
        if len(choices) != 1:
            raise StructuredOutputError(
                f"provider returned {len(choices)} choices; expected exactly one"
            )

        message = _field(choices[0], "message")
        tool_calls = _field(message, "tool_calls")
        if not isinstance(tool_calls, Sequence) or isinstance(
            tool_calls,
            (str, bytes),
        ):
            raise StructuredOutputError(
                "provider ignored the forced tool call and returned no tool call"
            )
        if len(tool_calls) != 1:
            raise StructuredOutputError(
                f"provider returned {len(tool_calls)} tool calls; expected exactly one"
            )

        function = _field(tool_calls[0], "function")
        name = _field(function, "name")
        if name != _OUTPUT_TOOL_NAME:
            raise StructuredOutputError(
                f"provider called {name!r}; expected {_OUTPUT_TOOL_NAME!r}"
            )

        arguments = _field(function, "arguments")
        if not isinstance(arguments, (str, Mapping)):
            raise StructuredOutputError(
                "forced output tool arguments must be a JSON string or object"
            )
        return arguments


def _field(value: Any, name: str) -> Any:
    """Read one field from either LiteLLM objects or mapping-based test doubles."""

    if isinstance(value, Mapping):
        return value.get(name)
    return getattr(value, name, None)
