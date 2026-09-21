"""Faithfulness contributor: are response claims supported by graph context?"""

from typing import Any

from graphrag.langgraph.workflow_evaluation_sequence.contributors.base import EvaluationInputs
from graphrag.langgraph.workflow_evaluation_sequence.contributors.ragas.base import (
    MetricDefinition,
    RagasMetricContributor,
)


class FaithfulnessContributor(RagasMetricContributor[EvaluationInputs]):
    definition = MetricDefinition(
        "faithfulness", ("user_input", "response", "retrieved_contexts")
    )

    def __init__(self, *, llm: Any) -> None:
        from ragas.metrics.collections import Faithfulness

        self.metric = Faithfulness(llm=llm)

    async def score(self, inputs: EvaluationInputs) -> Any:
        return await self.metric.ascore(
            user_input=inputs.user_input,
            response=inputs.response,
            retrieved_contexts=inputs.retrieved_contexts,
        )
