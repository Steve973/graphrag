"""Typed decisions and complete audit records for criterion query research."""

from typing import Literal

from pydantic import Field, JsonValue

from graphrag.model.base import ContractModel, NonEmptyStr
from graphrag.model.plan import PlanStep
from graphrag.model.tool_operations import ToolCallRequest, ToolCallResult


class ResearchCriterion(ContractModel):
    plan_step_id: NonEmptyStr
    statement: NonEmptyStr
    step_description: NonEmptyStr
    required_information: list[str] = Field(default_factory=list)

    @classmethod
    def from_plan_step(
        cls, step: PlanStep, criterion_index: int = 0
    ) -> "ResearchCriterion":
        """Adapt an existing string completion criterion without changing PlanStep."""
        if not 0 <= criterion_index < len(step.completion_criteria):
            raise ValueError(
                "criterion_index must identify a step completion criterion"
            )
        return cls(
            plan_step_id=step.id,
            statement=step.completion_criteria[criterion_index],
            step_description=step.description,
            required_information=step.required_information,
        )


class QueryStrategy(ContractModel):
    approach: NonEmptyStr = Field(
        description="Material retrieval method, not a query label."
    )
    intent: NonEmptyStr = Field(
        description="Immutable evidence question this query answers."
    )
    invariants: list[NonEmptyStr] = Field(
        min_length=1,
        description="Entities, relationships, filters, scope and evidence shape repairs must preserve.",
    )
    request: ToolCallRequest


class DelegateQuery(ContractModel):
    strategy: QueryStrategy


class WorkerConclusion(ContractModel):
    outcome: Literal["succeeded", "failed"] = Field(
        description="Actual query execution outcome. Empty successful data still count as succeeded.",
    )
    result_id: NonEmptyStr | None = Field(
        description="Exact successful tool result ID for succeeded; null for failed. Never invent an ID.",
    )
    rationale: NonEmptyStr


class ExecuteQuery(ContractModel):
    arguments: dict[str, JsonValue]
    rationale: NonEmptyStr


class QueryCandidate(ContractModel):
    id: NonEmptyStr
    strategy: QueryStrategy


class QueryRepair(ContractModel):
    arguments: dict[str, JsonValue]
    rationale: NonEmptyStr = Field(
        description="Explain each minimal edit and the error it fixes."
    )


class RepairReview(ContractModel):
    preserves_intent: bool
    minimal_change: bool
    rationale: NonEmptyStr


class WorkerAttempt(ContractModel):
    number: int = Field(ge=1, le=3)
    request: ToolCallRequest
    result: ToolCallResult | None = None
    repair: QueryRepair | None = None
    repair_review: RepairReview | None = None
    error: str | None = None


class QueryExecution(ContractModel):
    candidate: QueryCandidate
    attempts: list[WorkerAttempt] = Field(default_factory=list)
    result: ToolCallResult | None = None
    failure: str | None = None
    worker_summary: str | None = None
    worker_conclusion: WorkerConclusion | None = None
    worker_messages: list[dict[str, JsonValue]] = Field(default_factory=list)


class SupportDecision(ContractModel):
    candidate_id: NonEmptyStr
    keep: bool
    rationale: NonEmptyStr = Field(
        description="Explain actual returned support, gaps and limitations."
    )


class DiversityReview(ContractModel):
    retain_candidate_ids: list[NonEmptyStr] = Field(max_length=3)
    rationale: NonEmptyStr = Field(
        description="Compare actual executed retrieval paths and evidence; exclude superficial variants.",
    )


class ResearchAssessment(ContractModel):
    """Supervisor's final reasoning; raw evidence is joined by application IDs."""

    support_decisions: list[SupportDecision]
    diversity: DiversityReview
    rationale: NonEmptyStr


class ResearchResult(ContractModel):
    criterion: ResearchCriterion
    status: Literal["complete", "budget_exhausted"]
    candidates_used: int = Field(ge=0, le=6)
    accepted: list[QueryExecution] = Field(max_length=3)
    executions: list[QueryExecution]
    support_reviews: list[SupportDecision]
    diversity_reviews: list[DiversityReview]
    completion_rationale: NonEmptyStr
