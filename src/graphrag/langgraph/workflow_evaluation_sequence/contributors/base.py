"""Shared contracts for additive evaluation contributors."""

from __future__ import annotations

from enum import StrEnum
from typing import Any, Protocol

from pydantic import Field, JsonValue, model_validator

from graphrag.model.base import ContractModel, NonEmptyStr


class ContributorStatus(StrEnum):
    """Describe whether a contributor produced usable enrichment."""

    COMPLETED = "completed"
    SKIPPED = "skipped"
    FAILED = "failed"


class ContributorMetric(ContractModel):
    """One scored metric, retaining its native scale."""

    name: NonEmptyStr
    value: float
    minimum: float = 0.0
    maximum: float = 1.0
    higher_is_better: bool = True
    reason: NonEmptyStr | None = None

    @model_validator(mode="after")
    def validate_scale(self) -> ContributorMetric:
        if self.maximum <= self.minimum:
            raise ValueError("metric maximum must be greater than minimum")
        if not self.minimum <= self.value <= self.maximum:
            raise ValueError("metric value must be within its declared scale")
        return self

    @property
    def normalized_value(self) -> float:
        """Return the score normalized to 0..1 without losing its native value."""

        value = (self.value - self.minimum) / (self.maximum - self.minimum)
        return value if self.higher_is_better else 1.0 - value


class ContributorArtifact(ContractModel):
    """Structured evidence or metadata added by a contributor."""

    kind: NonEmptyStr
    data: JsonValue


class ContributorResult(ContractModel):
    """Common additive result consumed by the evaluation subgraph."""

    contributor: NonEmptyStr
    status: ContributorStatus
    metrics: list[ContributorMetric] = Field(default_factory=list)
    artifacts: list[ContributorArtifact] = Field(default_factory=list)
    warnings: list[NonEmptyStr] = Field(default_factory=list)

    @model_validator(mode="after")
    def validate_metric_names(self) -> ContributorResult:
        names = [metric.name for metric in self.metrics]
        if len(names) != len(set(names)):
            raise ValueError("contributor metric names must be unique")
        if self.status == ContributorStatus.COMPLETED and not (
            self.metrics or self.artifacts
        ):
            raise ValueError("a completed contributor must add a metric or artifact")
        return self


class EvaluationInputs(ContractModel):
    """Textual inputs shared by the Ragas metric contributors."""

    user_input: NonEmptyStr
    response: NonEmptyStr
    retrieved_contexts: list[NonEmptyStr] = Field(default_factory=list)
    reference_contexts: list[NonEmptyStr] = Field(default_factory=list)
    reference: NonEmptyStr | None = None


class Contributor(Protocol):
    """Minimal contributor interface used by an evaluation fan-out."""

    name: str

    async def contribute(self, inputs: Any) -> ContributorResult: ...
