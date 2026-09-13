from typing import Sequence, Mapping, Any

from litellm.types.utils import ModelResponse

from graph_rag.config.graph_rag_config import GraphRagSettings
from graph_rag.llm import LiteLlmClient
from graph_rag.model.base import ContractModel


class GraphRagNodeRunner:
    def __init__(
        self,
        settings: GraphRagSettings,
    ):
        self.settings = settings
        self.client = LiteLlmClient(settings)

    async def invoke_agent(
        self,
        messages: Sequence[Mapping[str, Any]],
        tools: Sequence[Mapping[str, Any]] | None,
        parallel_tool_calls: bool,
        response_model: type[ContractModel],
    ) -> ModelResponse:
        return await self.client.complete(
            messages=messages,
            tools=tools,
            parallel_tool_calls=parallel_tool_calls,
        )
