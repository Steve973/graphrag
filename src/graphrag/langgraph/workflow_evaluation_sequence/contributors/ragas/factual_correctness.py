"""Claim-level factual-correctness contributor."""

from typing import Any

from graphrag.langgraph.workflow_evaluation_sequence.contributors.base import EvaluationInputs
from graphrag.langgraph.workflow_evaluation_sequence.contributors.ragas.base import (
    MetricDefinition,
    RagasMetricContributor,
)


class FactualCorrectnessContributor(RagasMetricContributor[EvaluationInputs]):
    definition = MetricDefinition("factual_correctness", ("response", "reference"))

    def __init__(self, *, llm: Any) -> None:
        from ragas.metrics.collections import FactualCorrectness

        self.metric = FactualCorrectness(llm=llm)

    async def score(self, inputs: EvaluationInputs) -> Any:
        assert inputs.reference is not None
        return await self.metric.ascore(
            response=inputs.response,
            reference=inputs.reference,
        )
