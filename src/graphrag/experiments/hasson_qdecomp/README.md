# Hasson and Berant dependency-graph experiment

This experiment runs the upstream token-graph to QDMR decoder. It can decode
published BREAK graphs or graph files in the format accepted by the upstream
`examine_predictions.py qdmr` command. Each result includes QDMR steps, step
references, token spans and typed dependencies such as `group-value[count]`.

Run from the GraphRAG root using its existing uv environment and the upstream
source copy available on this machine:

```bash
upstream=/tmp/hasson-upstream/qdecomp_with_dependency_graphs-master
uv --no-cache run --no-sync python -I -m graphrag.experiments.hasson_qdecomp \
  --upstream "$upstream" --question-id CLEVR_dev_1262
```

For another checkout or machine, use a local clone of
[the upstream repository](https://github.com/matanhasson/qdecomp_with_dependency_graphs)
as `--upstream`. The published graphs are read directly from its `datasets.zip`.
GraphRAG's lock already supplies NetworkX. The experiment stages the upstream
decoder in a temporary directory, uses Python 3.12-compatible imports, and
defers optional rendering libraries. It also replaces the consecutive-range
helper's external dependency with the equivalent standard-library grouping.
It loads only the definitions needed by the decoder from the upstream training
and evaluation modules. No upstream installation is required.

## Publication example

```bash
uv --no-cache run --no-sync python -I -m graphrag.experiments.hasson_qdecomp \
  --upstream "$upstream" \
  --graph-file src/graphrag/experiments/hasson_qdecomp/examples/author_count.jsonl
```

For “Which authors published the most papers on feline cardiomyopathy?” the
hand-labeled input graph produces:

```text
1. return papers on feline cardiomyopathy
2. return authors of #1
3. return number of #1 for each #2
4. return #2 where #3 most
```

Step 3 has both a counted set and a grouping key. Step 4 depends on the author
set and those counts. The decoder also exposes the roles in
`span_dependencies`, whose IDs refer to `span_steps`. The separate
`qdmr_dependencies` pairs refer to the reordered step numbers in `steps`.
Both representations point from a dependent step to its prerequisite.

## Integrating with a LangGraph initialization flow

Use the upstream parser and decoder as the implementation behind your
question-breakdown node. Start by checking what that node reads from state,
what it writes, and which fields the next nodes consume. That contract determines
whether you can replace the whole node or just its step decomposition.

1. **Provide a question-to-graph runtime.** The upstream learned parser takes
   question text and produces a token dependency graph. It needs a compatible
   model runtime and trained weights. The experiment starts at the decoder and
   accepts the upstream prediction JSONL format through `--graph-file`, so you
   can test parser output against it before wiring up your node.
2. **Adapt the decoder output to your state.** Pass the question text your flow
   selects for decomposition to the parser, decode the graph, and return a
   partial state update in the shape your downstream nodes expect. Use
   `steps` and `qdmr_dependencies` for the numbered QDMR steps and their
   references. If you need typed argument roles, read `span_dependencies`
   with `span_steps`. Those IDs belong to the span graph and cannot be used
   directly as QDMR step IDs.
3. **Keep a source for concepts and unknowns.** Token spans can supply
   candidate phrases, but they do not mark exact concept boundaries or
   identify missing definitions. For example, a span may be “papers on feline
   cardiomyopathy,” while your resolver needs “feline cardiomyopathy” as a
   concept. In “foremost experts in feline cardiomyopathy,” the qualification
   and ranking rules may also need resolution. If your existing breakdown
   produces concept or uncertainty fields, retain that part or obtain those
   fields from another node. If your flow resolves terms before decomposition,
   pass the clarified question to the parser.
4. **Test the replacement on raw questions.** Compare the current and proposed
   state updates for representative questions with dates, rankings, ties, and
   undefined terms. Verify that downstream nodes can consume the result, that
   the steps preserve the original constraints, and that parser and decoder
   failures follow your flow's existing error handling. The decoder-only runs
   below do not verify the full question-to-breakdown path.

## What this run measures

With `--limit 99999`, the decoder produced nonempty QDMRs for 6,514 of the
7,409 published development graphs and rejected 895. Counts are decoder
coverage on supplied graphs. The experiment does not verify semantic
correctness. For example, `--question-id ATIS_dev_0` reconstructs the origin,
destination and availability but drops “tomorrow.” Batch errors go to stderr,
and any rejected record gives the run exit status 1.

The tested path begins with a graph. Running the upstream learned question-to-graph
parser requires trained weights. The upstream README documents training and
provides graph data, and no pretrained BiaffineDG checkpoint was available for
this experiment. The publication graph was hand-labeled to exercise the same
decoder against a GraphRAG-style question.
