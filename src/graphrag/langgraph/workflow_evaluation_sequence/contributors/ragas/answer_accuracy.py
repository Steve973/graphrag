"""Reference-based dual-judge answer-accuracy contributor."""

from typing import Any

from graphrag.langgraph.workflow_evaluation_sequence.contributors.base import EvaluationInputs
from graphrag.langgraph.workflow_evaluation_sequence.contributors.ragas.base import (
    MetricDefinition,
    RagasMetricContributor,
)


class AnswerAccuracyContributor(RagasMetricContributor[EvaluationInputs]):
    definition = MetricDefinition(
        "answer_accuracy", ("user_input", "response", "reference")
    )

    def __init__(self, *, llm: Any) -> None:
        from ragas.metrics.collections import AnswerAccuracy

        self.metric = AnswerAccuracy(llm=llm)

    async def score(self, inputs: EvaluationInputs) -> Any:
        assert inputs.reference is not None
        return await self.metric.ascore(
            user_input=inputs.user_input,
            response=inputs.response,
            reference=inputs.reference,
        )
