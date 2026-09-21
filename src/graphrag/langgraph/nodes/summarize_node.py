"""
Examines successful raw tool results produced during the current iteration and
creates prompt-friendly evidence records grounded in those results.

The evidence records remain iteration-local until the next iteration's context
evaluation accepts and incorporates them into the working context.
"""

from graphrag.langgraph.contracts import EvidenceSummaryResult
from graphrag.langgraph.node_runner import GraphRagNodeRunner
from graphrag.langgraph.prompts import evidence_prompt
from graphrag.model.rag_state import GraphRagState


async def summarize_results(
    state: GraphRagState,
    *,
    node_runner: GraphRagNodeRunner,
) -> dict[str, object]:
    """Summarize the current successful raw tool result."""

    evidence = state.current_evidence_data
    if evidence is None:
        return {"pending_evidence_summaries": []}
    result = await node_runner.invoke_structured(
        messages=evidence_prompt(
            state,
            evidence,
            "Create one or more concise evidence summaries grounded only in this "
            "raw payload. Every summary must cite the supplied EvidenceData ID.",
        ),
        response_model=EvidenceSummaryResult,
    )
    for summary in result.summaries:
        if set(summary.evidence_data_ids) != {evidence.id}:
            raise ValueError("summary must cite exactly the current EvidenceData ID")
    return {"pending_evidence_summaries": result.summaries}
