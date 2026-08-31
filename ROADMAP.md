# Agentic Workflow Roadmap

The following roadmap represents what I currently see as the most necessary and useful features to build on 
the minimum viable product and turn it into a system that is genuinely useful for the mission. The priorities 
are centered on making the workflow produce results that are as accurate, well-supported, and resistant to 
hallucination as possible, while also making those results understandable and actionable.

This ordering is not intended to be rigid. Urgent mission needs should be inserted into the roadmap at the
appropriate priority as they arise. The same applies to collaboration with MITRE and other teams: work that 
becomes important through those efforts should be merged into the priority list where it makes the most sense, 
or scheduled according to management direction.

## 0.5 AI-Generated Basic (React) UI

Create a lightweight AI-generated web interface to replace Swagger as the primary demonstration surface. The 
initial UI does not need to be a polished analyst application; its purpose is to make the existing workflow
easier to run, observe, and explain during development and demonstrations.

The UI should allow a user to submit a question and show meaningful workflow progress as the graph moves 
through evaluation, iteration, tool execution, query repair, evidence handling, and finalization. Progress
should be streamed from the backend, likely through Server-Sent Events, so that the user can see the workflow 
advancing rather than waiting on a single long-running HTTP response.

The progress stream should use application-level workflow events rather than exposing raw LangGraph state 
changes. This keeps the UI tied to stable concepts such as iteration started, plan step in progress, tool 
execution completed, query repair attempted, evidence evaluated, and iteration finalized, even if the internal 
graph structure changes later.

When execution completes, the same interface should display the final answer and, once available, the workflow
report. This provides a substantially better demonstration of the agentic workflow than Swagger because the 
planning, iteration, repair, and evaluation behavior becomes visible while it is happening.

This is intentionally a small, high-value UI effort. Most of the implementation can likely be generated with
an AI coding tool once the backend event contract is defined, allowing the effort to remain focused on the 
workflow itself rather than front-end development.

Even though this is listed first, it does not have to be the highest priority. I see it as something that
can be thrown together quickly while other items are being worked.

## 1. Workflow Report

Generate a structured workflow report at the end of each completed request and return it alongside the final
answer. The report should explain what the workflow actually did in a way that is useful to an analyst,
developer, or stakeholder rather than simply exposing raw logs.

The report should include the original question, major evaluation and decision points, iteration objectives,
tool activity, query repairs, evidence gathered, findings accepted or rejected, and the path that led to the
final answer. It should be generated from the workflow state and finalized iteration records so that it
reflects the actual execution rather than reconstructing events afterward.

Initially, the report can simply be returned in the Swagger response without requiring persistence. This is
a high-value early feature because most of the required information already exists, and it makes the
workflow's mechanical transparency immediately visible in a demonstration.

---

## 2. Antagonistic Evidence Validation

Add an independent validation step for evidence summaries. When the workflow summarizes a retrieved data
record, a separate evaluator should receive the user's question, the iteration purpose, the plan step the
evidence is intended to support, the generated summary, and the actual source record.

The evaluator should determine whether the summary genuinely follows from the source and whether the source
actually contributes evidence toward the intended plan step. It should look for unsupported claims,
hallucinated details, omitted qualifiers, ignored contradictions, overstatement, and conclusions that are
stronger than the source data allows.

This distinction matters because a summary may accurately describe a record while still failing to provide
evidence for the question the workflow is trying to answer. The evaluation should therefore challenge both
factual fidelity and evidentiary relevance.

The validation result should become part of the finalized iteration record and should also appear in the
workflow report. This is an early reliability improvement because it challenges hallucination and
evidentiary overreach at the point where source data becomes reasoning context.

---

## 3. Antagonistic Full-Context Evaluation

Add a second adversarial evaluation step at the broader workflow level. This evaluator should review the
accumulated evidence, findings, plan progress, and current interpretation and challenge whether the broader
conclusions actually follow from the available information.

It should look for unsupported connections between evidence, ignored contradictions, hidden assumptions,
excessive confidence, improper generalization, and conclusions that extend beyond what the evidence
establishes. It should also identify cases where individual evidence items are valid but are being combined
in a way that does not justify the resulting conclusion.

The evidence-level validator determines whether individual evidence summaries faithfully represent their
sources and actually support their intended purpose. The full-context evaluator determines whether those
pieces collectively justify the workflow's broader findings and final assessment.

Its output should influence final evaluation and should be included in the workflow report so that both the
supporting reasoning and the attempt to challenge that reasoning are visible.

---

## 4. Workflow Persistence

Persist completed workflow executions and their finalized iteration records. The persisted representation
should preserve enough structured information to reconstruct what happened without depending on transient
LangGraph state or application logs.

Useful persisted information includes the question, workflow identifier, iteration records, tool activity,
query repairs, evidence references, validation results, findings, final evaluation, final answer, execution
status, and relevant timing or diagnostic information.

The structured workflow record should remain the authoritative persisted representation of the execution.
The human-readable workflow report may also be stored, but it should remain something that can be regenerated
from the structured execution record after the workflow has completed.

Persistence should support multiple configured implementations where useful. One implementation might
preserve workflow history for reporting and auditability while another could support analytics or another
deployment-specific purpose. The workflow should provide stable persistence events without depending on the
storage technology behind them.

This provides the durable foundation for auditability, historical inspection, debugging, report generation,
and reuse of prior workflow results. It also provides stable artifacts that a question-context implementation
can use when deciding what information should become reusable context.

---

## 5. Question Context Service

Introduce a provider-neutral `QuestionContextService` responsible for preserving, relating, and retrieving
useful context created while the system answers questions. It should be independent of the tools used to
retrieve authoritative operational or domain data.

Each user question should initiate its own workflow execution. A follow-up question is therefore a new
question and a new workflow, not a continuation of the prior workflow. The new question can explicitly
reference a parent or previous question, while other relationships may also connect it to older questions,
entities, findings, concepts, or reasoning history.

The service should support three related forms of context: short-term question context, long-term question
context, and reasoning context. These have different lifecycles and retrieval patterns, but their
relationships are important because useful context often crosses those boundaries.

### Short-Term Question Context

Short-term context should preserve the interaction history surrounding questions and recent workflows. This
can include the question itself, the answer, clarifications, related recent questions, and references between
a new question and the question or workflow that prompted it.

A follow-up question should therefore have its own identity while still being able to reference a parent or
previous question. That relationship provides an explicit source of context without conflating two distinct
workflow executions.

Short-term context can also be searched rather than being limited to an exact parent relationship. A new
question may be related to an earlier question even when it was not asked as a direct follow-up, so recent
semantic or topical matches can also provide useful context.

This context will be most useful during initialization and early evaluation, where the workflow needs to
understand what the user is asking now and whether another question provides important context for
interpreting it.

### Long-Term Question Context

Long-term context should preserve structured concepts and knowledge accumulated across questions and workflow
executions. This may include entities, concepts, relationships, validated findings, contextual facts,
provenance, and links between those things and the questions in which they were encountered.

Questions themselves can contribute concepts and entities before the workflow retrieves any source data.
Evidence summaries and validated findings can contribute additional entities, facts, and relationships as
the workflow progresses. The resulting context should preserve where information came from so that remembered
context can still be traced back to the question, workflow, finding, or source that established it.

Long-term context should not replace the authoritative domain data being queried by the workflow. Its purpose
is to help recognize previously encountered subjects, locate related questions or findings, and identify
context worth bringing into a new workflow. Claims that matter to the answer can still be verified against
their authoritative sources when appropriate.

Entity and concept identity should also be managed rather than simply creating a new contextual object every
time a name appears. Different names, aliases, spellings, or descriptions may refer to the same underlying
thing. A context implementation should be able to resolve those cases, preserve aliases, and avoid
fragmenting related context across duplicate identities.

The context model may also use an ontology or schema to give extracted entities and relationships meaningful
types. This can improve extraction, constrain what relationships are valid, support more precise retrieval,
and allow deployments to adapt the context model to their own domain.

These capabilities make long-term context useful for questions such as:

- Have we encountered this entity or concept before?
- Which previous questions involved it?
- What validated findings were associated with it?
- Which other entities or concepts were related to it?
- Which workflows produced those findings?
- What source or workflow established a remembered fact?
- Are two differently worded questions connected through the same underlying concepts?

### Reasoning Context

Reasoning context should preserve how previous workflows attempted to answer questions. Each workflow can have
its own reasoning trace linked to the question that initiated it, while finalized iteration records provide
natural units for recording what happened during that trace.

Useful reasoning context may include the iteration objective, evaluation and decision information, selected
action, tool calls, query patterns, repair attempts, failures, evidence obtained, validation results, and
iteration outcome. The overall result and execution status can complete the reasoning trace when the workflow
finishes.

Reasoning should also remain connected to the context it operated on. When practical, the system should be
able to relate a reasoning trace or iteration to the question that triggered it and to important entities or
concepts encountered during the execution.

Future workflows can retrieve prior reasoning experience when it is relevant to the current question. That
may identify successful approaches, repeated failure patterns, useful tool sequences, productive query
strategies, or repairs that succeeded in similar situations.

This is retrieval of previous execution experience rather than model training. Prior reasoning provides
evidence about approaches that have worked before, while the current workflow remains responsible for
deciding whether those approaches make sense for the current question.

### Context Relationships and Retrieval

Relationships between context objects should be a first-class part of the service rather than an incidental
implementation detail.

Useful relationships may include:

- A question references a parent or previous question.
- A question initiated a particular workflow.
- A workflow produced particular findings.
- A workflow contains particular reasoning or iteration records.
- A question, finding, or evidence summary mentions an entity or concept.
- A remembered fact originated from a particular finding or source.
- Entities and concepts are related to one another.
- A reasoning step interacted with or produced information about an entity.
- Different questions are related through shared entities, concepts, or findings.

These links create several ways to discover useful context. An explicit parent relationship may be the
strongest signal for a follow-up question, but semantic similarity, shared entities, graph relationships,
temporal proximity, provenance, and workflow outcomes may all contribute to relevance.

The service should therefore retrieve structured context based on the needs of the workflow rather than
simply returning a flat list of semantically similar text. Different implementations may combine vector
similarity, graph traversal, filtering, temporal information, explicit relationships, or other retrieval
techniques.

The workflow should also request only the context appropriate to the current stage. Initialization may need
the parent question and recent related questions. Evaluation may benefit from related entities, concepts,
and prior findings. Planning or decision-making may benefit from relevant reasoning traces and their
outcomes.

### Implementation Independence

`QuestionContextService` should describe the capabilities the application needs rather than the storage model
used to provide them. The interface should not expose Cypher, Neo4j labels, Neo4j node identifiers, vector
indexes, Neo4j trace classes, or other backend-specific concepts.

A Neo4j implementation can map these capabilities onto Neo4j Agent Memory, including conversation and message
history, typed entities and relationships, entity resolution, reasoning traces, semantic search, provenance,
and graph traversal.

Another deployment may implement the same capabilities using a different database or a combination of
technologies. Some implementations may provide richer relationship or similarity capabilities than others,
so the abstraction should describe useful context operations without assuming that every backend implements
them in exactly the same way.

The important boundary is that the workflow depends on question context as an application capability, not on
Neo4j or any other particular persistence technology.

### Relationship to Workflow Persistence

Workflow persistence and question context should remain separate responsibilities even though they use some
of the same information.

Workflow persistence answers: what exactly happened during this workflow execution?

Question context answers: what information and relationships from previous questions and executions are
useful for this question?

The complete persisted workflow remains the authoritative execution history. `QuestionContextService` can
derive reusable context from questions, finalized iteration records, validated findings, evidence summaries,
and workflow outcomes while organizing that information for later retrieval.

This feature belongs after basic workflow persistence because stable workflow artifacts provide trustworthy
inputs for building reusable context without making the context service responsible for preserving the
authoritative execution record.

---

## 6. Competing Iteration Strategies

Allow a single iteration objective to fan out into multiple genuinely different approaches before selecting
or combining their results. The goal should be to explore meaningfully different strategies rather than
issuing superficial variations of the same query.

Possible differences could include alternative query formulations, different graph traversal approaches,
broad versus narrow retrieval, entity-driven versus relationship-driven investigation, different tool
sequences, or different decompositions of the same objective.

Some strategies may also intentionally use different sources of context. For example, one approach could be
generated from the current question and evidence alone while another incorporates a successful reasoning
pattern retrieved from previous workflows.

Each branch should produce a result that can be evaluated independently. The fan-in evaluation can then
select the strongest result, combine complementary evidence, reject weak approaches, or determine that none
of the strategies adequately satisfied the iteration objective.

The workflow report should expose the competing strategies and their outcomes so that it is possible to see
what alternatives were attempted and why particular results were retained.

This comes later because strategy fan-out increases tool use, cost, evaluation complexity, and the number of
possible failure modes. The antagonistic evaluators and workflow report should exist first so that the
behavior and value of competing strategies can be inspected.

---

## 7. Context-Informed Strategy Selection

Use accumulated reasoning and question context to improve future strategy generation and selection. Once
enough trustworthy context has accumulated, the workflow can use previous experience as one input when
deciding how to approach a new iteration.

This could include recognizing approaches that worked for similar questions, avoiding query patterns that
repeatedly failed, finding repair patterns that succeeded in comparable situations, or identifying useful
tool sequences associated with successful outcomes.

Context relationships can make this stronger than simple similarity matching. A previous workflow may be
relevant because it involved the same entities, a related concept, a parent question, or a comparable
reasoning objective even when the original question was phrased very differently.

Historical experience should be treated as evidence rather than authority. The workflow should still be able
to generate independent alternatives and compare them against context-informed strategies rather than simply
repeating whatever happened previously.

The workflow report should indicate when prior context materially influenced strategy selection. This keeps
adaptive behavior inspectable and makes it possible to evaluate whether context-informed orchestration is
actually improving results.

This is intentionally later in the roadmap because it depends on trustworthy validation, durable workflow
records, accumulated question context, and competing-strategy infrastructure. At that point, prior executions
can begin improving future orchestration rather than merely being retained.

---

# Rough Priority

### Immediate Value and Reliability

1. Workflow Report
2. Antagonistic Evidence Validation
3. Antagonistic Full-Context Evaluation

### Durable Workflow and Context

4. Workflow Persistence
5. Question Context Service

### More Advanced Agentic Behavior

6. Competing Iteration Strategies
7. Context-Informed Strategy Selection