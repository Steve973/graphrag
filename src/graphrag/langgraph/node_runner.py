from collections.abc import Mapping, Sequence
from typing import Any, TypeVar

from langchain_core.language_models.chat_models import BaseChatModel
from langchain_core.messages import AIMessage

from graphrag.config.graph_rag_config import GraphRagSettings
from graphrag.llm import LangChainClient
from graphrag.llm.structured_output import LangChainStructuredOutput, ToolDefinition
from graphrag.model.base import ContractModel

ResponseModel = TypeVar("ResponseModel", bound=ContractModel)


class GraphRagNodeRunner:
    """Run provider-neutral, schema-validated LLM node operations."""

    def __init__(
        self,
        settings: GraphRagSettings,
        *,
        chat_model: BaseChatModel | None = None,
    ) -> None:
        self.settings = settings
        self.client = LangChainClient(settings, chat_model=chat_model)
        self.structured_output = LangChainStructuredOutput(self.client)

    async def invoke_agent(
        self,
        messages: Sequence[Mapping[str, Any]],
        tools: Sequence[ToolDefinition] | None,
        parallel_tool_calls: bool,
        response_model: type[ContractModel],
    ) -> AIMessage:
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
