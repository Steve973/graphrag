# Agentic RAG Architecture, Reliability, and Quality Assessment Rubric

**Version:** 0.2  
**Status:** Working Draft — Requirements Inventory in Progress  
**Date:** November 22, 2026  
**Purpose:** Architecture assessment, implementation comparison, reliability evaluation, and integration planning

---

## 1. Purpose and Scope

This rubric provides an evidence-based framework for evaluating the architecture, design, implementation, and 
demonstrated reliability of agentic retrieval-augmented generation (RAG) systems.

The assessment is intended to determine how effectively a system understands research questions, plans and executes 
research, establishes evidentiary support, verifies its conclusions, handles uncertainty and failure, and produces 
accurate, inspectable results.

### 1.1 Objectives

1. Identify capabilities important to reliable agentic research workflows.
2. Evaluate whether an implementation adequately addresses those capabilities.
3. Identify architectural strengths, weaknesses, and omissions.
4. Distinguish design quality from implementation quality and demonstrated effectiveness.
5. Identify risks that could affect factual accuracy, completeness, consistency, or reliability.
6. Determine whether architectural deficiencies can be corrected within an existing design.
7. Identify opportunities for architectural improvement, integration, and reuse.
8. Establish an objective basis for comparing alternative implementations.
9. Provide evidence supporting technical decisions and customer recommendations.
10. Support engineering prioritization based on actual deficiencies and their consequences.

### 1.2 Implementations to Be Evaluated

The initial assessment will cover three implementations:

1. The KEA graph rag service.
2. The API/MCP based workflow.
3. MITRE's KDA.

Each implementation must be assessed independently before comparative conclusions are drawn. The evaluation is intended 
to determine which capabilities are strongest, which deficiencies are most consequential, and which architectural 
approaches offer the best foundation for meeting customer requirements.

### 1.3 Guiding Principle

**A high-quality agentic RAG architecture should reliably establish information from available evidence, recognize its 
limitations, and make its conclusions sufficiently verifiable for their intended use.**

The assessment must not favor an architecture merely because it uses:

- More agents or greater autonomy.
- More elaborate planning.
- A particular decomposition representation.
- A particular orchestration framework.
- A particular LLM or model family.
- Deterministic rather than probabilistic processing.
- A specific retrieval technique.
- A particular findings or verification representation.
- Any implementation-specific terminology.

Architectural quality should be established through demonstrated capabilities and engineering evidence.

---

## 2. Evaluation Methodology and Evidence Standards

### 2.1 Sources Establishing Assessment Criteria

Every criterion should have documented support for why it is relevant to the quality or reliability of an agentic RAG 
system.

Acceptable sources include:

- Peer-reviewed academic research.
- Empirical evaluations and benchmark studies.
- Formal technical standards.
- Recognized software engineering principles.
- Established industry architecture guidance.
- Authoritative technical documentation.
- Explicit customer or project requirements.

The evidence must support the concern being evaluated. A source demonstrating that one technique can improve performance 
does not establish that every system must use that technique.

### 2.2 Reference Classification

Each criterion should identify its supporting basis.

| Classification | Meaning |
|---|---|
| R | Academic research or empirical evidence |
| S | Formal standard or technical specification |
| G | Established industry or product engineering guidance |
| E | Engineering-derived requirement or architectural inference |
| P | Explicit project or customer requirement |

Multiple classifications may apply.

**Important:** An engineering-derived criterion may be entirely legitimate. It must simply be distinguished from a 
requirement directly established by research or standards.

### 2.3 Assessment Dimensions

Every criterion should be evaluated along three independent dimensions.

#### Architecture and Design

Does the architecture deliberately address the requirement?

Assess:

- Defined responsibilities.
- Architectural mechanisms.
- Interfaces and boundaries.
- State and data representations.
- Error conditions.
- Extensibility.
- Enforcement mechanisms.
- Architectural constraints.

#### Implementation

Does the actual implementation provide and enforce the intended behavior?

Assess:

- Implemented functionality.
- Correct use of architectural mechanisms.
- Runtime enforcement.
- Integration completeness.
- State consistency.
- Failure handling.
- Known implementation limitations.

#### Demonstrated Effectiveness

Does objective evidence establish that the capability works reliably?

Assess:

- Representative tests.
- Controlled scenarios.
- Accuracy measurements.
- Failure injection.
- Repeatability.
- Coverage.
- Performance.
- Known limitations.

An architectural design may be excellent without being fully implemented. An implementation may exist without adequate 
evidence that it performs correctly. These distinctions must remain visible in the assessment.

### 2.4 Scoring Scale and Assessment Dimensions

Each criterion must be independently scored from 0 to 4 across three dimensions: Architecture and Design,
Implementation, and Demonstrated Effectiveness. Scores must reflect evidence relevant to the particular dimension rather 
than the overall impression of the implementation.

The three dimensions evaluate different properties. A strong architecture may be incompletely implemented, and a 
complete implementation may lack sufficient evidence of reliable effectiveness. Scores in one dimension must not
automatically determine scores in another.

#### Architecture and Design

Evaluates whether the architecture deliberately accommodates the capability through appropriate responsibilities,
mechanisms, interfaces, constraints, and extension points.

| Score | Classification | Scoring anchor |
|---|---|---|
| 0 | Absent | No identifiable architectural provision for the capability, or the existing architecture fundamentally prevents its realization without substantial redesign |
| 1 | Ad hoc | Capability is only incidentally accommodated, with unclear responsibilities, significant architectural constraints, or substantial dependence on improvised solutions |
| 2 | Partial | Recognizable architectural mechanisms exist, but important responsibilities, interfaces, controls, or integration provisions are incomplete or inadequately addressed |
| 3 | Substantial | Architecture deliberately supports the capability through coherent mechanisms and appropriate interfaces, with limited deficiencies or constraints that can be addressed without substantial redesign |
| 4 | Strong | Architecture comprehensively accommodates the capability through well-defined responsibilities, mechanisms, interfaces, controls, and extension points, with no identified material architectural deficiencies |

#### Implementation

Evaluates whether the actual implementation provides the capability and correctly integrates and enforces its
intended behavior.

| Score | Classification | Scoring anchor |
|---|---|---|
| 0 | Absent | Capability is not implemented, or existing implementation is nonfunctional for its intended responsibility |
| 1 | Ad hoc | Limited functionality exists but relies on incomplete, inconsistent, or improvised mechanisms and lacks significant required behavior |
| 2 | Partial | Principal functionality is implemented, but material gaps remain in integration, enforcement, error handling, or required operational behavior |
| 3 | Substantial | Capability is substantially implemented and integrated, with appropriate operational controls and only limited deficiencies |
| 4 | Strong | Capability is comprehensively implemented, integrated, and enforced, including applicable constraints, failure handling, and consequential edge cases, with no identified material implementation deficiencies |

#### Demonstrated Effectiveness

Evaluates whether objective, independently inspectable evidence establishes that the capability performs correctly
and reliably under representative conditions.

| Score | Classification | Scoring anchor |
|---|---|---|
| 0 | Ineffective | Available evidence demonstrates that the capability fails to achieve its intended purpose or consistently produces unacceptable results |
| 1 | Weak | Demonstrated success is limited, inconsistent, or accompanied by substantial reliability or correctness deficiencies |
| 2 | Partial | Evidence establishes successful behavior in some representative conditions, but material limitations, failures, or reliability concerns remain |
| 3 | Substantial | Representative and reproducible evidence demonstrates generally reliable effectiveness, with limited identified deficiencies or untested consequential conditions |
| 4 | Strong | Comprehensive, reproducible evidence demonstrates reliable effectiveness across representative, challenging, and relevant exceptional conditions, with no identified material performance or correctness deficiencies |

#### Additional Assessment States

- **Not assessed:** Insufficient inspection or evaluation has occurred to establish a defensible score.
- **Not demonstrated:** The capability may exist, but evidence of its effectiveness is insufficient.
- **Not applicable:** The criterion does not apply to the assessed scope, with supporting justification.
- **Planned but not implemented:** The capability is documented as planned but is not implemented.
- **Blocked:** Necessary access, artifacts, or execution conditions are unavailable, preventing adequate assessment.

Insufficient evidence must not automatically be scored as zero. A zero score requires evidence of absence,
non-implementation, or demonstrated ineffectiveness, as appropriate to the assessment dimension.

Planned but unimplemented capabilities must receive an Implementation score of zero. Their Architecture and Design
score may reflect an established design, provided sufficient architectural evidence exists. Demonstrated Effectiveness
must not receive credit for capabilities that have not been implemented and evaluated.

### 2.5 Scoring Principles

- Scores must be supported by specific, independently inspectable evidence.
- The same scoring anchors must be applied consistently across all implementations.
- Architectural capability must be evaluated against the actual architecture, not hypothetical redesigns.
- Implementation scores must reflect existing functionality rather than intended future development.
- Demonstrated Effectiveness scores must reflect observed results rather than architectural potential or implementation 
  claims.
- An untested capability must not receive a high effectiveness score merely because its implementation appears correct.
- Material deficiencies must affect the score in the dimension to which they pertain.
- Different architectural mechanisms may satisfy the same requirement without receiving different scores solely because 
  of their implementation approach.
- Assessment confidence must remain distinguishable from capability quality.

Scores should be assigned as integers. Intermediate fractional scores should not be introduced unless subsequent
evaluation demonstrates that finer distinctions can be applied consistently and meaningfully.

The evaluator must:

1. Apply the same criteria to comparable implementation responsibilities.
2. Use predefined scoring anchors wherever possible.
3. Cite evidence supporting assigned scores.
4. Distinguish observed defects from hypothetical risks.
5. Avoid rewarding sophistication without demonstrated benefit.
6. Avoid penalizing simpler implementations that meet the requirements.
7. Distinguish project compliance from general architectural quality.
8. Record assessment confidence independently of quality.
9. Avoid double-counting closely related capabilities.
10. Make architectural judgments independently of the implementation being evaluated.

### 2.6 Assessment Evidence

Acceptable implementation evidence includes:

- Architecture documents.
- Source code.
- Configuration.
- Workflow definitions.
- Data models.
- Runtime contracts.
- Execution traces.
- Test cases.
- Test results.
- Performance measurements.
- Failure reports.
- Demonstrations.
- Historical execution records.

Claims made by an implementation's authors should be treated as statements requiring substantiation, not as proof of 
capability.

Every significant capability support finding and gap finding must cite specific, inspectable implementation evidence. 
Source-code citations must identify the relevant file, symbol, and code location where available. Runtime findings must 
identify the applicable test, execution trace, log, or observed behavior. Evidence references must be sufficiently 
precise for an independent evaluator to locate and examine the material supporting the finding. General architectural 
descriptions or unsupported assertions do not satisfy this requirement.

---

# Part I — Research Understanding and Planning

## 3. Question Understanding and Semantic Grounding

**Objective:** Determine whether the system accurately understands the user's information requirements, concepts, 
constraints, and assumptions.

**Research foundation:** Ambiguous-question answering, adaptive retrieval, ontology-grounded RAG, and question 
decomposition. [3], [4], [7], [10]

### Evaluation Criteria

| ID | Criterion | Required capability | Basis |
|---|---|---|---|
| Q1 | Information need identification | Correctly identifies the information requested and the expected form of a satisfactory answer | R/E [3], [7] |
| Q2 | Ambiguity recognition | Detects undefined concepts, ambiguous terminology, unresolved references, and material interpretation uncertainties | R [3] |
| Q3 | Constraint preservation | Distinguishes user-specified constraints from inferred assumptions and preserves them throughout execution | R/E [3], [10] |
| Q4 | Uncertainty resolution | Uses appropriate mechanisms to resolve material uncertainties before relying on uncertain interpretations | R/E [3], [4] |
| Q5 | Semantic fidelity | Preserves the original question's intent throughout decomposition, acquisition, assessment, and reporting | R/E [10], [11] |

### Evaluation Considerations

The evaluator should determine whether the system:

- Recognizes multiple reasonable interpretations of a question.
- Avoids silently assigning unsupported definitions.
- Identifies assumptions that materially affect the answer.
- Correctly resolves entities and domain terminology.
- Preserves temporal, numerical, relational, and other constraints.
- Recognizes when clarification or additional investigation is needed.
- Maintains the original information need across multiple research iterations.

**Example:** A request to identify "leading agriculture experts" may require establishing what "leading" means before 
choosing publication counts, citation counts, domain influence, or other measures.

The evaluator must not require a dedicated question-understanding agent.

---

## 4. Data-Model and Ontology Awareness

**Objective:** Determine whether the system understands the structure and semantics of available data and uses that 
understanding appropriately.

**Research foundation:** Ontology-grounded retrieval, knowledge-graph question answering, graph constraint validation, 
and symbolic graph execution. [4], [5], [6], [46]

### Evaluation Criteria

| ID | Criterion | Required capability | Basis |
|---|---|---|---|
| O1 | Schema discovery | Discovers or accesses relevant data structures, entities, properties, and relationships | R/G [5], [6], [46] |
| O2 | Semantic interpretation | Correctly understands what available data structures represent | R [4], [6] |
| O3 | Domain concept mapping | Maps concepts in the question to relevant domain entities, vocabulary, and relationships | R/G [4], [6], [46] |
| O4 | Structural constraint awareness | Respects relationship direction, entity types, cardinality, property semantics, and applicable domain constraints | S/E [5] |
| O5 | Semantically guided research | Uses schema or ontology knowledge to guide acquisition, reasoning, and applicable validation | R/G [4], [6], [46] |

### Capability Levels

**Schema awareness:** Understands available labels, properties, data types, and relationships.

**Semantic awareness:** Understands what those structures represent and how they relate to the research question.

**Ontology-grounded research:** Uses formal domain definitions, constraints, and relationships to guide or validate 
research operations.

These are distinguishable capabilities.

### Project-Specific Requirement

**PR6:** The workflow must meaningfully leverage the provided ontology when answering applicable research 
requests. The requirement specifies the use of Mobi to obtain the ontology.

The evaluator should determine whether ontology information affects actual workflow behavior, rather than merely being 
available to the system.

---

## 5. Early Feasibility and Answerability Assessment

**Objective:** Determine whether the workflow recognizes likely infeasible or unanswerable research objectives early 
enough to avoid unnecessary work without prematurely rejecting solvable questions.

**Research foundation:** Adaptive retrieval strategies, evidence sufficiency, and established agent-planning principles. 
[1], [7], [8]

The requirement for an explicit early feasibility assessment is an engineering-derived extension of these concerns, not 
a universally prescribed RAG architecture.

### Evaluation Criteria

| ID | Criterion | Required capability | Basis |
|---|---|---|---|
| FA1 | Early feasibility assessment | Assesses feasibility before substantial execution when meaningful assessment is possible | G/E [1], [7] |
| FA2 | Information availability assessment | Determines whether accessible data appears capable of providing the required information | R/E [7], [8] |
| FA3 | Capability and constraint assessment | Recognizes unavailable tools, unsupported operations, permission restrictions, and other known constraints | G/E [1], [2] |
| FA4 | Feasibility classification | Distinguishes likely feasible, uncertain, partially feasible, and demonstrably infeasible requests | E [7], [8] |
| FA5 | Appropriate feasibility response | Avoids futile work while supporting bounded exploration, clarification, partial answers, or justified termination | R/E [7], [8] |
| FA6 | Dynamic feasibility reassessment | Updates feasibility judgments when execution reveals new information or constraints | R/E [9], [12] |

### Evaluation Considerations

The system should recognize known limitations before committing substantial resources. For example, an initial 
feasibility estimate must not be treated as conclusive proof that a question cannot be answered before some exploratory 
retrieval has occurred.

### Suggested Measurements

- Detection rate for genuinely infeasible requests.
- False rejection rate for answerable requests.
- Avoidable execution cost.
- Accuracy of feasibility assessments.
- Effectiveness of reassessment after new information.

---

## 6. Question Decomposition and Research Planning

**Objective:** Determine whether the system establishes an appropriate, coherent, and sufficiently complete strategy for 
thoroughly understanding a research question.

**Research foundation:** Adaptive decomposition, multi-hop question answering, and evidence-oriented planning. 
[9], [10], [11]

### Evaluation Criteria

| ID | Criterion | Required capability | Basis |
|---|---|---|---|
| P1 | Evidence requirement identification | Identifies the information necessary to answer the original question | R/E [10], [11] |
| P2 | Appropriate decomposition | Breaks complex problems into manageable research objectives when beneficial | R [9], [10] |
| P3 | Dependency preservation | Correctly models prerequisites and logical relationships among objectives | R/E [9], [11] |
| P4 | Decomposition quality | Recognizes omissions, redundancy, unsupported assumptions, and incorrectly formulated subproblems | R/E [10], [11] |
| P5 | Plan adaptability | Supports changes to the research plan when new information invalidates assumptions or introduces new requirements | R [9], [12] |

### Evaluation Considerations

- Are all material components of the question represented?
- Are the research objectives logically coherent?
- Are prerequisites and dependencies preserved?
- Does the plan avoid unnecessary work?
- Can simple questions be answered without excessive decomposition?
- Can the plan be revised when its assumptions prove incorrect?

The rubric does not prescribe or favor a particular planning implementation, strategy, or algorithm.

---

## 7. Persistent Management of Research Obligations

**Objective:** Ensure unresolved information requirements remain accounted for throughout execution and do not silently 
disappear during iteration or replanning.

**Research foundation:** Adaptive planning, persistent agent context, workflow memory, and stopping research. 
[9], [12], [13], [14]

This is a proposed systems-engineering capability derived from those concerns.

### Evaluation Criteria

| ID | Criterion | Required capability | Basis |
|---|---|---|---|
| U1 | Outstanding obligation tracking | Maintains identifiable unresolved research requirements and uncertainties | R/E [13], [14] |
| U2 | Persistence across iterations | Preserves unresolved obligations through workflow stages, retries, and replanning | R/E [9], [13] |
| U3 | Obligation reassessment | Reevaluates outstanding requirements as new evidence becomes available | R/E [9], [12] |
| U4 | Resolution strategy management | Pursues appropriate alternatives when an obligation cannot initially be resolved | R/E [9], [12] |
| U5 | Explicit disposition | Provides a justified final disposition for each material obligation | E [12], [13] |
| U6 | Premature completion prevention | Prevents unresolved material obligations from silently becoming completed requirements | R/E [8], [12] |

### Expected Behavior

An unresolved requirement should remain identifiable until it is:

- Satisfied.
- Superseded.
- Explicitly deferred.
- Determined to be blocked.
- Declared unresolved with an appropriate explanation.

### Architectural Neutrality

Approaches including PlanPool, dependency graphs, research ledgers, persistent task state, and other representations may 
all satisfy these requirements. The existence of a particular mechanism is not itself evidence of correctness.

---

## 8. Adaptive Research Planning and Refinement

**Objective:** Determine whether the workflow recognizes an inadequate research strategy and adapts to unexpected 
complexity, dependencies, or limitations.

**Research foundation:** ADaPT, adaptive retrieval, and iterative research control. [7], [9], [12]

### Evaluation Criteria

| ID | Criterion | Required capability | Basis |
|---|---|---|---|
| A1 | Planning inadequacy detection | Recognizes when a task cannot be completed adequately using the current plan | R [9] |
| A2 | Impediment identification | Distinguishes missing prerequisites, inadequate decomposition, insufficient evidence, and execution failures where possible | R/E [9], [12] |
| A3 | Adaptive refinement | Revises, subdivides, replaces, or otherwise adapts objectives when justified | R [9] |
| A4 | Original intent preservation | Maintains correspondence between revised objectives and the original question | R/E [9], [10] |
| A5 | Research continuity | Preserves previously established valid results unless new information invalidates them | E [9], [13] |
| A6 | Adaptation effectiveness | Evaluates whether the new approach addresses the original impediment | R/E [9], [12] |

### Important Distinction

Retrying the same operation is not necessarily replanning or adaptation when a research task becomes difficult to 
investigate. A system should be able to recognize that an objective is more complex than initially anticipated and 
adjust its strategy accordingly.

Recursive decomposition is one possible mechanism, but it is not a mandatory implementation requirement.

---

## 9. Progress Assessment and Research Continuation

**Objective:** Determine whether the workflow recognizes meaningful progress and avoids both premature abandonment and 
unproductive repetition.

**Research foundation:** Adaptive stopping, research planning, and agent execution guidance. [1], [9], [12]

### Evaluation Criteria

| ID | Criterion | Required capability | Basis |
|---|---|---|---|
| C1 | Progress evaluation | Recognizes whether additional execution advances the research objective | R/E [12] |
| C2 | Strategy adjustment or deferral | Changes strategy, defers work, or terminates when repeated attempts are ineffective | R/E [9], [12] |
| C3 | Bounded research execution | Avoids unbounded, redundant, or unjustifiably expensive execution | R/G [1], [12] |
| C4 | Objective-oriented progress | Evaluates progress against information requirements rather than merely completed operations | R/E [8], [12] |

**Critical principle:** Successfully completing a research plan does not necessarily mean that the original question has 
been satisfactorily answered.

---

# Part II — Evidence Acquisition and Assessment

## 10. Evidence Acquisition

**Objective:** Determine whether the workflow reliably acquires the information needed to satisfy its research 
requirements.

**Research foundation:** RAGChecker, Corrective RAG, Self-RAG, Adaptive-RAG, Text2Cypher, and faithful agentic search 
research. [7], [15], [16], [17], [18], [45], [46]

### Evaluation Criteria

| ID | Criterion | Required capability | Basis |
|---|---|---|---|
| AC1 | Retrieval strategy selection | Selects appropriate sources, retrieval methods, and tools | R/G [7], [15], [46] |
| AC2 | Query semantic correctness | Constructs retrieval operations that correctly express intended information requirements | R/G [18], [45], [46] |
| AC3 | Retrieval precision | Obtains relevant information while controlling irrelevant or misleading results | R [17] |
| AC4 | Retrieval coverage | Obtains adequate coverage of relevant available information when required | R [17] |
| AC5 | Retrieval-result assessment | Recognizes irrelevant, incomplete, inadequate, or defective results | R/G [15], [16], [46] |
| AC6 | Corrective acquisition | Changes acquisition strategy when initial retrieval is inadequate | R/G [15], [46] |
| AC7 | Result integrity | Correctly handles result structures, duplicates, nulls, aggregations, pagination, and truncation | R/E [18], [17] |
| AC8 | Multi-step retrieval | Acquires information spanning multiple entities, relationships, or retrieval operations | R/G [10], [11], [46] |
| AC9 | Evidence diversity | Controls redundant evidence and obtains complementary information when appropriate | R/E [17] |
| AC10 | Provenance availability | Ensures evidence sources are available or recoverable for later substantiation | S/E [19], [20] |
| AC11 | Acquisition failure handling | Distinguishes legitimate empty results from errors, timeouts, and partial execution | R/E [15], [18] |
| AC12 | Retrieval efficiency | Obtains required information with proportionate latency and resource consumption | R [7], [12] |
| AC13 | Source suitability and trust | Uses appropriate authorized sources and respects untrusted-data boundaries | G [28] |
| AC14 | Retrieval completeness evaluation | Determines whether retrieved results adequately represent the available records satisfying the research requirements, using independent checks or defensible coverage estimates appropriate to the query | R/E [17], [8] |
| AC15 | Empty-result validation | Distinguishes correctly empty result sets from incorrect or inadequate retrieval, and prevents empty results from automatically receiving a successful acquisition evaluation | R/E [15], [8], [17] |
| AC16 | Hybrid and complementary retrieval | Supports appropriate selection, combination, and integration of lexical, semantic, structured, and graph-based retrieval techniques when complementary approaches are necessary to satisfy research requirements | R/G [40], [41], [42], [46] |
| AC17 | Query expressiveness and composability | Supports the construction and execution of sufficiently expressive retrieval operations, including complex filtering, relationship traversal, aggregation, and composition of multiple operations, without architectural restrictions that materially prevent satisfying research requirements | G/E [18], [46] |
| AC18 | Graph embedding-based retrieval | Supports graph representation learning and embedding-based discovery of structurally or semantically related entities, including integration with other retrieval methods when appropriate | R/G [43], [44] |

### 10.1 Query Correctness

Query execution success does not establish semantic correctness.

A syntactically valid Cypher query may return incorrect results because of:

- Incorrect relationship traversal.
- Incorrect property selection.
- Improper filtering.
- Incorrect aggregation.
- Duplicate records.
- Lost constraints.
- Incorrect interpretation of the ontology.
- Incorrect assumptions about data semantics.

Assessment should distinguish successful execution from successful acquisition.

### 10.2 Retrieval Coverage

A large result set does not necessarily establish adequate coverage.

The workflow should appropriately account for:

- Relevant records omitted by retrieval.
- Result limits.
- Pagination.
- Search scope.
- Missing relationships.
- Incomplete aggregation.
- Unknown population size.
- Data-source limitations.

Coverage requirements depend on the question. A request for representative examples may not require exhaustive 
retrieval. A request for a complete count or ranking may require substantially stronger coverage guarantees.

If the prompt specifies coverage requirements, is the system aware of them, and how does it attempt to evaluate them?
Sometimes questions explicitly mention quantities, and sometimes quantities are implicit. Other times, quantities are 
not established or required. Examples include:

- Find 10 documents concerning ...
- What are the newest ... ?
- Find all of the products that ...
- How many times have users ... ?
- Who are the top experts in ... ?
- Show me examples of ...

### 10.3 Acquisition Evaluation Measurements

Candidate measures include:

- Retrieval precision.
- Retrieval recall.
- Query execution accuracy.
- Semantic constraint preservation.
- Retrieval correction success.
- Truncation detection.
- Error classification accuracy.
- Provenance recoverability.
- Acquisition latency.
- Resource consumption.

---

## 11. Acquisition Provenance and Recoverability

**Objective:** Ensure that acquired data can subsequently be traced to evidence sufficient for independent 
substantiation from source material.

**Research foundation:** W3C provenance standards, knowledge-graph provenance research, and automated provenance 
verification. [19], [20], [21], [22]

### Evaluation Criteria

| ID | Criterion | Required capability | Basis |
|---|---|---|---|
| AC10.1 | Provenance identification | Identifies original source material or derivation records associated with acquired facts | S [19] |
| AC10.2 | Provenance recoverability | Ensures source evidence is available immediately or can be reliably retrieved later | S [20] |
| AC10.3 | Provenance granularity | Maintains sufficiently precise provenance for the particular facts or relationships used | S/R [19], [22] |
| AC10.4 | Provenance continuity | Preserves source associations through transformations, aggregation, and downstream processing | S/E [19], [21] |
| AC10.5 | Provenance failure handling | Detects unavailable or inadequate provenance and prevents silent treatment as verified evidence | R/E [22] |

### Supported Acquisition Approaches

**Eager provenance acquisition:** Retrieve supporting material during initial acquisition.

**Deferred provenance acquisition:** Employ a mechanism, such as the preservation of sufficient source identifiers and 
retrieval information, to obtain supporting material when verification requires it.

Both approaches are acceptable.

### Knowledge-Graph Considerations

Retrieved graph nodes and relationships may represent facts derived from:

- Publications.
- Documents.
- Source databases.
- Extraction pipelines.
- Entity-resolution processes.
- Inference rules.
- Other graph records.

The original substantiating material may not be contained directly in the retrieved node or edge. The architecture must 
provide a reliable means of reaching sufficiently granular evidence when required. A generic node identifier does not 
necessarily identify the source substantiating each of its factual relationships.

### Verification Boundary

Acquisition is responsible for making substantiation possible. It is not synonymous with verification that determines 
whether the identified evidence actually supports the factual claim. That will be covered in a separate assessment.

---

## 12. Evidence Assessment and Research Findings

**Objective:** Determine whether the system establishes how acquired evidence supports the research objectives derived 
from the original question.

**Research foundation:** FEVER, FEVEROUS, FActScore, attribution research, and faithful agentic search. 
[23], [24], [25], [26], [45]

The term *Evidence Assessment and Research Findings* is used here as an implementation-independent architectural 
category. It must not be used to preferentially score any particular implementation.

### Evaluation Criteria

| ID | Criterion | Required capability | Basis |
|---|---|---|---|
| EF1 | Objective-to-evidence association | Associates evidence with the particular research objective or proposition it addresses | R [23], [24] |
| EF2 | Support determination | Determines whether evidence supports, contradicts, qualifies, or is insufficient to establish a proposition | R [23], [24] |
| EF3 | Granular support assessment | Distinguishes supported portions from unsupported portions at appropriate granularity | R [25] |
| EF4 | Evidence combination | Supports conclusions requiring multiple records, sources, relationships, or computations | R [24] |
| EF5 | Contradictions and qualifications | Preserves material contradictory evidence, limitations, and qualifications | R [23], [24] |
| EF6 | Traceable support attribution | Preserves relationships among evaluated propositions, findings, and specific evidence | R [26] |
| EF7 | Observation versus inference | Distinguishes directly observed data from conclusions derived through computation or inference | R/E [24], [26], [45] |
| EF8 | Reusable assessment results | Preserves established support assessments for later processing, reconsideration, and reporting | E [26], [13] |

### Evaluation Considerations

The workflow should be able to determine:

1. What proposition or research objective is being evaluated.
2. Which data relates to that proposition.
3. What the data establishes.
4. What remains unsupported.
5. What qualifications apply.
6. Whether multiple evidence records must be combined.
7. Which source records support the assessment.
8. Whether coverage is adequate or complete.

### Architectural Neutrality

The rubric does not require specific implementation details:

- A dedicated findings agent.
- A dedicated findings phase.
- Atomic assertions in a particular representation.
- Specific support classification names.
- A specific JSON schema.
- LLM-based findings creation.
- Programmatic findings creation.

An architecture may integrate evidence assessment into acquisition, processing, or another stage. The assessed 
capability is the establishment of meaningful, attributable evidentiary support.

**Important:** Assessing support is distinct from independently verifying whether the assessment itself is correct.

---

## 13. Evidence Sufficiency and Research Completeness

**Objective:** Determine whether accumulated evidence adequately establishes individual research objectives and 
collectively satisfies the original question.

**Research foundation:** Sufficient Context, RAGChecker, FEVEROUS, and factual evaluation research. 
[8], [17], [24], [25]

### Evaluation Criteria

| ID | Criterion | Required capability | Basis |
|---|---|---|---|
| EC1 | Objective-level sufficiency | Determines whether findings adequately establish each research requirement | R/G/E [8], [24], [46] |
| EC2 | Question-level completeness | Determines whether established objectives collectively answer the original question | R/E [17], [25] |
| EC3 | Logical completeness | Accounts for necessary dependencies and relationships among objectives | R/E [24], [11] |
| EC4 | Evidence-gap identification | Identifies missing evidence or unresolved requirements preventing completion | R/E [8], [17] |
| EC5 | Qualified completion | Supports complete, partial, indeterminate, or unanswerable outcomes when justified | R [8] |
| EC6 | Completion-state consistency | Prevents unsupported objectives from being treated as satisfied | E [8], [12] |

### Three Distinct Answerability Concerns

**Early feasibility:** Is the question likely answerable with available resources?

**Evidence sufficiency:** Does accumulated evidence establish the individual research requirements?

**Question completeness:** Do the established requirements collectively satisfy the original question?

These must remain distinguishable.

### Logical Completeness

Completeness cannot always be determined by counting satisfied objectives.

For example:

- Three completed objectives may be insufficient if a fourth is a mandatory prerequisite.
- An unresolved optional objective may not prevent successful completion.
- A superseded objective may no longer be required.
- A contradiction may be a legitimate research result rather than a failure.

The completion mechanism must account for the actual logical requirements.

---

# Part III — Reliability, Validation, and Control

## 14. Runtime Contracts, Validation, and Error Recovery

**Objective:** Determine whether the architecture detects invalid inputs and outputs, enforces known constraints, 
contains errors, and recovers appropriately.

**Research foundation:** JSON Schema, SHACL, structured-output evaluation, and engineering reliability guidance. 
[5], [27], [29], [30]

### Evaluation Criteria

| ID | Criterion | Required capability | Basis |
|---|---|---|---|
| RC1 | Explicit interface contracts | Defines expected inputs, outputs, types, fields, and applicable constraints | S [27], [29] |
| RC2 | Structural validation | Detects missing, malformed, or structurally incompatible values | S/R [27], [30] |
| RC3 | Domain and value validation | Validates permitted values, ranges, enumerations, and domain-specific constraints | S [5], [27] |
| RC4 | Referential and contextual validation | Ensures identifiers and references are valid within the relevant execution context | S/E [5], [29] |
| RC5 | Error containment | Prevents invalid outputs from corrupting downstream state or conclusions | G/E [30], [31] |
| RC6 | Error classification and recovery | Recognizes failure types and selects appropriate corrective behavior | G/E [1], [31] |
| RC7 | Recovery effectiveness | Demonstrates that recovery restores valid execution or reaches justified termination | E [12], [31] |
| RC8 | Validation coverage | Ensures consequential workflow boundaries receive appropriate validation | S/E [27], [29] |

### Validation Levels

1. **Structural:** Correct representation and required fields.
2. **Domain:** Allowed values, types, and ranges.
3. **Referential:** References identify valid objects.
4. **Contextual:** Referenced objects and values are appropriate to the current operation.
5. **Evidentiary:** The data actually substantiates the asserted facts.

The first four are principally runtime contract concerns. The fifth belongs primarily under factual verification.

### Error-Recovery Measurements

- Invalid-output detection rate.
- False rejection rate.
- Recovery success rate.
- Error propagation rate.
- Recovery latency.
- Recovery resource cost.
- Percentage of consequential boundaries with enforced contracts.

### Example Failure Conditions

- Missing required output field.
- Invalid support classification.
- Fabricated evidence identifier.
- Existing identifier that references the wrong result set.
- Structurally valid but semantically invalid tool parameters.
- Unexpected tool response.
- Database timeout.
- Partial query result.
- Repeated unsuccessful recovery.

Recovery should be appropriate to the failure, not merely an unconditional retry.

---

## 15. Verification and Factual Reliability

**Objective:** Determine whether the workflow adequately checks the groundedness, accuracy, consistency, and evidentiary
validity of intermediate and final conclusions, and appropriately handles verification failures.

**Research foundation:** RAGAS, RAGChecker, FActScore, FEVER, attribution evaluation, and faithful reasoning research.
[17], [23], [25], [26], [32], [45]

### Evaluation Criteria

| ID | Criterion | Required capability | Basis |
|---|---|---|---|
| V1 | Claim groundedness | Checks whether factual claims are supported by associated evidence | R [23], [25], [32] |
| V2 | Hallucination detection | Detects fabricated or unsupported claims, references, and conclusions | R [23], [25] |
| V3 | Inference validity | Distinguishes supported inferences from unsupported interpretation or speculation | R/E [24], [26], [45] |
| V4 | Claim-to-evidence verification | Determines whether cited evidence actually supports the particular attributed claim | R [26], [45] |
| V5 | Factual and logical consistency | Detects material inconsistencies, contradictions, and factual errors | R/E [23], [24] |
| V6 | Verifier reliability | Establishes whether the verification mechanism itself reliably distinguishes correct and incorrect results | R/E [17], [32] |
| V7 | Verification rejection and remediation | Ensures failed verification results are rejected or appropriately qualified, supports corrective investigation and reverification when feasible, and prevents unresolved verification failures from being treated as established evidence or successful conclusions | R/E [15], [23], [45] |
| V8 | Verification coverage | Ensures consequential factual claims, inferences, evidence associations, and generated conclusions receive appropriate verification, including after material changes | R/E [17], [25], [26], [45] |

### Verification Scope and Coverage

Verification should be applied at the level of granularity appropriate to the claims, evidence, and decisions being 
evaluated.

The evaluator should determine whether the system:

- Identifies which claims, findings, inferences, and conclusions require verification.
- Applies verification at appropriate points during acquisition, assessment, reasoning, and reporting.
- Verifies that evidence references identify the intended records and actually substantiate the associated claims.
- Detects unsupported reasoning even when the underlying retrieved information is accurate.
- Ensures significant changes to evidence, findings, or conclusions trigger appropriate reverification.
- Prevents consequential results from bypassing required verification.
- Accounts for verification coverage rather than assuming that the existence of a verification mechanism establishes 
  adequate use.

Verification need not occur after every operation or require a separate model invocation for every claim. The
architecture should provide appropriate coverage without introducing unnecessary computation.

### Verification Failure Handling

A failed verification must have an appropriate operational consequence.

The evaluator should determine whether the system:

1. Rejects or appropriately qualifies results that fail verification.
2. Identifies the nature of the failure sufficiently to guide corrective action.
3. Determines whether the deficiency can be addressed through corrected retrieval, additional evidence, revised 
   inference, or other remediation.
4. Supports corrective investigation and reassessment when appropriate.
5. Requires repaired or materially modified results to satisfy verification before acceptance.
6. Preserves unresolved failures and prevents rejected results from being treated as established.
7. Propagates unresolved deficiencies to evidence sufficiency, research completion, and reporting.
8. Supports justified termination when further attempts are unlikely to resolve the deficiency.

A verification failure does not necessarily require abandoning the research objective. However, repeated unsuccessful
repair attempts must not result in automatic acceptance or indefinite execution.

### Verification Mechanism Reliability

The existence of a verifier does not establish that its assessments are correct.

The evaluator should examine:

- Verification method selection and suitability.
- Deterministic and probabilistic verification mechanisms.
- Independence of verification from the process producing the result, where relevant.
- Reliability against independently established ground truth.
- False acceptance and false rejection rates.
- Verification consistency and repeatability.
- Confidence calibration where confidence estimates are used.
- Verification performance across different claim types and evidence structures.
- Whether verification failures can be detected independently of the verifier itself.

Verification mechanisms may use language models, deterministic procedures, external services, or combinations of
approaches. Their suitability should be established by demonstrated performance rather than implementation type.

### Suggested Measurements

- Verification coverage.
- Unsupported claim acceptance rate.
- False acceptance and false rejection rates.
- Incorrect evidence attribution rate.
- Verification consistency across repeated evaluations.
- Verification failure detection rate.
- Verification rejection enforcement rate.
- Successful remediation and reverification rate.
- Unresolved verification failure propagation.
- Verification latency and resource consumption.

### Important Distinctions

**Groundedness:** Does identified evidence from the graph support the statement?

**Factual correctness:** Is the statement actually true relative to independently established facts?

**Verification reliability:** Does the verification mechanism accurately identify correct and incorrect statements?

These are related but not equivalent. A claim may accurately reflect a retrieved source while being factually incorrect
because the source itself is incorrect. Likewise, an LLM-based verifier may confidently accept an unsupported claim.
Using a verification tool does not establish that the verification mechanism is reliable.

**Verification success does not establish research completeness.** A collection of individually verified findings may
still fail to satisfy the original question because required information was never acquired or assessed. Retrieval
coverage and research completeness are evaluated separately under Sections 10 and 13.

---

## 16. Termination and Outcome Management

**Objective:** Determine whether the workflow stops appropriately, accurately characterizes the outcome, and 
distinguishes execution completion from research completion.

**Research foundation:** Stop-RAG, Sufficient Context, NIST AI RMF, and workflow persistence guidance. 
[8], [12], [31], [33]

### Evaluation Criteria

| ID | Criterion | Required capability | Basis |
|---|---|---|---|
| TM1 | Objective-based completion | Determines success from satisfaction of research requirements rather than completion of planned operations | R/E [8], [12] |
| TM2 | Evidence-based completion | Uses evidentiary sufficiency when deciding whether research objectives are satisfied | R [8] |
| TM3 | Partial and inconclusive outcomes | Distinguishes completed, unresolved, unsupported, and inconclusive research | R/E [8] |
| TM4 | Adaptive stopping | Determines whether further research is warranted | R [12] |
| TM5 | Resource and progress limits | Applies appropriate limits to unproductive or excessive execution | R/G [1], [12] |
| TM6 | Error-aware termination | Handles unrecoverable errors without falsely reporting successful completion | G/E [31], [33] |
| TM7 | Quality-gated completion | Prevents completion when mandatory quality conditions are unmet | G/E [31] |
| TM8 | Outcome accounting | Records why execution stopped and what was or was not established | G/E [31], [33] |
| TM9 | Interruption and resumption | Supports appropriate cancellation, suspension, and continuation while preserving valid state | G [33] |

### Recommended Outcome Model

The evaluator should determine whether the system preserves three conceptual distinctions.

#### Research Disposition

- Complete.
- Partially complete.
- No adequately substantiated answer.

#### Execution Disposition

- Completed.
- Failed.
- Cancelled.
- Suspended or awaiting input.

#### Termination Reason

- Objectives satisfied.
- Evidence insufficient.
- Further research not justified.
- Required data unavailable.
- Resource budget exhausted.
- Unrecoverable execution error.
- User cancellation.
- External input required.

These distinctions need not be represented using a specific set of software enums.

### Critical Failure Scenarios

- All planned operations finish, but a required objective remains unsupported.
- An LLM requests completion despite unmet requirements.
- Verification fails, but the workflow continues to report success.
- Research succeeds, but report generation fails.
- Execution stops after partial success because of a resource limit.
- Repeated iterations fail to produce meaningful progress.
- Previously established evidence is lost during recovery.
- An unresolved contradiction is represented as a certain conclusion.

The workflow should preserve the distinction between a completed execution and a satisfactorily answered question.

---

# Part IV — Reporting, Memory, and Engineering Quality

## 17. Report Synthesis, Transparency, and Analyst Inspectability

**Objective:** Determine whether reports faithfully communicate established research, accurately represent its 
completeness and limitations, and provide sufficient transparency for analysts to inspect significant conclusions.

**Research foundation:** AIS attribution research, FActScore, RAGChecker, Beyond Correctness, and NIST AI RMF.
[17], [25], [26], [31], [45]

### Evaluation Criteria

| ID | Criterion | Required capability | Basis |
|---|---|---|---|
| T1 | Evidence-aligned reporting | Produces conclusions consistent with established findings and their limitations | R [25], [26], [45] |
| T2 | Accessible supporting evidence | Makes supporting evidence available for material report claims | R/S [19], [26] |
| T3 | Operational transparency | Exposes relevant workflow operations, decisions, outcomes, and limitations | G/E [31] |
| T4 | Accurate limitation disclosure | Reports unresolved questions, contradictions, qualifications, and failures | R/E [8], [31] |
| T5 | Independent analyst inspectability | Supports independent reconstruction and review of consequential conclusions | S/G [19], [31] |
| T6 | Report verification | Verifies that synthesized report content accurately reflects established findings, preserves evidentiary support, and does not introduce unsupported claims or conclusions | R/E [25], [26], [32], [45] |
| T7 | Report completeness | Ensures the report adequately communicates the established research, addresses the original information requirements, and does not omit material findings, qualifications, or unresolved obligations | R/E [8], [17], [25] |

### Report Integrity

Report generation must preserve the meaning, evidentiary support, and limitations of the research results used to 
produce it.

The evaluator should determine whether the system:

- Accurately represents established findings and their evidentiary support.
- Avoids introducing unsupported facts, interpretations, or conclusions during synthesis.
- Preserves important distinctions between observations, derived conclusions, and unresolved propositions.
- Correctly attributes material claims to their supporting evidence.
- Maintains consistency across report sections and related conclusions.
- Applies appropriate verification to the final report or its consequential claims.
- Detects and addresses discrepancies introduced during report generation.

A report may be internally consistent and contain individually supported statements while still misrepresenting the
research through selective presentation, incorrect synthesis, or omission of material information.

### Report Completeness

Report completeness must be evaluated against both the original information requirements and the actual research
outcomes.

The evaluator should determine whether the report:

- Addresses each material component of the original question.
- Includes significant established findings relevant to those requirements.
- Preserves necessary relationships and dependencies among findings.
- Does not silently omit contradictory or qualifying evidence.
- Accurately communicates the extent of research completeness.
- Identifies material requirements that remain unresolved or unsupported.
- Distinguishes information that was not established from information that was established but omitted during synthesis.

**Research completeness and report completeness are distinct.** A workflow may adequately establish the required
information but produce an incomplete report. Conversely, a report may faithfully represent incomplete research while
appropriately disclosing its limitations. The latter is not necessarily a reporting failure.

### Transparency and Analyst Inspectability

Reports should provide sufficient information for an analyst to understand the basis of consequential conclusions and,
when appropriate, reconstruct how those conclusions were established.

The evaluator should examine:

- Accessibility and correctness of supporting evidence references.
- Traceability from report claims to established research findings.
- Traceability from findings to underlying evidence and source material.
- Visibility of material research decisions, assumptions, and transformations.
- Availability of relevant execution history and verification outcomes.
- Ability to inspect conflicting evidence and material qualifications.
- Ability to independently assess significant conclusions without relying solely on the report's assertions.

**Answer transparency:** Why is a particular conclusion supported?

**Operational transparency:** How did the system obtain, assess, validate, and use the evidence?

Both are important for analyst-facing applications. The required level of operational detail should reflect the
significance of the conclusions and the intended use of the report.

### Uncertainty and Limitation Disclosure

Reports must accurately communicate material uncertainty and limitations without presenting unsupported certainty.

The evaluator should determine whether the system appropriately reports:

- Research objectives that were not satisfied.
- Evidence that was unavailable or insufficient.
- Conflicting or contradictory findings.
- Material assumptions and qualifications.
- Limitations in source coverage or retrieval completeness.
- Verification failures that affect reported conclusions.
- Partial, inconclusive, or otherwise qualified research outcomes.
- Confidence estimates where they are used and can be meaningfully supported.

Uncertainty should reflect the evidentiary status of the research rather than merely the confidence expressed by a
language model.

### Suggested Measurements

- Unsupported claim rate in generated reports.
- Report claim-to-evidence attribution accuracy.
- Material finding omission rate.
- Original information requirement coverage.
- Accuracy of reported research completeness.
- Accuracy of uncertainty and limitation disclosure.
- Report verification failure detection rate.
- Cross-section factual and logical consistency.
- Supporting evidence accessibility and reference correctness.
- Independent analyst reconstruction success.
- Report generation and verification latency.

### Important Distinctions

**Finding correctness:** Are the established research findings supported and valid?

**Report faithfulness:** Does the report accurately represent those findings without introducing unsupported content?

**Report completeness:** Does the report adequately communicate the established research and address the original
information requirements?

**Report inspectability:** Can an analyst independently examine the evidence and reasoning underlying consequential
conclusions?

These are related but independently assessable properties. Correct findings do not guarantee a faithful or complete
report, and an accurately written report does not establish that the underlying research was correct.

The report-generation process must therefore be included in the overall reliability assessment.

---

## 18. Persistent Workflow Memory and Continuous Improvement

**Objective:** Determine whether workflow execution information is persistently stored, retrievable, structured, and 
useful for analysis and improvement.

**Research foundation:** CoALA, Reflexion, Agent Workflow Memory, and Neo4j Agent Memory documentation. 
[13], [14], [34], [35]

### Evaluation Criteria

| ID | Criterion | Required capability | Basis |
|---|---|---|---|
| WM1 | Execution history persistence | Records material workflow executions, decisions, outcomes, and failures | R/G [14], [35] |
| WM2 | Structured execution traceability | Preserves relationships among tasks, operations, inputs, outputs, agents, and tools | R/G [13], [35] |
| WM3 | Durable historical retrieval | Makes execution information available after the originating workflow terminates | R/G [13], [35] |
| WM4 | Cross-execution analysis | Supports identification of recurring failure modes and successful strategies | R [14], [34] |
| WM5 | Workflow improvement support | Provides evidence useful for improving workflow behavior, tools, planning, and configuration | R [14], [34] |
| WM6 | Memory quality and integrity | Preserves correct execution context, scope, versioning, and interpretability | R/E [13], [34] |
| WM7 | Neo4j Agent Memory integration | Persists required workflow information using the specified project technology | P/G [35] |

### Project Requirement

**PR9:** Required workflow information must be persisted using Neo4j Agent Memory. This is mandatory project 
compliance.

### Important Distinction

Persistence alone does not establish useful workflow memory. A system might store extensive logs without enabling useful 
analysis of its prior behavior.

The evaluation should determine whether historical information supports questions such as:

- Which research objectives fail repeatedly?
- Which acquisition strategies succeed?
- Which verification steps produce frequent rejections?
- Which workflow stages account for significant latency?
- Which failure modes cause repeated replanning?
- What changed between successful and unsuccessful executions?
- Which execution strategies could inform future tradecraft?

### Suggested Acceptance Tests

1. Successful execution is persisted.
2. Failed execution is persisted.
3. Material decisions are reconstructable.
4. Tool operations are associated with their originating tasks.
5. Historical results are retrievable.
6. Similar execution patterns can be compared.
7. Workflow changes can be correlated with results.
8. Memory access respects appropriate authorization.
9. Execution history remains interpretable across versions.

Automatic self-improvement is not assumed to be mandatory unless separately required.

---

## 19. Appropriate Allocation of Deterministic and Probabilistic Computation

**Objective:** Determine whether the architecture assigns reasoning, decision-making, computation, and validation to 
mechanisms appropriate to their requirements.

**Research foundation:** Anthropic agent guidance, Google architecture guidance, PAL, Satyrn, and symbolic knowledge 
graph question answering. [1], [2], [6], [36], [37]

### Evaluation Criteria

| ID | Criterion | Required capability | Basis |
|---|---|---|---|
| D1 | Appropriate LLM usage | Uses model reasoning where semantic flexibility, interpretation, or adaptability adds material value | G [1], [2] |
| D2 | Appropriate deterministic processing | Uses explicit algorithms, rules, computations, and validation when they can meet requirements more reliably | R/G [1], [36], [37] |
| D3 | Controlled probabilistic decisions | Validates or constrains consequential model-generated decisions where appropriate | R/E [30], [36] |
| D4 | Efficient computational allocation | Avoids unnecessary model calls and repeated probabilistic work without sacrificing quality | G/R [1], [2], [7] |
| D5 | Demonstrated architectural effectiveness | Measures correctness, consistency, performance, and cost to substantiate the chosen allocation | R/E [7], [17], [37] |

### Evaluation Principle

Use the mechanism best suited to the responsibility.

LLMs may be appropriate for:

- Natural-language interpretation.
- Semantic reasoning.
- Open-ended research planning.
- Ambiguity resolution.
- Strategy generation.
- Complex evidence interpretation.

Conventional mechanisms may be appropriate for:

- Database queries.
- Arithmetic.
- Aggregation.
- Schema validation.
- Enumerated-value validation.
- Referential integrity.
- Deterministic transformations.
- Explicit state transitions.
- Well-defined computations.

These are examples, not universal assignments.

### Important Qualifications

- Deterministic behavior does not guarantee correctness.
- A deterministic mechanism can consistently produce an incorrect result.
- LLM reasoning may be more suitable for genuinely semantic tasks.
- Generating deterministic procedures with an LLM does not eliminate the need to validate those procedures.
- A hybrid architecture is not automatically superior.
- Comparative outcomes should determine architectural quality.

### Suggested Measurements

- Correctness.
- Run-to-run consistency.
- LLM invocation count.
- End-to-end latency.
- Model and tool costs.
- Failure rate.
- Error recovery cost.
- Ability to handle unforeseen cases.
- Maintainability.

The evaluator should not automatically penalize an architecture for extensive LLM use. It should determine whether that 
use is justified by the task and its observed performance.

---

## 20. Testability and Demonstrated Reliability

**Objective:** Determine whether the architecture supports reproducible testing and meaningful measurement of research
correctness, reliability, and performance, including whether changes in the architecture or implementation affect
investigative outcomes.

**Research foundation:** RAGChecker, AgentBench, RAGAS, NIST AI RMF, structured-output benchmark research, faithful
reasoning evaluation, and GraphRAG evaluation guidance. [17], [30], [31], [32], [38], [45], [46]

### Evaluation Criteria

| ID | Criterion | Required capability | Basis |
|---|---|---|---|
| X1 | Deterministic workflow testing | Supports testing orchestration independently of live LLM variability | G/E [1], [31] |
| X2 | Execution path coverage | Tests representative success, failure, recovery, and exceptional paths | G/E [31], [38] |
| X3 | Representative evaluation scenarios | Maintains realistic cases with independently established expected outcomes | R/G [17], [38], [46] |
| X4 | Measured research quality | Quantifies retrieval, evidence, verification, and answer-quality characteristics | R/G [17], [32], [45], [46] |
| X5 | Reproducible regression testing | Supports comparison across software, model, configuration, and workflow changes | G/E [30], [31] |
| X6 | Evaluation validity | Establishes that evaluation methods, reference expectations, and quality measurements reliably identify the deficiencies they are intended to detect, without masking failures or overstating effectiveness | R/E [17], [32], [38] |
| X7 | End-to-end workflow regression testing | Supports repeatable execution of complete research workflows across successful, unsuccessful, incorrect, and unrecoverable-error scenarios, validating expected outcomes and detecting behavioral regressions after implementation, model, configuration, or workflow changes | G/E [31], [38] |

### Testing Scope and Coverage

The evaluator should determine whether the system supports appropriate testing at different levels of execution and
whether consequential behavior can be examined independently.

Relevant testing capabilities include:

- Unit testing of individual components and deterministic operations.
- Integration testing across agents, tools, data sources, and workflow boundaries.
- End-to-end testing against representative research questions.
- Deterministic agent-response simulation for orchestration testing.
- State-transition and workflow-invariant testing.
- Runtime contract and interface testing.
- Fault injection and recovery testing.
- Query correctness and retrieval coverage testing.
- Evidence assessment and verification accuracy testing.
- Final report correctness and completeness testing.
- Security and trust-boundary testing where applicable.

Testing coverage should reflect the responsibilities and failure modes of the implementation. The rubric does not 
require a particular testing framework, test organization, or implementation strategy.

### Evaluation Scenarios and Ground Truth

Evaluation scenarios should represent the research requirements, data characteristics, and operational conditions the
system is expected to handle.

The evaluator should examine:

- Whether scenarios include simple, complex, ambiguous, and multi-step research questions.
- Whether expected outcomes are established independently of the system being evaluated.
- Whether retrieval correctness and completeness can be evaluated against appropriate reference data.
- Whether scenarios include misleading, contradictory, incomplete, and unavailable evidence.
- Whether tests exercise unsuccessful acquisition, invalid findings, and verification rejection.
- Whether scenarios distinguish correct partial or inconclusive outcomes from incorrectly reported success.
- Whether the evaluation includes cases designed to expose known failure modes.
- Whether test coverage adequately represents the intended range of supported research questions.

Ground truth may include independently constructed queries, verified reference datasets, manually established answers,
controlled synthetic cases, or other defensible reference expectations.

Not every research question permits an exhaustive ground-truth answer. Where complete ground truth is unavailable,
the evaluator should distinguish directly established correctness from estimated quality or unverified assumptions.

### Evaluation Methodology and Validity

An evaluation mechanism must be capable of detecting the failures it is intended to measure.

The evaluator should determine whether:

- Metrics accurately represent the quality characteristics they purport to measure.
- Evaluation distinguishes retrieval quality from evidence assessment, reasoning, and report generation quality.
- Correctness of returned information is distinguished from completeness of retrieved information.
- Empty results are evaluated against expected retrieval behavior rather than automatically considered successful.
- Incorrect queries and incomplete retrieval can be detected even when returned records are individually valid.
- Expected answers and evaluation references are established independently of the system's generated output.
- Evaluation procedures distinguish unsupported claims from omitted information.
- Automated or LLM-based judges are tested against known correct and incorrect cases.
- Evaluation results are reproducible and sufficiently documented for independent inspection.
- Scoring methods do not conceal material failures through averaging or inappropriate treatment of missing results.

High evaluation scores do not establish reliability when the evaluation mechanism is incapable of detecting important
classes of failure. Evaluation validity must therefore be assessed independently of the quality scores it produces.

### End-to-End Workflow Regression Testing

The system should support repeatable execution of complete research workflows with controlled inputs and independently
established expected outcomes. These tests should establish that the workflow produces appropriate results, state
transitions, and termination dispositions across successful and unsuccessful scenarios.

Representative scenarios should include:

| Scenario | Expected behavior |
|---|---|
| Successful research | Produces the correct answer with adequate evidence, appropriate verification, and successful completion |
| Incorrect retrieval | Detects incorrect or incomplete acquisition and performs appropriate correction or reports the limitation |
| Incorrect evidence assessment | Rejects unsupported findings and performs corrective investigation when feasible |
| Verification failure | Enforces rejection, supports appropriate remediation, and prevents unsupported acceptance |
| Recoverable execution error | Recovers appropriately while preserving valid research state |
| Unrecoverable execution error | Terminates with an accurate failure disposition without falsely reporting research success |
| Insufficient evidence | Preserves unresolved requirements and reports partial or inconclusive results when appropriate |
| Incorrect research planning | Recognizes planning inadequacy and adapts, or accurately reports the resulting limitation |
| Incorrect final report | Detects or prevents unsupported claims, omissions, and misrepresented research outcomes |
| Interrupted execution | Preserves appropriate state and supports justified resumption or termination |

The evaluator should determine whether:

- Complete workflows can be executed repeatedly using controlled test conditions.
- Test scenarios establish expected research outcomes as well as expected execution behavior.
- Known failures can be reproduced through deterministic fixtures, simulated agent responses, controlled data, or fault 
  injection.
- Assertions examine relevant intermediate state, evidence, verification outcomes, and final dispositions.
- Regression tests distinguish expected failure handling from unintended workflow failure.
- Changes to orchestration, prompts, models, tools, configurations, and data-access mechanisms can be evaluated against 
  prior behavior.
- Regression results identify which scenarios changed, what behavior changed, and whether the change constitutes an 
  improvement or deficiency.
- Automated regression testing can detect previously resolved failures that reappear after implementation changes.

A workflow that terminates without an exception has not necessarily succeeded. Likewise, a workflow that correctly
identifies an unrecoverable condition and reports failure may have behaved exactly as required.

### Reproducibility and Change Assessment

Testing should provide a defensible basis for evaluating the effects of implementation changes.

The evaluator should examine:

- Versioning of software, models, prompts, configurations, and test datasets.
- Preservation of test inputs, expected outcomes, and observed results.
- Repeatability of deterministic execution paths.
- Measurement of variability in probabilistic execution.
- Comparison of results across versions and configurations.
- Identification of changes affecting correctness, completeness, reliability, or performance.
- Regression thresholds and criteria for accepting or rejecting changes.
- Availability of historical test results for investigation.

Deterministic agent-response simulation can establish whether orchestration correctly handles known inputs and
conditions. It cannot independently establish whether production LLMs correctly perform semantic reasoning or factual
evaluation. Both controlled workflow testing and representative live-model evaluation are necessary to establish
different aspects of reliability.

### Suggested Reliability Measures

- End-to-end scenario success rate.
- Correct outcome classification rate.
- Incorrect successful-completion rate.
- Error detection and recovery success rates.
- Unrecoverable-error handling correctness.
- Retrieval correctness and completeness.
- Evidence assessment accuracy.
- Unsupported claim acceptance rate.
- Verification failure enforcement rate.
- Report faithfulness and completeness.
- Regression detection rate.
- Execution path and scenario coverage.
- Run-to-run consistency.
- Latency and resource-consumption distributions.
- Evaluation false acceptance and false rejection rates.

### Important Distinctions

**Orchestration correctness:** Does the workflow execute the intended control logic and maintain valid state?

**Research correctness:** Does the workflow obtain and establish information that correctly answers the research
requirements?

**Evaluation validity:** Do the evaluation methods accurately detect the successes and deficiencies they claim to 
measure?

**Regression reliability:** Can the system detect changes that compromise previously demonstrated behavior or outcomes?

These are distinct but complementary concerns. A workflow may execute exactly as designed while producing an incorrect
answer. A correct answer may result from an execution containing serious defects. An evaluation may report excellent
results while overlooking consequential failures.

The assessment should establish whether the implementation can test these properties independently and demonstrate
their effectiveness across representative end-to-end scenarios.

---

## 21. Security, Governance, and Trust Boundaries

**Objective:** Determine whether the architecture protects data, workflow state, tools, and research integrity from
unauthorized access, disclosure, manipulation, or execution, and enforces applicable security controls throughout
research processing.

**Research foundation:** OWASP LLM security guidance, NIST AI RMF, Neo4j graph security documentation, and established
access-control engineering principles. [28], [31], [39], [47]

### Evaluation Criteria

| ID | Criterion | Required capability | Basis |
|---|---|---|---|
| G1 | Untrusted input isolation | Prevents retrieved content and tool responses from becoming unauthorized instructions or influencing execution beyond their intended evidentiary role | G [28], [39] |
| G2 | Access and authority control | Enforces appropriate authorization for users, agents, tools, data sources, and operations, including restrictions on the information each may access | G [28], [39] |
| G3 | Data and execution integrity | Protects data and workflow state against unauthorized or unintended modification | G/E [31], [39] |
| G4 | Auditability and governance | Supports appropriate access logging, execution accountability, policy enforcement, and configuration control | G [31] |
| G5 | Tool and operation safety | Constrains agent-generated tool calls, queries, and executable operations according to authorized capabilities and applicable security requirements | G/E [28], [39] |
| G6 | Data confidentiality and isolation | Prevents unauthorized disclosure or cross-boundary exposure of information through retrieval, processing, persistent state, and generated outputs | G/E [28], [31], [39] |
| G7 | Persistent state and memory security | Protects workflow memory, checkpoints, and retained execution information against unauthorized access, manipulation, or inappropriate reuse | G/E [31], [35], [39] |
| G8 | Adversarial robustness | Evaluates whether applicable security and trust boundaries remain effective under malicious or manipulated inputs, retrieved content, and tool responses | G/E [28], [31], [39] |
| G9 | Fine-grained graph authorization | Enforces applicable access restrictions on graph entities, relationships, properties, and query results according to the requesting user's authorization, including dynamically generated queries and derived results | G/E [31], [39], [47] |

### Trust Boundaries and Untrusted Content

Retrieved documents, graph properties, external tool results, and other acquired information may contain content
intended to influence an agent's behavior. The workflow must distinguish information used as research evidence from
instructions that the system is authorized to execute.

The evaluator should determine whether the system:

- Maintains appropriate trust boundaries between instructions, tools, and retrieved information.
- Recognizes and appropriately handles prompt injection and malicious content in retrieved evidence.
- Prevents tool responses from introducing unauthorized instructions or expanding agent authority.
- Handles manipulated, misleading, or poisoned retrieval content without compromising security controls.
- Prevents unauthorized instructions from propagating through intermediate research artifacts or persistent memory.
- Applies appropriate validation and restrictions before executing consequential operations.

The architecture need not use a particular prompt-injection defense or trust-boundary mechanism. Its protections
should be evaluated according to the actual threats and demonstrated behavior.

### Authorization and Data Protection

Authorization must be enforced at the granularity required by the data and deployment environment.

The evaluator should examine:

- Authentication and authorization of requesting users and services.
- Authorization of agents, tools, data sources, and permitted operations.
- Propagation of the requesting user's authorization context through research operations.
- Enforcement of least-privilege access where applicable.
- Protection against unauthorized retrieval or disclosure of sensitive information.
- Isolation between users, projects, sessions, and research contexts.
- Appropriate handling of missing, invalid, or expired authorization.
- Protection of acquired information throughout evidence processing, reporting, and persistence.

Successful authentication or authorization to invoke a tool does not necessarily establish authorization to access
all information available through that tool.

### Fine-Grained Graph Authorization

Knowledge graphs may contain entities, relationships, and properties with different access restrictions. A user
authorized to access one portion of the graph may not be authorized to access related entities, individual properties,
or information derived through graph operations.

The evaluator should determine whether the architecture:

- Supports heterogeneous access restrictions across graph entities, relationships, and properties.
- Enforces the requesting user's applicable permissions during graph retrieval and traversal.
- Prevents dynamically generated queries from bypassing authorization restrictions.
- Restricts access to protected properties and relationships even when their associated entities are accessible.
- Prevents unauthorized information disclosure through aggregations, counts, rankings, traversals, and derived results.
- Applies authorization consistently across direct queries, retrieval tools, and multi-step research operations.
- Prevents restricted data from reaching an LLM or other unauthorized processing component.
- Preserves applicable information restrictions through findings, reports, caches, and persistent workflow memory.
- Handles missing authorization context and authorization failures without defaulting to unrestricted access.
- Supports appropriate testing of authorized and unauthorized access under representative graph-query scenarios.

Authorization may be enforced through database security mechanisms, controlled query interfaces, query rewriting,
result filtering, or other suitable approaches. The implementation must demonstrate that its chosen mechanisms
prevent unauthorized access and disclosure.

Filtering a final report is not sufficient protection if unauthorized information has already been disclosed to an
agent or processing component that was not permitted to receive it.

### Tool and Execution Safety

Agent-generated operations may introduce security risks that do not arise from conventional predefined application
queries or service calls.

The evaluator should determine whether the system:

- Restricts executable operations to authorized tools and capabilities.
- Validates consequential tool parameters and generated queries.
- Prevents unauthorized database modifications or administrative operations.
- Constrains executable code where code execution is supported.
- Prevents operations from exceeding the requesting user's authority.
- Handles attempted privilege escalation or unauthorized tool use.
- Maintains appropriate boundaries between research operations and system administration.
- Detects and responds appropriately to unsafe or prohibited operations.

A read-only research workflow may satisfy these requirements through comparatively simple restrictions. An
implementation with broader execution capabilities may require additional controls.

### Persistent State and Memory Security

Research workflows may retain evidence, user information, reasoning artifacts, execution traces, and other
potentially sensitive information beyond the originating execution.

The evaluator should examine:

- Authorization of access to stored workflow information.
- Isolation of persistent information across users and research contexts.
- Prevention of unauthorized modification of retained evidence and execution state.
- Protection against inappropriate reuse of information from unrelated or unauthorized workflows.
- Preservation of applicable security context during interruption, recovery, and resumption.
- Appropriate handling of information retention and deletion requirements.
- Auditability of consequential memory access and modification.

Persistent memory must not become an alternative path for bypassing authorization restrictions applied during
the original acquisition.

### Adversarial Testing and Governance

Security controls should be evaluated against realistic attempts to violate the trust boundaries applicable to
the implementation.

Representative scenarios include:

- Prompt injection embedded in retrieved documents or graph properties.
- Malicious instructions introduced through tool responses.
- Unauthorized graph traversal or property access.
- Agent-generated queries attempting to bypass data restrictions.
- Unauthorized access through aggregation or derived information.
- Cross-user or cross-project information exposure.
- Unauthorized tool invocation or privilege escalation.
- Manipulation of persistent memory or execution state.
- Exposure of restricted information through generated reports.
- Recovery or resumption under missing or changed authorization context.

The evaluator should determine whether protections are enforced by the architecture and implementation rather
than relying solely on an LLM's willingness to follow security instructions.

Security testing should reflect the system's actual capabilities, deployment environment, data sensitivity,
and applicable threat model.

### Suggested Measurements

- Unauthorized data-access prevention rate.
- Fine-grained graph authorization enforcement accuracy.
- Unauthorized property and relationship disclosure rate.
- Prompt-injection attack success rate.
- Unsafe tool-operation rejection rate.
- Cross-context information leakage rate.
- Authorization failure-handling correctness.
- Persistent memory isolation effectiveness.
- Security regression test coverage.
- Audit completeness for consequential operations.

### Important Distinctions

**Tool authorization:** Is an agent permitted to invoke a particular operation?

**Data authorization:** Is the requesting user permitted to access the information involved in that operation?

**Graph-level authorization:** Are applicable permissions enforced for individual entities, relationships, properties,
and derived information?

**Trust-boundary enforcement:** Can untrusted information influence operations beyond its authorized role?

These are related but independently assessable responsibilities. An agent may be authorized to execute a read-only
query without being authorized to retrieve every record that query could return.

The required controls must reflect the actual deployment environment. However, an architecture intended to support
heterogeneous graph data must provide an enforceable mechanism for respecting the applicable access restrictions
rather than assuming uniform authorization across the graph.

---

## 22. Performance, Scalability, and Maintainability

**Objective:** Determine whether the architecture delivers required research quality with acceptable resource
consumption, scales appropriately with data volume, workload, and question complexity, and supports sustainable
engineering, extension, and operational management.

**Research foundation:** Anthropic and Google agent architecture guidance, Adaptive-RAG, Stop-RAG, NIST AI RMF,
and workflow orchestration engineering guidance. [1], [2], [7], [12], [31], [33]

### Evaluation Criteria

| ID | Criterion | Required capability | Basis |
|---|---|---|---|
| F1 | Computational efficiency | Uses models, retrieval operations, and other computational resources proportionately without unnecessary execution or degradation of required research quality | G/R [1], [7], [12] |
| F2 | Scalability | Maintains acceptable behavior as data volume, concurrent workload, and research complexity increase | G/E [2], [31] |
| F3 | Performance | Meets appropriate latency, throughput, and resource-consumption requirements across representative workloads | R/E [7], [12] |
| F4 | Maintainability | Supports understandable, configurable, modular, and reasonably replaceable components without disproportionate engineering complexity | G/E [1], [2] |
| F5 | Architectural extensibility | Accommodates new research capabilities, retrieval methods, tools, verification mechanisms, and workflow behaviors through appropriate interfaces and extension points without disproportionate architectural changes | G/E [1], [2], [33] |
| F6 | Workload-adaptive execution | Adjusts research strategy, computational effort, model usage, and execution complexity according to question requirements, estimated difficulty, and observed progress | R/G [7], [12] |
| F7 | Operational observability | Provides sufficient visibility into workflow execution, component behavior, resource consumption, failures, and performance characteristics to support diagnosis, measurement, and improvement | G/E [2], [31], [33] |

### Computational Efficiency and Performance

The evaluator should determine whether the architecture uses computational resources appropriately while preserving the 
correctness, completeness, and reliability required by the research task.

Relevant considerations include:

- Number and cost of LLM invocations.
- Sequential versus parallel execution.
- Retrieval and database query efficiency.
- Batching of related operations.
- Redundant computation and repeated retrieval.
- Reuse of established results.
- Caching and its effects on correctness and freshness.
- Context-window utilization and management.
- Tool invocation overhead.
- Data transfer and serialization costs.
- Verification and evaluation overhead.
- Resource limits and execution budgets.
- End-to-end latency and throughput.

Performance must be evaluated relative to the requirements of the research task. A faster execution is not necessarily 
better when it sacrifices evidentiary sufficiency, factual correctness, or required verification.

The evaluator should distinguish computational cost that provides demonstrable value from overhead caused by unnecessary 
processing, inefficient orchestration, or architectural constraints.

### Scalability

The architecture should support acceptable behavior as workload characteristics change.

The evaluator should examine scalability with respect to:

- Number of records, entities, and relationships in underlying data sources.
- Size and complexity of retrieved result sets.
- Complexity and depth of graph traversals.
- Number of required research objectives and dependencies.
- Number of research iterations and corrective operations.
- Concurrent research executions.
- Model and tool service capacity.
- Persistent workflow state and execution history.
- Memory and context requirements.
- Network and data-transfer demands.
- Database contention and resource availability.
- Increasing verification and reporting workloads.

Scalability should be evaluated through representative measurements rather than assumptions about the underlying
technology or architectural style.

The evaluator should determine whether increased workload produces proportionate resource consumption or introduces
significant bottlenecks, contention, instability, or unacceptable degradation.

### Workload-Adaptive Execution

Different research questions may require substantially different levels of investigation.

The evaluator should determine whether the workflow:

- Recognizes differences in expected research complexity.
- Selects appropriate retrieval methods and tools for the question.
- Avoids unnecessarily elaborate processing for straightforward requests.
- Allocates additional investigation and verification effort when justified by complexity or uncertainty.
- Adjusts execution strategy when observed difficulty differs from initial expectations.
- Supports appropriate model selection or routing where beneficial.
- Controls the number and depth of research iterations.
- Balances execution cost against the value of additional evidence or verification.
- Avoids premature termination merely to satisfy performance objectives.
- Supports configurable execution limits or quality requirements where appropriate.

Adaptive behavior need not require dedicated complexity-classification components or multiple execution modes. The 
relevant capability is adjusting research effort appropriately to the requirements and circumstances.

### Architectural Extensibility

The evaluator should determine whether the existing architecture can accommodate additional capabilities without
requiring disproportionate changes or introducing excessive coupling.

Relevant considerations include:

- Availability and suitability of component interfaces and extension points.
- Ability to introduce new research tools and retrieval techniques.
- Support for complementary or hybrid retrieval strategies.
- Ability to extend query expressiveness and supported research operations.
- Ability to introduce new evidence assessment or verification mechanisms.
- Ability to incorporate additional data sources and domain models.
- Support for new workflow behaviors and research strategies.
- Ability to replace or upgrade models, tools, and external services.
- Separation of research orchestration from data access and presentation concerns.
- Dependencies that constrain the introduction of new functionality.
- Compatibility and versioning of interfaces and persisted data.
- Effects of extensions on existing functionality, reliability, and performance.

Extensibility must be assessed against the implementation's actual interfaces, dependencies, and architectural
constraints. Theoretical flexibility or the availability of a general-purpose programming language does not establish
that a capability can be integrated efficiently into the existing architecture.

The evaluator should distinguish capabilities that can be added through existing extension mechanisms from those
requiring substantial restructuring or architectural replacement.

### Maintainability

The evaluator should examine whether the implementation can be understood, modified, tested, and operated without
disproportionate engineering effort.

Relevant considerations include:

- Separation of responsibilities and concerns.
- Component cohesion and coupling.
- Clarity of interfaces and runtime contracts.
- Understandability of workflow definitions and state transitions.
- Configuration management and environment portability.
- Dependency management and version compatibility.
- Error handling and diagnostic consistency.
- Testability of individual components and integrated workflows.
- Ability to modify behavior without introducing unrelated changes.
- Documentation of consequential architectural decisions.
- Complexity introduced by custom orchestration or infrastructure.
- Maintainability of prompts, schemas, tools, and model integrations.

The evaluator should distinguish complexity that is justified by the requirements from unnecessary complexity.

A simpler implementation should not automatically receive a higher maintainability score. The assessment should consider 
whether its apparent simplicity is achieved by omitting required capabilities or shifting responsibilities to external 
components.

### Operational Observability

The architecture should expose sufficient operational information to understand how research executions behave, identify 
deficiencies, and evaluate the effects of changes.

The evaluator should determine whether the system provides:

- Traceability of workflow stages, research objectives, and tool operations.
- Timing and resource measurements for consequential operations.
- Visibility into LLM invocation counts, latency, and resource consumption.
- Query execution timing and database-related performance information.
- Identification of execution bottlenecks and excessive repetition.
- Visibility into failures, retries, recovery, and termination reasons.
- Diagnostic information for incomplete or unexpectedly expensive research.
- Correlation of operations and results within a research execution.
- Comparability of performance across executions and software versions.
- Sufficient information to investigate performance regressions.

Observability should provide actionable diagnostic information rather than merely generating extensive logs. Operational 
measurements should be associated with the relevant execution context so that performance and failure patterns can be 
meaningfully analyzed.

### Suggested Measurements

- End-to-end research latency.
- Latency distribution by question complexity.
- Per-stage execution time.
- LLM invocation count and cost.
- Database query latency and resource consumption.
- Tool invocation count and overhead.
- Retrieval and verification overhead.
- Concurrent execution throughput.
- Performance degradation as workload increases.
- Memory and persistent-state resource consumption.
- Redundant operation rate.
- Successful adaptation to unexpected question complexity.
- Time and scope of changes required to introduce new capabilities.
- Regression frequency following implementation changes.
- Diagnostic completeness for failed or degraded executions.
- Time required to identify significant performance bottlenecks.

### Important Distinctions

**Performance:** How quickly and efficiently does the system perform its work under specified conditions?

**Scalability:** How does system behavior change as data volume, concurrency, and research complexity increase?

**Maintainability:** How readily can the implementation be understood, modified, corrected, and sustained?

**Extensibility:** How readily can the existing architecture accommodate new capabilities and requirements?

**Workload adaptability:** Does the system allocate effort appropriately to the needs and observed complexity of the
research task?

**Observability:** Can engineers determine what happened during execution and identify the causes of failures or
performance deficiencies?

These are related but independently assessable properties. An implementation may perform efficiently on current 
workloads while being difficult to extend. Another may be highly extensible but introduce unacceptable execution
overhead. A system may also perform poorly because of implementation defects rather than fundamental architectural
limitations.

Performance, scalability, and maintainability must be evaluated in the context of the system's required capabilities.
Efficiency gains must not compensate for fundamental failures of correctness, evidentiary integrity, verification, or 
mandatory security controls.

# Part V — Project Compliance and Common Evaluation

## 23. Non-Negotiable Project Requirements

Mandatory acceptance requirements should be assessed separately from weighted architectural scores.

### 23.1 Confirmed Project Requirements

| ID | Requirement | Evaluation expectation |
|---|---|---|
| PR6 | Ontology integration | The provided ontology must meaningfully assist in answering research requests |
| PR9 | Neo4j Agent Memory | Required workflow execution information must be persisted using Neo4j Agent Memory |
| PR10 | Provenance | Provenance must be used when assessing retrieved results |

### 23.2 Proposed Acceptance Gates

The following are proposed from the intended use of accurate, verifiable, actionable information. They should be 
confirmed against formal customer acceptance requirements.

| ID | Requirement | Evaluation expectation |
|---|---|---|
| PR1 | Evidence grounding | Consequential factual conclusions have adequate evidentiary support or appropriate qualification |
| PR2 | Evidence provenance | Supporting evidence is available or recoverable for independent review |
| PR3 | Accuracy controls | Unsupported factual conclusions are detected and appropriately handled |
| PR4 | Incomplete evidence handling | Inadequate support does not silently become a completed conclusion |
| PR5 | Semantic integrity | Research operations preserve the meaning and constraints of the data |
| PR7 | Operational integrity | Errors and invalid states do not silently produce successful outcomes |
| PR8 | Analyst inspectability | Consequential conclusions and their supporting research can be independently examined |

An architecture can score highly on general quality while failing a mandatory project requirement. Conversely, meeting a 
project-specific technology requirement does not automatically establish architectural quality.

---

## 24. Common Evaluation Scenarios

A standardized benchmark should exercise comparable responsibilities across the three implementations.

### 24.1 Question Understanding

- Ambiguous terminology.
- Undefined concepts.
- Conflicting constraints.
- Entity ambiguity.
- Unsupported assumptions.
- Material semantic misinterpretation.

### 24.2 Feasibility

- Clearly infeasible request.
- Partially feasible request.
- Difficult but answerable request.
- Missing tool capability.
- Newly discovered constraint.
- Incorrect initial feasibility estimate.

### 24.3 Decomposition and Planning

- Simple factual question.
- Multi-hop question.
- Missing research objective.
- Redundant research objective.
- Incorrect dependency.
- Newly discovered prerequisite.
- Unexpected task complexity.

### 24.4 Research Obligation Management

- Unresolved objective spanning iterations.
- Objective lost during replanning.
- Superseded objective.
- Partially satisfied objective.
- Repeated attempts without progress.

### 24.5 Acquisition

- Syntactically valid but incorrect query.
- Semantically incorrect retrieval.
- Irrelevant result set.
- Incomplete result set.
- Truncated result set.
- Incorrect aggregation.
- Duplicated records.
- Multi-hop retrieval.
- Empty result versus failed retrieval.
- Missing provenance.
- Deferred provenance retrieval.
- Unrecoverable source material.

### 24.6 Evidence Assessment

- Direct support.
- Contradictory evidence.
- Partial support.
- Multiple required records.
- Relevant but insufficient evidence.
- Qualified support.
- Unsupported inference.
- Invalid evidence reference.

### 24.7 Validation and Recovery

- Invalid output schema.
- Missing required field.
- Invalid enumeration.
- Fabricated identifier.
- Contextually invalid identifier.
- Tool timeout.
- Plausible but incorrect tool result.
- Failed recovery.
- Successful recovery with preserved state.

### 24.8 Completion and Termination

- All requirements satisfied.
- Required objective unsupported.
- Partial success.
- Unresolved contradiction.
- Resource budget exhausted.
- Unrecoverable error.
- Premature completion request.
- Report generation failure following successful research.

### 24.9 Reporting

- Unsupported claim introduced during synthesis.
- Material qualification omitted.
- Invalid citation.
- Partial findings represented as complete.
- Report inconsistent with research state.
- Incorrect confidence characterization.

### 24.10 Memory

- Successful execution persisted.
- Failed execution persisted.
- Historical execution reconstructed.
- Similar failure patterns identified.
- Workflow versions compared.
- Historical results analyzed.

### 24.11 Security

- Retrieved prompt injection.
- Unauthorized tool request.
- Unauthorized data access.
- Malicious tool response.
- Memory access isolation failure.

---

## 25. Structured Assessment Record

Each evaluated criterion should produce a record containing the following information.

### 25.1 Criterion Identification

- Criterion ID.
- Criterion name.
- Definition.
- Applicability.
- Supporting references.
- Strength of research support.

### 25.2 Architecture Assessment

- Score.
- Observed design.
- Mechanisms.
- Architectural constraints.
- Supporting evidence.

### 25.3 Implementation Assessment

- Score.
- Implemented behavior.
- Enforcement mechanisms.
- Deficiencies.
- Supporting evidence.

### 25.4 Effectiveness Assessment

- Score.
- Test scenarios.
- Measured outcomes.
- Reliability measurements.
- Supporting evidence.

### 25.5 Overall Assessment

- 3 Final scores per criterion.
- Assessment confidence.
- Scoring rationale.
- Significance of the capability.
- Consequences of deficiencies.

### 25.6 Deficiency Analysis

The evaluator should distinguish:

- Missing capabilities.
- Partially implemented capabilities.
- Demonstrated defects.
- Unverified capabilities.
- Architectural limitations.
- Potential risks.

### 25.7 Remediation Analysis

Architectural remediation feasibility must be evaluated against the actual architecture and implementation under 
assessment. For each material gap, the evaluator must identify the relevant existing components, interfaces, extension 
points, dependencies, and architectural constraints, supported by specific implementation evidence. Feasibility must 
reflect the changes necessary within that architecture, not the ease of implementing the capability in a hypothetical 
alternative architecture. Proposed remediation must identify the affected implementation locations and the specific 
changes required to establish the missing capability.

For each material deficiency, assess:

1. Whether the current architecture can support the missing capability.
2. Whether existing mechanisms can be extended.
3. Whether significant architectural changes are necessary.
4. What dependencies affect remediation.
5. Which alternative mechanisms are viable.
6. What tests would establish successful remediation.
7. What level of disruption remediation would introduce.

### 25.8 Evaluation Constraints

The evaluator must:

- Cite actual implementation evidence.
- Avoid inventing implementation details.
- Distinguish absent functionality from missing evidence.
- Explain the significance of important omissions.
- Identify realistic paths to improvement.
- Avoid assuming architectural replacement is necessary.
- Avoid overstating confidence.
- Record unresolved assessment questions.

### 25.9 Reusable Per-Criterion Assessment Template

The following template defines the required structure for assessing an implementation against the criteria in this 
rubric. Each applicable rubric section must be identified, and each criterion within that section must receive an
individual assessment. The template is defined once rather than repeated for each section or criterion.

Each criterion assessment must identify significant supporting capabilities, deficiencies, architectural remediation
feasibility, and requirements for addressing identified gaps. Findings must be individually identifiable and supported
by specific, independently inspectable implementation evidence. Source-code references must identify relevant files,
symbols, and precise code locations where available. Runtime evidence must identify relevant tests, execution traces,
logs, or observed results.

Architectural remediation feasibility must be assessed against the actual architecture and implementation under
evaluation, considering existing components, interfaces, extension points, dependencies, and constraints. Remediation
recommendations must identify the specific changes needed within that architecture rather than proposing hypothetical
alternatives without considering the existing design.

The evaluator must distinguish demonstrated deficiencies from capabilities that could not be adequately assessed.
Missing documentation alone does not establish that a capability is absent. Planned but unimplemented capabilities must 
receive an Implementation score of zero, consistent with Section 2.4.

```text
IMPLEMENTATION: <KEA-RAG | KEA-MCP | KDA>

SECTION: <section-id> — <section-name>

  ITEM: <criterion-id> — <criterion-name>

  SCORES:
    Architecture and design: <0–4 | not assessed  | not applicable>
    Implementation: <0–4 | not assessed | not applicable>
    Demonstrated Effectiveness: <0–4 | not assessed | not demonstrated | not applicable>

  SUPPORT DETAILS
    <individually identified capabilities that satisfy the criterion,
     with specific implementation evidence and references>

  SUPPORT GAPS
    <individually identified deficiencies, their significance, and
     specific implementation evidence and references>

  ARCHITECTURAL GAP REMEDIATION FEASIBILITY
    <for each identified gap, how readily the existing architecture
     can accommodate remediation, with supporting evidence>

  GAP REMEDIATION REQUIREMENTS
    <for each identified gap, the specific changes required to address
     it and how successful remediation would be established>

  <Repeat ITEM for each criterion in the section.>

<Repeat SECTION for each applicable section in the rubric.>

REPORT CONCLUSION AND ASSESSMENT COVERAGE

<A section each, named "Architecture Rating", "Implementation Rating", and "Demonstrated Effectiveness Rating">:
  Total report points possible: <sum indicating the highest possible score from all reportable criteria>
  Total assessable points: <sum indicating the highest possible score from assessable criteria>
  Total score: <sum from all criteria assessments>
  Percent total: <percentage of total report points possible>
  Percent assessable: <percentage of total assessable points>

FAILED MANDATORY REQUIREMENTS

<identifiers of mandatory requirements determined to be unmet, or none>

OVERALL ASSESSMENT / SUMMARY / ACTION ITEMS
<This section addresses something the numerical scores and individual findings don't: what the assessment actually means 
for using and improving the system.>

System Strengths:
<An explanation of use cases where this system is likely to perform well. This can include the types of questions that
this system could likely answer well and correctly. Be sure to distinguish use cases supported by actual test results 
from those inferred from architectural capabilities. This section can list highlights and aspects that seem 
particularly good.>

System Limitations:
<An explanation of use cases where this system is likely to perform poorly, struggle, or fail. This can include the 
types of questions that this system is not likely to answer well or correctly. Be sure to distinguish between use cases 
supported by actual test results, source-code inspection, or an architectural constraint/capability. This section can 
list the aspects that seem particularly weak and in need of prioritized or immediate improvement.>

Architectural Assessment:
<Provide an overall assessment of the system's architecture and design, considering its suitability for the intended 
research responsibilities, coherence of its components and interfaces, separation of concerns, allocation of 
responsibilities, extensibility, maintainability, and architectural constraints.

Evaluate whether the architecture provides a sound foundation for reliable agentic research and whether its design can 
accommodate missing or future capabilities without disproportionate restructuring. Distinguish fundamental architectural 
limitations from implementation deficiencies that can be corrected within the existing design.

Identify particularly effective or problematic architectural decisions, their consequences, and significant technical 
tradeoffs. Support conclusions with specific architectural or implementation evidence rather than general impressions.>

Assessment Deficiencies:
<For each criterion that could not be adequately assessed, identify the criterion, explain why the assessment could not 
be completed, and specify what additional evidence, access, testing, or other information would be required to reach a 
defensible conclusion. When feasible and applicable, explain how the missing information or evidence could be obtained 
or produced to support a future assessment.>

Improvement Plan:
<Include a concise, prioritized plan to improve the system. Prioritize improvements by their consequences, not simply by 
their scores. Consider listing sections that contain crucial items, best ROI items, easy/quick fixes, simple errors, 
etc., depending on what has been found during analysis and may be of particular interest or help to the user that 
receives the report.>
```

Each support finding and gap must be separately identifiable, allowing its evidence and corresponding remediation 
analysis to be traced without ambiguity. Multiple findings may be provided under each heading as necessary. The 
assessment must not combine unrelated deficiencies into a single finding or substitute general conclusions for
specific implementation evidence.

For every material gap, the evaluator must identify its architectural remediation feasibility and the changes required 
to address it. Where remediation cannot be adequately assessed, the evaluator must identify the missing information 
rather than speculate. The remediation analysis must remain consistent with the architecture actually examined.

The report conclusion must distinguish the total available score from the score that could be established using 
available assessment evidence. Confirmed deficiencies must receive their appropriate scores and must not be excluded
from the assessable-point total. Criteria that genuinely cannot be evaluated must not be assigned zero solely because of 
insufficient access or evidence.

Mandatory requirements must be evaluated independently of numerical scoring. Any mandatory requirement determined to be 
unmet must be explicitly identified in the report conclusion, regardless of the overall assessment score.

## 26. Static and Dynamic Evaluation

### 26.1 Static Architecture Assessment

Inspect:

- Architecture documentation.
- Source code.
- Workflow definitions.
- State models.
- Interfaces.
- Contracts.
- Agent responsibilities.
- Tool boundaries.
- Verification mechanisms.
- Persistence mechanisms.
- Test infrastructure.

Determine whether the architecture deliberately supports each required capability.

### 26.2 Implementation Assessment

Inspect actual runtime enforcement and operational behavior. Capabilities described only in documentation should not 
receive full implementation credit.

### 26.3 Dynamic Evaluation

Execute standardized scenarios and compare observed results with independently established expectations.

Measure:

- Correctness.
- Coverage.
- Consistency.
- Error recovery.
- Evidence integrity.
- Factual accuracy.
- Performance.
- Reproducibility.

### 26.4 Comparative Assessment

Apply identical criteria to comparable responsibilities. Differences in system scope must be documented. A component 
should not automatically be penalized for lacking functionality outside its agreed responsibility. For integration 
analysis, assess whether missing capabilities must be supplied by another component.

### 26.5 Assessment Confidence

Assessment confidence must remain independent of the score. An implementation may have a strong design but insufficient 
available evidence for a high-confidence assessment.

### 26.6 Final Scoring

At this time, all criteria have equal weight. Adding weights for items with higher consequence, etc., will be 
considered in the future.

---

# Part VI — Bibliography

## 27. Reference Sources

The references below provide the research and engineering foundation for the candidate requirements. They do not 
necessarily prescribe the exact architectural requirements in this document. Where a criterion extends a research 
finding into a proposed systems-engineering requirement, that distinction is identified through its basis 
classification.

### 27.1 Agent Architecture, Question Understanding, and Planning

1. **Anthropic (2024). _Building Effective Agents_.**  
   Industry guidance distinguishing predefined workflows from autonomous agents, emphasizing simplicity, predictability, and appropriate agent use.  
   [Source][1]

2. **Google Cloud. _Choose a Design Pattern for Your Agentic AI System_.**  
   Architecture selection guidance addressing orchestration, task characteristics, complexity, latency, and agent autonomy.  
   [Source][2]

3. **Kim et al. (2023). _Tree of Clarifications: Answering Ambiguous Questions with Retrieval-Augmented Large Language Models_. EMNLP 2023.**  
   Research addressing ambiguity and alternative interpretations in retrieval-based question answering.  
   [Source][3]

4. **_OG-RAG: Ontology-Grounded Retrieval-Augmented Generation for Large Language Models_. EMNLP 2025.**  
   Research investigating how domain ontologies can guide retrieval and improve factual question answering.  
   [Source][4]

5. **W3C (2017). _Shapes Constraint Language (SHACL)_.**  
   Formal standard for expressing and validating constraints over RDF graph data.  
   [Source][5]

6. **Agarwal et al. (2024). _SymKGQA: Few-Shot Knowledge Graph Question Answering via Symbolic Program Generation and Execution_. ACL 2024.**  
   Research on combining language-model interpretation with symbolic knowledge-graph operations.  
   [Source][6]

7. **Jeong et al. (2024). _Adaptive-RAG: Learning to Adapt Retrieval-Augmented Large Language Models through Question Complexity_. NAACL 2024.**  
   Research on selecting retrieval strategies according to question complexity.  
   [Source][7]

8. **Joren et al. (2025). _Sufficient Context: A New Lens on Retrieval-Augmented Generation Systems_. ICLR 2025.**  
   Research distinguishing sufficient from insufficient retrieval context and examining answer generation versus abstention.  
   [Source][8]

9. **_ADaPT: As-Needed Decomposition and Planning with Language Models_. Findings of NAACL 2024.**  
   Research on decomposing difficult tasks when execution reveals that further refinement is needed.  
   [Source][9]

10. **_Optimizing Question Semantic Space for Dynamic Retrieval-Augmented Multi-hop Question Answering (Q-DREAM)_. ACL 2025.**  
    Research addressing semantic reformulation and dynamic multi-hop retrieval.  
    [Source][10]

11. **Ammann et al. (2025). _Question Decomposition for Retrieval-Augmented Generation_. ACL Student Research Workshop.**  
    Research on using decomposition to retrieve complementary evidence for multi-hop questions.  
    [Source][11]

12. **Park et al. (2025). _Stop-RAG: Value-Based Retrieval Control for Iterative RAG_.**  
    Research on adaptive stopping decisions for iterative retrieval, including the cost and accuracy consequences of additional retrieval.  
    [Source][12]

### 27.2 Persistent Research State and Agent Memory

13. **Sumers et al. (2023). _Cognitive Architectures for Language Agents (CoALA)_.**  
    Conceptual framework for agent memory, action, and decision-making.  
    [Source][13]

14. **Shinn et al. (2023). _Reflexion: Language Agents with Verbal Reinforcement Learning_. NeurIPS 2023.**  
    Research on using feedback and retained reflections to improve subsequent agent behavior.  
    [Source][14]

### 27.3 Evidence Retrieval and Acquisition

15. **Yan et al. (2024). _Corrective Retrieval Augmented Generation (CRAG)_.**  
    Research on evaluating retrieval quality and correcting inadequate retrieved context.  
    [Source][15]

16. **Asai et al. (2024). _Self-RAG: Learning to Retrieve, Generate, and Critique through Self-Reflection_. ICLR 2024.**  
    Research integrating retrieval decisions and critique into language-model generation.  
    [Source][16]

17. **Ru et al. (2024). _RAGChecker: A Fine-Grained Framework for Diagnosing Retrieval-Augmented Generation_. NeurIPS 2024.**  
    Fine-grained evaluation framework distinguishing retrieval and generation quality and providing diagnostic metrics.  
    [Source][17]

18. **Chauhan et al. (2025). _Mind the Query: A Benchmark Dataset towards Text2Cypher Task_. EMNLP Industry Track.**  
    Research on natural-language-to-Cypher query generation and evaluation.  
    [Source][18]

### 27.4 Provenance and Evidence Traceability

19. **W3C (2013). _PROV-O: The PROV Ontology_.**  
    Formal representation of provenance involving entities, activities, agents, and derivations.  
    [Source][19]

20. **W3C (2013). _PROV-AQ: Provenance Access and Query_.**  
    Mechanisms for discovering, accessing, and querying provenance information.  
    [Source][20]

21. **W3C (2013). _PROV-DM: The PROV Data Model_.**  
    Conceptual model supporting representation of provenance and derivation relationships.  
    [Source][21]

22. **_ProVe: Automated Provenance Verification of Knowledge Graphs_. Semantic Web.**  
    Research addressing whether source documents actually substantiate knowledge-graph statements.  
    [Source][22]

### 27.5 Evidentiary Support and Factual Assessment

23. **Thorne et al. (2018). _FEVER: A Large-Scale Dataset for Fact Extraction and Verification_. NAACL 2018.**  
    Benchmark for evaluating claims as supported, refuted, or lacking sufficient information.  
    [Source][23]

24. **_FEVEROUS: Fact Extraction and Verification over Unstructured and Structured Information_. 2021.**  
    Fact-verification work involving textual and structured evidence, including combinations of evidence.  
    [Source][24]

25. **Min et al. (2023). _FActScore: Fine-Grained Atomic Evaluation of Factual Precision in Long-Form Text Generation_. EMNLP 2023.**  
    Fine-grained factual precision evaluation using atomic factual content.  
    [Source][25]

26. **Rashkin et al. (2023). _Measuring Attribution in Natural Language Generation Models_. Computational Linguistics.**  
    Establishes an attribution evaluation framework for determining whether generated statements are supported by identified sources.  
    [Source][26]

### 27.6 Runtime Contracts and Validation

27. **JSON Schema. _Draft 2020-12 Specification_.**  
    Standardized mechanisms for defining and validating structured data contracts.  
    [Source][27]

28. **OWASP. _Top 10 for LLM Applications_.**  
    Security guidance covering prompt injection, excessive agency, unsafe handling of untrusted information, and related risks.  
    [Source][28]

29. **OpenAPI Initiative. _OpenAPI Specification_.**  
    Specification for describing API interfaces, operations, and data contracts.  
    [Source][29]

30. **Geng et al. (2025). _JSONSchemaBench: A Rigorous Benchmark of Structured Outputs for Language Models_.**  
    Empirical evaluation of constrained structured-output generation, schema coverage, and output quality.  
    [Source][30]

### 27.7 Reliability, Verification, and Execution Control

31. **NIST (2023). _AI Risk Management Framework, AI RMF 1.0_.**  
    Framework covering AI risk identification, measurement, governance, reliability, transparency, and accountability.  
    [Source][31]

32. **Es et al. (2023). _RAGAS: Automated Evaluation of Retrieval Augmented Generation_.**  
    Framework for evaluating RAG properties including faithfulness and retrieval-related quality.  
    [Source][32]

33. **LangChain. _LangGraph Persistence Documentation_.**  
    Technical documentation for checkpointing and persistent workflow state, including interruption and recovery capabilities.  
    [Source][33]

### 27.8 Workflow Memory and Improvement

34. **Wang et al. (2025). _Agent Workflow Memory_. ICML 2025.**  
    Research on retaining and reusing prior agent workflows to improve execution of later tasks.  
    [Source][34]

35. **Neo4j Labs. _Neo4j Agent Memory_.**  
    Product documentation describing structured graph-backed agent memory, including reasoning traces and execution history.  
    [Source][35]

### 27.9 Deterministic and Probabilistic Processing

36. **Gao et al. (2023). _PAL: Program-Aided Language Models_. ICML 2023.**  
    Research using language models to construct programs while delegating computations to conventional execution.  
    [Source][36]

37. **Sterbentz et al. (2024). _Satyrn: A Platform for Analytics Augmented Generation_. EMNLP 2024.**  
    Research using structured analytics to establish facts before language-model report generation.  
    [Source][37]

### 27.10 Agent Evaluation

38. **Liu et al. (2024). _AgentBench: Evaluating LLMs as Agents_. ICLR 2024.**  
    Benchmark framework examining language-model agent performance in interactive environments.  
    [Source][38]

### 27.11 Security

39. **OWASP GenAI Security Project (2026). _Top 10 for LLM Applications_.**  
    Updated security guidance for LLM-based applications and related agentic risks.  
    [Source][39]

### 27.12 Hybrid Retrieval and Graph Embeddings

40. **Neo4j. _Hybrid Search_.**  
    Technical guidance on combining lexical and vector retrieval, ranking fusion, and graph expansion.  
    [Source][40]

41. **Microsoft. _Relevance Scoring in Hybrid Search Using Reciprocal Rank Fusion (RRF)_.**  
    Technical documentation for merging ranked retrieval results from multiple search methods.  
    [Source][41]

42. **Wang et al. (2025). _Balancing the Blend: An Experimental Analysis of Trade-offs in Hybrid Search_.**  
    Empirical study of trade-offs among full-text, sparse-vector, dense-vector, and tensor search methods and their combinations.  
    [Source][42]

43. **Grover and Leskovec (2016). _node2vec: Scalable Feature Learning for Networks_. KDD 2016.**  
    Research on learning node representations from graph structure for downstream tasks including link prediction.  
    [Source][43]

44. **Neo4j. _Node Embeddings — Graph Data Science Manual_.**  
    Technical documentation on graph embedding algorithms and their use in graph-based machine learning.  
    [Source][44]

### 27.13 Faithful Reasoning in Agentic Retrieval

45. **Xu et al. (2026). _Beyond Correctness: Rewarding Faithful Reasoning in Retrieval-Augmented Generation_. Transactions on Machine Learning Research.**  
    Research evaluating faithfulness across reasoning-to-search, retrieved-information-to-reasoning, and reasoning-to-answer transitions in agentic search.  
    [Source][45]

### 27.14 GraphRAG Engineering and Evaluation

46. **Bratanič and Hane (2025). _Essential GraphRAG_. Manning Publications.**  
    Practical engineering guidance covering knowledge-graph retrieval, schema-grounded Text2Cypher, hybrid search, agentic retrieval and critique, and evaluation using representative benchmarks and ground-truth queries.  
    [Source][46]

### 27.15 Data Security: Fine-Grained Access Control

47. **Neo4j. _Fine-Grained Access Control_.**
    Product documentation describing role-based authorization and fine-grained
    access restrictions for graph data, including nodes, relationships, and properties.
    [Source][47]

---

## 28. Reference Link Definitions

The following are standard Markdown reference definitions.

[1]: https://www.anthropic.com/engineering/building-effective-agents
[2]: https://docs.cloud.google.com/architecture/choose-design-pattern-agentic-ai-system/
[3]: https://aclanthology.org/2023.emnlp-main.63/
[4]: https://aclanthology.org/2025.emnlp-main.1674/
[5]: https://www.w3.org/TR/shacl/
[6]: https://aclanthology.org/2024.acl-long.545/
[7]: https://aclanthology.org/2024.naacl-long.389/
[8]: https://proceedings.iclr.cc/paper_files/paper/2025/hash/33dffa2e3d2ab74a783d1a8c292f66d9-Abstract-Conference.html
[9]: https://aclanthology.org/2024.findings-naacl.264/
[10]: https://aclanthology.org/2025.acl-long.871/
[11]: https://aclanthology.org/2025.acl-srw.32/
[12]: https://arxiv.org/abs/2510.14337
[13]: https://arxiv.org/abs/2309.02427
[14]: https://proceedings.neurips.cc/paper_files/paper/2023/hash/1b44b878bb782e6954cd888628510e90-Abstract-Conference.html
[15]: https://arxiv.org/abs/2401.15884
[16]: https://arxiv.org/abs/2310.11511
[17]: https://proceedings.neurips.cc/paper_files/paper/2024/hash/27245589131d17368cccdfa990cbf16e-Abstract.html
[18]: https://aclanthology.org/2025.emnlp-industry.133/
[19]: https://www.w3.org/TR/prov-o/
[20]: https://www.w3.org/TR/prov-aq/
[21]: https://www.w3.org/TR/prov-dm/
[22]: https://journals.sagepub.com/doi/full/10.3233/SW-233467
[23]: https://aclanthology.org/N18-1074/
[24]: https://aclanthology.org/2021.fever-1.1/
[25]: https://aclanthology.org/2023.emnlp-main.741/
[26]: https://aclanthology.org/2023.cl-4.2/
[27]: https://json-schema.org/draft/2020-12
[28]: https://owasp.org/projects/top-10-for-large-language-model-applications/
[29]: https://spec.openapis.org/oas/
[30]: https://arxiv.org/abs/2501.10868
[31]: https://airc.nist.gov/airmf-resources/airmf/5-sec-core/
[32]: https://arxiv.org/abs/2309.15217
[33]: https://docs.langchain.com/oss/python/langgraph/persistence
[34]: https://proceedings.mlr.press/v267/wang25bx.html
[35]: https://neo4j.com/labs/agent-memory/
[36]: https://proceedings.mlr.press/v202/gao23f.html
[37]: https://aclanthology.org/2024.emnlp-main.365/
[38]: https://arxiv.org/abs/2308.03688
[39]: https://genai.owasp.org/resource/owasp-genai-llm-top-10-2026/
[40]: https://neo4j.com/developer/genai-ecosystem/hybrid-search/
[41]: https://learn.microsoft.com/en-us/azure/search/hybrid-search-ranking
[42]: https://arxiv.org/abs/2508.01405
[43]: https://pmc.ncbi.nlm.nih.gov/articles/PMC5108654/
[44]: https://neo4j.com/docs/graph-data-science/current/machine-learning/node-embeddings/
[45]: https://arxiv.org/abs/2510.13272
[46]: https://go.neo4j.com/rs/710-RRC-335/images/Essential-GraphRAG.pdf
[47]: https://neo4j.com/docs/operations-manual/current/authentication-authorization/access-control/

---

### Final Evaluation Principle

The objective is not to identify the architecture with the most agents, the most elaborate design, or the greatest 
number of implemented features. The objective is to determine which architecture most effectively delivers accurate, 
consistent, evidence-based, inspectable, and reliable research outcomes. Where deficiencies exist, the assessment should 
identify their significance and the most appropriate path toward improvement.

**End of Working Draft — Version 1.0**