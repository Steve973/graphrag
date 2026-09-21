"""Reference-based context-recall contributor."""

from typing import Any

from graphrag.langgraph.workflow_evaluation_sequence.contributors.base import EvaluationInputs
from graphrag.langgraph.workflow_evaluation_sequence.contributors.ragas.base import (
    MetricDefinition,
    RagasMetricContributor,
)


class ContextRecallContributor(RagasMetricContributor[EvaluationInputs]):
    definition = MetricDefinition(
        "context_recall", ("user_input", "retrieved_contexts", "reference")
    )

    def __init__(self, *, llm: Any) -> None:
        from ragas.metrics.collections import ContextRecall

        self.metric = ContextRecall(llm=llm)

    async def score(self, inputs: EvaluationInputs) -> Any:
        assert inputs.reference is not None
        return await self.metric.ascore(
            user_input=inputs.user_input,
            retrieved_contexts=inputs.retrieved_contexts,
            reference=inputs.reference,
        )
