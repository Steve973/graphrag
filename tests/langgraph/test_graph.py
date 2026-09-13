"""End-to-end tests for graph construction, routing, and node retries."""

from __future__ import annotations

import asyncio
from typing import Any, Sequence, Mapping

from litellm.types.utils import ModelResponse
from pydantic import SecretStr, AnyHttpUrl

from graph_rag.config.graph_rag_config import GraphDataProfile, GraphRagSettings
from graph_rag.graph_store.provider import GraphProvider
from graph_rag.langgraph.contracts import (
    ActionDecision,
    EvidenceSummaryResult,
    FinalAnswerDraft,
)
from graph_rag.langgraph.graph import build_graph_rag_graph
from graph_rag.langgraph.node_runner import GraphRagNodeRunner
from graph_rag.model.action import CallToolAction, FinalizeAction
from graph_rag.model.base import Answerability, PlanStepStatus, WorkflowStatus
from graph_rag.model.plan import Plan, PlanStep, PlanUpdate, ReplacePlanStep
from graph_rag.model.question import Question, WorkflowLimits
from graph_rag.model.rag_state import GraphContext, GraphRagState, create_initial_state
from graph_rag.model.supporting_data import EvidenceSummary
from graph_rag.model.tool_operations import (
    AvailableTool,
    ToolCallRequest,
    ToolCallResult,
    ToolReference,
    ToolResultStatus,
)
from graph_rag.model.workflow import EvaluationResult
from graph_rag.service.graph_rag_service import GraphRagService
from graph_rag.utils import utc_now


def settings() -> GraphRagSettings:
    """Return deterministic settings with effectively immediate retry delays."""

    return GraphRagSettings(
        data_profile=GraphDataProfile(version="1"),
        llm_url=AnyHttpUrl("https://llm.example.test/v1"),
        llm_api_key=SecretStr("secret"),
        llm_model="test-model",
        llm_provider="test-provider",
        llm_num_retries=0,
        node_retry_max_attempts=2,
        node_retry_initial_interval=0.001,
        node_retry_max_interval=0.001,
        graph_db_mcp_url=AnyHttpUrl("https://graph.example.test/mcp"),
        graph_db_username="neo4j",
        graph_db_password=SecretStr("secret"),
        graph_db_database="neo4j",
    )


class FakeProvider(GraphProvider):
    """Provide one read-only graph tool and optionally fail initialization once."""

    def __init__(self, *, fail_once: bool = False) -> None:
        self.build_attempts = 0
        self.fail_once = fail_once
        self.execute_attempts = 0
        self.fail_execute_once = False

    async def build_graph_context(self, profile_id: str) -> GraphContext:
        """Return graph context after an optional transient failure."""

        self.build_attempts += 1
        if self.fail_once and self.build_attempts == 1:
            raise ConnectionError("temporary MCP disconnect")
        return GraphContext(
            profile_id=profile_id,
            schema_ddl="NODE Person (name: STRING)",
            available_tools=[
                AvailableTool(
                    reference=ToolReference(name="read_graph"),
                    description="Read graph data",
                    input_schema={"type": "object"},
                )
            ],
        )

    async def execute_graph_operation(self, request: ToolCallRequest) -> ToolCallResult:
        """Return one successful result for the selected request."""

        self.execute_attempts += 1
        if self.fail_execute_once and self.execute_attempts == 1:
            raise ConnectionError("temporary tool disconnect")
        now = utc_now()
        return ToolCallResult(
            request_id=request.id,
            status=ToolResultStatus.SUCCESS,
            data={"name": "Ada"},
            started_at=now,
            completed_at=now,
        )


class FakeNodeRunner:
    """Return contract-valid decisions for a two-iteration workflow."""

    def __init__(self) -> None:
        self.evaluations = 0
        self.plan_evaluations = 0

    async def invoke_structured(
        self,
        messages: Any,
        response_model: type,
    ) -> Any:
        """Return the next deterministic structured model response."""

        del messages
        if response_model is Plan:
            self.plan = Plan(objective="Answer the question", steps=[PlanStep(description="Read data")])
            return self.plan
        if response_model is PlanUpdate:
            self.plan_evaluations += 1
            if self.plan_evaluations == 2:
                step = self.plan.steps[0].model_copy(update={"status": PlanStepStatus.COMPLETE})
                return PlanUpdate(
                    rationale="The graph evidence completes the step.",
                    changes=[ReplacePlanStep(step_id=step.id, replacement=step)],
                )
            return PlanUpdate(rationale="The plan remains appropriate.")
        if response_model is EvaluationResult:
            self.evaluations += 1
            if self.evaluations == 1:
                return EvaluationResult(
                    answerability=Answerability.NOT_READY,
                    iteration_purpose="Retrieve graph evidence",
                    rationale="No evidence has been retrieved yet.",
                )
            state_summary = self.summary
            return EvaluationResult(
                answerability=Answerability.COMPLETE,
                iteration_purpose="Produce the supported answer",
                rationale="The required graph evidence is available.",
                new_evidence_records=[state_summary],
            )
        if response_model is ActionDecision:
            if self.evaluations == 1:
                return ActionDecision(
                    action=CallToolAction(
                        rationale="Evidence is required.",
                        request=ToolCallRequest(
                            tool=ToolReference(name="read_graph"),
                            rationale="Retrieve the needed person.",
                        ),
                    )
                )
            return ActionDecision(
                action=FinalizeAction(
                    rationale="The answer is fully supported.",
                    evidence_record_ids=[self.summary.id],
                    status=WorkflowStatus.COMPLETE,
                )
            )
        if response_model is EvidenceSummaryResult:
            raise AssertionError("summary response is set by the test-specific runner")
        if response_model is FinalAnswerDraft:
            return FinalAnswerDraft(answer="The graph identifies Ada.", confidence=0.95)
        raise AssertionError(response_model)

    summary: EvidenceSummary


class WorkflowRunner(FakeNodeRunner):
    """Capture the runtime EvidenceData ID when summarization is requested."""

    async def invoke_structured(self, messages: Any, response_model: type) -> Any:
        """Return a summary citing the ID embedded in the evidence prompt."""

        if response_model is EvidenceSummaryResult:
            content = messages[-1]["content"]
            raw_section = content.rsplit("## Raw Evidence Data:", 1)[1]
            evidence_id = raw_section.split("id: ", 1)[1].splitlines()[0].strip()
            self.summary = EvidenceSummary(
                summary="The graph result names Ada.",
                evidence_data_ids=[evidence_id],
            )
            return EvidenceSummaryResult(summaries=[self.summary])
        return await super().invoke_structured(messages, response_model)


def test_graph_runs_two_iterations_and_finalizes() -> None:
    """Run the main retrieve, summarize, evaluate, and finalize loop."""

    graph = build_graph_rag_graph(settings(), FakeProvider(), node_runner=WorkflowRunner())
    question = Question(text="Who is named?", limits=WorkflowLimits(max_iterations=3))
    result = asyncio.run(graph.ainvoke(create_initial_state(question)))
    state = GraphRagState.model_validate(result)

    assert state.status == WorkflowStatus.COMPLETE
    assert state.final_answer is not None
    assert state.final_answer.answer == "The graph identifies Ada."
    assert len(state.iterations) == 2
    assert len(state.evidence_data) == 1
    assert len(state.evidence_summaries) == 1


def test_transient_initialization_failure_is_retried() -> None:
    """Retry a transient provider read at the LangGraph node boundary."""

    provider = FakeProvider(fail_once=True)
    graph = build_graph_rag_graph(settings(), provider, node_runner=WorkflowRunner())
    question = Question(text="Who is named?", limits=WorkflowLimits(max_iterations=3))
    result = asyncio.run(graph.ainvoke(create_initial_state(question)))

    assert result["status"] == WorkflowStatus.COMPLETE
    assert provider.build_attempts == 2


def test_retried_tool_node_commits_results_only_once() -> None:
    """Keep the iteration transaction clean when tool execution is retried."""

    provider = FakeProvider()
    provider.fail_execute_once = True
    graph = build_graph_rag_graph(settings(), provider, node_runner=WorkflowRunner())
    question = Question(text="Who is named?", limits=WorkflowLimits(max_iterations=3))
    state = GraphRagState.model_validate(
        asyncio.run(graph.ainvoke(create_initial_state(question)))
    )

    assert provider.execute_attempts == 2
    assert len(state.iterations[0].tool_results) == 1
    assert len(state.iterations[0].evidence_records) == 1


def test_service_runs_the_checkpointed_graph() -> None:
    """Expose graph execution through the application service boundary."""

    service = GraphRagService(
        settings(),
        FakeProvider(),
        node_runner=WorkflowRunner(),
    )
    state = asyncio.run(service.answer(Question(text="Who is named?")))

    assert state.final_answer is not None
    assert state.final_answer.status == WorkflowStatus.COMPLETE


def test_exhausted_retry_becomes_failed_workflow_state() -> None:
    """Route an exhausted transient failure through the node error handler."""

    provider = FakeProvider()

    async def always_fail(profile_id: str) -> GraphContext:
        provider.build_attempts += 1
        raise ConnectionError(f"cannot load {profile_id}")

    provider.build_graph_context = always_fail  # type: ignore[method-assign]
    graph = build_graph_rag_graph(settings(), provider, node_runner=WorkflowRunner())
    state = GraphRagState.model_validate(
        asyncio.run(graph.ainvoke(create_initial_state(Question(text="Who?"))))
    )

    assert provider.build_attempts == 2
    assert state.status == WorkflowStatus.FAILED
    assert state.final_answer is not None
    assert len(state.errors) == 1


def test_node_runner_preserves_raw_agent_tool_call_api() -> None:
    """Protect the pre-existing invoke_structured signature and forwarding behavior."""

    request: dict[str, Any] = {}

    class Client:
        async def complete(self, **kwargs: Any) -> ModelResponse:
            request.update(kwargs)
            return ModelResponse(choices=[])

    runner = GraphRagNodeRunner(settings())
    runner.client = Client()  # type: ignore[assignment]
    messages: Sequence[Mapping[str, Any]] = [{"role": "user", "content": "hello"}]
    asyncio.run(
        runner.invoke_structured(
            messages=messages,
            response_model=Plan,
        )
    )

    assert request["messages"] is messages
    assert request["response_model"] is Plan
