"""Question-to-context relevance contributor."""

from typing import Any

from graphrag.langgraph.workflow_evaluation_sequence.contributors.base import EvaluationInputs
from graphrag.langgraph.workflow_evaluation_sequence.contributors.ragas.base import (
    MetricDefinition,
    RagasMetricContributor,
)


class ContextRelevanceContributor(RagasMetricContributor[EvaluationInputs]):
    definition = MetricDefinition("context_relevance", ("user_input", "retrieved_contexts"))

    def __init__(self, *, llm: Any) -> None:
        from ragas.metrics.collections import ContextRelevance

        self.metric = ContextRelevance(llm=llm)

    async def score(self, inputs: EvaluationInputs) -> Any:
        return await self.metric.ascore(
            user_input=inputs.user_input,
            retrieved_contexts=inputs.retrieved_contexts,
        )
