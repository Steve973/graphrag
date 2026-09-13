from langgraph.types import interrupt, Command

from graph_rag.langgraph.node_runner import GraphRagNodeRunner
from graph_rag.langgraph.prompts import state_prompt
from graph_rag.model.base import WorkflowStatus
from graph_rag.model.question import (
    UserClarificationResponse,
    UserClarificationEvaluationResult,
    UserClarificationRequest,
)
from graph_rag.model.rag_state import GraphRagState


async def user_clarification(
    state: GraphRagState,
    *,
    node_runner: GraphRagNodeRunner,
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

    TODO: There should probably be a 'GraphRagSubgraphState' base class that
      exists as a property on the main GraphRagState instance instead of having
      multiple subgraph state instances. Only one subgraph is executing at a time,
      even if any are executed via 'Send' and fan out. Each subgraph's state
      implementations would be derived from this base class, and the main state
      instance can just use this instance when the subgraph is running, and then
      after its results are used in the node that applies the results (in the
      main graph), the subgraph state can be cleared to 'None'. These state
      implementations might work well as TypedDicts.

    TODO: The current iteration instance captures all activities in the
      iteration so that the whole workflow is traceable and can be evaluated.
      Clarification requests and responses also need to be recorded on the
      current iteration instance for the same reason.

    Args:
        state: A GraphRagState that represents the current state of the graph
            for processing.
        node_runner: A GraphRagNodeRunner instance responsible for managing the
            execution of the agent node.

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
    clarification_request = await node_runner.invoke_structured(
        messages=state_prompt(
            state,
            "Formulate the minimum specific clarification request needed to resolve "
            "the blocking ambiguity identified by the latest iteration. If an earlier "
            "clarification response was insufficient, ask only for the remaining "
            "information identified by its evaluation.",
        ),
        response_model=UserClarificationRequest,
    )

    # First node also invokes the interrupt to interact with the user.
    # LangGraph restarts this node when it resumes, so this model call is repeated
    # until the TODO above is implemented as separate checkpointed subgraph nodes.
    response_value = interrupt(
        {
            "type": "user_clarification",
            "question": clarification_request.user_message,
            "reason": clarification_request.rationale,
        }
    )
    response = UserClarificationResponse.model_validate(
        {"response": response_value}
        if isinstance(response_value, str)
        else response_value
    )

    ###################################################################
    ## Second clarification subgraph node
    ###################################################################

    # Second node conducts an evaluation of the user clarification response.
    evaluation = await node_runner.invoke_structured(
        messages=state_prompt(
            state,
            "Evaluate whether the following request and user response resolve the "
            "blocking uncertainty. If unresolved, state exactly what information is "
            "still needed.\n\n"
            f"Clarification request:\n{clarification_request.to_structured_text()}\n\n"
            f"User response:\n{response.to_structured_text()}",
        ),
        response_model=UserClarificationEvaluationResult,
    )

    resolved = evaluation.resolved
    if not resolved:
        return Command(
            update={
                "status": WorkflowStatus.NEEDS_CLARIFICATION,
                "clarification_request": clarification_request,
                "clarification_response": response,
                "clarification_evaluation": evaluation,
            },
            # Back to first node to request further clarification
            goto="user_clarification",
        )

    return Command(
        update={
            "status": WorkflowStatus.RUNNING,
            "clarification_request": clarification_request,
            "clarification_response": response,
            "clarification_evaluation": evaluation,
        },
        # Rejoin the main graph because the clarification was accepted
        goto="start_iteration",
    )
