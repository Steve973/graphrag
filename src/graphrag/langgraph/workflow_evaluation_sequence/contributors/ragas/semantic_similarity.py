"""Embedding-based answer/reference semantic-similarity contributor."""

from typing import Any

from graphrag.langgraph.workflow_evaluation_sequence.contributors.base import EvaluationInputs
from graphrag.langgraph.workflow_evaluation_sequence.contributors.ragas.base import (
    MetricDefinition,
    RagasMetricContributor,
)


class SemanticSimilarityContributor(RagasMetricContributor[EvaluationInputs]):
    definition = MetricDefinition("semantic_similarity", ("response", "reference"))

    def __init__(self, *, embeddings: Any) -> None:
        from ragas.metrics.collections import SemanticSimilarity

        self.metric = SemanticSimilarity(embeddings=embeddings)

    async def score(self, inputs: EvaluationInputs) -> Any:
        assert inputs.reference is not None
        return await self.metric.ascore(
            reference=inputs.reference,
            response=inputs.response,
        )
