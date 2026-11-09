# Findings Verification Enhancement Ideas for Investigation

One aspect of the agentic rag workflow that is expensive is the verification of findings. This process involves checking
the faithfulness of the findings through invocations of ragas. When the question is simple and when the amount of data
is not particularly large, the process still seems to be rather long and expensive. I want to explore some strategies or
experiments to improve this process.

This is intended as ways to explore improvements, rather than prescriptive approaches.

## 1. Explore the reduction of examined data volume

Check the volume of examined data when ragas is invoked on a finding. Is the entire evidence data or query result
examined? Or is there some indexed subset that is given to ragas with the finding? If that is true, then we should add a
step to the findings creation process that points to the actual records within the evidence data that is specifically
relevant to the finding.

### 1.1. Examine "JSON Pointer" for specifying the relevant records

**JSON Pointer (RFC 6901)**: Identifies a specific location in a JSON document, such as
`/results/3/publications/2/title`.

A JSON pointer may be particularly applicable here because we preserve the MCP query results verbatim, and those records
are considered immutable for the entire workflow lifecycle. The query is not re-executed, so any pointers will remain
stable and valid for examination, and even when the results are persisted. The caveat is that we cannot later update any
results if the database is updated and not have to go through the entire analysis and verification process again. That
should be a full re-execution of the workflow, even if the question is identical.

The LLM call that creates a finding needs to be able to accurately and reliably identify the relevant records that
pertain directly to the finding. Whether the LLM can be trusted to specify the pointer correctly (ever single time) 
remains to be seen. But if there is a way that it can identify the relevant records, and then the exact pointer can be
programmatically determined, that might be a more reliable approach. There would likely be a list of one or more JSON
pointers for later examination.

Whenever a finding is examined, the JSON pointers can be used to programmatically access the relevant records. Those
records would be provided for examination. When there is genuinely a lot of data to be examined, the cost savings might
be less significant, but that is a problem that cannot be entirely reduced, since we want to balance efficiency with
accuracy. There must be enough information to protect against hallucination and invalid reasoning.

### 1.2. Examine JSONPath for specifying the relevant records

**JSONPath (RFC 9535)**: Can select values based on structure, including arrays, nested objects, and filters. Its
normalized paths can uniquely identify individual nodes within a particular JSON document.

This approach is probably more complex, and we should hold off on experimenting with this unless and until the JSON
pointer approach is proven to be inadequate, and unless this approach appears to be a likely better alternative.

## 2. Consider using a simpler LLM for Ragas faithfulness

MiniCheck and HHEM are specific model families that may be simpler alternatives that could reduce cost (time and money).
If our environment only provides access to certain Bedrock-hosted models, they may not be practical options. Therefore,
this is only an option if MiniCheck or HHEM models are available through Bedrock. After that, it remains to be seen if
their performance realizes a performance benefit that justifies using separate models for this purpose.

## 3. Consider making acceptance or rejection of faithfulness programmatic

After performing Ragas faithfulness evaluations of findings, they can be accepted or rejected based on those evaluation
results. Instead of using an LLM to make this decision, it could be a matter of using an acceptance threshold.

Examine how faithfulness scores are calculated for individual findings, particularly when each finding references a
single atomic assertion, to determine whether a numerical acceptance threshold is meaningful.

## 4. Consider how Ragas groundedness is used for criterion-level verification

If groundedness is used to examine every atomic statement under a criterion, this is probably not the best approach,
since it would not provide significant benefit over the faithfulness evaluation of each atomic assertion.

The purpose would be to determine whether the findings collectively establish the overall criterion, rather than 
repeating the faithfulness evaluation of each atomic assertion. This would provide an additional check that the atomic 
assertions and their supporting findings adequately preserve the planner's intent for the criterion.

The groundedness evaluation should consider the full criterion statement, the associated findings, and any relevant 
deficiencies or limitations. It should determine whether the findings collectively provide adequate support for the 
criterion, including any reasoning or conclusions that depend on multiple atomic assertions.

If the individual atomic assertions are supported but the overall criterion is not adequately grounded, this could 
indicate a problem with the decomposition, missing information, or an unsupported inference. Such discrepancies should 
be examined rather than automatically overriding the existing verification results.

Examine whether groundedness is currently performing redundant evaluations and whether performing it once per criterion 
would improve performance. The evaluation should reuse existing findings and verification results where appropriate, 
without unnecessarily reexamining all original evidence data.

If this approach is adopted, criterion-level groundedness would be performed after the individual findings have 
undergone faithfulness verification and acceptance. Thus, only accepted findings would be used for this evaluation. The 
groundedness results would then be available to the final adversarial review, along with the status of the atomic 
assertions and any remaining deficiencies, to determine whether the criterion is adequately supported or requires 
further work.

## 5. Consider whether an adversarial review is necessary after findings have been established

If we accept/reject findings based on faithfulness scores, and evaluate the groundedness of the criterion "as a whole" 
using the accepted findings (assuming that this approach is adopted), then the current findings-stage adversarial
review may not be necessary. It may not provide significant additional value over what has already been established
through these evaluations.

Examine what the existing adversarial review actually does and whether its responsibilities are adequately covered by
faithfulness verification, criterion-level groundedness, or the subsequent overall complete-question review. If it
performs evaluations that are not covered elsewhere, determine whether those evaluations are necessary and whether they
could be handled more efficiently without introducing redundant LLM operations.

If the adversarial review is no longer necessary, consider how the findings step should be modified to respond to
rejected findings, insufficient criterion-level groundedness, or other deficiencies identified during verification.
These situations may require additional evidence acquisition, invoking the existing feature of further processing the 
existing evidence, criterion modification, or something else. Determine whether the existing workflow mechanisms can 
handle these situations without requiring another adversarial LLM review.

Eliminating this review could improve performance by avoiding an expensive LLM invocation, but only if doing so does not
remove a meaningful validation responsibility.

## 6. Consider the responsibilities of the overall "complete question" review

The overall complete-question review already examines the original question and the work performed by the workflow to
determine whether there is enough information to produce an adequate answer. If faithfulness and criterion-level
groundedness have already established the support for individual findings and criteria, then this review should focus on
whether the research as a whole is sufficient, rather than repeating those earlier evaluations.

Consider the following:

- Does satisfying the criteria actually answer the original research question?

  This is probably the most important remaining responsibility. The planning process decomposes the original question
  into criteria, but even if every criterion is adequately supported, the complete set of criteria might not fully
  address what the user asked. For example, a question asking for the most influential researchers might be decomposed
  into publication counts and topic relevance. Both could be well supported, but influence may also require citations or
  other measures. This would not be a failure of finding faithfulness or criterion groundedness, but a potential failure
  to preserve the original question's meaning during planning.

- Are there contradictions or inconsistencies across accepted findings or criteria?

  Each individual finding may be supported by its evidence, and each criterion may appear grounded, while findings
  across different criteria conflict. For example, two findings might reach incompatible conclusions because they use
  different time periods, population definitions, or query scopes. The overall reviewer should identify material
  inconsistencies that were not apparent during criterion-level verification.

- Are the criteria collectively sufficient, including required dependencies?

  Even when all planned criteria have been satisfied, the resulting information may not support the intended synthesis.
  For example, a comparative conclusion might depend on consistent definitions and comparable samples across multiple
  criteria. Each criterion could be grounded independently without establishing that the comparison is valid. The
  reviewer should examine how the results fit together, rather than simply whether each component passed its individual
  evaluations.

- Are there unresolved limitations that materially affect the answer?

  Some criteria might remain incomplete because data is unavailable, insufficient, or contradictory. The reviewer should
  determine whether those limitations prevent an adequate answer or whether a qualified answer is still possible, and
  whether additional research would be useful or necessary.

Assuming the earlier verification stages are functioning properly, it might not be necessary for the overall
complete-question reviewer to routinely reevaluate individual atomic assertions against their source evidence,
recalculate faithfulness or groundedness, reconsider every accepted finding independently, or repeat criterion-level
support assessments. Those operations could still be requested when the reviewer discovers a concrete inconsistency or
deficiency, but they should not be part of its normal responsibilities.

The purpose of this review would remain determining whether the research is sufficient to answer the original question,
whether additional work is required, or whether the workflow should proceed with an answer that acknowledges its
limitations. This is a distinct responsibility from verifying individual findings or determining whether a particular
criterion is grounded.

## 7. Consider whether groundedness should be used for final answer, report verification, or both

Also consider whether groundedness should be used when evaluating the final answer or generated report, particularly to 
identify conclusions or interpretations introduced during synthesis that are not supported by the accepted findings. 
This should be considered separately from criterion-level groundedness to avoid redundant verification. My primary
concern is that, for the final answer or for the generated report, groundedness may be a very time-expensive operation
that would delay the already time-expensive report generation process.

## 8. Important note!

This is the only prescriptive portion of this document.

Satisfaction and completeness of a criterion is not determined by Ragas evaluation. Ragas evaluation is a method of
scoring criterion-related information to assist with satisfaction and completeness determination.

---

# Other Items To Check

There are some other items to discuss that are separate from the enhancements mentioned above. These are items to check
against the current implementation and consider as additions. When writing this, I am not entirely sure of the current 
implementation details, so we should discuss any inconsistencies before work is carried out.

## 1. Findings types

Findings might not always indicate support for a criterion's atomic statement. Evidence could lead to a finding that
indicates a contradiction, even when other evidence leads to a finding that indicates support. Both findings could be
valid and independently verified, since a finding being faithful to its evidence does not necessarily mean that other
evidence cannot contradict it. Consider the following table for possible findings types:

| Finding type | Evidence role |
|------------------------|--------------------------------------------------------------------------------|
| SUPPORTS | provides affirmative support for the assertion |
| CONTRADICTS | supports a conclusion inconsistent with the assertion |
| QUALIFIES | adds conditions/exceptions to, or narrows, the assertion |
| PARTIAL | establishes some portion of the assertion but not everything it claims |
| CONTEXTUALIZES | informs interpretation of the assertion without supporting or contradicting it |
| CHALLENGES | raises a specific concern about the validity or reliability of the assertion |

If we modify findings to specify these types, we will also need to determine how to handle types other than `SUPPORTS`
in the workflow. For example, how should an atomic assertion be assessed when it has both a `SUPPORTS` finding and a
`CONTRADICTS` finding? The presence of contradictory findings does not necessarily indicate a deficiency in the findings
or verification process. Both findings might be adequately grounded in their respective evidence, and the contradiction
may represent a legitimate inconsistency in the available information rather than something that needs to be corrected.

Examine whether multiple findings associated with the same atomic assertion can independently support, contradict,
qualify, or otherwise inform the assessment of that assertion. When conflicting evidence is discovered, the system 
should be able to retain the findings, preserve their provenance, explicitly represent the contradiction, and determine 
whether previously accepted findings require reassessment. The criterion assessment should consider the combined 
implications of all accepted findings rather than treating each finding independently as sufficient to establish the 
assertion. Determine whether the existing findings processing and overall review mechanisms can adequately handle these 
situations, including unresolved contradictions, without requiring additional review mechanisms.

## 2. Deficiency dispositions

While a deficiency identifies what is incorrect, missing, etc., it should have a disposition that indicates how that
deficiency should be handled. For example:

- an assertion might be unsupported by its referenced evidence
- its evidence selection might be incomplete
- its supporting finding might fail verification

Those situations potentially require different corrective actions, rather than treating every failed verification as a 
generic rejection.

Examine whether the findings verification process distinguishes different types of deficiencies and produces actionable
outcomes. Determine whether existing mechanisms can appropriately handle them through:

- evidence reselection
- additional processing of existing evidence
- further acquisition
- finding correction
- criterion revision
- recording an unresolved limitation

The disposition should identify the corrective action appropriate to the deficiency and allow the workflow to route that 
work to the responsible mechanism without requiring another adversarial LLM review when the verification result already 
provides sufficient information.

Also distinguish the disposition of a deficiency from its resolution status. The disposition identifies what should be
done, while the resolution status indicates whether the deficiency has been resolved, rejected as invalid, or remains
outstanding. Consider whether these distinctions can be represented and tracked using existing workflow state, and
whether they provide enough information to avoid repeating unsuccessful corrective actions or reopening work that has
already been satisfactorily addressed.

## 3. Deferred criterion instances

Determine the precise conditions under which a criterion may be deferred, including whether deferral represents an 
unresolved dependency, a requirement for further decomposition, or work that must cross a stage boundary. Establish 
which corrective or additional operations belong within the current acquisition or findings invocation, and which 
require another planning cycle. Ensure that deferred criteria preserve their outstanding requirements and the reasons 
for deferral so subsequent planning can act on them without repeating completed work.

Consider the following table:

| Situation | Appropriate handling |
|---|---|
| Acquisition query needs refinement or another retrieval attempt | Current acquisition invocation |
| Additional retrieval is needed to satisfy an existing acquisition criterion | Current acquisition invocation |
| Existing evidence needs further analysis, synthesis, or screening | Current findings invocation |
| Additional local criteria are needed within acquisition or findings | Current subgraph, using its existing proposal/review mechanism |
| Findings reveal a need for additional graph evidence | Overall review, then planning in the next iteration |
| A criterion requires substantial decomposition into new dependent research requirements | ADaPT-style breakdown through planning in the next iteration |
| A criterion cannot be satisfied because evidence is unavailable | Record the limitation; determine whether further work is viable |

Examine whether a criterion's atomic statement is genuinely atomic when it cannot be satisfied through the existing 
acquisition or processing mechanisms. If establishing the statement requires resolving subordinate questions or 
previously unrecognized dependencies, consider whether ADaPT-style decomposition is appropriate. Determine when such 
decomposition should trigger deferral and another planning iteration, rather than continued attempts to satisfy the 
statement within the current iteration. When an atomic statement is decomposed, it follows the promotion logic, and the 
atomic statement is satisfied when the promoted criterion is satisfied. If the remaining statements of the original 
criterion are already satisfied, now that criterion is also satisfied.
