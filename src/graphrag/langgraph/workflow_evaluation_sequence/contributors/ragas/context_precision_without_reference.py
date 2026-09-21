"""Response-based context-precision contributor."""

from typing import Any

from graphrag.langgraph.workflow_evaluation_sequence.contributors.base import EvaluationInputs
from graphrag.langgraph.workflow_evaluation_sequence.contributors.ragas.base import (
    MetricDefinition,
    RagasMetricContributor,
)


class ContextPrecisionWithoutReferenceContributor(RagasMetricContributor[EvaluationInputs]):
    definition = MetricDefinition(
        "context_precision_without_reference",
        ("user_input", "response", "retrieved_contexts"),
    )

    def __init__(self, *, llm: Any) -> None:
        from ragas.metrics.collections import ContextPrecisionWithoutReference

        self.metric = ContextPrecisionWithoutReference(llm=llm)

    async def score(self, inputs: EvaluationInputs) -> Any:
        return await self.metric.ascore(
            user_input=inputs.user_input,
            response=inputs.response,
            retrieved_contexts=inputs.retrieved_contexts,
        )
