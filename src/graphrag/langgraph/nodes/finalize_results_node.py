"""
Adds the current iteration's raw tool results and derived evidence records to
the iteration record builder.

This node does not add the new evidence to the cumulative working context. The
next iteration's evaluation determines whether and how that evidence is
incorporated.
"""

from copy import deepcopy

from graphrag.model.rag_state import GraphRagState
from graphrag.model.tool_operations import ToolResultStatus


async def finalize_results(state: GraphRagState) -> dict[str, object]:
    """Attach pending evidence summaries to the active iteration builder."""

    builder = state.current_iteration
    if builder is None or not builder.tool_results:
        raise ValueError("result finalization requires an executed tool action")
    summaries = state.pending_evidence_summaries
    if builder.tool_results[-1].status == ToolResultStatus.SUCCESS and not summaries:
        raise ValueError("successful tool calls require summarized evidence")
    updated_builder = deepcopy(builder)
    for summary in summaries:
        updated_builder.add_evidence_record(summary)
    return {
        "current_iteration": updated_builder,
        "pending_evidence_summaries": [],
        "current_evidence_data": None,
    }
