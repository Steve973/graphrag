"""Async LiteLLM client configured for one GraphRAG model deployment."""

from __future__ import annotations

from collections.abc import Awaitable, Callable, Mapping, Sequence
from typing import Any

import litellm
from litellm.types.utils import ModelResponse

from graph_rag.config.graph_rag_config import GraphRagSettings


CompletionCallable = Callable[..., Awaitable[Any]]


class LiteLlmClient:
    """Make non-streaming chat completions through LiteLLM 1.93.

    LiteLLM's provider-prefixed model identifier is assembled once here so all
    callers use the same provider, endpoint, credentials, timeout, retry, and
    sampling configuration. Provider exceptions remain LiteLLM's normalized
    OpenAI-compatible exception types and are intentionally not obscured.
    """

    def __init__(
        self,
        settings: GraphRagSettings,
        *,
        completion: CompletionCallable = litellm.acompletion,
    ) -> None:
        self._settings = settings
        self._completion = completion

    async def complete(
        self,
        *,
        messages: Sequence[Mapping[str, Any]],
        tools: Sequence[Mapping[str, Any]] | None = None,
        tool_choice: str | Mapping[str, Any] | None = None,
        parallel_tool_calls: bool | None = None,
    ) -> ModelResponse:
        """Return one normalized, non-streaming chat completion."""

        request: dict[str, Any] = {
            "model": self._model,
            "messages": [dict(message) for message in messages],
            "base_url": str(self._settings.llm_url),
            "api_key": self._settings.llm_api_key.get_secret_value(),
            "temperature": self._settings.llm_temperature,
            "max_tokens": self._settings.llm_max_tokens,
            "timeout": self._settings.llm_timeout_seconds,
            "num_retries": self._settings.llm_num_retries,
            "stream": False,
            "drop_params": False,
        }
        if tools is not None:
            request["tools"] = list(tools)
        if tool_choice is not None:
            request["tool_choice"] = tool_choice
        if parallel_tool_calls is not None:
            request["parallel_tool_calls"] = parallel_tool_calls

        response = await self._completion(**request)
        if not isinstance(response, ModelResponse):
            raise TypeError(
                "LiteLLM returned an unexpected response type "
                f"{type(response).__name__}; expected ModelResponse"
            )
        return response

    @property
    def _model(self) -> str:
        provider_prefix = f"{self._settings.llm_provider}/"
        if self._settings.llm_model.startswith(provider_prefix):
            return self._settings.llm_model
        return f"{provider_prefix}{self._settings.llm_model}"
