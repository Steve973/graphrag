"""
Evaluates the current plan, cumulative working context, and, when available,
the immediately preceding iteration record.

Determines what is known, what remains unresolved, and the purpose that should
guide the current iteration.
"""

from graphrag.langgraph.node_runner import GraphRagNodeRunner
from graphrag.langgraph.prompts import state_prompt
from graphrag.model.rag_state import GraphRagState
from graphrag.model.workflow import (
    ContradictionEvaluationResult,
    EvaluationDecision,
    EvidenceSelectionResult,
)


async def evaluate_evidence(
    state: GraphRagState,
    *,
    node_runner: GraphRagNodeRunner,
) -> dict[str, EvidenceSelectionResult]:
    """Select useful evidence from the immediately preceding iteration."""

    if state.current_iteration is None:
        raise ValueError("evidence evaluation requires an active iteration")
    result = await node_runner.invoke_structured(
        messages=state_prompt(
            state,
            "Use the evidence records from the immediately preceding "
            "iteration. Return their exact IDs; return an empty list when there is "
            "no new useful evidence.",
        ),
        response_model=EvidenceSelectionResult,
    )
    return {"pending_evidence_selection": result}


async def evaluate_contradictions(
    state: GraphRagState,
    *,
    node_runner: GraphRagNodeRunner,
) -> dict[str, ContradictionEvaluationResult]:
    """Evaluate only contradiction changes against the accepted evidence."""

    if state.current_iteration is None:
        raise ValueError("contradiction evaluation requires an active iteration")
    result = await node_runner.invoke_structured(
        messages=state_prompt(
            state,
            "Evaluate only contradictions. Return the complete current contradiction "
            "set, preserving IDs for contradictions that remain. Return an empty list "
            "when no contradictions remain.",
        ),
        response_model=ContradictionEvaluationResult,
    )
    return {"pending_contradiction_evaluation": result}


async def evaluate_outcome(
    state: GraphRagState,
    *,
    node_runner: GraphRagNodeRunner,
) -> dict[str, EvaluationDecision]:
    """Choose one workflow outcome after the narrower evaluations are complete."""

    if state.current_iteration is None:
        raise ValueError("evaluation requires an active iteration")
    contradiction_evaluation = state.pending_contradiction_evaluation
    if contradiction_evaluation is None:
        raise ValueError("workflow decision requires contradiction evaluation")
    messages = state_prompt(
        state,
        "Choose exactly one workflow outcome after considering the updated plan, "
        "accepted evidence, retained errors, and contradiction evaluation: CONTINUE, "
        "CLARIFY, COMPLETE, PARTIAL, or FAILED. State the immediate iteration "
        "purpose and concise rationale. Do not select a tool or formulate a user "
        "message.",
    )
    messages[-1]["content"] += (
        "\n\n## Contradiction Evaluation:\n"
        + contradiction_evaluation.to_structured_text()
    )
    evaluation = await node_runner.invoke_structured(
        messages=messages,
        response_model=EvaluationDecision,
    )
    return {"pending_evaluation": evaluation}
