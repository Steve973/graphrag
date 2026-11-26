# Breakdown and planning integration

The goal for the agentic RAG app is a faster, more faithful path from the user’s question to acquisition. Start with a
reviewed breakdown representation of the question, ground it in the ontology, model, schema, etc., then derive criteria 
and atomic assertions that preserve the breakdown semantics and requested scope.

**Integration order:** Question and existing context → PENMAN draft → semantic review → breakdown grounding and
resolution as needed → criteria and atomic assertions → coverage review → criterion and assertion grounding → planning
and acquisition.

## Initial Analysis and Integration Plan

- [ ] Identify the strengths of the current structured breakdown and review them with the user to determine the 
  strengths to keep when integrating the improvements.

  For example:
  - reserve exact source quotes, the distinction between explicit meaning and interpretation
  - the trace from requirements to meanings
  - unresolved choices for PlanPool

- [ ] Identify any ambiguities and challenges that must be resolved between the experiment and the existing system that 
  were not anticipated or covered in the experiment/prototype.

## First-pass breakdown and review

- [ ] Keep the strengths of the current structured breakdown as identified from the initial integration review.
- [ ] Use a model available in the work environment to compare PENMAN generation with the current direct breakdown.
  Start with the same model on both paths to isolate the effect of the representation. Evaluate a faster work-available
  model for the first pass if it preserves semantic accuracy, and compare the cost of escalating difficult cases. Use
  the same questions and review criteria, and compare through the same downstream checkpoint so any graph-to-breakdown
  conversion cost is counted.
- [ ] Preserve answer-changing structure explicitly. Check Boolean grouping and negation, entity and modifier
  attachment, inclusive versus exclusive boundaries, quantifiers, the ranking population and measure, the selection
  limit, and presentation order when specified. Keep ranking for selection distinct from presentation order.
- [ ] Route review outcomes to acceptance, targeted graph repair followed by verification, a full rewrite for structural
  defects, or PlanPool for a consequential ambiguity. Preserve the original question, raw graph, review decision, and
  any edits so the first pass can be assessed separately from the repaired result. Validate graph structure and
  references before accepting a repair.
- [ ] Hand a consequential ambiguity about user intent directly to PlanPool when the reviewer identifies it. Pass the
  source phrase, affected breakdown entries, and plausible interpretations when known. For an unspecified ranking
  metric, ask for the metric and apply the clarification to the affected graph and downstream entries. Reparse when the
  clarification changes the shape of the question. Treat a dropped explicit constraint as a breakdown defect the
  workflow can repair.

## Grounding the breakdown

- [ ] Build two independently searchable embedding catalogs at app startup. Use Mobi as the ontology source if that is
  where the work ontology is maintained. Embed the ontology’s classes, properties, labels, aliases, definitions, and
  domain/range where available. Reuse the existing app startup path that reads the Neo4j schema and generates DDL. Build
  the schema embeddings from that DDL, using one entry per node label, property declaration, or directed relationship
  pattern. Include the property’s owning label and type, and both relationship endpoints and direction in the lookup
  text. Keep the structured metadata behind each result.
- [ ] Keep rankings for the ontology and schema separate. Attach top matches to the corresponding breakdown entry, with
  source quote, ontology IRI or schema ID, source revision, and binding status. Use the phrase and its role or
  relationship context to form the search. Batch and deduplicate searches across entries.
- [ ] Decide how to host and refresh the catalogs. Try a process-local vector store for startup-built collections if
  available in the work environment. Neo4j or an available persistent vector store can serve the catalogs if they need
  to be shared. Measure startup build time and lookup latency separately. Pin each run to its catalog versions and
  refresh cached vectors when the ontology, schema, or embedding model changes.
- [ ] Use catalog results for routine grounding. Keep similarity hits as candidates until the available metadata or a
  targeted check supports a binding. A clear, documented binding can proceed without a live graph lookup. When a choice
  could change the answer and the catalog leaves it unresolved, have the grounding reviewer request one specific graph
  check.

| Decision | Route |
| --- | --- |
| Documented binding fits the question | Carry the binding forward into criteria and acquisition. |
| Actual records can distinguish the candidates | Run a bounded graph probe and return its result to the reviewer. |
| The choice depends on user intent | Send the source phrase and clarification to PlanPool. |
| The bounded probe is inconclusive | Retain the uncertainty and route it based on what is still missing. |

A read-only probe request should identify the breakdown entry, source phrase, competing bindings, why the choice
matters, what result would resolve it, and the minimum fields and rows needed. Return the result to the grounding
reviewer before expanding the search. If the graph only supplies plausible candidates and the choice still depends on
intent, route it to PlanPool. For “J. Smith,” return candidate author IDs and distinguishing metadata. Publication
records are outside that identity check.

## Criteria, atomic assertions, and acquisition

- [ ] Pass reviewed breakdown entries and their relevant grounding into the generation prompt for both criteria and
  atomic assertions. Keep each criterion linked to the originating meaning or graph element and each assertion linked to
  its parent criterion. Let the question and resolved intent control the obligations. Use ontology and schema context to
  identify what those obligations refer to.
- [ ] Review coverage at both levels. The criteria should jointly cover the question without expanding it. The atomic
  assertions should jointly establish their parent criterion, and each assertion should be justified by that criterion.
  Ask reviewers for concrete counterexamples to missing or added obligations.
- [ ] Run a second grounding pass on the approved criteria and each atomic assertion. Inherit reviewed bindings by ID
  and search both catalogs again where a criterion or assertion adds useful detail. Attach new results to the relevant
  criterion or assertion and reuse searches for repeated concepts. Preserve conflicting candidates for review before
  changing a binding. In GTD, the live check supported `iyear`, even though search for the later cutoff assertion
  favored `incident_date`.
- [ ] Give planning and acquisition the approved criteria and assertions, inherited bindings, and any remaining
  candidate mappings. Let acquisition choose the query and evidence strategy. If a binding is rejected, revisit that
  binding first. When a replan proposes a new criterion or changes an assertion, run the same scope and coverage checks
  and carry forward the approvals that still apply.

## Integration checks

- [ ] **75 latest publications by this author.** Preserve authorship, the recency measure, and the limit. Accept
  database-side top-75 selection. Inject a whole-cohort fetch requirement at the criterion level and again at the atomic
  assertion level. Verify that each is rejected and that replanning cannot reintroduce it. Require newest-first
  presentation when the user asks for it.
- [ ] **Spain in 2010 or France in 2011.** Preserve both country/year pairings through grounding and criterion creation.
  Test “after 2010” and “in or after 2010” as a paired case for boundary preservation.
- [ ] **Top-N with a known-date filter.** Attach the filter to the eligible records. Verify that no omitted qualifying
  record is strictly newer than the oldest selected record. Leave unspecified tie choices flexible when they fit the
  request.
- [ ] **“Biggest” without a metric.** Preserve the ambiguity and route it to PlanPool without a redundant rewrite.
  Capture the explicit metric in the paired question that supplies one.
- [ ] **Year versus exact date.** Preserve the reviewed year binding even if a later embedding search ranks the
  exact-date field higher.
- [ ] **Catalog-only versus targeted lookup.** Verify that a well-documented binding proceeds without a live planning
  query. Verify that a name match returns only identity candidates and routes to PlanPool if the candidates still need
  user disambiguation.
- [ ] **Grounding handoff.** Confirm that the generator receives the breakdown matches and that approved criterion and
  assertion grounding reaches acquisition with binding IDs intact.

Measure first-pass semantic accuracy, acceptance without edits, successful patches, full rewrites, and correct
clarifications. Record catalog build time, search latency, and time to request clarification. Compare time to approved
criteria and **time to first accepted acquisition result**, including graph conversion, probes, retries, and replans.
Track how often grounding triggers a probe and whether that probe resolves the decision.

## Prototype status

The GTD prototype attaches ontology and schema matches to breakdown entries and searches again for approved criteria and
assertions. Its coverage prompts currently strip the first-pass matches, so passing that context into generation is an
integration item. The tests above are proposed checks for the work app.
