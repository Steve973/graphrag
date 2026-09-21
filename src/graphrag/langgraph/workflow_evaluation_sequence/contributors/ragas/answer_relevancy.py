"""Answer-relevancy contributor."""

from typing import Any

from graphrag.langgraph.workflow_evaluation_sequence.contributors.base import EvaluationInputs
from graphrag.langgraph.workflow_evaluation_sequence.contributors.ragas.base import (
    MetricDefinition,
    RagasMetricContributor,
)


class AnswerRelevancyContributor(RagasMetricContributor[EvaluationInputs]):
    definition = MetricDefinition("answer_relevancy", ("user_input", "response"))

    def __init__(self, *, llm: Any, embeddings: Any) -> None:
        from ragas.metrics.collections import AnswerRelevancy

        self.metric = AnswerRelevancy(llm=llm, embeddings=embeddings)

    async def score(self, inputs: EvaluationInputs) -> Any:
        return await self.metric.ascore(
            user_input=inputs.user_input,
            response=inputs.response,
        )
