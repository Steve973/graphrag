"""Exercise the production question-semantics client through native Bedrock calls."""

import asyncio
from unittest.mock import Mock

from graphrag.experiments.qdmr import decompose
from graphrag.experiments.qdmr.cli_backend import CliClient, LlmSettings
from graphrag.llm.structured_output import LangChainStructuredOutput
from tests.llm.test_client import MODEL, RuntimeStub
from tests.llm.test_structured_output import tool_response


def test_real_cli_client_through_structured_output(
    monkeypatch, semantic_payload, semantic_question
):
    runtime = RuntimeStub(tool_response(semantic_payload))
    monkeypatch.setattr(
        "langchain_aws.chat_models.bedrock_converse.create_aws_client",
        lambda **kwargs: (
            runtime if kwargs["service_name"] == "bedrock-runtime" else Mock()
        ),
    )
    configuration = LlmSettings(
        _env_file=None, _secrets_dir=(), llm_model=MODEL, llm_region="us-east-1"
    )
    result = asyncio.run(
        decompose(
            semantic_question,
            backend=LangChainStructuredOutput(CliClient(configuration)),
            backend_name=configuration.model_name,
        )
    )
    assert result.decomposition.concepts[0].expression == "experts"
    (request,) = runtime.requests
    assert request["modelId"] == MODEL
    assert request["messages"][0]["content"][0]["text"] == semantic_question
    assert request[
        "system"
    ]  # The prompt's system message is native Bedrock system content.
    assert request["toolConfig"]["toolChoice"] == {
        "tool": {"name": "return_structured_output"}
    }
    assert (
        request["toolConfig"]["tools"][0]["toolSpec"]["inputSchema"]["json"][
            "additionalProperties"
        ]
        is False
    )
