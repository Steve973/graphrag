# Evaluation contributors

These examples add independent evidence and scores to an evaluation state. They
do not decide whether an answer passes; the evaluation/adversarial-verification
steps can interpret the complete list of `ContributorResult` objects.

## Ragas 0.4.3

Ragas 0.4 uses collections metrics and `await metric.ascore(...)`. No contributor
uses `ragas.metrics`, sample objects, or `single_turn_ascore`. Every metric
has its own contributor class and module, so an evaluation sequence can select
only what it needs. Each class calls the concrete metric with its actual keyword
signature; there is no pretend common `ascore(**kwargs)` protocol.

```python
import boto3

from graphrag.langgraph.workflow_evaluation_sequence.contributors import (
    EvaluationInputs,
    build_bedrock_converse_ragas_models,
    build_ragas_contributors,
    run_ragas_contributors,
)

bedrock_runtime = boto3.client("bedrock-runtime", region_name="us-east-1")
models = build_bedrock_converse_ragas_models(
    bedrock_runtime_client=bedrock_runtime,
    model="us.anthropic.claude-sonnet-4-5-20250929-v1:0",
    embedding_model="amazon.titan-embed-text-v2:0",
)
contributors = build_ragas_contributors(
    llm=models.llm,
    embeddings=models.embeddings,
)

results = await run_ragas_contributors(
    contributors,
    EvaluationInputs(
        user_input=question.text,
        response=answer,
        # Preserve one item per graph result/evidence unit and its retrieval order.
        retrieved_contexts=[record.summary for record in evidence_records],
        # Optional. Reference-dependent metrics are explicitly skipped without it.
        reference=reference_answer,
    ),
)
```

`build_bedrock_converse_ragas_models` constructs LangChain
`ChatBedrockConverse` and `BedrockEmbeddings` instances around the supplied
boto3 `bedrock-runtime` client. The Ragas adapter delegates structured output to
LangChain's `with_structured_output`; it does not create a LiteLLM or Instructor
client. If the application already owns configured LangChain models, call
`adapt_langchain_models(chat_model, embedding_model)` instead.

The Ragas 0.4.3 collections package rejects its own legacy
`LangchainLLMWrapper`, despite older integration documentation showing that
wrapper. `LangChainRagasLLM` implements the collections package's newer
structured-output contract while retaining the requested LangChain execution
path. Ragas unfortunately names that internal abstract contract
`InstructorBaseRagasLLM`; inheriting it is required by its runtime validation,
but this adapter does not use the Instructor client library.

Embeddings are optional. Omitting `embedding_model` excludes the three metrics
that actually require embeddings (`answer_relevancy`, `answer_correctness`, and
`semantic_similarity`) while retaining the LLM-only and deterministic
contributors.

The contributors can also be selected independently:

```python
from graphrag.langgraph.workflow_evaluation_sequence.contributors.ragas import (
    FaithfulnessContributor,
    ResponseGroundednessContributor,
)

contributors = [
    FaithfulnessContributor(llm=models.llm),
    ResponseGroundednessContributor(llm=models.llm),
]
```

The optional factory includes modern contributors from adjacent categories when
they operate on the same textual inputs:

- `SemanticSimilarityContributor` for reference-answer comparison.
- `SummaryScoreContributor` for evidence-summary coverage and conciseness.
- `GraphDerivationRubricContributor` for a graph-specific 1–5 reasoning rubric.
- `QuotedSpansAlignmentContributor` for deterministic quoted-evidence checking.

Rubric results retain their native 1–5 scale. `ContributorMetric.normalized_value`
provides a comparable 0–1 value without discarding the original score.

Use graph-result/evidence text for `retrieved_contexts`, not schema descriptions
or general prompt instructions. Faithfulness and response groundedness answer
whether claims follow from those contexts. They do not prove that the graph fact
itself is supported by its original source.

## Evidence provenance

`EvidenceProvenanceContributor` fills that second gap. Give it a lookup function
that resolves materially considered entity/relationship IDs into
`ProvenancePath` objects. `NEO4J_PROVENANCE_QUERY` is an example query for:

```text
(entity)-[:HAS_EVIDENCE]->(evidence)-[:HAS_SOURCE]->(source)
```

The resulting source artifacts should be considered by the evaluator and then
checked again by the adversarial verifier. Keep them additive; do not replace
the graph contexts used by Ragas.

## Tool-use contributors

Tool-call accuracy and F1 use the modern collections API and run without an
evaluator LLM. Golden expected calls are intentionally separate from the calls
actually recorded by the workflow:

```python
from graphrag.langgraph.workflow_evaluation_sequence.contributors.ragas import (
    ToolCallEvaluationInputs,
    ToolCallF1Contributor,
    ToolCallSpec,
)

inputs = ToolCallEvaluationInputs.from_state(
    state,
    reference_tool_calls=[
        ToolCallSpec(name="read_graph", arguments={"entity_id": "person-1"}),
    ],
)
result = await ToolCallF1Contributor().contribute(inputs)
```

Use these for offline cases with known acceptable calls. They should not be used
as an online correctness oracle when several different graph queries could be
equally valid.
