"""
Finalizes the workflow when the evaluation determines that the workflow is complete or cannot continue:
 - Answers the question if the workflow successfully resolved the plan items
 - Answers the question partially if a partial answer could be produced
 - Stops if an unrecoverable error occurred
"""

from graphrag.langgraph.contracts import FinalAnswerDraft
from graphrag.langgraph.node_runner import GraphRagNodeRunner
from graphrag.langgraph.prompts import state_prompt
from graphrag.model.action import FinalizeAction
from graphrag.model.base import WorkflowStatus
from graphrag.model.question import FinalAnswer
from graphrag.model.rag_state import GraphRagState


async def finalize_workflow(
    state: GraphRagState,
    *,
    node_runner: GraphRagNodeRunner,
) -> dict[str, object]:
    """Produce the terminal public answer from accepted workflow evidence."""

    last_action = state.iterations[-1].action if state.iterations else None
    latest_iteration_evidence = (
        state.iterations[-1].evidence_records if state.iterations else []
    )
    if isinstance(last_action, FinalizeAction):
        status = last_action.status
    elif state.evidence_summaries or latest_iteration_evidence:
        status = WorkflowStatus.PARTIAL
    else:
        status = WorkflowStatus.FAILED

    if status == WorkflowStatus.FAILED:
        draft = FinalAnswerDraft(
            answer="The workflow could not gather enough reliable graph evidence to answer the question.",
            confidence=0.0,
        )
    else:
        draft = await node_runner.invoke_structured(
            messages=state_prompt(
                state,
                "Write the direct final answer using only accepted evidence and plan "
                "findings. Clearly qualify material gaps when the terminal status is "
                f"{status.value}.",
            ),
            response_model=FinalAnswerDraft,
        )
    answer = FinalAnswer(
        workflow_id=state.workflow_id,
        status=status,
        answer=draft.answer,
        confidence=draft.confidence,
    )
    return {"status": status, "final_answer": answer}
