"""Protect the existing forced-output contract with native LangChain responses."""

import asyncio

import pytest
from langchain_core.messages import AIMessage
from pydantic import Field

from graphrag.llm.structured_output import (
    LangChainStructuredOutput,
    StructuredOutputError,
)
from graphrag.model.base import ContractModel
from tests.llm.test_client import bedrock_response, make_client


class ExampleResponse(ContractModel):
    answer: str
    confidence: float = Field(ge=0.0, le=1.0)


def tool_response(arguments, *, name="return_structured_output"):
    return bedrock_response(
        [
            {"toolUse": {"toolUseId": "call_1", "name": name, "input": arguments}},
        ]
    )


def test_forces_one_schema_tool_and_validates_its_arguments() -> None:
    client, runtime = make_client(tool_response({"answer": "yes", "confidence": 0.9}))
    result = asyncio.run(
        LangChainStructuredOutput(client).complete(
            messages=[{"role": "user", "content": "Is it supported?"}],
            response_model=ExampleResponse,
        )
    )
    assert result == ExampleResponse(answer="yes", confidence=0.9)
    (request,) = runtime.requests
    assert request["toolConfig"]["toolChoice"] == {
        "tool": {"name": "return_structured_output"}
    }
    tools = request["toolConfig"]["tools"]
    assert len(tools) == 1
    specification = tools[0]["toolSpec"]
    assert specification["name"] == "return_structured_output"
    assert specification["inputSchema"]["json"]["additionalProperties"] is False
    assert (
        specification["inputSchema"]["json"]["properties"]["confidence"]["maximum"]
        == 1.0
    )


@pytest.mark.parametrize(
    "response,match",
    [
        (bedrock_response(), "expected exactly one"),
        (
            tool_response({"answer": "yes", "confidence": 0.9}, name="some_other_tool"),
            "some_other_tool",
        ),
        (tool_response({"answer": "yes", "confidence": 4}), "failed validation"),
        (
            tool_response({"answer": "yes", "confidence": 0.9, "unexpected": "extra"}),
            "failed validation",
        ),
    ],
)
def test_invalid_responses_do_not_become_workflow_results(response, match) -> None:
    client, _ = make_client(response)
    with pytest.raises(StructuredOutputError, match=match):
        asyncio.run(
            LangChainStructuredOutput(client).complete(
                messages=[], response_model=ExampleResponse
            )
        )


def test_invalid_tool_arguments_cannot_be_ignored_alongside_a_valid_call() -> None:
    class Client:
        async def complete(self, **kwargs):
            return AIMessage(
                content="",
                tool_calls=[
                    {
                        "name": "return_structured_output",
                        "args": {"answer": "yes", "confidence": 0.9},
                        "id": "valid",
                    }
                ],
                invalid_tool_calls=[
                    {
                        "name": "return_structured_output",
                        "args": "{invalid",
                        "id": "invalid",
                        "error": "bad JSON",
                        "type": "invalid_tool_call",
                    }
                ],
            )

    with pytest.raises(StructuredOutputError, match="malformed tool arguments"):
        asyncio.run(
            LangChainStructuredOutput(Client()).complete(
                messages=[], response_model=ExampleResponse
            )
        )


def test_multiple_native_tool_calls_are_rejected() -> None:
    class Client:
        async def complete(self, **kwargs):
            return AIMessage(
                content="",
                tool_calls=[
                    {
                        "name": "return_structured_output",
                        "args": {"answer": "yes", "confidence": 0.9},
                        "id": "one",
                    },
                    {
                        "name": "return_structured_output",
                        "args": {"answer": "yes", "confidence": 0.9},
                        "id": "two",
                    },
                ],
            )

    with pytest.raises(StructuredOutputError, match="expected exactly one"):
        asyncio.run(
            LangChainStructuredOutput(Client()).complete(
                messages=[], response_model=ExampleResponse
            )
        )
