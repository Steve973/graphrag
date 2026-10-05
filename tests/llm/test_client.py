"""Exercise the native LangChain Bedrock transport with only AWS calls stubbed."""

import asyncio
from copy import deepcopy
from types import SimpleNamespace
from unittest.mock import Mock

import pytest
from langchain_aws import ChatBedrockConverse
from pydantic import SecretStr

from graphrag.config.graph_rag_config import GraphDataProfile, GraphRagSettings
from graphrag.llm.client import LangChainClient, create_chat_model
from graphrag.llm.structured_output import StructuredOutputError

MODEL = "anthropic.claude-sonnet-4-20250514-v1:0"


def settings(**overrides) -> GraphRagSettings:
    values = {
        "data_profile": GraphDataProfile(version="1"),
        "llm_model": MODEL,
        "llm_region": "us-east-1",
        "graph_db_mcp_url": "https://graph.example.test/mcp",
        "graph_db_username": "neo4j",
        "graph_db_password": SecretStr("secret"),
        "graph_db_database": "neo4j",
    }
    values.update(overrides)
    return GraphRagSettings(_env_file=None, **values)


def bedrock_response(content=None):
    return {
        "output": {
            "message": {"role": "assistant", "content": content or [{"text": "hello"}]}
        },
        "stopReason": "tool_use" if content else "end_turn",
        "usage": {"inputTokens": 1, "outputTokens": 1, "totalTokens": 2},
        "metrics": {"latencyMs": 1},
        "ResponseMetadata": {"RequestId": "test", "HTTPStatusCode": 200},
    }


class RuntimeStub:
    def __init__(self, response):
        self.meta = SimpleNamespace(region_name="us-east-1")
        self.response = response
        self.requests = []

    def converse(self, **kwargs):
        self.requests.append(kwargs)
        return deepcopy(self.response)


def make_client(response=None):
    runtime = RuntimeStub(response or bedrock_response())
    model = ChatBedrockConverse(
        model=MODEL,
        client=runtime,
        bedrock_client=Mock(),
        temperature=0.0,
        max_tokens=4096,
        disable_streaming=True,
    )
    return LangChainClient(settings(), chat_model=model), runtime


def test_native_bedrock_async_completion() -> None:
    client, runtime = make_client()
    result = asyncio.run(
        client.complete(messages=[{"role": "user", "content": "hello"}])
    )
    assert result.content == "hello"
    (request,) = runtime.requests
    assert request["modelId"] == MODEL
    assert request["messages"] == [{"role": "user", "content": [{"text": "hello"}]}]
    assert request["inferenceConfig"] == {"temperature": 0.0, "maxTokens": 4096}
    assert "toolConfig" not in request


def test_bedrock_configuration_preserves_timeouts_retries_and_credential_discovery(
    monkeypatch,
) -> None:
    runtime = RuntimeStub(bedrock_response())
    calls = []

    def create_client(**kwargs):
        calls.append(kwargs)
        return runtime if kwargs["service_name"] == "bedrock-runtime" else Mock()

    monkeypatch.setattr(
        "langchain_aws.chat_models.bedrock_converse.create_aws_client", create_client
    )
    config = settings(
        llm_model="bedrock_converse/" + MODEL, llm_aws_profile="work", llm_num_retries=2
    )
    model = create_chat_model(config)
    assert model.model_id == MODEL
    assert calls[0]["region_name"] == "us-east-1"
    assert calls[0]["credentials_profile_name"] == "work"
    assert calls[0]["api_key"] is None
    assert calls[0]["endpoint_url"] is None
    assert calls[0]["config"].read_timeout == 60.0
    assert calls[0]["config"].retries["total_max_attempts"] == 3


def test_bedrock_optional_endpoint_and_api_key(monkeypatch) -> None:
    calls = []
    runtime = RuntimeStub(bedrock_response())

    def create_client(**kwargs):
        calls.append(kwargs)
        return runtime if kwargs["service_name"] == "bedrock-runtime" else Mock()

    monkeypatch.setattr(
        "langchain_aws.chat_models.bedrock_converse.create_aws_client", create_client
    )
    create_chat_model(
        settings(llm_url="https://bedrock.example.test", llm_api_key="token")
    )
    assert calls[0]["endpoint_url"] == "https://bedrock.example.test/"
    assert calls[0]["api_key"].get_secret_value() == "token"


def test_native_tool_binding_and_no_openai_parallel_parameter() -> None:
    client, runtime = make_client()
    asyncio.run(
        client.complete(
            messages=[{"role": "user", "content": "hello"}],
            tools=[
                {
                    "name": "answer",
                    "description": "Answer",
                    "parameters": {"type": "object", "properties": {}},
                }
            ],
            tool_choice="answer",
            parallel_tool_calls=False,
        )
    )
    (request,) = runtime.requests
    assert request["toolConfig"]["toolChoice"] == {"tool": {"name": "answer"}}
    assert "parallelToolCalls" not in request
    assert "parallel_tool_calls" not in request


def test_multiple_calls_are_rejected_when_parallel_calls_are_disabled() -> None:
    client, _ = make_client(
        bedrock_response(
            [
                {"toolUse": {"toolUseId": "one", "name": "answer", "input": {}}},
                {"toolUse": {"toolUseId": "two", "name": "answer", "input": {}}},
            ]
        )
    )
    with pytest.raises(StructuredOutputError, match="expected at most one"):
        asyncio.run(client.complete(messages=[], parallel_tool_calls=False))


def test_forced_choice_is_not_silently_downgraded() -> None:
    client, runtime = make_client()
    assert isinstance(client.chat_model, ChatBedrockConverse)
    client.chat_model.supports_tool_choice_values = ("auto",)
    with pytest.raises(ValueError, match="does not support tool choice"):
        asyncio.run(client.complete(messages=[], tools=[], tool_choice="answer"))
    assert runtime.requests == []


def test_other_model_providers_require_explicit_injection() -> None:
    with pytest.raises(ValueError, match="inject a configured chat_model"):
        create_chat_model(settings(llm_provider="other"))
