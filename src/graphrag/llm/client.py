"""LangChain chat transport with an AWS Bedrock Converse default."""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from typing import Any, Protocol

from botocore.config import Config
from langchain_aws import ChatBedrockConverse
from langchain_core.language_models import LanguageModelInput
from langchain_core.language_models.chat_models import BaseChatModel
from langchain_core.messages import AIMessage, BaseMessage
from langchain_core.runnables import Runnable
from pydantic import AnyHttpUrl, SecretStr

from graphrag.llm.structured_output import StructuredOutputError, ToolDefinition


class LlmConfiguration(Protocol):
    """Configuration shared by the application and standalone semantics CLI."""

    llm_model: str
    llm_provider: str
    llm_url: AnyHttpUrl | None
    llm_api_key: SecretStr | None
    llm_region: str | None
    llm_aws_profile: str | None
    llm_temperature: float
    llm_max_tokens: int
    llm_timeout_seconds: float
    llm_num_retries: int


def create_chat_model(settings: LlmConfiguration) -> ChatBedrockConverse:
    """Create a Bedrock model using AWS credential discovery or a Bedrock API key.

    A caller can instead inject its own configured BaseChatModel into the client.
    SDK retries default to zero so LangGraph owns retry orchestration.
    """

    if settings.llm_provider not in {"bedrock", "bedrock_converse"}:
        raise ValueError(
            "The default LangChain client uses Bedrock; select bedrock_converse "
            "or inject a configured chat_model"
        )
    model_id = settings.llm_model.removeprefix(f"{settings.llm_provider}/")
    return ChatBedrockConverse(
        model=model_id,
        region_name=settings.llm_region,
        credentials_profile_name=settings.llm_aws_profile,
        base_url=str(settings.llm_url) if settings.llm_url is not None else None,
        api_key=settings.llm_api_key,
        temperature=settings.llm_temperature,
        max_tokens=settings.llm_max_tokens,
        disable_streaming=True,
        config=Config(
            connect_timeout=settings.llm_timeout_seconds,
            read_timeout=settings.llm_timeout_seconds,
            retries={
                "mode": "standard",
                "total_max_attempts": settings.llm_num_retries + 1,
            },
        ),
    )


class LangChainClient:
    """Invoke a configured LangChain model and retain its native AIMessage."""

    def __init__(
        self,
        settings: LlmConfiguration,
        *,
        chat_model: BaseChatModel | None = None,
    ) -> None:
        self.chat_model = (
            chat_model if chat_model is not None else create_chat_model(settings)
        )

    async def complete(
        self,
        *,
        messages: Sequence[Mapping[str, Any] | BaseMessage],
        tools: Sequence[ToolDefinition] | None = None,
        tool_choice: str | None = None,
        parallel_tool_calls: bool | None = None,
    ) -> AIMessage:
        """Bind native tools, invoke asynchronously and reject multiple calls when required.

        Bedrock has no generic parallel_tool_calls flag. Its SDK receives no
        OpenAI-only option; the existing single-call response rule is enforced
        after generation. Named tool choice requires model support.
        """

        runnable: Runnable[LanguageModelInput, BaseMessage] = self.chat_model
        if tools is not None:
            if (
                isinstance(self.chat_model, ChatBedrockConverse)
                and tool_choice is not None
            ):
                # LangChain can downgrade forced choice with thinking enabled.
                # This workflow requires forcing; fail rather than downgrade.
                choice_kind = tool_choice if tool_choice in {"auto", "any"} else "tool"
                if choice_kind not in (
                    self.chat_model.supports_tool_choice_values or ()
                ):
                    raise ValueError(
                        f"Configured Bedrock model does not support tool choice {tool_choice!r}"
                    )
            runnable = self.chat_model.bind_tools(list(tools), tool_choice=tool_choice)
        elif tool_choice is not None:
            raise ValueError("tool_choice requires tools")
        response = await runnable.ainvoke(
            [
                dict(message) if isinstance(message, Mapping) else message
                for message in messages
            ]
        )
        if not isinstance(response, AIMessage):
            raise TypeError(
                f"LangChain returned {type(response).__name__}; expected AIMessage"
            )
        call_count = len(response.tool_calls) + len(response.invalid_tool_calls)
        if parallel_tool_calls is False and call_count > 1:
            raise StructuredOutputError(
                f"Model returned {call_count} tool calls; expected at most one"
            )
        return response
