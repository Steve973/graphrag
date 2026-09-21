"""Coverage and conciseness contributor for evidence summaries."""

from typing import Any

from graphrag.langgraph.workflow_evaluation_sequence.contributors.base import EvaluationInputs
from graphrag.langgraph.workflow_evaluation_sequence.contributors.ragas.base import (
    MetricDefinition,
    RagasMetricContributor,
)


class SummaryScoreContributor(RagasMetricContributor[EvaluationInputs]):
    definition = MetricDefinition(
        "summary_score", ("reference_contexts", "response")
    )

    def __init__(
        self,
        *,
        llm: Any,
        length_penalty: bool = True,
        conciseness_weight: float = 0.5,
    ) -> None:
        from ragas.metrics.collections import SummaryScore

        self.metric = SummaryScore(
            llm=llm,
            length_penalty=length_penalty,
            coeff=conciseness_weight,
        )

    async def score(self, inputs: EvaluationInputs) -> Any:
        return await self.metric.ascore(
            reference_contexts=inputs.reference_contexts,
            response=inputs.response,
        )
