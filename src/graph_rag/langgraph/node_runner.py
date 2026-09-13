from typing import Any, Mapping, Sequence, TypeVar

from litellm.types.utils import ModelResponse

from graph_rag.config.graph_rag_config import GraphRagSettings
from graph_rag.llm import LiteLlmClient
from graph_rag.llm.structured_output import LiteLlmStructuredOutput
from graph_rag.model.base import ContractModel

ResponseModel = TypeVar("ResponseModel", bound=ContractModel)


class GraphRagNodeRunner:
    """Run provider-neutral, schema-validated LLM node operations."""

    def __init__(
        self,
        settings: GraphRagSettings,
    ):
        self.settings = settings
        self.client = LiteLlmClient(settings)
        self.structured_output = LiteLlmStructuredOutput(self.client)

    async def invoke_agent(
        self,
        messages: Sequence[Mapping[str, Any]],
        tools: Sequence[Mapping[str, Any]] | None,
        parallel_tool_calls: bool,
        response_model: type[ContractModel],
    ) -> ModelResponse:
        """Preserve the original raw agent-completion boundary."""

        del response_model
        return await self.client.complete(
            messages=messages,
            tools=tools,
            parallel_tool_calls=parallel_tool_calls,
        )

    async def invoke_structured(
        self,
        messages: Sequence[Mapping[str, Any]],
        response_model: type[ResponseModel],
    ) -> ResponseModel:
        """Return one response validated against the node's contract model."""

        return await self.structured_output.complete(
            messages=messages,
            response_model=response_model,
        )
