"""Reference-based context-precision contributor."""

from typing import Any

from graphrag.langgraph.workflow_evaluation_sequence.contributors.base import EvaluationInputs
from graphrag.langgraph.workflow_evaluation_sequence.contributors.ragas.base import (
    MetricDefinition,
    RagasMetricContributor,
)


class ContextPrecisionWithReferenceContributor(RagasMetricContributor[EvaluationInputs]):
    definition = MetricDefinition(
        "context_precision_with_reference",
        ("user_input", "reference", "retrieved_contexts"),
    )

    def __init__(self, *, llm: Any) -> None:
        from ragas.metrics.collections import ContextPrecisionWithReference

        self.metric = ContextPrecisionWithReference(llm=llm)

    async def score(self, inputs: EvaluationInputs) -> Any:
        assert inputs.reference is not None
        return await self.metric.ascore(
            user_input=inputs.user_input,
            reference=inputs.reference,
            retrieved_contexts=inputs.retrieved_contexts,
        )
