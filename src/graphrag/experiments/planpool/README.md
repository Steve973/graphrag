# PlanPool clarification experiment

[Resolving Underspecification in Agentic Text-to-SQL](https://arxiv.org/html/2610.02739v1)
uses **PlanPool** to track clarification needs. BIRD-Lite is one of its
evaluation datasets. This experiment adapts the clarification loop to GraphRAG
questions using LangGraph. It does not run the paper's SQL benchmark.

## Discovery and resolution

1. The detector gets the **original question**, any supplied decomposition
   steps, candidate unknowns from another component, and available datasource
   observations. It looks for consequential decisions that the user has left
   open. It checks the original wording against the steps because a
   decomposition can implicitly choose a definition or omit a constraint. An
   explicit constraint dropped by decomposition is a breakdown defect and
   should be restored, with no clarification needed for that constraint.
2. The detector proposes a prioritized list of needs. Each has a target, a
   specific user question, an explanation of the gap, an exact quote from the
   original prompt, and optional step and discovery observation references.
   Python checks the quote and reference IDs. Detection is model-driven,
   so these checks establish traceability rather than completeness.
3. PlanPool keeps that list in checkpointed state. On each turn the model can
   request a datasource lookup through the optional `probe` callback, ask
   the highest-priority pending question, add a newly discovered need, or
   close an existing one as resolved or dropped. A user question pauses the
   graph with an interrupt. Resuming records the response as an observation.
   One response may resolve multiple needs or reveal a follow-up.
4. Closing a need requires a reason and references to observations already
   recorded. The model judges whether those observations actually resolve
   the need or make it irrelevant. A datasource lookup can establish a
   graph mapping or domain definition. A user preference, such as which
   ranking to apply when both are viable, normally requires the user's input.
   The graph rejects a finish action while any item is pending. Reaching the
   turn budget returns `blocked` with the remaining pool intact.

For example, a breakdown step like “identify the foremost experts” does not
specify a ranking measure. The detector can attach the ranking ambiguity to
that step and quote “foremost experts” from the original question. If the user
chooses publication count and volunteers a qualification threshold, both
items can be closed against that reply. The choice of publication count can
then reveal a new unknown about the time window.

## Run the experiment

Run these from the GraphRAG repo:

```bash
.venv/bin/python -m graphrag.experiments.planpool --demo
```

The scripted demo exercises the actual LangGraph state transitions and
interrupt/resume path. It attempts to finish early, records one response
against two needs, drops a now irrelevant item, adds a date-range question,
and finishes after the follow-up. Its detector output, model decisions,
and simulated user replies are scripted.

Use the model-backed path to test detection and resolution on new questions:

```bash
.venv/bin/python -m graphrag.experiments.planpool \
  --question 'Who are the foremost experts in feline cardiomyopathy?' \
  --context 'The graph has publication dates, authorship, and citation counts.'
```

Codex uses the existing CLI login. `--backend llm` uses the existing Bedrock
settings and structured-output adapter. Questions appear on stderr and are
answered one at a time on stdin. The final JSON on stdout contains the
discovered needs, dispositions, and observation history. Use `--hint` for
candidate unknowns from an existing stage and repeat `--context` for
additional initial observations.

To pass steps from the Hasson decoder, use `--breakdown path/to/record.json`.
Supply a single decoder record and pass its original question separately
with `--question`. Published or hand-labeled Hasson graphs demonstrate that
input interface. Applying the Hasson method to new raw questions first
requires the question-to-graph parser and its trained weights.

To evaluate discovery, run the same question with and without its breakdown
using the same datasource context and no hints. Keep your expected unknowns
separate from the model input. Compare which unknowns the detector found,
which unnecessary questions it proposed, and whether the cited observations
actually justify each final disposition. A `ready` result means the pool
was accounted for. It does not establish that the detector found every
consequential unknown.

## Fit into another initialization flow

Call `build_graph(backend, checkpointer=..., probe=...)` with your structured
model backend and a checkpointer appropriate for your flow. Provide the original
question, plus any observations, numbered steps, and unknown hints your flow
already produces. If decomposition runs later in your initialization, omit
the steps and detect against the original question and available context.
An optional async `probe(request) -> str` adapter can route a lookup to your
existing schema or ontology tools. The standalone CLI accepts static context.

Run with a thread ID, surface the interrupt payload through your existing
clarification UI, and resume with `Command(resume=answer)` on the same thread.
Allow at least `2 * max_turns + 4` graph steps for this loop. When status is
`ready`, pass the original question and the resolved decisions with their
supporting observations to the next phase. The experiment outputs those
records without rewriting the question. A `blocked` result leaves open needs
available for your workflow's error or review path.

```bash
.venv/bin/python -m pytest -q tests/experiments/test_planpool.py
```
