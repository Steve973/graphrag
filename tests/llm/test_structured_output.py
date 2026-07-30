from __future__ import annotations

import asyncio
from typing import Any

import pytest
from litellm.types.utils import ModelResponse
from pydantic import Field, SecretStr

from graph_rag.config.graph_rag_config import GraphDataProfile, GraphRagSettings
from graph_rag.llm.client import LiteLlmClient
from graph_rag.llm.structured_output import (
    LiteLlmStructuredOutput,
    StructuredOutputError,
)
from graph_rag.model.base import ContractModel


class ExampleResponse(ContractModel):
    answer: str
    confidence: float = Field(ge=0.0, le=1.0)


def settings() -> GraphRagSettings:
    return GraphRagSettings(
        data_profile=GraphDataProfile(version="1"),
        llm_url="https://llm.example.test/v1",
        llm_api_key=SecretStr("secret"),
        llm_model="test-model",
        llm_provider="test-provider",
        graph_db_mcp_url="https://graph.example.test/mcp",
        graph_db_username="neo4j",
        graph_db_password=SecretStr("secret"),
        graph_db_database="neo4j",
    )


def tool_response(
    arguments: str | dict[str, Any],
    *,
    name: str = "return_structured_output",
) -> ModelResponse:
    return ModelResponse(
        **{
            "choices": [
                {
                    "message": {
                        "tool_calls": [
                            {
                                "type": "function",
                                "function": {
                                    "name": name,
                                    "arguments": arguments,
                                },
                            }
                        ]
                    }
                }
            ]
        }
    )


def test_forces_one_schema_tool_and_validates_its_arguments() -> None:
    request: dict[str, Any] = {}

    async def completion(**kwargs: Any) -> ModelResponse:
        request.update(kwargs)
        return tool_response('{"answer": "yes", "confidence": 0.9}')

    client = LiteLlmStructuredOutput(
        LiteLlmClient(settings(), completion=completion),
    )

    result = asyncio.run(
        client.complete(
            messages=[{"role": "user", "content": "Is it supported?"}],
            response_model=ExampleResponse,
        )
    )

    assert result == ExampleResponse(answer="yes", confidence=0.9)
    assert request["tool_choice"] == {
        "type": "function",
        "function": {"name": "return_structured_output"},
    }
    assert request["parallel_tool_calls"] is False
    assert len(request["tools"]) == 1
    function = request["tools"][0]["function"]
    assert function["name"] == "return_structured_output"
    assert function["parameters"] == ExampleResponse.model_json_schema()


def test_rejects_plain_text_when_provider_ignores_forced_tool() -> None:
    async def completion(**kwargs: Any) -> ModelResponse:
        return ModelResponse(
            choices=[{"message": {"content": '{"answer": "yes"}'}}],
        )

    client = LiteLlmStructuredOutput(
        LiteLlmClient(settings(), completion=completion),
    )

    with pytest.raises(StructuredOutputError, match="ignored the forced tool call"):
        asyncio.run(client.complete(messages=[], response_model=ExampleResponse))


def test_rejects_wrong_tool_name() -> None:
    async def completion(**kwargs: Any) -> ModelResponse:
        return tool_response(
            {"answer": "yes", "confidence": 0.9},
            name="some_other_tool",
        )

    client = LiteLlmStructuredOutput(
        LiteLlmClient(settings(), completion=completion),
    )

    with pytest.raises(StructuredOutputError, match="some_other_tool"):
        asyncio.run(client.complete(messages=[], response_model=ExampleResponse))


def test_rejects_schema_invalid_tool_arguments() -> None:
    async def completion(**kwargs: Any) -> ModelResponse:
        return tool_response('{"answer": "yes", "confidence": 4}')

    client = LiteLlmStructuredOutput(
        LiteLlmClient(settings(), completion=completion),
    )

    with pytest.raises(StructuredOutputError, match="failed validation"):
        asyncio.run(client.complete(messages=[], response_model=ExampleResponse))
