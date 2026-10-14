"""Framework middleware for bounded agents and validated final conclusions."""

from langchain.agents.middleware import AgentMiddleware, hook_config
from langchain_core.messages import AIMessage, HumanMessage, ToolMessage


class FinalConclusionGuard(AgentMiddleware):
    """Validate structured conclusions without introducing bookkeeping tools."""

    def __init__(self, validate, record=None):
        self.validate = validate
        self.record = record

    @hook_config(can_jump_to=["model"])
    async def aafter_model(self, state, runtime):
        conclusion = state.get("structured_response")
        last_ai = next(
            message
            for message in reversed(state["messages"])
            if isinstance(message, AIMessage)
        )
        if conclusion is None:
            if not last_ai.tool_calls:
                return {
                    "messages": [
                        HumanMessage(
                            content="Use your tools or return the required structured conclusion."
                        )
                    ],
                    "jump_to": "model",
                }
            return None
        # A conclusion may not bypass tool calls bundled into the same response.
        if any(
            call["name"] != type(conclusion).__name__ for call in last_ai.tool_calls
        ):
            raise ValueError(
                "delegate/execute tools and final output must be separate model turns"
            )
        if self.record is not None:
            self.record(conclusion)
        error = self.validate(conclusion, state)
        if error:
            return {
                "structured_response": None,
                "messages": [HumanMessage(content=error)],
                "jump_to": "model",
            }
        return None

    async def awrap_tool_call(self, request, handler):
        # Workers must serialize execution and repair, so each edit uses the actual
        # preceding execution error. Supervisor delegations may still run in parallel.
        if request.tool_call["name"] == "run_query":
            last_ai = next(
                message
                for message in reversed(request.state["messages"])
                if isinstance(message, AIMessage)
            )
            if len(last_ai.tool_calls) != 1:
                return ToolMessage(
                    content="Call run_query once per turn; wait for the execution error before repairing.",
                    tool_call_id=request.tool_call["id"],
                    status="error",
                )
        return await handler(request)
