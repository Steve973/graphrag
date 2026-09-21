"""Verify that quoted answer spans occur in the supplied evidence contexts."""

from typing import Any

from graphrag.langgraph.workflow_evaluation_sequence.contributors.base import EvaluationInputs
from graphrag.langgraph.workflow_evaluation_sequence.contributors.ragas.base import (
    MetricDefinition,
    RagasMetricContributor,
)


class QuotedSpansAlignmentContributor(RagasMetricContributor[EvaluationInputs]):
    definition = MetricDefinition(
        "quoted_spans_alignment", ("response", "retrieved_contexts")
    )

    def __init__(self, *, casefold: bool = True, min_span_words: int = 3) -> None:
        from ragas.metrics.collections import QuotedSpansAlignment

        self.metric = QuotedSpansAlignment(
            casefold=casefold,
            min_span_words=min_span_words,
        )

    async def score(self, inputs: EvaluationInputs) -> Any:
        return await self.metric.ascore(
            response=inputs.response,
            retrieved_contexts=inputs.retrieved_contexts,
        )
