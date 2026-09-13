"""Evaluate whether the current investigation plan needs revision."""

from graph_rag.langgraph.node_runner import GraphRagNodeRunner
from graph_rag.langgraph.prompts import state_prompt
from graph_rag.model.plan import PlanUpdate
from graph_rag.model.rag_state import GraphRagState


async def evaluate_plan(
    state: GraphRagState,
    *,
    node_runner: GraphRagNodeRunner,
) -> dict[str, PlanUpdate]:
    """Ask the model for an ordered, contract-valid plan change set."""

    if state.plan is None or state.current_iteration is None:
        raise ValueError("plan evaluation requires a plan and active iteration")
    update = await node_runner.invoke_structured(
        messages=state_prompt(
            state,
            "Review the current plan using the latest completed iteration and accepted "
            "evidence. Return only necessary plan changes; return an empty change list "
            "when the plan remains appropriate.",
        ),
        response_model=PlanUpdate,
    )
    return {"pending_plan_update": update}
