from __future__ import annotations

import asyncio
from typing import Any

import pytest
from litellm.types.utils import ModelResponse

from graph_rag.llm.client import LiteLlmClient
from tests.llm.test_structured_output import settings


def response() -> ModelResponse:
    return ModelResponse(
        model="test-model",
        choices=[
            {
                "finish_reason": "stop",
                "index": 0,
                "message": {"role": "assistant", "content": "hello"},
            }
        ],
    )


def test_uses_current_async_completion_parameters() -> None:
    request: dict[str, Any] = {}

    async def completion(**kwargs: Any) -> ModelResponse:
        request.update(kwargs)
        return response()

    client = LiteLlmClient(settings(), completion=completion)
    result = asyncio.run(
        client.complete(messages=[{"role": "user", "content": "hello"}])
    )

    assert result.choices[0].message.content == "hello"
    assert request == {
        "model": "test-provider/test-model",
        "messages": [{"role": "user", "content": "hello"}],
        "base_url": "https://llm.example.test/v1",
        "api_key": "secret",
        "temperature": 0.0,
        "max_tokens": 4096,
        "timeout": 60.0,
        "num_retries": 2,
        "stream": False,
        "drop_params": False,
    }


def test_does_not_duplicate_existing_provider_prefix() -> None:
    request: dict[str, Any] = {}
    configured = settings().model_copy(
        update={"llm_model": "test-provider/test-model"},
    )

    async def completion(**kwargs: Any) -> ModelResponse:
        request.update(kwargs)
        return response()

    client = LiteLlmClient(configured, completion=completion)
    asyncio.run(client.complete(messages=[]))

    assert request["model"] == "test-provider/test-model"


def test_forwards_tools_only_when_supplied() -> None:
    request: dict[str, Any] = {}

    async def completion(**kwargs: Any) -> ModelResponse:
        request.update(kwargs)
        return response()

    client = LiteLlmClient(settings(), completion=completion)
    asyncio.run(
        client.complete(
            messages=[],
            tools=[{"type": "function", "function": {"name": "answer"}}],
            tool_choice="required",
            parallel_tool_calls=False,
        )
    )

    assert request["tools"][0]["function"]["name"] == "answer"
    assert request["tool_choice"] == "required"
    assert request["parallel_tool_calls"] is False


def test_rejects_unexpected_streaming_or_non_normalized_response() -> None:
    async def completion(**kwargs: Any) -> Any:
        return {"choices": []}

    client = LiteLlmClient(settings(), completion=completion)

    with pytest.raises(TypeError, match="expected ModelResponse"):
        asyncio.run(client.complete(messages=[]))
