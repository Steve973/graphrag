"""Prompt assembly for GraphRAG workflow nodes."""

from graph_rag.llm.prompts.context_prompt_building import (
    StateSectionSpec,
    StateSectionType,
    build_rag_state_prompt_sections,
    create_single_evidence_data_section,
)
from graph_rag.model.rag_state import GraphRagState
from graph_rag.model.supporting_data import EvidenceData


def state_prompt(state: GraphRagState, instruction: str) -> list[dict[str, str]]:
    """Build a concise system instruction and complete reasoning context."""

    sections = [
        StateSectionSpec(StateSectionType.QUESTION),
        StateSectionSpec(StateSectionType.GRAPH_CONTEXT),
        StateSectionSpec(StateSectionType.PLAN),
        StateSectionSpec(StateSectionType.LATEST_ITERATION)
        if state.iterations
        else None,
        StateSectionSpec(StateSectionType.LATEST_EVALUATION)
        if state.latest_evaluation
        else None,
        StateSectionSpec(StateSectionType.ACCUMULATED_EVIDENCE_SUMMARY),
        StateSectionSpec(StateSectionType.WORKFLOW_STATUS),
    ]
    context = build_rag_state_prompt_sections(
        state,
        [section for section in sections if section is not None],
    )
    clarification_parts = [
        ("Clarification Request", state.clarification_request),
        ("User Clarification Response", state.clarification_response),
        ("Clarification Evaluation", state.clarification_evaluation),
    ]
    for title, value in clarification_parts:
        if value is not None:
            context += f"\n\n## {title}:\n{value.to_structured_text()}"
    return [
        {
            "role": "system",
            "content": (
                "You are one node in a controlled GraphRAG workflow. Follow the "
                "requested response schema exactly. Treat graph context as guidance "
                "and evidence summaries as the only support for factual conclusions."
            ),
        },
        {"role": "user", "content": f"{instruction}\n\n{context}"},
    ]


def evidence_prompt(
    state: GraphRagState,
    evidence: EvidenceData,
    instruction: str,
) -> list[dict[str, str]]:
    """Build a summarization prompt containing one raw evidence payload."""

    messages = state_prompt(state, instruction)
    messages[-1]["content"] += "\n\n" + create_single_evidence_data_section(
        evidence,
    )
    return messages
