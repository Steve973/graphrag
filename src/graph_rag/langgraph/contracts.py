"""Structured response contracts used by workflow nodes."""

from pydantic import Field

from graph_rag.model.action import WorkflowAction
from graph_rag.model.base import ContractModel, NonEmptyStr
from graph_rag.model.supporting_data import EvidenceSummary


class ActionDecision(ContractModel):
    """Wrap the discriminated workflow-action union for structured output."""

    action: WorkflowAction


class EvidenceSummaryResult(ContractModel):
    """Contain evidence summaries derived from one successful tool result."""

    summaries: list[EvidenceSummary] = Field(min_length=1)


class FinalAnswerDraft(ContractModel):
    """Contain model-authored terminal answer content."""

    answer: NonEmptyStr
    confidence: float = Field(ge=0.0, le=1.0)
