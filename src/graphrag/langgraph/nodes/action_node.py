"""
Selects the iteration's action using the fully evaluated and updated working
context. The action may use only evidence that has already been incorporated
into the working context.
"""

from copy import deepcopy

from graphrag.langgraph.contracts import ActionDecision
from graphrag.langgraph.node_runner import GraphRagNodeRunner
from graphrag.langgraph.prompts import state_prompt
from graphrag.model.action import FinalizeAction, RequestClarificationAction
from graphrag.model.base import Answerability, PlanStepStatus, WorkflowStatus
from graphrag.model.rag_state import GraphRagState


async def determine_action(
    state: GraphRagState,
    *,
    node_runner: GraphRagNodeRunner,
) -> dict[str, object]:
    """Select a graph tool after evaluation has decided work should continue."""

    builder = state.current_iteration
    evaluation = state.latest_evaluation
    if builder is None or evaluation is None or state.graph_context is None:
        raise ValueError("action selection requires an applied evaluation")
    if evaluation.failure is not None or evaluation.answerability != Answerability.NOT_READY:
        raise ValueError("tool selection requires a non-failing NOT_READY evaluation")
    decision = await node_runner.invoke_structured(
        messages=state_prompt(
            state,
            "The evaluation has decided the workflow should continue. Choose exactly "
            "one catalogued graph tool call that best advances the iteration purpose.",
        ),
        response_model=ActionDecision,
    )
    action = decision.action
    available = {
        (tool.reference.namespace, tool.reference.name)
        for tool in state.graph_context.available_tools
    }
    selected = (action.request.tool.namespace, action.request.tool.name)
    if selected not in available:
        raise ValueError(f"selected tool is not in the graph context: {selected!r}")

    updated_builder = deepcopy(builder).set_action(action)
    return {"current_iteration": updated_builder}


async def record_evaluation_outcome(state: GraphRagState) -> dict[str, object]:
    """Turn the evaluator's terminal or clarification decision into an action record."""

    builder = state.current_iteration
    evaluation = state.latest_evaluation
    if builder is None or evaluation is None or state.plan is None:
        raise ValueError("recording an evaluation outcome requires an applied evaluation")

    evidence_ids = [record.id for record in evaluation.evidence_records]
    if evaluation.failure is not None:
        action = FinalizeAction(
            rationale=evaluation.failure.rationale,
            evidence_record_ids=evidence_ids,
            status=WorkflowStatus.FAILED,
        )
    elif evaluation.answerability == Answerability.NEEDS_CLARIFICATION:
        action = RequestClarificationAction(
            rationale=evaluation.rationale,
            evidence_record_ids=evidence_ids,
            question=evaluation.iteration_purpose,
        )
    elif evaluation.answerability in {Answerability.COMPLETE, Answerability.PARTIAL}:
        status = {
            Answerability.COMPLETE: WorkflowStatus.COMPLETE,
            Answerability.PARTIAL: WorkflowStatus.PARTIAL,
        }[evaluation.answerability]
        if status == WorkflowStatus.COMPLETE and any(
            step.required and step.status != PlanStepStatus.COMPLETE
            for step in state.plan.steps
        ):
            raise ValueError("complete finalization requires every required plan step")
        action = FinalizeAction(
            rationale=evaluation.rationale,
            evidence_record_ids=evidence_ids,
            status=status,
        )
    else:
        raise ValueError("NOT_READY evaluation must continue through tool selection")

    return {"current_iteration": deepcopy(builder).set_action(action)}
