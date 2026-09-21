"""Graph-specific reasoning rubric using Ragas's modern rubric scorer."""

from typing import Any

from graphrag.langgraph.workflow_evaluation_sequence.contributors.base import EvaluationInputs
from graphrag.langgraph.workflow_evaluation_sequence.contributors.ragas.base import (
    MetricDefinition,
    RagasMetricContributor,
)


GRAPH_DERIVATION_RUBRICS = {
    "score1_description": (
        "The response materially contradicts the supplied graph evidence, reverses or "
        "invents relationships, or makes unsupported claims."
    ),
    "score2_description": (
        "Some claims use the graph evidence, but major conclusions require missing "
        "edges, entities, provenance, or unjustified reasoning steps."
    ),
    "score3_description": (
        "The main conclusion is plausible from the graph evidence, but one or more "
        "material derivation steps, qualifications, or provenance links are unclear."
    ),
    "score4_description": (
        "The response is correctly derived from the supplied graph evidence with only "
        "minor omissions that do not change the conclusion."
    ),
    "score5_description": (
        "Every material claim is correctly derived from explicit entities and directed "
        "relationships in the supplied graph evidence, with uncertainty and provenance "
        "represented accurately."
    ),
}


class GraphDerivationRubricContributor(RagasMetricContributor[EvaluationInputs]):
    definition = MetricDefinition(
        "graph_derivation_rubric",
        ("user_input", "response", "retrieved_contexts"),
        minimum=1.0,
        maximum=5.0,
    )

    def __init__(self, *, llm: Any) -> None:
        from ragas.metrics.collections import DomainSpecificRubrics

        self.metric = DomainSpecificRubrics(
            llm=llm,
            rubrics=GRAPH_DERIVATION_RUBRICS,
            with_reference=False,
            name=self.definition.name,
        )

    async def score(self, inputs: EvaluationInputs) -> Any:
        return await self.metric.ascore(
            user_input=inputs.user_input,
            response=inputs.response,
            retrieved_contexts=inputs.retrieved_contexts,
            reference_contexts=inputs.reference_contexts or None,
            reference=inputs.reference,
        )
