"""
Applies the context evaluation produced at the beginning of the iteration.

Updates the cumulative working context, incorporates accepted evidence from the
immediately preceding iteration, updates plan progress, stores the evaluation
as the working context's latest evaluation, and adds the same evaluation to the
current iteration record builder.
"""

from copy import deepcopy

from graph_rag.model.rag_state import GraphRagState
from graph_rag.model.supporting_data import Contradiction
from graph_rag.model.workflow import WorkflowEvaluation


async def apply_evaluation(state: GraphRagState) -> dict[str, object]:
    """Validate and apply the pending evaluation as one state transition."""

    result = state.pending_evaluation
    builder = state.current_iteration
    if result is None or builder is None or state.plan is None:
        raise ValueError("evaluation application requires pending evaluation and iteration")

    previous = list(state.latest_evaluation.contradictions) if state.latest_evaluation else []
    contradictions = _apply_contradictions(previous, result.contradictions_updates)
    allowed = {
        item.id
        for item in (state.iterations[-1].evidence_records if state.iterations else [])
    }
    supplied = {item.id for item in result.new_evidence_records}
    if not supplied <= allowed:
        raise ValueError(
            "evaluation introduced evidence not present in the preceding iteration: "
            f"{sorted(supplied - allowed)!r}"
        )

    accumulated = [*state.evidence_summaries]
    known = {item.id for item in accumulated}
    accumulated.extend(
        item for item in result.new_evidence_records if item.id not in known
    )
    evaluation = WorkflowEvaluation(
        iteration_number=state.iteration_number,
        contradictions=contradictions,
        evidence_records=accumulated,
        answerability=result.answerability,
        iteration_purpose=result.iteration_purpose,
        rationale=result.rationale,
        failure=result.failure,
    )
    updated_builder = deepcopy(builder)
    updated_builder.purpose = result.iteration_purpose
    updated_builder.set_plan(state.plan).set_evaluation_result(result)
    return {
        "current_iteration": updated_builder,
        "iteration_purpose": result.iteration_purpose,
        "latest_evaluation": evaluation,
        "evidence_summaries": accumulated,
        "pending_evaluation": None,
    }


def _apply_contradictions(previous: list[Contradiction], updates: list) -> list[Contradiction]:
    """Apply ordered contradiction updates from an evaluation result."""

    current = list(previous)
    for update in updates:
        if update.type == "replace":
            current = list(update.contradictions)
        elif update.type == "remove":
            removed = {item.id for item in update.contradictions}
            current = [item for item in current if item.id not in removed]
        else:
            by_id = {item.id: item for item in current}
            by_id.update({item.id: item for item in update.contradictions})
            current = list(by_id.values())
    return current
