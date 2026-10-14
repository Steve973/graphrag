"""Run actual create_agent supervisors and workers with deterministic chat models."""

import asyncio
import json

import pytest
from langchain_core.language_models.chat_models import BaseChatModel
from langchain_core.messages import AIMessage, HumanMessage, SystemMessage, ToolMessage
from langchain_core.outputs import ChatGeneration, ChatResult
from pydantic import Field

from graphrag.graph_store.provider import GraphProvider
from graphrag.langgraph.node_runner import GraphRagNodeRunner
from graphrag.langgraph.query_research import ResearchCriterion, build_query_research_graph
from graphrag.model.plan import PlanStep
from graphrag.model.rag_state import GraphContext
from graphrag.model.tool_operations import AvailableTool, ToolCallResult, ToolReference, ToolResultStatus
from graphrag.utils import utc_now
from tests.langgraph.test_graph import settings


class ResearchModel(BaseChatModel):
    """Emit native tool calls; production create_agent owns all execution/routing."""

    calls: list[dict] = Field(default_factory=list)
    bound_names: list[str] = Field(default_factory=list)
    overlap: bool = False
    overlap_once: bool = False
    drift: bool = False
    duplicate: bool = False
    unknown_tool: bool = False
    sequential: bool = False
    overdelegate: bool = False
    premature: bool = False
    dishonest: bool = False
    invalid_arguments: bool = False
    refuse_tools: bool = False
    worker_overcalls: bool = False
    worker_false_outcome: bool = False
    worker_wrong_result: bool = False
    worker_premature: bool = False
    worker_invalid_arguments: bool = False

    @property
    def _llm_type(self):
        return "deterministic-research-model"

    def bind_tools(self, tools, **kwargs):
        names = [tool.__name__ if isinstance(tool, type) else tool.name if hasattr(tool, "name") else tool["function"]["name"] for tool in tools]
        return self.model_copy(update={"bound_names": names})

    def _generate(self, *args, **kwargs):
        raise AssertionError("Agents must use the async model path")

    async def _agenerate(self, messages, stop=None, run_manager=None, **kwargs):
        self.calls.append({"tools": self.bound_names, "messages": list(messages)})
        if self.refuse_tools:
            return ChatResult(generations=[ChatGeneration(message=AIMessage(content="Done without using tools"))])
        system = next((message.content for message in messages if isinstance(message, SystemMessage)), "")
        initial = next(message for message in messages if isinstance(message, HumanMessage))
        context = json.loads(initial.content.split("\n\n", 1)[1])
        reports = [message for message in messages if isinstance(message, ToolMessage)]

        def response(name, args):
            return AIMessage(content="", tool_calls=[{
                "name": name, "args": args, "id": f"call_{len(self.calls)}",
            }])

        if self.bound_names == ["RepairReview"]:
            message = response("RepairReview", {
                "preserves_intent": not self.drift, "minimal_change": not self.drift,
                "rationale": "Preserves filters" if not self.drift else "Dropped filter",
            })
        elif "query execution subagent" in system:
            worker_reports = [report for report in reports if report.name == "run_query"]
            executed = [json.loads(report.content) for report in worker_reports if report.status != "error"]
            original = context["candidate"]["strategy"]["request"]["arguments"]
            concluded_before = any(
                call["name"] == "WorkerConclusion" for message in messages
                if isinstance(message, AIMessage) for call in message.tool_calls
            )
            done = len(worker_reports) >= 6 if self.worker_overcalls else executed and (executed[-1].get("stop") or len(executed) >= 3)
            if self.worker_invalid_arguments:
                done = len(worker_reports) >= 3
            if done or (self.worker_premature and not concluded_before):
                success = next((item["result"] for item in reversed(executed)
                                if item.get("result", {}).get("status") == "success"), None)
                outcome = "succeeded" if success else "failed"
                result_id = success["id"] if success else None
                if self.worker_false_outcome and not concluded_before:
                    outcome = "failed" if success else "succeeded"
                if self.worker_wrong_result and not concluded_before:
                    result_id = "invented-result"
                message = response("WorkerConclusion", {
                    "outcome": outcome, "result_id": result_id,
                    "rationale": "Report actual execution outcome",
                })
            else:
                arguments = original if not executed else {**original, "fixed": True}
                if self.worker_invalid_arguments:
                    arguments = "not an argument object"
                message = response("run_query", {"arguments": arguments, "rationale": "Execute original" if not executed else "Minimal syntax correction"})
        else:
            executions = [json.loads(report.content)["execution"] for report in reports
                          if report.name == "delegate_query" and report.status != "error"
                          and "execution" in json.loads(report.content)]
            last_ai = next((message for message in reversed(messages) if isinstance(message, AIMessage)), None)
            previous = next((call["args"] for message in reversed(messages) if isinstance(message, AIMessage)
                             for call in message.tool_calls if call["name"] == "ResearchAssessment"), None)
            if (not reports and not self.premature) or (last_ai and last_ai.tool_calls[0]["name"] == "ResearchAssessment"):
                retained = previous["diversity"]["retain_candidate_ids"] if previous else []
                count = min(3 - len(retained), 6 - len(executions))
                if self.sequential:
                    count = 1
                if self.overdelegate and not executions:
                    count = 7
                calls = []
                for offset in range(1, count + 1):
                    index = len(executions) + offset
                    strategy = {
                        "approach": f"path {index}", "intent": "Find incomplete blockers",
                        "invariants": ["Preserve incomplete filter and dependency relation"],
                        "request": {
                            "tool": {"name": "invented" if self.unknown_tool else "read_graph"},
                            "arguments": {"query": "same query" if self.duplicate else f"path {index}", "fixed": False},
                            "rationale": "Retrieve blockers",
                        },
                    }
                    args = {"strategy": {"invalid": True}} if self.invalid_arguments else {"strategy": strategy}
                    calls.append({"name": "delegate_query", "args": args, "id": f"assign_{len(self.calls)}_{offset}"})
                message = AIMessage(content="", tool_calls=calls)
            else:
                supported = [item["candidate"]["id"] for item in executions if item["result"] and item["result"]["data"]]
                retained = supported[:3]
                if self.overlap or (self.overlap_once and previous is None):
                    retained = retained[:1 if self.overlap else 2]
                lie = self.dishonest and not (previous and previous["support_decisions"])
                message = response("ResearchAssessment", {
                    "support_decisions": [{
                        "candidate_id": item["candidate"]["id"],
                        "keep": lie or item["candidate"]["id"] in supported,
                        "rationale": "Evaluate actual worker support",
                    } for item in executions],
                    "diversity": {"retain_candidate_ids": retained, "rationale": "Compare actual evidence paths"},
                    "rationale": "Final support and diversity assessment",
                })
        return ChatResult(generations=[ChatGeneration(message=message)])


class ResearchProvider(GraphProvider):
    def __init__(self, mode="success"):
        self.mode = mode
        self.requests = []
        self.active = 0
        self.max_active = 0

    async def build_graph_context(self, profile_id):
        return GraphContext(
            profile_id=profile_id, schema_ddl="Test graph schema",
            available_tools=[AvailableTool(reference=ToolReference(name="read_graph"), description="Read graph data")],
        )

    async def execute_graph_operation(self, request):
        self.requests.append(request)
        self.active += 1
        self.max_active = max(self.max_active, self.active)
        await asyncio.sleep(0.001)
        self.active -= 1
        if self.mode == "exception":
            raise ConnectionError("Disconnected")
        status = ToolResultStatus.SUCCESS
        if self.mode == "error" or (self.mode == "repair" and not request.arguments["fixed"]):
            status = ToolResultStatus.ERROR
        elif self.mode == "rejected":
            status = ToolResultStatus.REJECTED
        now = utc_now()
        return ToolCallResult(
            request_id=request.id, status=status,
            data=[] if self.mode == "empty" else [{"blocker": "task-1"}],
            error=None if status == ToolResultStatus.SUCCESS else "Invalid syntax",
            started_at=now, completed_at=now,
        )


def run(provider, model):
    async def invoke():
        context = await provider.build_graph_context("test")
        criterion = ResearchCriterion.from_plan_step(PlanStep(
            id="step-1", description="Investigate blockers", completion_criteria=["Identify incomplete prerequisite tasks"],
        ))
        graph = build_query_research_graph(
            provider=provider, supervisor_runner=GraphRagNodeRunner(settings(), chat_model=model),
        )
        return await graph.ainvoke({"criterion": criterion, "graph_context": context})
    return asyncio.run(invoke())


def test_standard_agents_delegate_to_concurrent_workers_and_keep_full_reports():
    provider = ResearchProvider()
    model = ResearchModel()
    state = run(provider, model)
    result = state["result"]
    assert result.status == "complete"
    assert result.candidates_used == len(provider.requests) == 3
    assert provider.max_active == 3
    assert len(result.accepted) == 3
    assert all(item.result.data == [{"blocker": "task-1"}] for item in result.accepted)
    assert all(item.worker_messages for item in result.accepted)
    assert all(request.related_plan_step_ids == ["step-1"] for request in provider.requests)
    agent_toolsets = {tuple(call["tools"]) for call in model.calls}
    assert ("delegate_query", "ResearchAssessment") in agent_toolsets
    assert ("run_query", "WorkerConclusion") in agent_toolsets
    assert not any({"review_results", "check_diversity", "finish_research"} & set(tools) for tools in agent_toolsets)
    reports = [message for message in state["messages"] if isinstance(message, ToolMessage) and message.name == "delegate_query"]
    assert len(reports) == 3
    assert len({message.tool_call_id for message in reports}) == 3


def test_workers_reason_about_errors_and_make_guarded_minimal_repairs():
    provider = ResearchProvider("repair")
    result = run(provider, ResearchModel())["result"]
    assert result.status == "complete"
    assert len(provider.requests) == 6
    assert len({request.id for request in provider.requests}) == 6
    for execution in result.accepted:
        assert len(execution.attempts) == 2
        assert execution.candidate.strategy.request.arguments["fixed"] is False
        assert execution.attempts[-1].request.arguments["fixed"] is True
        assert execution.attempts[-1].repair_review.preserves_intent


@pytest.mark.parametrize("mode", ["error", "exception"])
def test_six_candidates_and_three_worker_rounds_are_hard_limits(mode):
    provider = ResearchProvider(mode)
    result = run(provider, ResearchModel())["result"]
    assert result.status == "budget_exhausted"
    assert result.candidates_used == 6
    assert len(provider.requests) == 18
    assert all(len(item.attempts) == 3 for item in result.executions)
    assert result.accepted == []


def test_repair_drift_is_rejected_before_execution():
    provider = ResearchProvider("error")
    result = run(provider, ResearchModel(drift=True))["result"]
    assert result.status == "budget_exhausted"
    assert len(provider.requests) == 6
    assert all(len(item.attempts) == 2 for item in result.executions)
    assert all(item.attempts[-1].result is None for item in result.executions)


@pytest.mark.parametrize("mode", ["empty", "rejected"])
def test_empty_success_and_rejection_stop_worker_without_rewriting(mode):
    provider = ResearchProvider(mode)
    result = run(provider, ResearchModel())["result"]
    assert result.status == "budget_exhausted"
    assert len(provider.requests) == 6
    assert all(len(item.attempts) == 1 for item in result.executions)
    assert all(item.worker_conclusion.outcome == ("succeeded" if mode == "empty" else "failed")
               for item in result.executions)


def test_agent_chooses_replacements_after_diversity_assessment():
    result = run(ResearchProvider(), ResearchModel(overlap_once=True))["result"]
    assert result.status == "complete"
    assert result.candidates_used == 4
    assert len(result.diversity_reviews) == 2
    assert len(result.accepted) == 3


def test_unresolvable_overlap_returns_partial_at_budget():
    result = run(ResearchProvider(), ResearchModel(overlap=True))["result"]
    assert result.status == "budget_exhausted"
    assert result.candidates_used == 6
    assert len(result.accepted) == 1


@pytest.mark.parametrize("unknown_tool", [False, True])
def test_duplicate_and_unknown_catalog_queries_cannot_execute(unknown_tool):
    provider = ResearchProvider()
    result = run(provider, ResearchModel(duplicate=True, unknown_tool=unknown_tool))["result"]
    assert result.status == "budget_exhausted"
    assert result.candidates_used == 6
    assert len(provider.requests) == (0 if unknown_tool else 1)


def test_overdelegation_cannot_exceed_six_candidates():
    provider = ResearchProvider()
    result = run(provider, ResearchModel(overdelegate=True))["result"]
    assert result.candidates_used == len(provider.requests) == 6
    assert provider.max_active == 3


def test_agent_can_choose_sequential_subagents():
    provider = ResearchProvider()
    result = run(provider, ResearchModel(sequential=True))["result"]
    assert result.status == "complete"
    assert result.candidates_used == 3
    assert provider.max_active == 1


def test_final_guard_prevents_early_exit_and_acceptance_of_failures():
    model = ResearchModel(premature=True, dishonest=True)
    result = run(ResearchProvider("rejected"), model)["result"]
    assert result.status == "budget_exhausted"
    assert result.accepted == []
    assert any(
        "Failed executions cannot be kept" in message.content
        for call in model.calls for message in call["messages"] if isinstance(message, HumanMessage)
    )


def test_criterion_adapter_rejects_invalid_index():
    with pytest.raises(ValueError, match="criterion_index"):
        ResearchCriterion.from_plan_step(PlanStep(description="No criteria"))


def test_native_tool_limit_counts_malformed_delegations_toward_budget():
    provider = ResearchProvider()
    state = run(provider, ResearchModel(invalid_arguments=True))
    assert state["result"].status == "budget_exhausted"
    assert state["result"].candidates_used == 6
    assert state["result"].executions == []
    assert provider.requests == []


def test_native_model_limit_stops_supervisor_that_refuses_tools():
    from langchain.agents.middleware.model_call_limit import ModelCallLimitExceededError

    model = ResearchModel(refuse_tools=True)
    with pytest.raises(ModelCallLimitExceededError):
        run(ResearchProvider(), model)
    assert len(model.calls) == 32


def test_native_worker_limit_blocks_extra_execution_calls():
    provider = ResearchProvider("error")
    result = run(provider, ResearchModel(worker_overcalls=True))["result"]
    assert result.candidates_used == 6
    assert len(provider.requests) == 18
    assert all(len(item.attempts) == 3 for item in result.executions)
    assert all(any(
        message.get("status") == "error" and "Tool call limit exceeded" in message["content"]
        for message in item.worker_messages
    ) for item in result.executions)


@pytest.mark.parametrize("mode", ["success", "rejected"])
def test_worker_false_outcome_is_corrected_against_execution(mode):
    result = run(ResearchProvider(mode), ResearchModel(worker_false_outcome=True))["result"]
    for execution in result.executions:
        conclusion = execution.worker_conclusion
        assert conclusion.outcome == ("succeeded" if execution.result is not None else "failed")
        assert any(
            message["type"] == "human" and "must match the actual query execution" in message["content"]
            for message in execution.worker_messages
        )


def test_worker_invented_result_reference_is_corrected():
    result = run(ResearchProvider(), ResearchModel(worker_wrong_result=True))["result"]
    for execution in result.accepted:
        assert execution.worker_conclusion.result_id == execution.result.id
        assert any(
            message["type"] == "human" and "actual successful tool result" in message["content"]
            for message in execution.worker_messages
        )


def test_worker_cannot_conclude_before_attempting_original_query():
    provider = ResearchProvider()
    result = run(provider, ResearchModel(worker_premature=True))["result"]
    assert result.status == "complete"
    assert len(provider.requests) == 3
    assert all(len(item.attempts) == 1 for item in result.accepted)
    assert all(any(
        message["type"] == "human" and "still have attempts available" in message["content"]
        for message in item.worker_messages
    ) for item in result.accepted)


def test_invalid_worker_calls_exhaust_budget_with_explicit_failure():
    provider = ResearchProvider()
    result = run(provider, ResearchModel(worker_invalid_arguments=True))["result"]
    assert result.status == "budget_exhausted"
    assert provider.requests == []
    assert all(item.attempts == [] for item in result.executions)
    assert all(item.failure == "Execution budget consumed by invalid worker tool calls" for item in result.executions)
    assert all(item.worker_conclusion.outcome == "failed" for item in result.executions)
