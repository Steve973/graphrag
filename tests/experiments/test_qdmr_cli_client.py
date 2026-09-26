"""Exercise the production experiment client, mocking only the remote call."""
import asyncio
import json

import litellm
import pytest
from litellm.types.utils import ModelResponse

from graphrag.experiments.qdmr import decompose
from graphrag.experiments.qdmr.cli_backend import CliClient, LlmSettings
from graphrag.llm.structured_output import ChatCompletionClient, LiteLlmStructuredOutput


def settings():
    return LlmSettings(
        _env_file=None, _secrets_dir=(),
        llm_url="https://example.test/v1", llm_api_key="test-key",
        llm_model="test-model", llm_provider="test-provider",
    )


def test_real_cli_client_through_structured_output(monkeypatch, semantic_payload, semantic_question):
    requests = []

    async def completion(**kwargs):
        requests.append(kwargs)
        return ModelResponse(choices=[{"message": {"role": "assistant", "tool_calls": [{
            "id": "call_1", "type": "function", "function": {
                "name": "return_structured_output",
                "arguments": json.dumps(semantic_payload),
            },
        }]}}])

    monkeypatch.setattr(litellm, "acompletion", completion)
    client: ChatCompletionClient = CliClient(settings())
    result = asyncio.run(decompose(
        semantic_question, backend=LiteLlmStructuredOutput(client),
        backend_name="test-provider/test-model",
    ))
    assert result.decomposition.concepts[0].expression == "experts"
    request, = requests
    assert request["model"] == "test-provider/test-model"
    assert request["base_url"] == "https://example.test/v1"
    assert request["messages"][1]["content"] == semantic_question
    assert request["tool_choice"]["function"]["name"] == "return_structured_output"
    assert request["tools"][0]["function"]["parameters"]["additionalProperties"] is False
    assert request["parallel_tool_calls"] is False
    assert request["stream"] is False


def test_real_cli_client_rejects_wrong_response_type(monkeypatch):
    async def completion(**kwargs):
        return {"choices": []}

    monkeypatch.setattr(litellm, "acompletion", completion)
    with pytest.raises(TypeError, match="expected ModelResponse"):
        asyncio.run(CliClient(settings()).complete(messages=[]))
