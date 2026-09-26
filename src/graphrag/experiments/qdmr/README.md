# Question semantics experiment

An isolated, async question-understanding utility for GraphRAG. It describes the
question's concepts, meaning and what must be established to answer it. The
historical `graphrag.experiments.qdmr` command is retained for convenience, but the
output is now **`question-semantics/1`**, not a QDMR operation sequence or a
Break-trained parse. No dependencies were added for this change.

## Try it

From the GraphRAG repository, using its virtual environment:

```sh
.venv/bin/python -m graphrag.experiments.qdmr --backend codex \
  'Show me the top five foremost experts in feline cardiomyopathy.'

.venv/bin/python -m graphrag.experiments.qdmr --backend codex \
  'Show me the top five experts in feline cardiomyopathy. An expert has authored or co-authored at least four publications on this subject. Rank experts by this publication count, highest first. Include everyone in the five highest distinct ranking groups.'

.venv/bin/python -m graphrag.experiments.qdmr
.venv/bin/python -m graphrag.experiments.qdmr --file questions.txt --jsonl
```

The default backend is Codex with the saved CLI login; no `.env` or database
configuration is needed. Interactive mode accepts one question per line; blank
line or Ctrl-D exits. Files and piped stdin also take one question per line.
`--jsonl` emits one successful result per line. Failures go to stderr, set exit
status 1, and do not prevent the remaining questions from being attempted.

## Output contract

The envelope contains `schema_version`, `method`, `backend`, the original
`question` (with outer whitespace trimmed), and `decomposition`:

| Section | Purpose |
| --- | --- |
| `concepts` | Exact expressions in the question, including overlapping compound phrases and constituent concepts; `component_ids` records composition. |
| `meanings` | Requested result, relationships, definitions, qualification/ranking/selection/scope constraints. Each has concept references, exact `source_quotes`, and `basis: explicit` or `interpretation`. |
| `requirements` | Statements of what must be established, linked to the meanings that require them. Dependencies express logical dependence, not a required retrieval sequence. |
| `unresolved` | Declarative notes on unspecified meaning, with affected concepts and requirements. This section is not a list of unanswered factual questions or a decision to prompt the user. |

For the short expert question, useful concepts include `experts`, `foremost`,
`foremost experts`, `feline`, `cardiomyopathy`, and `feline cardiomyopathy`.
Qualification and ranking remain undefined. In the detailed version, the supplied
publication threshold, ranking measure, group limit and tie policy should be
recorded as explicit meanings. The requirements then concern satisfying those
rules, not redefining them. This is the intended behavior to inspect when trying
these examples; model output can vary.

Every ID is unique. Compound references and requirement dependencies point
backward within their respective lists; missing/duplicate references and cycles
are rejected. Exact concept expressions and all source quotes must occur in the
input. Both backends go through these validations. A matching quote provides
traceability; it does **not** prove that the interpretation is correct or complete.
Requirements are derived semantic obligations, not claims quoted from the user.
Their `meaning_ids` provide the trace back to the original text.

There are no `steps`, `operator`, `status`, `assumptions`, or `final_step_id`
fields. This is a breaking replacement for `qdmr-inspired/1` and `/2`. Explicit
rules and interpretations now live together in `meanings` with distinct `basis`
values. The method is `llm_semantic_analysis`; this makes no claim to Break training.

## Responsibility boundary

This stage assumes no database schema, ontology mapping, stored expertise list,
publication record availability, inference route or evidence proxy. An applicable
stored list or aggregate might satisfy several requirements at once; the output
does not mandate reconstructing it from individual records.

Downstream GraphRAG owns resolving concepts against its data, planning, determining
criteria that the question did not supply, research queries, checking sufficiency,
and asking the user if the database/context cannot resolve a consequential issue.
No planner, graph tool, or workflow state is invoked or modified by this utility.
A successful parse is not a statement that the question is answerable.

## Callable interface

```python
from graphrag.experiments.qdmr import decompose
from graphrag.experiments.qdmr.codex_backend import CodexBackend

backend = CodexBackend()
result = await decompose(question, backend=backend, backend_name=backend.name)
understanding = result.model_dump(mode="json")
```

For the app's existing LLM connection:

```python
from graphrag.llm.client import LiteLlmClient
from graphrag.llm.structured_output import LiteLlmStructuredOutput

result = await decompose(
    question,
    backend=LiteLlmStructuredOutput(LiteLlmClient(settings)),
    backend_name=settings.llm_model,
)
```

The async `complete(messages=..., response_model=...)` interface remains the
integration seam. Provider errors and validation errors propagate to callers;
there is no fabricated or automatic fallback result.

## Backend setup

Codex requires a recent CLI supporting `--ignore-user-config`, `--ephemeral` and
`--output-schema`. Use `codex login` and `codex login status`. Saved ChatGPT login
uses the plan allowance; saved API-key login uses API billing. Each question uses
a fresh ephemeral session, temporary working directory, read-only sandbox and
JSON output schema. User configuration is ignored, saved authentication is retained,
and inherited `OPENAI_API_KEY`/`CODEX_API_KEY` variables are removed from the child
process. The prompt requests text transformation without tool use.
`--codex-model MODEL` overrides the model; otherwise the provenance label is
`codex/cli-default` (not a verified resolved model ID). `--codex-timeout 300`
increases the per-question timeout from 180 seconds.
[Official Codex scripting documentation](https://learn.chatgpt.com/docs/non-interactive-mode).

`--backend llm` selects the existing LiteLLM transport and forced output tool.
It requires `GRAPH_RAG_LLM_URL`, `GRAPH_RAG_LLM_API_KEY`, `GRAPH_RAG_LLM_MODEL`, and
`GRAPH_RAG_LLM_PROVIDER`, supplied by environment or `.env`. Run from the repository
root to load `.env`. It also accepts the app's LLM temperature, timeout, retry,
and maximum-token settings. Detailed semantic output may need a larger
`GRAPH_RAG_LLM_MAX_TOKENS` than short questions. The model must support forced tool
calls. This transport has not been live-verified against Bedrock; use your work
project's authenticated backend through the callable seam where appropriate.

## Validation

```sh
.venv/bin/python -m pytest tests/experiments tests/llm -q
```

Tests exercise the actual LiteLLM adapter with only its remote call mocked, the
Codex subprocess boundary, exact-source validation, compound/reference integrity,
requirement dependencies, explicit/interpretation labeling and CLI batch failure
handling. These tests establish mechanical correctness, not semantic quality.
Compare outputs for underspecified versus explicitly defined questions, ties,
negation, compound concepts, missing referents, and unrelated domains.

## Earlier parser assessment

[allenai/Break](https://github.com/allenai/Break) is the dataset. The separate
[original parser](https://github.com/tomerwolgithub/Break/tree/master/qdmr_parsing)
documents Python 3.6.8 and AllenNLP. The
[later T5 parser](https://github.com/tomerwolgithub/question-decomposition-to-sql)
documents a separate Python 3.8 environment and a downloadable checkpoint.
Those research environments were not installed or runtime-verified here. The
experiment initially borrowed QDMR's operators; user trials showed that the
required boundary was conceptual question understanding rather than relational
calculation. The new schema therefore replaces those operators entirely.
