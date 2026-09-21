"""
Builds and validates the completed iteration record from the current builder,
then appends it to the GraphRAG state's immutable iteration history.
"""

from graphrag.model.rag_state import GraphRagState


async def finalize_iteration(state: GraphRagState) -> dict[str, object]:
    """Commit the active iteration builder to append-only history."""

    if state.current_iteration is None:
        raise ValueError("iteration finalization requires an active builder")
    record = state.current_iteration.build()
    return {
        "iterations": [record],
        "current_iteration": None,
        "iteration_start_time": None,
        "iteration_purpose": None,
    }
