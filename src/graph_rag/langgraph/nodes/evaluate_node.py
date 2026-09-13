"""
Evaluates the current plan, cumulative working context, and, when available,
the immediately preceding iteration record.

Determines what is known, what remains unresolved, and the purpose that should
guide the current iteration.
"""

from graph_rag.langgraph.node_runner import GraphRagNodeRunner
from graph_rag.langgraph.prompts import state_prompt
from graph_rag.model.rag_state import GraphRagState
from graph_rag.model.workflow import EvaluationResult


async def evaluate_context(
    state: GraphRagState,
    node_runner: GraphRagNodeRunner,
) -> dict[str, EvaluationResult]:
    """Evaluate current progress and identify this iteration's purpose."""

    if state.current_iteration is None:
        raise ValueError("evaluation requires an active iteration")
    evaluation = await node_runner.invoke_structured(
        messages=state_prompt(
            state,
            "Evaluate the current plan and evidence. On iterations after the first, "
            "copy only useful evidence summaries from the immediately preceding "
            "iteration into new_evidence_records. Determine answerability and a "
            "specific purpose for this iteration.",
        ),
        response_model=EvaluationResult,
    )
    return {"pending_evaluation": evaluation}
