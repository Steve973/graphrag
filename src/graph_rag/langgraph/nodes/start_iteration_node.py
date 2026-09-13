"""
Starts an iteration.

- Increments the iteration number
- Records the iteration start time
- Creates a new empty iteration record builder
"""

from graph_rag.model.base import WorkflowStatus
from graph_rag.model.iteration import IterationRecordBuilder
from graph_rag.model.rag_state import GraphRagState
from graph_rag.utils import utc_now


async def start_iteration(state: GraphRagState) -> dict[str, object]:
    """Create a fresh builder for the next investigation iteration."""

    if state.plan is None or not state.plan.steps:
        raise ValueError("an active iteration requires an actionable plan")
    started_at = utc_now()
    return {
        "current_iteration": IterationRecordBuilder(
            iteration_number=state.iteration_number,
            started_at=started_at,
            plan=state.plan,
        ),
        "iteration_start_time": started_at,
        "iteration_purpose": None,
        "status": WorkflowStatus.RUNNING,
    }
