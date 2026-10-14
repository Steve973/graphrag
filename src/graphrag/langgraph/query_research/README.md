# Criterion query research

The supervisor and query workers are standard LangChain `create_agent` agents.
LangChain manages their model/tool loops on LangGraph. The supervisor has one
application tool, `delegate_query`, which invokes a fresh worker agent and returns
its report. It chooses assignments, reasons about returned support, compares
query diversity and chooses replacements. There are no separate review,
diversity or finish bookkeeping tools, and no custom model/tool execution loop.

Each worker has a `run_query` tool. The worker decides when to execute the original
query, how to minimally repair an actual error, and when to conclude. Its tool
boundary enforces the original tool identity and first-query arguments. LangChain's
`ToolCallLimitMiddleware` enforces the three-call budget. Repairs receive an
independent intent/minimality review through the model's standard
`with_structured_output(RepairReview)` interface before execution.

The supervisor returns `ResearchAssessment` through `create_agent`'s
`response_format=ToolStrategy(...)`. This final structured response contains
support decisions for every candidate and a final diversity assessment. The
application validates IDs, execution success, exact duplicates and completion
budgets, then joins the assessment to the real retained results. The model never
supplies the authoritative raw evidence or execution status.

This follows
the [LangChain subagents pattern](https://docs.langchain.com/oss/python/langchain/multi-agent/subagents#basic-implementation).

## Framework API audit

| Responsibility                                | Standard API used                                       |
|-----------------------------------------------|---------------------------------------------------------|
| Supervisor and worker model/tool loops        | `create_agent`                                          |
| Delegation and database execution             | `StructuredTool` and agent `.ainvoke`                   |
| Agent conclusions                             | `response_format=ToolStrategy(...)`                     |
| Independent repair judgment                   | Chat model `.with_structured_output(...)`               |
| Six delegation calls and three worker calls   | `ToolCallLimitMiddleware`, scoped by tool name          |
| Conversation cost limits                      | `ModelCallLimitMiddleware`                              |
| Domain-specific validation and retry feedback | Documented `AgentMiddleware` hooks and `hook_config`    |
| Parent workflow integration                   | `StateGraph`, `START`, `END`, and async node invocation |

The [built-in middleware](https://docs.langchain.com/oss/python/langchain/middleware/built-in)
owns tool/model limits. [Custom middleware hooks](https://docs.langchain.com/oss/python/langchain/middleware/custom)
host criterion-specific validation. This package supplies the prompts, schemas,
query intent checks, evidence acceptance rules, audit records and a normal Python
semaphore limiting concurrent workers to three. LangGraph's async tool dispatcher
in the installed version gathers calls without applying `max_concurrency` as a
worker semaphore, so the local concurrency cap remains explicit. None of this
reimplements an agent loop or a tool dispatcher.

## Call it from your LangGraph flow

```python
from graphrag.langgraph.node_runner import GraphRagNodeRunner
from graphrag.langgraph.query_research import (
    ResearchCriterion,
    build_query_research_graph,
)

# settings, provider, state and step come from your initialized workflow.
runner = GraphRagNodeRunner(settings)
research_graph = build_query_research_graph(
    provider=provider,
    supervisor_runner=runner,
    # Optional: worker_runner=another_runner with a separate configured model.
)
research_state = await research_graph.ainvoke({
    "criterion": ResearchCriterion.from_plan_step(step, criterion_index=0),
    "graph_context": state.graph_context,
})
result = research_state["result"]
for execution in result.accepted:
    actual_query = execution.attempts[-1].request
    raw_support = execution.result
    worker_conversation = execution.worker_messages
supervisor_conversation = research_state["messages"]
```

The builder returns a callable LangGraph subgraph with an async research node.
Call it after planning and graph initialization. Store `ResearchResult` in a
parent state field and feed accepted raw results through evidence summarization
before making supported findings. The existing main workflow records one action
per iteration; this example does not change those bookkeeping contracts.

## Example criterion

For “Identify which projects are blocked by incomplete prerequisites, with the
blocking task IDs,” the supervisor might delegate:

1. A project-to-task-to-prerequisite traversal returning explicit blocking paths.
2. A blocker-first impact analysis grouping affected projects by prerequisite.
3. A corroboration query comparing dependency-derived blockage with explicit
   blocker records or blocked status, returning agreements and contradictions.

These are illustrative approaches; the actual schema must support them. Reversing
a traversal alone does not make a query materially different. The supervisor
must compare actual retrieval methods and results, and may replace the second
approach if it duplicates the first. It cannot invent fields to enable the third.

## Enforced bounds and audit

- Six candidate delegation calls total, enforced by `ToolCallLimitMiddleware`
  before dispatch. Rejected, duplicate, unsupported and failed candidates consume
  slots. Malformed tool arguments also consume a call under the standard middleware's
  semantics; their error messages remain in the supervisor transcript. A seventh
  delegation is blocked even if the model issues parallel calls.
- Up to three workers run concurrently. The supervisor can also choose sequential
  assignments informed by earlier reports. Each parent invocation has its own
  ledger and budgets.
- Each worker gets three `run_query` calls through the native tool limit. One call per model
  turn ensures a repair uses the preceding actual error. The first query must
  exactly match the assignment. Success, including empty results, ends execution.
  Provider rejection and rejected repair also end execution.
- Repair arguments can change; tool identity, original intent and invariants
  remain fixed. An independent review checks minimality and intent preservation
  against both the original and previous query. Rejected semantic drift never
  reaches the database. An alternative strategy requires a new delegation.
- Final-conclusion middleware prevents premature termination, acceptance of
  failed executions, unknown or repeated IDs and exact duplicate retained queries.
  An incomplete assessment with remaining budget goes back to the agent with
  feedback; the agent chooses replacement work itself.
- If the budget is exhausted without three distinct supported queries, the result
  is `budget_exhausted` with any partial accepted set. Intermediate and final
  support/diversity assessments, raw results, worker transcripts, repair judgments
  and supervisor messages remain available for inspection.
- `ModelCallLimitMiddleware` caps the supervisor at 32 model calls and each worker
  at 12 model calls. These limits do not grant additional query attempts. Native
  counters update before validation can request another model turn; middleware
  after-model hooks run in reverse registration order. Model failures and inconsistent provider
  result IDs propagate as failures rather than invented successful reports.

Expose read-only research tools and a provider that enforces query restrictions.
The package does not parse arbitrary Cypher or independently enforce database
permissions. Minimal semantic repairs and material diversity are model judgments,
not formal equivalence proofs. Full raw reports currently go to the supervisor;
large datasets need a deliberate bounded review projection while preserving raw
results in the audit store. No live model/database behavior is claimed by the
local deterministic tests.
