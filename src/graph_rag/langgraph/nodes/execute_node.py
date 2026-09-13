"""
Executes the selected action and adds the action and its execution result to
the current iteration record builder. Raw tool results are retained for later
summarization when the action invokes a tool.
"""

from copy import deepcopy

from graph_rag.graph_store.provider import GraphProvider
from graph_rag.model.action import CallToolAction, CallToolActionResult
from graph_rag.model.base import ActionOutcome, ErrorCategory
from graph_rag.model.rag_state import GraphRagState
from graph_rag.model.supporting_data import EvidenceData
from graph_rag.model.tool_operations import ToolResultStatus
from graph_rag.model.workflow import WorkflowError


async def execute_action(
    state: GraphRagState,
    provider: GraphProvider,
) -> dict[str, object]:
    """Execute a validated graph tool request and retain its raw result."""

    builder = state.current_iteration
    if builder is None or not isinstance(builder.action, CallToolAction):
        raise ValueError("execute_action requires a call-tool action")

    result = await provider.execute_graph_operation(builder.action.request)
    if result.request_id != builder.action.request.id:
        raise ValueError("tool result does not reference the selected request")
    outcome = {
        ToolResultStatus.SUCCESS: ActionOutcome.SUCCEEDED,
        ToolResultStatus.ERROR: ActionOutcome.FAILED,
        ToolResultStatus.REJECTED: ActionOutcome.REJECTED,
    }[result.status]
    action_result = CallToolActionResult(
        action_id=builder.action.id,
        outcome=outcome,
        error=result.error,
        tool_result_id=result.id,
    )
    updated_builder = deepcopy(builder)
    updated_builder.add_tool_result(result).set_action_result(action_result)
    update: dict[str, object] = {"current_iteration": updated_builder}
    if result.status == ToolResultStatus.SUCCESS:
        evidence = EvidenceData(tool_call_result_id=result.id, data=result.data)
        update["evidence_data"] = [*state.evidence_data, evidence]
        update["current_evidence_data"] = evidence
    else:
        updated_builder.add_error(
            WorkflowError(
                category=(
                    ErrorCategory.QUERY_REJECTED
                    if result.status == ToolResultStatus.REJECTED
                    else ErrorCategory.TOOL_EXECUTION
                ),
                message=result.error or "Graph tool operation failed",
                recoverable=result.status == ToolResultStatus.ERROR,
                details={"tool_result_id": result.id},
            )
        )
    return update
