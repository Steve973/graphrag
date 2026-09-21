"""Dual-judge response-groundedness contributor."""

from typing import Any

from graphrag.langgraph.workflow_evaluation_sequence.contributors.base import EvaluationInputs
from graphrag.langgraph.workflow_evaluation_sequence.contributors.ragas.base import (
    MetricDefinition,
    RagasMetricContributor,
)


class ResponseGroundednessContributor(RagasMetricContributor[EvaluationInputs]):
    definition = MetricDefinition(
        "response_groundedness", ("response", "retrieved_contexts")
    )

    def __init__(self, *, llm: Any) -> None:
        from ragas.metrics.collections import ResponseGroundedness

        self.metric = ResponseGroundedness(llm=llm)

    async def score(self, inputs: EvaluationInputs) -> Any:
        return await self.metric.ascore(
            response=inputs.response,
            retrieved_contexts=inputs.retrieved_contexts,
        )
