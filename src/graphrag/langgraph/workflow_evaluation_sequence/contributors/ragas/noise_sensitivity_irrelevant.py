"""Irrelevant-context noise-sensitivity contributor (lower is better)."""

from typing import Any

from graphrag.langgraph.workflow_evaluation_sequence.contributors.base import EvaluationInputs
from graphrag.langgraph.workflow_evaluation_sequence.contributors.ragas.base import (
    MetricDefinition,
    RagasMetricContributor,
)


class IrrelevantNoiseSensitivityContributor(RagasMetricContributor[EvaluationInputs]):
    definition = MetricDefinition(
        "noise_sensitivity_irrelevant",
        ("user_input", "response", "reference", "retrieved_contexts"),
        higher_is_better=False,
    )

    def __init__(self, *, llm: Any) -> None:
        from ragas.metrics.collections import NoiseSensitivity

        self.metric = NoiseSensitivity(llm=llm, mode="irrelevant")

    async def score(self, inputs: EvaluationInputs) -> Any:
        assert inputs.reference is not None
        return await self.metric.ascore(
            user_input=inputs.user_input,
            response=inputs.response,
            reference=inputs.reference,
            retrieved_contexts=inputs.retrieved_contexts,
        )
