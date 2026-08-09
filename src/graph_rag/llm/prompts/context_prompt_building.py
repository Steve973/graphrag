from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum
from typing import Literal, Sequence

from graph_rag.model.base import WorkflowStatus
from graph_rag.model.iteration import IterationRecord
from graph_rag.model.plan import Plan
from graph_rag.model.question import Question
from graph_rag.model.rag_state import GraphContext, GraphRagState
from graph_rag.model.supporting_data import EvidenceData, EvidenceSummary
from graph_rag.model.workflow import WorkflowEvaluation


class StateSectionType(StrEnum):
    QUESTION = "question"
    GRAPH_CONTEXT = "graph_context"
    PLAN = "plan"
    LATEST_ITERATION = "iteration"
    LATEST_EVALUATION = "evaluation"
    ACCUMULATED_EVIDENCE_DATA = "accumulated_evidence_data"
    ACCUMULATED_EVIDENCE_SUMMARY = "single_evidence_summary"
    SINGLE_EVIDENCE_DATA = "single_evidence_data"
    WORKFLOW_STATUS = "workflow_status"


@dataclass(frozen=True)
class StateSectionSpec:
    name: StateSectionType
    include_header: bool = True
    header_level: int = 3
    include: set[str] | None = None
    exclude: set[str] | None = None
    exclude_none: bool = True
    indent: int = 2
    required: bool = False


YamlFormat = Literal["yaml"]
FenceLanguage = Literal["yaml", "text"]


def _yaml_document_stream(documents: Sequence[str]) -> str:
    return "\n".join(
        "\n".join(["---", document.rstrip()])
        for document in documents
    )


def _header(title: str, include_header: bool, header_level: int) -> list[str]:
    if not include_header:
        return []
    if header_level < 1 or header_level > 6:
        raise ValueError("header_level must be between 1 and 6")
    return [f"{'#' * header_level} {title}:"]


def _fenced_section(
        *,
        title: str,
        description: str,
        body: str | Sequence[str],
        include_header: bool = True,
        header_level: int = 3,
        text_format: FenceLanguage = "yaml",
) -> str:
    body = body or (
        "# No data is currently available."
        if text_format == "yaml"
        else "No data is currently available."
    )
    lines = [
        *_header(title, include_header, header_level),
        description,
        f"```{text_format}",
        body if isinstance(body, str) else "\n".join(body),
        "```",
    ]
    return "\n".join(lines) + "\n"


def create_question_section(
        question: Question,
        include_header: bool = True,
        header_level: int = 3,
) -> str:
    return _fenced_section(
        title="User Supplied Question",
        description="The user supplied the following question about the graph database:",
        body=question.text,
        include_header=include_header,
        header_level=header_level,
        text_format="text",
    )


def create_graph_context_section(
        graph_context: GraphContext,
        include_header: bool = True,
        header_level: int = 3,
        text_format: YamlFormat = "yaml",
        include: set[str] | None = None,
        exclude: set[str] | None = None,
        exclude_none: bool = True,
        indent: int = 2,
) -> str:
    return _fenced_section(
        title="Graph Context",
        description="The following data provides information about the graph database:",
        body=graph_context.to_structured_text(
            text_format=text_format,
            include=include,
            exclude=exclude,
            exclude_none=exclude_none,
            indent=indent,
        ),
        include_header=include_header,
        header_level=header_level,
        text_format=text_format,
    )


def create_plan_section(
        plan: Plan,
        include_header: bool = True,
        header_level: int = 3,
        text_format: YamlFormat = "yaml",
        include: set[str] | None = None,
        exclude: set[str] | None = None,
        exclude_none: bool = True,
        indent: int = 2,
) -> str:
    return _fenced_section(
        title="Current Plan Revision",
        description="The current revision of the plan to answer the user's question:",
        body=plan.to_structured_text(
            text_format=text_format,
            include=include,
            exclude=exclude,
            exclude_none=exclude_none,
            indent=indent,
        ),
        include_header=include_header,
        header_level=header_level,
        text_format=text_format,
    )


def create_latest_iteration_section(
        iteration: IterationRecord,
        include_header: bool = True,
        header_level: int = 3,
        include: set[str] | None = None,
        exclude: set[str] | None = None,
        exclude_none: bool = True,
        indent: int = 2,
) -> str:
    return _fenced_section(
        title="Latest Completed Iteration Data",
        description="The following data represents the information pertaining to the most recent completed iteration:",
        body=iteration.to_structured_text(
            include=include,
            exclude=exclude,
            exclude_none=exclude_none,
            indent=indent,
        ),
        include_header=include_header,
        header_level=header_level,
    )


def create_latest_evaluation_section(
        evaluation: WorkflowEvaluation,
        include_header: bool = True,
        header_level: int = 3,
        include: set[str] | None = None,
        exclude: set[str] | None = None,
        exclude_none: bool = True,
        indent: int = 2,
) -> str:
    return _fenced_section(
        title="Latest Evaluation Data",
        description="The following data represents the latest evaluation from the beginning of the current iteration:",
        body=evaluation.to_structured_text(
            include=include,
            exclude=exclude,
            exclude_none=exclude_none,
            indent=indent,
        ),
        include_header=include_header,
        header_level=header_level,
    )


def create_accumulated_evidence_data_section(
        evidence_items: list[EvidenceData],
        include_header: bool = True,
        header_level: int = 3,
        include: set[str] | None = None,
        exclude: set[str] | None = None,
        exclude_none: bool = True,
        indent: int = 2,
) -> str:
    return _fenced_section(
        title="All Accumulated Raw Evidence Data",
        description="The following is all of the accumulated raw evidence data up to this point in the workflow:",
        body=_yaml_document_stream([
            evidence_data.to_structured_text(
                include=include,
                exclude=exclude,
                exclude_none=exclude_none,
                indent=indent,
            )
            for evidence_data in evidence_items
        ]),
        include_header=include_header,
        header_level=header_level,
    )


def create_accumulated_evidence_summary_section(
        evidence_summaries: list[EvidenceSummary],
        include_header: bool = True,
        header_level: int = 3,
        include: set[str] | None = None,
        exclude: set[str] | None = None,
        exclude_none: bool = True,
        indent: int = 2,
) -> str:
    return _fenced_section(
        title="All Accumulated Evidence Summary Data",
        description="The following is all of the accumulated evidence summary data up to this point in the workflow:",
        body=_yaml_document_stream([
            evidence_summary.to_structured_text(
                include=include,
                exclude=exclude,
                exclude_none=exclude_none,
                indent=indent,
            )
            for evidence_summary in evidence_summaries
        ]),
        include_header=include_header,
        header_level=header_level,
    )


def create_single_evidence_data_section(
        evidence_data: EvidenceData,
        include_header: bool = True,
        header_level: int = 3,
        include: set[str] | None = None,
        exclude: set[str] | None = None,
        exclude_none: bool = True,
        indent: int = 2,
) -> str:
    return _fenced_section(
        title="Raw Evidence Data",
        description="The following is raw evidence data requested by you (the agent) to support the plan:",
        body=evidence_data.to_structured_text(
            include=include,
            exclude=exclude,
            exclude_none=exclude_none,
            indent=indent,
        ),
        include_header=include_header,
        header_level=header_level,
    )


def create_current_workflow_status_section(
        status: WorkflowStatus,
        include_header: bool = True,
        header_level: int = 3,
) -> str:
    return _fenced_section(
        title="Current Workflow Status",
        description="The following is the current workflow status:",
        body=status.value,
        include_header=include_header,
        header_level=header_level,
    )


def build_rag_state_prompt_sections(
        state: GraphRagState,
        sections: Sequence[StateSectionSpec],
) -> str:
    rendered_sections: list[str] = []

    for section in sections:
        match section.name:
            case StateSectionType.QUESTION:
                rendered_sections.append(
                    create_question_section(
                        state.question,
                        include_header=section.include_header,
                        header_level=section.header_level,
                    )
                )

            case StateSectionType.GRAPH_CONTEXT:
                if state.graph_context is None:
                    if section.required:
                        raise ValueError("graph_context section requested but state.graph_context is None")
                    continue

                rendered_sections.append(
                    create_graph_context_section(
                        state.graph_context,
                        include_header=section.include_header,
                        header_level=section.header_level,
                        include=section.include,
                        exclude=section.exclude,
                        exclude_none=section.exclude_none,
                        indent=section.indent,
                    )
                )

            case StateSectionType.PLAN:
                if state.plan is None:
                    if section.required:
                        raise ValueError("plan section requested but state.plan is None")
                    continue

                rendered_sections.append(
                    create_plan_section(
                        state.plan,
                        include_header=section.include_header,
                        header_level=section.header_level,
                        include=section.include,
                        exclude=section.exclude,
                        exclude_none=section.exclude_none,
                        indent=section.indent,
                    )
                )

            case StateSectionType.LATEST_ITERATION:
                if not state.iterations:
                    raise ValueError("latest iteration section requested but state.iterations is empty")

                rendered_sections.append(
                    create_latest_iteration_section(
                        state.iterations[-1],
                        include_header=section.include_header,
                        header_level=section.header_level,
                        include=section.include,
                        exclude=section.exclude,
                        exclude_none=section.exclude_none,
                        indent=section.indent,
                    )
                )

            case StateSectionType.LATEST_EVALUATION:
                if state.latest_evaluation is None:
                    raise ValueError("latest evaluation section requested but state.latest_evaluation is None")

                rendered_sections.append(
                    create_latest_evaluation_section(
                        state.latest_evaluation,
                        include_header=section.include_header,
                        header_level=section.header_level,
                        include=section.include,
                        exclude=section.exclude,
                        exclude_none=section.exclude_none,
                        indent=section.indent,
                    )
                )

            case StateSectionType.ACCUMULATED_EVIDENCE_DATA:
                rendered_sections.append(
                    create_accumulated_evidence_data_section(
                        state.evidence_data,
                        include_header=section.include_header,
                        header_level=section.header_level,
                        include=section.include,
                        exclude=section.exclude,
                        exclude_none=section.exclude_none,
                        indent=section.indent,
                    )
                )

            case StateSectionType.ACCUMULATED_EVIDENCE_SUMMARY:
                rendered_sections.append(
                    create_accumulated_evidence_summary_section(
                        state.evidence_summaries,
                        include_header=section.include_header,
                        header_level=section.header_level,
                        include=section.include,
                        exclude=section.exclude,
                        exclude_none=section.exclude_none,
                        indent=section.indent,
                    )
                )

            case StateSectionType.SINGLE_EVIDENCE_DATA:
                raise ValueError(
                    "single_evidence_data cannot be built from GraphRagState alone; "
                    "call create_single_evidence_data_section with an EvidenceData instance"
                )

            case StateSectionType.WORKFLOW_STATUS:
                rendered_sections.append(
                    create_current_workflow_status_section(
                        state.status,
                        include_header=section.include_header,
                        header_level=section.header_level,
                    )
                )

    return "\n".join(rendered_sections)


def build_single_evidence_data_sections(
        state: GraphRagState,
) -> list[str]:
    return [
        create_single_evidence_data_section(
            data_item,
            include_header=True,
            header_level=2,
            indent=0,
        )
        for data_item in state.evidence_data
    ]

