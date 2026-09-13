"""Construction of the controlled GraphRAG LangGraph workflow."""

from datetime import timedelta
from functools import partial
from typing import Literal

from langgraph.checkpoint.base import BaseCheckpointSaver
from langgraph.graph import END, START, StateGraph
from langgraph.graph.state import CompiledStateGraph

from graph_rag.config.graph_rag_config import GraphRagSettings
from graph_rag.graph_store.provider import GraphProvider
from graph_rag.langgraph.node_runner import GraphRagNodeRunner
from graph_rag.langgraph.nodes.action_node import determine_action
from graph_rag.langgraph.nodes.apply_evaluation_node import apply_evaluation
from graph_rag.langgraph.nodes.evaluate_node import evaluate_context
from graph_rag.langgraph.nodes.execute_node import execute_action
from graph_rag.langgraph.nodes.finalize_iteration_node import finalize_iteration
from graph_rag.langgraph.nodes.finalize_results_node import finalize_results
from graph_rag.langgraph.nodes.finalize_workflow_node import finalize_workflow
from graph_rag.langgraph.nodes.init_node import initialize_workflow
from graph_rag.langgraph.nodes.plan_node import create_plan
from graph_rag.langgraph.nodes.plan_evaluation_node import evaluate_plan
from graph_rag.langgraph.nodes.modify_plan_node import modify_plan
from graph_rag.langgraph.nodes.start_iteration_node import start_iteration
from graph_rag.langgraph.nodes.summarize_node import summarize_results
from graph_rag.langgraph.nodes.user_clarification import user_clarification
from graph_rag.langgraph.retry import (
    fail_workflow,
    inference_retry_policies,
    provider_retry_policy,
)
from graph_rag.model.action import CallToolAction, RequestClarificationAction
from graph_rag.model.base import WorkflowLimitsMode
from graph_rag.model.rag_state import GraphRagState
from graph_rag.model.tool_operations import ToolResultStatus
from graph_rag.utils import utc_now

NodeRoute = Literal["execute", "finalize_iteration"]
ResultRoute = Literal["summarize", "finalize_results"]
LoopRoute = Literal["start_iteration", "finalize_workflow", "user_clarification"]


def build_graph_rag_graph(
    settings: GraphRagSettings,
    provider: GraphProvider,
    *,
    node_runner: GraphRagNodeRunner | None = None,
    checkpointer: BaseCheckpointSaver | None = None,
) -> CompiledStateGraph:
    """Build and compile the GraphRAG workflow with per-node retry policies."""

    runner = node_runner or GraphRagNodeRunner(settings)
    retry_args = {
        "max_attempts": settings.node_retry_max_attempts,
        "initial_interval": settings.node_retry_initial_interval,
        "backoff_factor": settings.node_retry_backoff_factor,
        "max_interval": settings.node_retry_max_interval,
    }
    inference_retry = inference_retry_policies(**retry_args)
    provider_retry = provider_retry_policy(**retry_args)

    graph = StateGraph(GraphRagState)
    graph.add_node(
        "initialize",
        partial(initialize_workflow, provider=provider, settings=settings),
        retry_policy=provider_retry,
        error_handler=fail_workflow,
    )
    graph.add_node(
        "plan",
        partial(create_plan, node_runner=runner),
        retry_policy=inference_retry,
        error_handler=fail_workflow,
    )
    graph.add_node("start_iteration", start_iteration, error_handler=fail_workflow)
    graph.add_node(
        "evaluate_plan",
        partial(evaluate_plan, node_runner=runner),
        retry_policy=inference_retry,
        error_handler=fail_workflow,
    )
    graph.add_node("modify_plan", modify_plan, error_handler=fail_workflow)
    graph.add_node(
        "evaluate",
        partial(evaluate_context, node_runner=runner),
        retry_policy=inference_retry,
        error_handler=fail_workflow,
    )
    graph.add_node("apply_evaluation", apply_evaluation, error_handler=fail_workflow)
    graph.add_node(
        "determine_action",
        partial(determine_action, node_runner=runner),
        retry_policy=inference_retry,
        error_handler=fail_workflow,
    )
    graph.add_node(
        "execute",
        partial(execute_action, provider=provider),
        retry_policy=provider_retry,
        error_handler=fail_workflow,
    )
    graph.add_node(
        "summarize",
        partial(summarize_results, node_runner=runner),
        retry_policy=inference_retry,
        error_handler=fail_workflow,
    )
    graph.add_node("finalize_results", finalize_results, error_handler=fail_workflow)
    graph.add_node("finalize_iteration", finalize_iteration, error_handler=fail_workflow)
    graph.add_node(
        "finalize_workflow",
        partial(finalize_workflow, node_runner=runner),
        retry_policy=inference_retry,
        error_handler=fail_workflow,
    )
    # Preserve the existing clarification flow and its documented subgraph design.
    # Its placeholder parent rejoin target remains intentionally unresolved.
    graph.add_node(
        "user_clarification",
        partial(user_clarification, node_runner=runner),
        retry_policy=inference_retry,
        error_handler=fail_workflow,
    )

    graph.add_edge(START, "initialize")
    graph.add_edge("initialize", "plan")
    graph.add_edge("plan", "start_iteration")
    graph.add_edge("start_iteration", "evaluate_plan")
    graph.add_edge("evaluate_plan", "modify_plan")
    graph.add_edge("modify_plan", "evaluate")
    graph.add_edge("evaluate", "apply_evaluation")
    graph.add_edge("apply_evaluation", "determine_action")
    graph.add_conditional_edges("determine_action", route_action)
    graph.add_conditional_edges("execute", route_result)
    graph.add_edge("summarize", "finalize_results")
    graph.add_edge("finalize_results", "finalize_iteration")
    graph.add_conditional_edges("finalize_iteration", route_iteration)
    graph.add_edge("finalize_workflow", END)
    return graph.compile(checkpointer=checkpointer)


async def route_action(state: GraphRagState) -> NodeRoute:
    """Route tool actions to execution and terminal actions to commitment."""

    action = state.current_iteration.action if state.current_iteration else None
    return "execute" if isinstance(action, CallToolAction) else "finalize_iteration"


async def route_result(state: GraphRagState) -> ResultRoute:
    """Route successful tool results through evidence summarization."""

    result = state.current_iteration.tool_results[-1]
    return "summarize" if result.status == ToolResultStatus.SUCCESS else "finalize_results"


async def route_iteration(state: GraphRagState) -> LoopRoute:
    """Continue, finalize, or pause after committing an iteration."""

    action = state.iterations[-1].action
    if isinstance(action, RequestClarificationAction):
        return "user_clarification"
    if not isinstance(action, CallToolAction) or _limit_reached(state):
        return "finalize_workflow"
    return "start_iteration"


def _limit_reached(state: GraphRagState) -> bool:
    """Return whether the question's configured stopping rule now applies."""

    limits = state.question.limits
    iterations = len(state.iterations) >= limits.max_iterations
    elapsed = utc_now() - state.question.submitted_at >= timedelta(
        seconds=limits.max_elapsed_seconds,
    )
    return {
        WorkflowLimitsMode.FIRST: iterations or elapsed,
        WorkflowLimitsMode.ALL: iterations and elapsed,
        WorkflowLimitsMode.ITERATION: iterations,
        WorkflowLimitsMode.ELAPSED: elapsed,
    }[limits.mode]
