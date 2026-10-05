"""Verify native AWS failures retain workflow retry and audit behavior."""

import asyncio

import pytest
from botocore.exceptions import ClientError, EndpointConnectionError

from graphrag.langgraph.graph import build_graph_rag_graph
from graphrag.langgraph.retry import inference_retry_policies
from graphrag.model.base import ErrorCategory, WorkflowStatus
from graphrag.model.question import Question
from graphrag.model.rag_state import GraphRagState, create_initial_state
from tests.langgraph.test_graph import FakeProvider, WorkflowRunner, settings


def aws_error(code: str, status: int) -> ClientError:
    return ClientError(
        {
            "Error": {"Code": code, "Message": "test failure"},
            "ResponseMetadata": {"HTTPStatusCode": status},
        },
        "Converse",
    )


@pytest.mark.parametrize(
    "error, expected",
    [
        (EndpointConnectionError(endpoint_url="https://bedrock.example.test"), True),
        (aws_error("ThrottlingException", 429), True),
        (aws_error("ModelNotReadyException", 424), True),
        (aws_error("ModelTimeoutException", 408), True),
        (aws_error("ServiceUnavailableException", 503), True),
        (aws_error("AccessDeniedException", 403), False),
        (aws_error("ValidationException", 400), False),
        (ValueError("unsupported forced tool choice"), False),
    ],
)
def test_inference_policy_retries_only_transient_aws_failures(error, expected):
    policy, _ = inference_retry_policies(
        max_attempts=2,
        initial_interval=0.001,
        backoff_factor=2,
        max_interval=0.001,
    )
    assert callable(policy.retry_on)
    assert policy.retry_on(error) is expected


@pytest.mark.parametrize(
    "code, status, attempts",
    [
        ("ThrottlingException", 429, 2),
        ("AccessDeniedException", 403, 1),
    ],
)
def test_aws_failure_terminates_workflow_with_provider_audit(code, status, attempts):
    class FailingRunner(WorkflowRunner):
        def __init__(self):
            super().__init__()
            self.attempts = 0

        async def invoke_structured(self, messages, response_model):
            self.attempts += 1
            raise aws_error(code, status)

    runner = FailingRunner()
    graph = build_graph_rag_graph(settings(), FakeProvider(), node_runner=runner)
    result = GraphRagState.model_validate(
        asyncio.run(
            graph.ainvoke(create_initial_state(Question(text="Who?"))),
        )
    )
    assert runner.attempts == attempts
    assert result.status == WorkflowStatus.FAILED
    assert len(result.errors) == 1
    assert result.errors[0].category == ErrorCategory.LLM_PROVIDER
    assert result.errors[0].details["exception"] == "ClientError"
