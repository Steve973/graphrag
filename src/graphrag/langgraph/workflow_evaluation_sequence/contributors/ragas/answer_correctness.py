"""Reference-based answer-correctness contributor."""

from typing import Any

from graphrag.langgraph.workflow_evaluation_sequence.contributors.base import EvaluationInputs
from graphrag.langgraph.workflow_evaluation_sequence.contributors.ragas.base import (
    MetricDefinition,
    RagasMetricContributor,
)


class AnswerCorrectnessContributor(RagasMetricContributor[EvaluationInputs]):
    definition = MetricDefinition(
        "answer_correctness", ("user_input", "response", "reference")
    )

    def __init__(self, *, llm: Any, embeddings: Any) -> None:
        from ragas.metrics.collections import AnswerCorrectness

        self.metric = AnswerCorrectness(llm=llm, embeddings=embeddings)

    async def score(self, inputs: EvaluationInputs) -> Any:
        assert inputs.reference is not None
        return await self.metric.ascore(
            user_input=inputs.user_input,
            response=inputs.response,
            reference=inputs.reference,
        )
