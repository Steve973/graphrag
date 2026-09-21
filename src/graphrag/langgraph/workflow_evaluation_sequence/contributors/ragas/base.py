"""Shared adapter used by individual Ragas metric contributors."""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import Any

from graphrag.langgraph.workflow_evaluation_sequence.contributors.base import (
    ContributorMetric,
    ContributorResult,
    ContributorStatus,
)


@dataclass(frozen=True)
class MetricDefinition:
    """Declare exactly what one Ragas contributor consumes and contributes."""

    name: str
    input_fields: tuple[str, ...]
    minimum: float = 0.0
    maximum: float = 1.0
    higher_is_better: bool = True
    allow_empty_fields: tuple[str, ...] = ()


class RagasMetricContributor[InputT](ABC):
    """Run one explicitly typed Ragas 0.4 metric and normalize its result shape."""

    definition: MetricDefinition

    @property
    def name(self) -> str:
        return f"ragas.{self.definition.name}"

    async def contribute(self, inputs: InputT) -> ContributorResult:
        missing = [
            field
            for field in self.definition.input_fields
            if getattr(inputs, field) is None
            or (
                not getattr(inputs, field)
                and field not in self.definition.allow_empty_fields
            )
        ]
        if missing:
            return ContributorResult(
                contributor=self.name,
                status=ContributorStatus.SKIPPED,
                warnings=[f"Missing required input(s): {', '.join(missing)}"],
            )

        try:
            result = await self.score(inputs)
            metric = ContributorMetric(
                name=self.definition.name,
                value=float(result.value),
                minimum=self.definition.minimum,
                maximum=self.definition.maximum,
                higher_is_better=self.definition.higher_is_better,
                reason=getattr(result, "reason", None) or None,
            )
        except Exception as error:
            return ContributorResult(
                contributor=self.name,
                status=ContributorStatus.FAILED,
                warnings=[f"{type(error).__name__}: {error}"],
            )

        return ContributorResult(
            contributor=self.name,
            status=ContributorStatus.COMPLETED,
            metrics=[metric],
        )

    @abstractmethod
    async def score(self, inputs: InputT) -> Any:
        """Call the concrete metric with its real, explicit parameter signature."""
