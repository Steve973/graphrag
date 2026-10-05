"""End-to-end tests for graph construction, routing, and node retries."""

from __future__ import annotations

import asyncio
import inspect
from typing import Any, Sequence, Mapping

from pydantic import SecretStr, AnyHttpUrl

from graphrag.config.graph_rag_config import GraphDataProfile, GraphRagSettings
from graphrag.graph_store.provider import GraphProvider
from graphrag.langgraph.contracts import (
    ActionDecision,
    EvidenceSummaryResult,
    FinalAnswerDraft,
)
from graphrag.langgraph import graph as graph_module
from graphrag.langgraph.graph import build_graph_rag_graph
from graphrag.langgraph.node_runner import GraphRagNodeRunner
from graphrag.llm.structured_output import LangChainStructuredOutput
from graphrag.model.action import (
    CallToolAction,
    FinalizeAction,
    RequestClarificationAction,
)
from graphrag.model.base import (
    ErrorCategory,
    EvaluationOutcome,
    PlanStepStatus,
    WorkflowStatus,
)
from graphrag.model.plan import Plan, PlanStep, PlanUpdate, ReplacePlanStep
from graphrag.model.question import (
    Question,
    UserClarificationEvaluationResult,
    UserClarificationRequest,
    UserClarificationResponse,
    WorkflowLimits,
)
from graphrag.model.rag_state import GraphContext, GraphRagState, create_initial_state
from graphrag.model.supporting_data import EvidenceSummary
from graphrag.model.tool_operations import (
    AvailableTool,
    ToolCallRequest,
    ToolCallResult,
    ToolReference,
    ToolResultStatus,
)
from graphrag.model.workflow import (
    ContradictionEvaluationResult,
    EvaluationDecision,
    EvidenceSelectionResult,
    WorkflowError,
)
from graphrag.service.graph_rag_service import GraphRagService
from graphrag.utils import utc_now


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
        if response_model is EvidenceSelectionResult:
            accepted = [self.summary.id] if hasattr(self, "summary") else []
            return EvidenceSelectionResult(
                accepted_evidence_record_ids=accepted,
                rationale="Accept useful evidence when available.",
            )
        if response_model is ContradictionEvaluationResult:
            return ContradictionEvaluationResult(
                rationale="No contradiction changes are needed."
            )
        if response_model is EvaluationDecision:
            self.evaluations += 1
            if self.evaluations == 1:
                return EvaluationDecision(
                    outcome=EvaluationOutcome.CONTINUE,
                    iteration_purpose="Retrieve graph evidence",
                    rationale="No evidence has been retrieved yet.",
                )
            return EvaluationDecision(
                outcome=EvaluationOutcome.COMPLETE,
                iteration_purpose="Produce the supported answer",
                rationale="The required graph evidence is available.",
            )
        if response_model is ActionDecision:
            if self.evaluations != 1:
                raise AssertionError(
                    "terminal evaluations must bypass action selection"
                )
            return ActionDecision(
                action=CallToolAction(
                    rationale="Evidence is required.",
                    request=ToolCallRequest(
                        tool=ToolReference(name="read_graph"),
                        rationale="Retrieve the needed person.",
                    ),
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


class ClarificationRunner(FakeNodeRunner):
    """Pause once for clarification, then complete after accepting the response."""

    async def invoke_structured(self, messages: Any, response_model: type) -> Any:
        if response_model is UserClarificationRequest:
            return UserClarificationRequest(
                rationale="The name is ambiguous.",
                user_message="Which name do you mean?",
            )
        if response_model is UserClarificationEvaluationResult:
            assert "Ada" in messages[-1]["content"]
            return UserClarificationEvaluationResult(
                resolved=True,
                rationale="The user supplied the intended name.",
            )
        if response_model is EvaluationDecision:
            self.evaluations += 1
            return EvaluationDecision(
                outcome=(
                    EvaluationOutcome.CLARIFY
                    if self.evaluations == 1
                    else EvaluationOutcome.COMPLETE
                ),
                iteration_purpose=(
                    "Resolve the ambiguous name"
                    if self.evaluations == 1
                    else "Answer using the clarification"
                ),
                rationale=(
                    "The intended name is ambiguous."
                    if self.evaluations == 1
                    else "The clarification resolved the ambiguity."
                ),
            )
        if response_model is ActionDecision:
            raise AssertionError(
                "clarification and terminal evaluations must bypass action selection"
            )
        if response_model is FinalAnswerDraft:
            return FinalAnswerDraft(answer="You meant Ada.", confidence=0.9)
        return await super().invoke_structured(messages, response_model)


class EvaluationFailureRunner(FakeNodeRunner):
    """Have evaluation terminate based on an existing non-recoverable error."""

    async def invoke_structured(self, messages: Any, response_model: type) -> Any:
        if response_model is EvaluationDecision:
            return EvaluationDecision(
                outcome=EvaluationOutcome.FAILED,
                iteration_purpose="Stop after a non-recoverable failure",
                rationale="The retained failure prevents safe continuation.",
            )
        if response_model is ActionDecision:
            raise AssertionError("evaluation failure must bypass action selection")
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


def test_all_graph_nodes_use_state_first_signatures() -> None:
    """Keep LangGraph state positional and injected dependencies keyword-only."""

    node_names = (
        "initialize_workflow",
        "create_plan",
        "start_iteration",
        "evaluate_plan",
        "modify_plan",
        "evaluate_evidence",
        "apply_evidence_selection",
        "evaluate_contradictions",
        "evaluate_outcome",
        "apply_evaluation",
        "determine_action",
        "record_evaluation_outcome",
        "execute_action",
        "summarize_results",
        "finalize_results",
        "finalize_iteration",
        "user_clarification",
        "finalize_workflow",
    )
    for name in node_names:
        parameters = list(
            inspect.signature(getattr(graph_module, name)).parameters.values()
        )
        assert parameters[0].name == "state", name
        assert all(
            parameter.kind is inspect.Parameter.KEYWORD_ONLY
            for parameter in parameters[1:]
        ), name


def test_evaluation_response_contracts_stay_narrow() -> None:
    """Keep each staged LLM response focused on one evaluation concern."""

    assert tuple(EvidenceSelectionResult.model_fields) == (
        "accepted_evidence_record_ids",
        "rationale",
    )
    assert tuple(ContradictionEvaluationResult.model_fields) == (
        "contradictions",
        "rationale",
    )
    assert tuple(EvaluationDecision.model_fields) == (
        "outcome",
        "iteration_purpose",
        "rationale",
    )


def test_graph_uses_one_default_error_handler() -> None:
    """Apply the shared failure handler once through graph node defaults."""

    graph = build_graph_rag_graph(
        settings(),
        FakeProvider(),
        node_runner=WorkflowRunner(),
    )

    assert graph.node_error_handler_map
    assert set(graph.node_error_handler_map.values()) == {"__default_error_handler__"}


def test_iteration_limit_preserves_latest_partial_evidence() -> None:
    """Use evidence from the just-committed final iteration in a partial answer."""

    graph = build_graph_rag_graph(
        settings(),
        FakeProvider(),
        node_runner=WorkflowRunner(),
    )
    question = Question(text="Who is named?", limits=WorkflowLimits(max_iterations=1))
    state = GraphRagState.model_validate(
        asyncio.run(graph.ainvoke(create_initial_state(question)))
    )

    assert state.status == WorkflowStatus.PARTIAL
    assert state.final_answer is not None
    assert state.iterations[-1].evidence_records


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
    execution = asyncio.run(service.answer(Question(text="Who is named?")))

    assert not execution.interrupted
    assert execution.state.final_answer is not None
    assert execution.state.final_answer.status == WorkflowStatus.COMPLETE


def test_service_interrupts_and_resumes_clarification() -> None:
    """Expose a typed pause/resume boundary using one checkpoint thread."""

    service = GraphRagService(
        settings(),
        FakeProvider(),
        node_runner=ClarificationRunner(),
    )
    question = Question(text="Tell me about the name.")

    paused = asyncio.run(service.answer(question))

    assert paused.interrupted
    assert paused.state.status == WorkflowStatus.NEEDS_CLARIFICATION
    assert isinstance(paused.state.iterations[-1].action, RequestClarificationAction)
    assert paused.interrupts[0].value["question"] == "Which name do you mean?"

    completed = asyncio.run(
        service.resume(
            question.id,
            UserClarificationResponse(response="I mean Ada."),
        )
    )

    assert not completed.interrupted
    assert completed.state.status == WorkflowStatus.COMPLETE
    assert completed.state.clarification_evaluation is not None
    assert completed.state.clarification_evaluation.resolved
    assert completed.state.final_answer is not None
    assert completed.state.final_answer.answer == "You meant Ada."


def test_evaluation_failure_deterministically_stops_workflow() -> None:
    """Let evaluation, rather than action selection, decide semantic failure."""

    retained_error = WorkflowError(
        category=ErrorCategory.TOOL_EXECUTION,
        message="The required graph operation cannot be completed.",
        recoverable=False,
    )
    graph = build_graph_rag_graph(
        settings(),
        FakeProvider(),
        node_runner=EvaluationFailureRunner(),
    )
    initial_state = create_initial_state(Question(text="Who is named?")).model_copy(
        update={"errors": [retained_error]}
    )

    state = GraphRagState.model_validate(asyncio.run(graph.ainvoke(initial_state)))

    assert state.status == WorkflowStatus.FAILED
    assert isinstance(state.iterations[-1].action, FinalizeAction)
    assert state.iterations[-1].action.status == WorkflowStatus.FAILED


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


def test_node_runner_invokes_structured_output() -> None:
    """Protect structured invocation and its forced output tool contract."""

    request: dict[str, Any] = {}

    from langchain_core.messages import AIMessage
    from langchain_core.tools import StructuredTool
    from tests.llm.test_client import make_client

    class Client:
        async def complete(self, **kwargs: Any) -> AIMessage:
            request.update(kwargs)
            plan = Plan(
                objective="Answer the question",
                steps=[PlanStep(description="Read data")],
            )
            return AIMessage(
                content="",
                tool_calls=[
                    {
                        "name": "return_structured_output",
                        "args": plan.model_dump(mode="json"),
                        "id": "plan",
                    }
                ],
            )

    transport, _ = make_client()
    runner = GraphRagNodeRunner(settings(), chat_model=transport.chat_model)
    runner.structured_output = LangChainStructuredOutput(Client())
    messages: Sequence[Mapping[str, Any]] = [{"role": "user", "content": "hello"}]
    result = asyncio.run(
        runner.invoke_structured(
            messages=messages,
            response_model=Plan,
        )
    )

    assert isinstance(result, Plan)
    assert request["messages"] == list(messages)
    assert request["tool_choice"] == "return_structured_output"
    output_tool = request["tools"][0]
    assert isinstance(output_tool, StructuredTool)
    assert output_tool.args_schema == Plan.model_json_schema()
