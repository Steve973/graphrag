"""Focused tests for additive evaluation contributors."""

from __future__ import annotations

import asyncio
from typing import Any

from langchain_core.embeddings import Embeddings
from pydantic import BaseModel
from ragas.embeddings.base import BaseRagasEmbedding
from ragas.metrics.collections import Faithfulness

from graphrag.langgraph.workflow_evaluation_sequence.contributors import (
    ContributorMetric,
    ContributorStatus,
    EvaluationInputs,
    EvidenceProvenanceContributor,
    LangChainRagasEmbeddings,
    LangChainRagasLLM,
    ProvenancePath,
    ProvenanceRequest,
    RagasMetricContributor,
)
from graphrag.langgraph.workflow_evaluation_sequence.contributors.ragas.base import (
    MetricDefinition,
)
from graphrag.langgraph.workflow_evaluation_sequence.contributors.ragas import (
    RAGAS_CONTRIBUTOR_TYPES,
    QuotedSpansAlignmentContributor,
    SemanticSimilarityContributor,
    ToolCallAccuracyContributor,
    ToolCallEvaluationInputs,
    ToolCallF1Contributor,
    ToolCallSpec,
)


class FakeMetricResult:
    value = 0.75
    reason = "Three of four claims are supported."


class FakeEmbeddings(BaseRagasEmbedding):
    """Return deterministic vectors while exercising the real Ragas metric."""

    def embed_text(self, text: str, **kwargs: Any) -> list[float]:
        del kwargs
        return [1.0, 0.0] if "Ada" in text else [0.0, 1.0]

    async def aembed_text(self, text: str, **kwargs: Any) -> list[float]:
        return self.embed_text(text, **kwargs)


class FakeLangChainEmbeddings(Embeddings):
    def embed_documents(self, texts: list[str]) -> list[list[float]]:
        return [[float(len(text))] for text in texts]

    def embed_query(self, text: str) -> list[float]:
        return [float(len(text))]

    async def aembed_documents(self, texts: list[str]) -> list[list[float]]:
        return self.embed_documents(texts)

    async def aembed_query(self, text: str) -> list[float]:
        return self.embed_query(text)


class ExampleStructuredOutput(BaseModel):
    answer: str


class FakeStructuredRunnable:
    def __init__(self, schema: type[BaseModel]) -> None:
        self.schema = schema

    def invoke(self, prompt: str) -> BaseModel:
        return self.schema.model_validate({"answer": prompt})

    async def ainvoke(self, prompt: str) -> BaseModel:
        return self.invoke(prompt)


class FakeChatModel:
    def with_structured_output(
        self, schema: type[BaseModel]
    ) -> FakeStructuredRunnable:
        return FakeStructuredRunnable(schema)


def test_each_ragas_contributor_has_its_own_module_and_definition() -> None:
    definitions = [contributor.definition for contributor in RAGAS_CONTRIBUTOR_TYPES]

    assert len(RAGAS_CONTRIBUTOR_TYPES) == 19
    assert len({contributor.__module__ for contributor in RAGAS_CONTRIBUTOR_TYPES}) == 19
    assert len({definition.name for definition in definitions}) == 19


def test_metric_retains_native_scale_and_exposes_normalized_value() -> None:
    metric = ContributorMetric(
        name="graph_derivation_rubric",
        value=4.0,
        minimum=1.0,
        maximum=5.0,
    )

    assert metric.value == 4.0
    assert metric.normalized_value == 0.75


def test_langchain_llm_adapter_satisfies_collections_metric_contract() -> None:
    llm = LangChainRagasLLM(FakeChatModel())  # type: ignore[arg-type]

    # Ragas collections validates this contract with isinstance at construction.
    Faithfulness(llm=llm)
    result = asyncio.run(llm.agenerate("hello", ExampleStructuredOutput))

    assert result == ExampleStructuredOutput(answer="hello")


def test_langchain_embeddings_adapter_uses_langchain_model() -> None:
    embeddings = LangChainRagasEmbeddings(FakeLangChainEmbeddings())

    assert embeddings.embed_text("Ada") == [3.0]
    assert asyncio.run(embeddings.aembed_text("Charles")) == [7.0]


def test_ragas_contributor_maps_inputs_and_result() -> None:
    class FakeFaithfulnessContributor(RagasMetricContributor[EvaluationInputs]):
        definition = MetricDefinition(
            "faithfulness", ("user_input", "response", "retrieved_contexts")
        )

        async def score(self, inputs: EvaluationInputs):
            self.received = inputs
            return FakeMetricResult()

    contributor = FakeFaithfulnessContributor()

    result = asyncio.run(
        contributor.contribute(
            EvaluationInputs(
                user_input="Who is connected to Ada?",
                response="Ada is connected to Charles.",
                retrieved_contexts=["(Ada)-[:KNOWS]->(Charles)"],
            )
        )
    )

    assert result.status == ContributorStatus.COMPLETED
    assert result.metrics[0].value == 0.75
    assert contributor.received.response == "Ada is connected to Charles."


def test_reference_metric_is_explicitly_skipped_without_reference() -> None:
    class FakeAnswerAccuracyContributor(RagasMetricContributor[EvaluationInputs]):
        definition = MetricDefinition(
            "answer_accuracy", ("user_input", "response", "reference")
        )

        async def score(self, inputs: EvaluationInputs):
            raise AssertionError("a skipped contributor must not call its metric")

    contributor = FakeAnswerAccuracyContributor()

    result = asyncio.run(
        contributor.contribute(
            EvaluationInputs(user_input="Question", response="Answer")
        )
    )

    assert result.status == ContributorStatus.SKIPPED
    assert result.metrics == []
    assert "reference" in result.warnings[0]


def test_real_tool_call_contributors_produce_scores() -> None:
    actual = ToolCallSpec(name="read_graph", arguments={"entity_id": "person-1"})
    expected = ToolCallSpec(name="read_graph", arguments={"entity_id": "person-1"})
    inputs = ToolCallEvaluationInputs(
        user_input="Find the person",
        actual_tool_calls=[actual],
        reference_tool_calls=[expected],
    )

    accuracy = asyncio.run(ToolCallAccuracyContributor().contribute(inputs))
    f1 = asyncio.run(ToolCallF1Contributor().contribute(inputs))

    assert accuracy.status == ContributorStatus.COMPLETED
    assert accuracy.metrics[0].value == 1.0
    assert f1.status == ContributorStatus.COMPLETED
    assert f1.metrics[0].value == 1.0


def test_real_semantic_similarity_contributor_produces_score() -> None:
    contributor = SemanticSimilarityContributor(embeddings=FakeEmbeddings())
    inputs = EvaluationInputs(
        user_input="Who is named?",
        response="Ada is named.",
        reference="The person is Ada.",
    )

    result = asyncio.run(contributor.contribute(inputs))

    assert result.status == ContributorStatus.COMPLETED
    assert result.metrics[0].value == 1.0


def test_real_quoted_spans_contributor_checks_evidence() -> None:
    contributor = QuotedSpansAlignmentContributor(min_span_words=3)
    inputs = EvaluationInputs(
        user_input="What does the evidence say?",
        response='The evidence states "Ada knew Charles personally".',
        retrieved_contexts=["The record says Ada knew Charles personally in 1843."],
    )

    result = asyncio.run(contributor.contribute(inputs))

    assert result.status == ContributorStatus.COMPLETED
    assert result.metrics[0].value == 1.0


def test_tool_call_f1_scores_an_extra_call() -> None:
    inputs = ToolCallEvaluationInputs(
        user_input="Read the graph",
        actual_tool_calls=[
            ToolCallSpec(name="read_graph"),
            ToolCallSpec(name="unneeded_graph_call"),
        ],
        reference_tool_calls=[ToolCallSpec(name="read_graph")],
    )

    result = asyncio.run(ToolCallF1Contributor().contribute(inputs))

    assert result.status == ContributorStatus.COMPLETED
    assert result.metrics[0].value == 0.6667


def test_provenance_contributor_adds_structured_paths() -> None:
    async def lookup(request: ProvenanceRequest):
        assert request.entity_ids == ["entity-1"]
        return [
            ProvenancePath(
                entity_id="entity-1",
                has_evidence_id="rel-evidence",
                evidence_id="evidence-1",
                has_source_id="rel-source",
                source_id="source-1",
                evidence={"quote": "Ada knew Charles."},
                source={"title": "Correspondence"},
            )
        ]

    contributor = EvidenceProvenanceContributor(lookup)
    result = asyncio.run(
        contributor.contribute(ProvenanceRequest(entity_ids=["entity-1"]))
    )

    assert result.status == ContributorStatus.COMPLETED
    assert result.artifacts[0].kind == "provenance_path"
    artifact = result.artifacts[0].data
    assert isinstance(artifact, dict)
    assert artifact["source_id"] == "source-1"
