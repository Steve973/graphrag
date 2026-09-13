"""
Creates a plan to answer the question based on the provided graph context.
"""

from graph_rag.langgraph.node_runner import GraphRagNodeRunner
from graph_rag.langgraph.prompts import state_prompt
from graph_rag.model.plan import Plan
from graph_rag.model.rag_state import GraphRagState


async def create_plan(
    state: GraphRagState,
    *,
    node_runner: GraphRagNodeRunner,
) -> dict[str, Plan]:
    """Create the initial actionable investigation plan."""

    if state.graph_context is None:
        raise ValueError("planning requires initialized graph_context")
    plan = await node_runner.invoke_structured(
        messages=state_prompt(
            state,
            "Create the initial investigation plan. Include at least one actionable "
            "step, use only the available graph capabilities, and do not claim facts "
            "that have not been retrieved.",
        ),
        response_model=Plan,
    )
    if not plan.steps:
        raise ValueError("the initial plan must contain at least one step")
    return {"plan": plan}
