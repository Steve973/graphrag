# Hasson and Berant dependency-graph experiment

This experiment includes a raw-question graph parser trained on the published
BREAK token graphs and runs the upstream token-graph to QDMR decoder. It can decode
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

## Original upstream BiaffineDG training and prediction

Use this path to test the authors' model. It loads the upstream
`biaffine-graph-parser--transformer-encoder.json`, trains with AllenNLP,
and runs the upstream `BiaffineDependencyParserPredictor` on raw questions.
The launcher bypasses the upstream script's machine-specific Conda and
GPU settings. The model, dataset reader, and predictor come from the
upstream checkout. With `--decode`, the graph-to-QDMR conversion also runs
inside the upstream environment.

### Python 3.12 setup

Use GraphRAG's uv toolchain with the experiment dependency list. It uses
the archived AllenNLP revision that relaxed its dependency bounds, Torch
2.5, and Transformers 4.39. The launcher stages a copy of the upstream
Python source for the Python 3.12 worker. It adapts removed Python and
NumPy APIs and imports only the reader, model, predictor, and metrics
needed by BiaffineDG. The upstream checkout stays intact.

Run from the GraphRAG root using the project's existing `.venv`. The worker
defaults to the same interpreter used to start the launcher.

```bash
upstream=/tmp/hasson-upstream/qdecomp_with_dependency_graphs-master
requirements=src/graphrag/experiments/hasson_qdecomp/requirements-py312.txt
constraints=$(mktemp)
uv --no-cache pip freeze --python .venv/bin/python --exclude-editable \
  --exclude huggingface-hub --exclude rich > "$constraints"
uv --no-cache pip install --python .venv/bin/python --constraint "$constraints" \
  --extra-index-url https://download.pytorch.org/whl/cpu -r "$requirements"
export NLTK_DATA="$PWD/.venv/nltk_data"
.venv/bin/python -m nltk.downloader -d "$NLTK_DATA" wordnet
.venv/bin/python -c 'from huggingface_hub import snapshot_download; snapshot_download("google-bert/bert-base-uncased", local_dir=".venv/bert-base-uncased", allow_patterns=["config.json", "model.safetensors", "tokenizer.json", "tokenizer_config.json", "vocab.txt"])'
```

For Blackwell GPUs, apply `requirements-cu128.txt` after the Python 3.12
setup to replace Torch and TorchVision with CUDA 12.8 builds. Run this from
a terminal with access to the GPU and confirm that a CUDA operation succeeds
before training.

```bash
uv pip install --python .venv/bin/python \
  -r src/graphrag/experiments/hasson_qdecomp/requirements-cu128.txt
.venv/bin/python -c 'import torch; print(torch.cuda.get_device_name(0), torch.ones(1, device="cuda").item())'
```

To measure a representative epoch, use `--cuda-device 0 --epochs 1` with the
full training and validation splits and a fresh serialization directory.
The training log records training and validation durations.

The experiment pins Hugging Face Hub and Rich to versions compatible with
Transformers and `cached-path`. Exclude those two packages when generating
constraints so their currently installed versions can be replaced.

Download [Break-dataset.zip](https://github.com/allenai/Break/raw/master/break_dataset/Break-dataset.zip)
for the reference development QDMRs. Hasson's own archive contains the
graph and span files, while the original validation metric reads
`datasets/Break/QDMR/dev.csv` from BREAK. The launcher can populate the
missing CSV from the ZIP. The local upstream checkout already has the
verified CSV, so the ZIP is optional there. The configuration also loads the pretrained
`bert-base-uncased` encoder and tokenizer. If those files are already
local, pass `--bert /absolute/path/to/bert-base-uncased` to training and
keep that directory available for archive loading.

```bash
original=graphrag.experiments.hasson_qdecomp.upstream
run=/tmp/graphrag-original-biaffine
export ALLENNLP_CACHE_ROOT="$PWD/.venv/allennlp_cache"
export NLTK_DATA="$PWD/.venv/nltk_data"

.venv/bin/python -m "$original" train \
  --upstream "$upstream" \
  --bert "$PWD/.venv/bert-base-uncased" \
  --serialization-dir "$run" --cuda-device -1

.venv/bin/python -m "$original" predict \
  --upstream "$upstream" \
  --archive "$run/model.tar.gz" --decode \
  'Who are the foremost experts in feline cardiomyopathy?' \
  'Which authors published the most papers on feline cardiomyopathy since 2015?' \
  > /tmp/graphrag-original-predictions.jsonl
```

The original configuration specifies 200 epochs. For a short training run,
use a separate serialization directory and add `--epochs 1 --train-samples
96 --validation-samples 32`. Omit the sample flags to use the full splits.
Use `--cuda-device 0` for a GPU run. If you have an original model archive, start with
`predict`. The launcher disables the validation metric for raw prompts,
which have no reference QDMRs. Training still uses the original metric.
Each prediction includes the original tokens, arc indices and arc labels.
With `--decode`, it also contains the upstream steps or the decoder error.

The original parser trained and validated under Python 3.12 in GraphRAG's
`.venv` using the downloaded pretrained BERT. A 96-example smoke run
saved and reloaded an archive and exercised raw-text inference. For the
larger CPU pilot, add `--epochs 3 --train-samples 4096 --validation-samples 128`
to the training command. The sample flags use a fixed seed and leave the
published data intact. The pilot completed all three epochs. At the
original arc cutoff, its final validation labeled-arc micro F1 was 35.7%,
and logical-form exact match was 15 of 128 (11.7%).

The original predictor and decoder returned these steps from raw prompts:

| Prompt | QDMR steps in order |
| --- | --- |
| Who are the foremost experts in feline cardiomyopathy? | `return feline cardiomyopathy`, `return foremost experts in` |
| Which authors published the most papers on feline cardiomyopathy since 2015? | `return feline cardiomyopathy`, `return since 2015` |
| How many papers were published in 2015? | `return papers`, `return #1 in 2015`, `return How many #2` |

The first two outputs have disconnected spans. They omit the operations
needed to identify experts or rank authors. The paper-count prompt
produced a connected decomposition. These are pilot results from 4,096
training questions, with no claim about performance after full training.
The local baseline below is a separate experiment.

## From a raw question to a graph and QDMR

The parser in `predict.py` is a small CPU-trainable baseline inspired by the
paper's biaffine graph parser. It uses a convolutional encoder and predicts
arc presence and labels for pairs of tokens, including the upstream special
tokens. It uses the same training graph format and label vocabulary as the
upstream decoder. Its architecture and weights differ from the published
BERT/AllenNLP model. The decoder runs the upstream code.

Run from the GraphRAG root. Training was verified with Torch 2.5.1+cpu already
installed in `.venv`. If Torch is absent, install a PyTorch build suitable for
your platform in that environment before training. The decoder alone can run
without Torch.

```bash
upstream=/tmp/hasson-upstream/qdecomp_with_dependency_graphs-master
checkpoint=/tmp/graphrag-break-biaffine.pt

# Train once. The archive contains the labeled training and development graphs.
.venv/bin/python -m graphrag.experiments.hasson_qdecomp.predict train \
  --upstream "$upstream" --checkpoint "$checkpoint"

# Predict from text. Save the intermediate graph so you can inspect it.
.venv/bin/python -m graphrag.experiments.hasson_qdecomp.predict predict \
  --checkpoint "$checkpoint" 'How many papers were published in 2015?' \
  > /tmp/graphrag-predicted-graph.jsonl

# Decode that prediction with the upstream converter.
.venv/bin/python -I -m graphrag.experiments.hasson_qdecomp \
  --upstream "$upstream" --graph-file /tmp/graphrag-predicted-graph.jsonl
```

With the default six-epoch training run, the question above produced these
predicted argument arcs (token positions are zero-based):

| From token | To token | Predicted role |
| --- | --- | --- |
| `many` (1) | `2015` (6) | `aggregate-arg[count]` |
| `2015` (6) | `papers` (2) | `filter-sub` |

The prediction also contains `span` arcs that join tokens into step phrases.
The upstream decoder returned:

```text
1. return papers
2. return #1 were published in 2015
3. return How many #2
```

By default the predictor drops conflicting arcs in confidence order before
decoding, for example two competing targets for a single-valued argument
role. Use `predict --raw` to inspect the unpruned predictions. The default run
trained on 43,166 graphs and selected a checkpoint and arc threshold on
1,000 development graphs. Its unpruned labeled-arc F1 on that development
sample was 0.407. This measures agreement on individual arcs.

### Held-out baseline evaluation

I evaluated the saved checkpoint on the other 6,409 published development
graphs, excluding the 1,000 used to select the checkpoint and threshold. The
parser received the published token boundaries and extra tokens, so the
evaluation isolates graph prediction from differences in raw-text tokenization.

| Measure | Result |
| --- | ---: |
| Labeled-arc F1 before pruning | 41.6% |
| Labeled-arc F1 after pruning | 42.7% |
| Labeled-arc F1 after pruning, excluding `span` arcs | 28.1% |
| Exact labeled graph match after pruning | 320 / 6,409 (5.0%) |
| Predicted graphs yielding QDMR steps | 5,038 / 6,409 |
| Same decoded steps as the gold graph, among cases where the gold graph decoded | 386 / 5,630 (6.9%) |

For the last measure, both graphs were run through the same decoder. Step
matching ignores case and whitespace and requires identical step sequences.
This is a strict comparison of decoder output, with no test for logical
equivalence. These results are for the local baseline. The paper's original
model and its logical-form evaluation were outside this run.

On “Which authors published the most papers on feline cardiomyopathy since
2015?”, the baseline predicted a maximum over authors but left the ranking
input empty in the decoded steps. On “Who are the foremost experts in feline
cardiomyopathy?”, it returned two disconnected steps. Use the raw-prompt
path to see which decisions the parser makes, which constraints it preserves,
and where a separate clarification or breakdown check is needed.

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

Use a question-to-graph parser and the upstream decoder behind your
question-breakdown node. Start by checking what that node reads from state,
what it writes, and which fields the next nodes consume. That contract determines
whether you can replace the whole node or just its step decomposition.

1. **Provide a question-to-graph runtime.** The upstream learned parser takes
   question text and produces a token dependency graph. It needs a compatible
   model runtime and trained weights. The experiment's baseline above is one
   runnable option. The decoder accepts the upstream prediction JSONL format
   through `--graph-file`, so you can test output from either model before
   wiring up your node.
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
   failures follow your flow's existing error handling.

## What this run measures

With `--limit 99999`, the decoder produced nonempty QDMRs for 6,514 of the
7,409 published development graphs and rejected 895. Counts are decoder
coverage on supplied graphs. The experiment does not verify semantic
correctness. For example, `--question-id ATIS_dev_0` reconstructs the origin,
destination and availability but drops “tomorrow.” Batch errors go to stderr,
and any rejected record gives the run exit status 1.

Those decoder-only counts begin with published graphs. The raw-question
example above exercises the separate locally trained parser. The upstream
README documents training the original BiaffineDG model and provides graph
data. No pretrained checkpoint for the original model was available in this
experiment. The earlier publication graph remains a hand-labeled decoder
example.
