# Findings replay experiment

Run finding generation against retained query results. Each replay case carries
a criterion, its atomic assertions, the executed query, and one successful
`ToolCallResult`. The experiment evaluates the assertion against that result
and can produce multiple findings across replays of different results.
Finding generation and optional review run independently of acquisition and
criterion sufficiency.

From the project root:

```sh
.venv/bin/python -m graphrag.experiments.findings
.venv/bin/python -m graphrag.experiments.findings \
  --case complete --backend codex --mode compare --review
```

The first command runs the synthetic publication fixtures with hand-authored
expressions. The second runs the model-only and hybrid paths on the same
fixture, with a separate findings review for each path. `--backend codex`
uses authenticated Codex CLI. `--backend llm` uses the repo's
`GRAPH_RAG_LLM_*` configuration. Use `--model` to select a model with
either backend. Model runs send query or evidence content to the configured
provider. Use data approved for that provider.

## Adding a replay case

Pass `--input path/to/cases.json` with a JSON array in the format of
[publications.json](publications.json). Put the retained tool result in
`result` and the final executed query in `query`. `rows_pointer` is a JSON
Pointer relative to `result.data`. Use an empty string for a root array.
Pointers in returned findings use that same coordinate system. Source IDs
identify the exact retained result.

Coverage defaults to `unknown`. Mark it `complete` only when the result
exhausts the query's scope. Use `partial` for limited or truncated results.
The runtime uses counts or extrema from incomplete results as bounds when
possible. For instance, one observed publication supports “at least one,”
partially supports “at least two,” and says nothing about how many rows exist
beyond the observed subset. Review compares the actual query scope with the
assertion.

## Interpreting results

- `manual` runs supplied expressions and uses a model only for fallback and
  optional review. Without a backend, assertions needing fallback are marked
  `model_required`.
- `hybrid` asks the model to produce expressions in one batch using the
  assertions, executed query, observed field names and types, and coverage
  metadata. The evaluator runs the expressions on the original rows.
  Assertions with no expression or a runtime mismatch go to one finding
  generation call with the raw result.
- `model` sends all assertions and the raw result to the finding generator.
  `compare` runs that mode and then the hybrid mode.

Pipeline expressions run an ordered list of table operations. Each operation
can use the columns produced by the preceding operation. Available operations
include filtering, grouping and aggregating, deriving arithmetic columns,
ranking with an explicit tie rule, sorting, and limiting. The final scalar
comparison can compare two fields or a field and a literal. The shorter
filter/reduce/compare form remains available for single reductions.

For example, `publication-rank` filters by year, groups by author, counts
distinct publications, ranks authors, and then filters to Alice. Its lineage
includes the authors she was ranked against. `mean-publications` groups by
author to get publication counts and then aggregates those counts again to
get the mean. Pipeline results from partial or unknown coverage provide
context about the returned rows. The shorter form can establish a definitive
finding from incomplete coverage when its reduction supplies a suitable bound.

Row schema inference records observed types and missing fields.
Execution validates referenced values and produces pointers to the source
rows it used. A finding that depends on the full collection also cites that
collection. Semantic findings use pointers supplied by the model and checked
by the runtime. Review receives the expression and computed result for
programmatic findings, and the cited raw payload for model findings.

Output is one JSON record per case and mode. It includes the selected paths,
expressions, candidate findings, review decisions, accepted findings, and
wall-clock and per-phase model timings. Each assertion can have an optional
expected relation, scalar value, and exact pointer set. A null expected
relation checks that no finding was produced. Exact pointer agreement is
stricter than a reviewer judging whether different references also support
the same finding. The built-in fixtures are a functional test. Representative
work cases and repeated runs are needed to estimate production accuracy and
latency, including the cost of binding in a separate model call.
