"""Reference-entity coverage contributor."""

from typing import Any

from graphrag.langgraph.workflow_evaluation_sequence.contributors.base import EvaluationInputs
from graphrag.langgraph.workflow_evaluation_sequence.contributors.ragas.base import (
    MetricDefinition,
    RagasMetricContributor,
)


class ContextEntityRecallContributor(RagasMetricContributor[EvaluationInputs]):
    definition = MetricDefinition(
        "context_entity_recall", ("reference", "retrieved_contexts")
    )

    def __init__(self, *, llm: Any) -> None:
        from ragas.metrics.collections import ContextEntityRecall

        self.metric = ContextEntityRecall(llm=llm)

    async def score(self, inputs: EvaluationInputs) -> Any:
        assert inputs.reference is not None
        return await self.metric.ascore(
            reference=inputs.reference,
            retrieved_contexts=inputs.retrieved_contexts,
        )
