"""
Selects the iteration's action using the fully evaluated and updated working
context. The action may use only evidence that has already been incorporated
into the working context.
"""

from copy import deepcopy

from graph_rag.langgraph.contracts import ActionDecision
from graph_rag.langgraph.node_runner import GraphRagNodeRunner
from graph_rag.langgraph.prompts import state_prompt
from graph_rag.model.action import CallToolAction, FinalizeAction
from graph_rag.model.base import Answerability, PlanStepStatus, WorkflowStatus
from graph_rag.model.rag_state import GraphRagState


async def determine_action(
    state: GraphRagState,
    node_runner: GraphRagNodeRunner,
) -> dict[str, object]:
    """Select and validate the single action for the current iteration."""

    builder = state.current_iteration
    evaluation = state.latest_evaluation
    if builder is None or evaluation is None or state.graph_context is None:
        raise ValueError("action selection requires an applied evaluation")
    decision = await node_runner.invoke_structured(
        messages=state_prompt(
            state,
            "Choose exactly one next action. Call one catalogued tool when more "
            "evidence is needed; finalize only when the evaluation supports it; ask "
            "for clarification only for a genuinely blocking ambiguity.",
        ),
        response_model=ActionDecision,
    )
    action = decision.action
    if isinstance(action, CallToolAction):
        available = {
            (tool.reference.namespace, tool.reference.name)
            for tool in state.graph_context.available_tools
        }
        selected = (action.request.tool.namespace, action.request.tool.name)
        if selected not in available:
            raise ValueError(f"selected tool is not in the graph context: {selected!r}")
    if isinstance(action, FinalizeAction):
        expected = {
            Answerability.COMPLETE: WorkflowStatus.COMPLETE,
            Answerability.PARTIAL: WorkflowStatus.PARTIAL,
        }.get(evaluation.answerability)
        if expected is None or action.status != expected:
            raise ValueError("finalize action conflicts with current answerability")
        if action.status == WorkflowStatus.COMPLETE and any(
            step.required and step.status != PlanStepStatus.COMPLETE
            for step in state.plan.steps
        ):
            raise ValueError("complete finalization requires every required plan step")

    updated_builder = deepcopy(builder).set_action(action)
    return {"current_iteration": updated_builder}
