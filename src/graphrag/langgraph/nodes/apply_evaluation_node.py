"""
Applies the context evaluation produced at the beginning of the iteration.

Updates the cumulative working context, incorporates accepted evidence from the
immediately preceding iteration, updates plan progress, stores the evaluation
as the working context's latest evaluation, and adds the same evaluation to the
current iteration record builder.
"""

from copy import deepcopy

from graphrag.model.base import Answerability, EvaluationOutcome, WorkflowStatus
from graphrag.model.rag_state import GraphRagState
from graphrag.model.supporting_data import Contradiction
from graphrag.model.workflow import EvaluationFailureDisposition, WorkflowEvaluation


async def apply_evidence_selection(state: GraphRagState) -> dict[str, object]:
    """Resolve selected evidence IDs and add those records to working context."""

    result = state.pending_evidence_selection
    if result is None:
        raise ValueError("evidence application requires a pending selection")
    available = state.iterations[-1].evidence_records if state.iterations else []
    by_id = {record.id: record for record in available}
    selected_ids = result.accepted_evidence_record_ids
    if len(selected_ids) != len(set(selected_ids)):
        raise ValueError("evidence selection contains duplicate IDs")
    missing = set(selected_ids) - set(by_id)
    if missing:
        raise ValueError(
            f"evidence selection references unavailable records: {sorted(missing)!r}"
        )

    accumulated = [*state.evidence_summaries]
    known = {record.id for record in accumulated}
    accumulated.extend(
        by_id[record_id] for record_id in selected_ids if record_id not in known
    )
    return {
        "evidence_summaries": accumulated,
        "pending_evidence_selection": None,
    }


async def apply_evaluation(state: GraphRagState) -> dict[str, object]:
    """Validate and apply the pending evaluation as one state transition."""

    result = state.pending_evaluation
    builder = state.current_iteration
    if result is None or builder is None or state.plan is None:
        raise ValueError("evaluation application requires pending evaluation and iteration")

    contradiction_result = state.pending_contradiction_evaluation
    if contradiction_result is None:
        raise ValueError("evaluation application requires contradiction evaluation")
    contradictions = list(contradiction_result.contradictions)
    answerability = {
        EvaluationOutcome.CONTINUE: Answerability.NOT_READY,
        EvaluationOutcome.CLARIFY: Answerability.NEEDS_CLARIFICATION,
        EvaluationOutcome.COMPLETE: Answerability.COMPLETE,
        EvaluationOutcome.PARTIAL: Answerability.PARTIAL,
        EvaluationOutcome.FAILED: Answerability.NOT_READY,
    }[result.outcome]
    failure = None
    if result.outcome == EvaluationOutcome.FAILED:
        available_errors = [
            *state.errors,
            *(state.iterations[-1].errors if state.iterations else []),
            *builder.errors,
        ]
        non_recoverable_ids = [
            error.id for error in available_errors if not error.recoverable
        ]
        if not non_recoverable_ids:
            raise ValueError("FAILED evaluation requires a retained non-recoverable error")
        failure = EvaluationFailureDisposition(
            error_ids=non_recoverable_ids,
            rationale=result.rationale,
        )

    evaluation = WorkflowEvaluation(
        iteration_number=state.iteration_number,
        contradictions=contradictions,
        evidence_records=state.evidence_summaries,
        answerability=answerability,
        iteration_purpose=result.iteration_purpose,
        rationale=result.rationale,
        failure=failure,
    )
    updated_builder = deepcopy(builder)
    updated_builder.purpose = result.iteration_purpose
    updated_builder.set_plan(state.plan).set_evaluation_result(result)
    update: dict[str, object] = {
        "current_iteration": updated_builder,
        "iteration_purpose": result.iteration_purpose,
        "latest_evaluation": evaluation,
        "pending_evaluation": None,
        "pending_contradiction_evaluation": None,
    }
    if result.outcome == EvaluationOutcome.CLARIFY:
        update.update(
            status=WorkflowStatus.NEEDS_CLARIFICATION,
            clarification_request=None,
            clarification_response=None,
            clarification_evaluation=None,
        )
    return update


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
