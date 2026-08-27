# Agentic Workflow Roadmap

## 1. Generate the Workflow Report

Build the report directly from the workflow state and finalized iteration records and return it alongside the answer in 
the Swagger response.

The report should expose the execution in a way that makes the workflow mechanically inspectable.

Useful contents include:

- Original request
- Initial evaluation
- Iteration objectives
- Decisions made during each iteration
- Tool calls and query arguments
- Query repair attempts
- Raw evidence references
- Evidence summaries
- Result evaluations
- Accepted and rejected findings
- Final evaluation
- Final answer
- Execution timing and other useful metadata

Initially, this does not need persistence. The report can simply be constructed at Finalize and returned with the 
response.

**Why now:** The underlying workflow already works, and most of the information already exists. This should have high 
demo value for relatively little architectural risk. It also immediately exposes weaknesses in the execution record 
because anything missing from the report becomes obvious.

---

## 2. Add Antagonistic Evidence-Summary Evaluation

After evidence has been summarized, independently evaluate the summary against the actual source record that produced 
it.

The antagonistic evaluator should challenge whether:

- Every substantive claim is supported by the underlying record
- Anything was hallucinated or inferred beyond the evidence
- Important qualifiers were omitted
- Contradictory information was ignored
- The summary accurately represents the strength of the source evidence
- The evidence actually supports the purpose of the current iteration
- The summary should be accepted, rejected, or qualified

Store the antagonistic evaluation with the iteration so it also becomes visible in the workflow report.

**Why here:** This is a relatively contained change with potentially high reliability payoff. It strengthens the 
evidence entering the rest of the reasoning process without requiring a major redesign.

---

## 3. Add Antagonistic Full-Context Evaluation

Add an adversarial review after the workflow has accumulated enough context to form broader findings or conclusions.

This evaluator should challenge whether:

- The conclusions actually follow from the collected evidence
- Evidence from different sources is being combined legitimately
- Correlation or association is being overstated
- Unsupported assumptions are bridging gaps in the evidence
- Contradictory evidence has been addressed
- Confidence is appropriate for the available evidence
- The final interpretation goes beyond what the investigation established
- Important uncertainty should be exposed to the user

The output of this evaluation should become part of both the final decision process and the workflow report.

**Why after evidence-level validation:** The first antagonistic layer checks whether individual evidence representations 
are trustworthy. This layer then checks whether those trustworthy pieces are being assembled into a defensible 
conclusion.

---

## 4. Add Workflow Persistence

Persist the completed workflow execution and its iteration history.

The persisted representation should be based on stable execution artifacts rather than blindly serializing every piece 
of transient LangGraph state.

Persist enough information to reconstruct what happened, including:

- Workflow execution identifier
- Request
- Iteration records
- Tool activity
- Evidence and evidence references
- Repair activity
- Validation results
- Findings
- Final evaluation
- Final response
- Workflow status
- Execution metadata

The generated workflow report can also be persisted, although the structured execution record should remain the 
authoritative source from which a report can be regenerated.

Persistence should support multiple configured strategies when useful rather than assuming one destination.

**Why here:** By this point the persisted workflow includes both the original execution history and the additional 
antagonistic validation information. The report has also helped reveal exactly which information is worth retaining.

---

## 5. Add Continuation / Investigation Context Persistence

Define what information should survive specifically to support follow-on questions or continued investigations.

This does not necessarily need to be identical to the full persisted workflow record.

It may include:

- Original request
- Relevant accumulated context
- Accepted findings
- Evidence references
- Important entities
- Unresolved questions
- Final answer
- Prior iteration summaries
- Investigation or conversation identifier

A follow-on request can then attach to an existing investigation rather than beginning from an empty context.

This could also support exposing related prior questions or investigations when appropriate.

**Why separate from workflow persistence:** Audit history and continuation context serve different purposes. Keeping 
them conceptually separate prevents the entire historical state from automatically becoming prompt context for every 
follow-on request.

---

## 6. Introduce the `AgenticMemoryStrategy` Abstraction

Create a provider-neutral abstraction for operational or experiential memory.

The workflow should express needs such as:

- Begin an execution memory trace
- Record finalized iteration experience
- Complete the trace with an outcome
- Retrieve relevant prior experience
- Retrieve similar successful or unsuccessful executions
- Optionally retrieve useful strategy or tool-use history

The abstraction should not expose Neo4j-specific concepts such as Cypher, labels, node IDs, or Neo4j trace objects.

The currently active trace identifier can live in the main graph state so concurrent workflow executions remain 
independent.

Multiple implementations should be possible, and Agentic Memory should be optional for deployments that do not need it.

**Why after general persistence:** The lifecycle and durable execution model will already be understood. Agentic Memory 
can then consume those same finalized execution artifacts without influencing the core workflow design.

---

## 7. Implement Neo4j Agent Memory

Create a Neo4j implementation of `AgenticMemoryStrategy`.

At workflow initialization:

- Start a reasoning trace
- Store the resulting trace identifier in the main graph state

At each finalized iteration:

- Translate the iteration record into useful reasoning-memory information
- Record relevant steps
- Record tool calls and outcomes
- Preserve failures, repairs, and successful approaches where useful

At workflow completion:

- Complete the reasoning trace
- Record the overall outcome and success or failure state

For future executions, retrieve semantically similar or otherwise relevant prior traces and provide selected experience 
to the workflow.

That previous experience may help answer questions such as:

- What approaches worked for similar requests?
- What query patterns repeatedly failed?
- Which tools were useful?
- Which repairs succeeded?
- What strategy produced a good result previously?

**Why here:** This delivers the concrete capability the Tech Director suggested without making Neo4j a foundational 
requirement of the workflow.

---

## 8. Feed Relevant Agentic Memory into Evaluation / Planning

Once memory is being accumulated, determine where prior experience provides the most value.

The first useful integration point is likely near the early Evaluate or Decide portion of the workflow.

Relevant memory might include:

- Similar successful investigations
- Similar failed investigations
- Useful tool sequences
- Query approaches that succeeded
- Known failure patterns
- Repairs that worked
- Previously discovered limitations

The model should receive a small, intentionally selected set of relevant experience rather than an unrestricted dump of 
historical traces.

The workflow report should indicate when prior experience materially influenced a decision.

**Why separate from storing memory:** First collect trustworthy experience. Then experiment with how much of it improves 
current reasoning. This makes it possible to evaluate whether Agentic Memory is actually helping rather than assuming 
that more historical context automatically produces better answers.

---

## 9. Add Competing Iteration Strategies

Allow an iteration action to fan out into genuinely different candidate approaches.

Possible competing strategies could include:

- Different query formulations
- Different graph traversal approaches
- Broad-first versus narrow-first retrieval
- Entity-driven versus relationship-driven investigation
- Different tool sequences
- Different decomposition of the same investigation objective
- A strategy informed by Agentic Memory versus a strategy generated from the current context alone

Each strategy should operate independently enough that the fan-out produces meaningful alternatives rather than several 
superficial variations of the same query.

The results then fan back into an evaluator that can:

- Select the strongest result
- Combine complementary evidence
- Reject weak strategies
- Record why one approach was preferable

**Why later:** This has potentially large upside, but it also multiplies tool calls, cost, evaluation complexity, and 
possible failure modes. The antagonistic evaluators, report, and persistence infrastructure should exist first so the 
behavior of competing strategies can actually be measured and inspected.

---

## 10. Evaluate and Refine Strategy Selection

Once competing strategies and Agentic Memory both exist, begin using execution history to improve which strategies are 
generated or selected.

Possible uses include:

- Prefer strategies that historically succeed for similar problems
- Avoid strategies with repeated repair or failure patterns
- Adjust fan-out width based on task difficulty
- Generate alternatives specifically because previous approaches failed
- Compare memory-informed strategies against independently generated strategies
- Track which strategies contribute useful evidence rather than merely completing successfully

This can eventually move the system from simple retrieval of prior experience toward deliberate experience-informed 
orchestration.

**Why last:** This is where several earlier capabilities begin reinforcing one another. It requires reliable execution 
records, evaluation, persistence, memory, and competing strategies before there is enough trustworthy information to 
make adaptive strategy selection meaningful.

---

# Rough Priority

**Highest immediate bang for buck**

1. Workflow report
2. Antagonistic evidence-summary evaluation
3. Antagonistic full-context evaluation

**Foundation for durable system behavior**

4. Workflow persistence
5. Continuation / investigation context
6. `AgenticMemoryStrategy`
7. Neo4j Agent Memory

**Higher-order agentic improvements**

8. Use prior experience during reasoning
9. Competing iteration strategies
10. Experience-informed strategy selection