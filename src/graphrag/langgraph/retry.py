"""LangGraph node retry and terminal error handling."""

from copy import deepcopy

import httpx
from botocore.exceptions import (
    ClientError,
    ConnectionClosedError,
    ConnectTimeoutError,
    EndpointConnectionError,
    ReadTimeoutError,
)
from langgraph.errors import NodeError
from langgraph.graph import END
from langgraph.types import Command, RetryPolicy

from graphrag.llm.structured_output import StructuredOutputError
from graphrag.model.base import ErrorCategory, WorkflowStatus
from graphrag.model.question import FinalAnswer
from graphrag.model.rag_state import GraphRagState
from graphrag.model.workflow import WorkflowError

TRANSIENT_PROVIDER_ERRORS = (
    ConnectionClosedError,
    ConnectTimeoutError,
    EndpointConnectionError,
    ReadTimeoutError,
    ConnectionError,
    TimeoutError,
)


def _retry_inference_error(error: BaseException) -> bool:
    """Classify AWS transport, throttling and server errors without retrying auth failures."""

    if isinstance(error, TRANSIENT_PROVIDER_ERRORS):
        return True
    if isinstance(error, ClientError):
        details = error.response
        code = details.get("Error", {}).get("Code")
        status = details.get("ResponseMetadata", {}).get("HTTPStatusCode", 0)
        return (
            status == 429
            or status >= 500
            or code
            in {
                "ThrottlingException",
                "TooManyRequestsException",
                "ModelNotReadyException",
                "ModelTimeoutException",
                "InternalServerException",
                "ServiceUnavailableException",
            }
        )
    return False


def inference_retry_policies(
    *,
    max_attempts: int,
    initial_interval: float,
    backoff_factor: float,
    max_interval: float,
) -> tuple[RetryPolicy, ...]:
    """Create policies for transient provider and malformed model responses."""

    common = {
        "initial_interval": initial_interval,
        "backoff_factor": backoff_factor,
        "max_interval": max_interval,
        "jitter": True,
    }
    return (
        RetryPolicy(
            max_attempts=max_attempts,
            retry_on=_retry_inference_error,
            **common,
        ),
        RetryPolicy(
            max_attempts=min(max_attempts, 2),
            retry_on=StructuredOutputError,
            **common,
        ),
    )


def provider_retry_policy(
    *,
    max_attempts: int,
    initial_interval: float,
    backoff_factor: float,
    max_interval: float,
) -> RetryPolicy:
    """Create a policy for idempotent graph-provider reads."""

    return RetryPolicy(
        initial_interval=initial_interval,
        backoff_factor=backoff_factor,
        max_interval=max_interval,
        max_attempts=max_attempts,
        jitter=True,
        retry_on=_retry_graph_provider_error,
    )


def _retry_graph_provider_error(error: Exception) -> bool:
    """Retry only transport, timeout, throttling, and server-side failures."""

    if isinstance(
        error,
        (ConnectionError, TimeoutError, httpx.NetworkError, httpx.TimeoutException),
    ):
        return True
    if isinstance(error, httpx.HTTPStatusError):
        return error.response.status_code == 429 or error.response.status_code >= 500
    return False


async def fail_workflow(state: GraphRagState, error: NodeError) -> Command:
    """Convert an exhausted or non-retryable node exception into terminal state."""

    failure = WorkflowError(
        category=_error_category(error.node, error.error),
        message=f"Node {error.node!r} failed: {error.error}",
        recoverable=False,
        details={"node": error.node, "exception": type(error.error).__name__},
    )
    update: dict[str, object] = {
        "errors": [failure],
        "status": WorkflowStatus.FAILED,
        "final_answer": FinalAnswer(
            workflow_id=state.workflow_id,
            status=WorkflowStatus.FAILED,
            answer="The workflow stopped because an internal operation failed.",
            confidence=0.0,
        ),
    }
    if state.current_iteration is not None:
        builder = deepcopy(state.current_iteration)
        builder.add_error(failure)
        update["current_iteration"] = builder
    return Command(update=update, goto=END)


def _error_category(node: str, error: BaseException) -> ErrorCategory:
    """Map an exhausted node exception to its audit category."""

    if isinstance(error, StructuredOutputError):
        return ErrorCategory.LLM_VALIDATION
    if isinstance(error, (*TRANSIENT_PROVIDER_ERRORS, ClientError)):
        return (
            ErrorCategory.MCP_CONNECTION
            if node in {"initialize", "execute"}
            else ErrorCategory.LLM_PROVIDER
        )
    if isinstance(error, ValueError):
        return (
            ErrorCategory.TOOL_VALIDATION
            if node in {"determine_action", "execute"}
            else ErrorCategory.INTERNAL
        )
    return ErrorCategory.INTERNAL
