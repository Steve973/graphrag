from langgraph.types import interrupt, Command

from graph_rag.langgraph.node_runner import GraphRagNodeRunner
from graph_rag.model.base import WorkflowStatus
from graph_rag.model.question import (
    UserClarificationResponse,
    UserClarificationEvaluationResult,
)
from graph_rag.model.rag_state import GraphRagState


async def user_clarification(
        node_runner: GraphRagNodeRunner,
        state: GraphRagState,
) -> Command:
    """
    Handles the user clarification process by invoking an agent and processing
    its response. This function facilitates interaction with a conversational
    agent to generate a clarification response and constructs the result
    containing the processed output.

    TODO: Implement this as a subgraph. This will allow the request to happen,
      and then the response can come back and be evaluated. When the response
      is accepted, it can be added to a list of clarifications on the question
      instance itself. That is a new concept, so it would have to be used when
      the LLM is considering the question as context when taking actions or
      when performing evaluations. The evaluation would produce an instance of
      the UserClarificationEvaluationResult. In cases where the response is
      evaluated to *not* resolve the uncertainty, it would redirect the flow
      to perform the same interruption again and prompt for further
      clarification.

    TODO: When it is determined that clarification is needed in the first place,
      we should create a 'UserClarificationSubgraphState' instance and store it
      on the GraphRagState instance. This state is transient, but will remain on
      the GraphRagState instance until the ambiguity is considered resolved.
      This is similar to other subgraph states, so it fits the existing pattern.
      Then, when clarification is complete, that clarification state instance
      can be cleared to 'None'.

    TODO: The current iteration instance captures all activities in the
      iteration so that the whole workflow is traceable and can be evaluated.
      Clarification requests and responses also need to be recorded on the
      current iteration instance for the same reason.

    Args:
        node_runner: A GraphRagNodeRunner instance responsible for managing the
            execution of the agent node.
        state: A GraphRagState that represents the current state of the graph
            for processing.

    Returns:
        a Command object specifying the next node to invoke, depending on
        whether the clarification was sufficient to resolve the uncertainty
        and resume the workflow, or if further clarification is needed.
    """

    ###################################################################
    ## First clarification subgraph node
    ###################################################################

    # First node in the subflow would be to tell the LLM to formulate a
    # clarification request.
    clarification_request = await node_runner.invoke_agent(
        messages=[{"role": "user", "content": "Hello!"}],
        tools=[],
        parallel_tool_calls=False,
        response_model=UserClarificationResponse,
    )

    # First node also invokes the interrupt to interact with the user.
    response = interrupt(
        {
            "type": "user_clarification",
            "question": clarification_request.get("question"),
            "context": clarification_request.get("context"),
        }
    )

    ###################################################################
    ## Second clarification subgraph node
    ###################################################################

    # Second node conducts an evaluation of the user clarification response.
    evaluation = await node_runner.invoke_agent(
        messages=[{"role": "user", "content": "Hello!"}],
        tools=[],
        parallel_tool_calls=False,
        response_model=UserClarificationEvaluationResult,
    )

    resolved = evaluation.get("resolution", False)
    if not resolved:
        return Command(
            update={
                "clarification_evaluation": evaluation,
            },
            # Back to first node to request further clarification
            goto="user_clarification",
        )

    return Command(
        update={
            "workflow_status": WorkflowStatus.RUNNING,
            "clarification_evaluation": evaluation,
        },
        # Rejoin the main graph because the clarification was accepted
        goto="whatever_rejoins_the_parent",
    )
