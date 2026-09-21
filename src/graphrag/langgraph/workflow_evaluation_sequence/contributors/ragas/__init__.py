"""Independently selectable Ragas contributors and an optional all-metrics factory."""

from __future__ import annotations

import asyncio
from collections.abc import Sequence
from typing import Any

from graphrag.langgraph.workflow_evaluation_sequence.contributors.base import (
    ContributorResult,
    EvaluationInputs,
)
from graphrag.langgraph.workflow_evaluation_sequence.contributors.ragas.answer_accuracy import (
    AnswerAccuracyContributor,
)
from graphrag.langgraph.workflow_evaluation_sequence.contributors.ragas.answer_correctness import (
    AnswerCorrectnessContributor,
)
from graphrag.langgraph.workflow_evaluation_sequence.contributors.ragas.answer_relevancy import (
    AnswerRelevancyContributor,
)
from graphrag.langgraph.workflow_evaluation_sequence.contributors.ragas.base import (
    MetricDefinition,
    RagasMetricContributor,
)
from graphrag.langgraph.workflow_evaluation_sequence.contributors.ragas.context_entity_recall import (
    ContextEntityRecallContributor,
)
from graphrag.langgraph.workflow_evaluation_sequence.contributors.ragas.context_precision_with_reference import (
    ContextPrecisionWithReferenceContributor,
)
from graphrag.langgraph.workflow_evaluation_sequence.contributors.ragas.context_precision_without_reference import (
    ContextPrecisionWithoutReferenceContributor,
)
from graphrag.langgraph.workflow_evaluation_sequence.contributors.ragas.context_recall import (
    ContextRecallContributor,
)
from graphrag.langgraph.workflow_evaluation_sequence.contributors.ragas.context_relevance import (
    ContextRelevanceContributor,
)
from graphrag.langgraph.workflow_evaluation_sequence.contributors.ragas.factual_correctness import (
    FactualCorrectnessContributor,
)
from graphrag.langgraph.workflow_evaluation_sequence.contributors.ragas.faithfulness import (
    FaithfulnessContributor,
)
from graphrag.langgraph.workflow_evaluation_sequence.contributors.ragas.graph_derivation_rubric import (
    GraphDerivationRubricContributor,
)
from graphrag.langgraph.workflow_evaluation_sequence.contributors.ragas.langchain_models import (
    LangChainRagasEmbeddings,
    LangChainRagasLLM,
    LangChainRagasModels,
    adapt_langchain_models,
    build_bedrock_converse_ragas_models,
)
from graphrag.langgraph.workflow_evaluation_sequence.contributors.ragas.noise_sensitivity_irrelevant import (
    IrrelevantNoiseSensitivityContributor,
)
from graphrag.langgraph.workflow_evaluation_sequence.contributors.ragas.noise_sensitivity_relevant import (
    RelevantNoiseSensitivityContributor,
)
from graphrag.langgraph.workflow_evaluation_sequence.contributors.ragas.response_groundedness import (
    ResponseGroundednessContributor,
)
from graphrag.langgraph.workflow_evaluation_sequence.contributors.ragas.quoted_spans_alignment import (
    QuotedSpansAlignmentContributor,
)
from graphrag.langgraph.workflow_evaluation_sequence.contributors.ragas.semantic_similarity import (
    SemanticSimilarityContributor,
)
from graphrag.langgraph.workflow_evaluation_sequence.contributors.ragas.summary_score import (
    SummaryScoreContributor,
)
from graphrag.langgraph.workflow_evaluation_sequence.contributors.ragas.tool_call_accuracy import (
    ToolCallAccuracyContributor,
)
from graphrag.langgraph.workflow_evaluation_sequence.contributors.ragas.tool_call_f1 import (
    ToolCallF1Contributor,
)
from graphrag.langgraph.workflow_evaluation_sequence.contributors.ragas.tool_calls import (
    ToolCallEvaluationInputs,
    ToolCallSpec,
)


RAGAS_CONTRIBUTOR_TYPES = (
    FaithfulnessContributor,
    AnswerRelevancyContributor,
    AnswerCorrectnessContributor,
    AnswerAccuracyContributor,
    FactualCorrectnessContributor,
    ContextPrecisionWithReferenceContributor,
    ContextPrecisionWithoutReferenceContributor,
    ContextRecallContributor,
    ContextRelevanceContributor,
    ContextEntityRecallContributor,
    RelevantNoiseSensitivityContributor,
    IrrelevantNoiseSensitivityContributor,
    ResponseGroundednessContributor,
    SemanticSimilarityContributor,
    SummaryScoreContributor,
    GraphDerivationRubricContributor,
    QuotedSpansAlignmentContributor,
    ToolCallAccuracyContributor,
    ToolCallF1Contributor,
)


def build_ragas_contributors(
    *, llm: Any, embeddings: Any | None = None
) -> list[RagasMetricContributor[EvaluationInputs]]:
    """Optionally assemble every contributor that consumes ``EvaluationInputs``."""

    contributors: list[RagasMetricContributor[EvaluationInputs]] = [
        FaithfulnessContributor(llm=llm),
        AnswerAccuracyContributor(llm=llm),
        FactualCorrectnessContributor(llm=llm),
        ContextPrecisionWithReferenceContributor(llm=llm),
        ContextPrecisionWithoutReferenceContributor(llm=llm),
        ContextRecallContributor(llm=llm),
        ContextRelevanceContributor(llm=llm),
        ContextEntityRecallContributor(llm=llm),
        RelevantNoiseSensitivityContributor(llm=llm),
        IrrelevantNoiseSensitivityContributor(llm=llm),
        ResponseGroundednessContributor(llm=llm),
        SummaryScoreContributor(llm=llm),
        GraphDerivationRubricContributor(llm=llm),
        QuotedSpansAlignmentContributor(),
    ]
    if embeddings is not None:
        contributors.extend(
            [
                AnswerRelevancyContributor(llm=llm, embeddings=embeddings),
                AnswerCorrectnessContributor(llm=llm, embeddings=embeddings),
                SemanticSimilarityContributor(embeddings=embeddings),
            ]
        )
    return contributors


async def run_ragas_contributors(
    contributors: Sequence[RagasMetricContributor[EvaluationInputs]],
    inputs: EvaluationInputs,
) -> list[ContributorResult]:
    """Run a selected set concurrently; each contributor contains its own failure."""

    return list(await asyncio.gather(*(item.contribute(inputs) for item in contributors)))


__all__ = [
    "AnswerAccuracyContributor",
    "AnswerCorrectnessContributor",
    "AnswerRelevancyContributor",
    "ContextEntityRecallContributor",
    "ContextPrecisionWithReferenceContributor",
    "ContextPrecisionWithoutReferenceContributor",
    "ContextRecallContributor",
    "ContextRelevanceContributor",
    "FaithfulnessContributor",
    "FactualCorrectnessContributor",
    "GraphDerivationRubricContributor",
    "IrrelevantNoiseSensitivityContributor",
    "LangChainRagasEmbeddings",
    "LangChainRagasLLM",
    "LangChainRagasModels",
    "MetricDefinition",
    "RAGAS_CONTRIBUTOR_TYPES",
    "RagasMetricContributor",
    "QuotedSpansAlignmentContributor",
    "RelevantNoiseSensitivityContributor",
    "ResponseGroundednessContributor",
    "SemanticSimilarityContributor",
    "SummaryScoreContributor",
    "ToolCallAccuracyContributor",
    "ToolCallEvaluationInputs",
    "ToolCallF1Contributor",
    "ToolCallSpec",
    "adapt_langchain_models",
    "build_bedrock_converse_ragas_models",
    "build_ragas_contributors",
    "run_ragas_contributors",
]
