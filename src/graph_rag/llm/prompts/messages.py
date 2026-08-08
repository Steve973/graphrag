from enum import StrEnum
from typing import Literal

from pydantic import BaseModel


class LlmMessageRole(StrEnum):
    """Roles supported by the LLM message protocol."""

    SYSTEM = "system"
    USER = "user"
    ASSISTANT = "assistant"
    TOOL = "tool"


class LlmMessage(BaseModel):
    """Base message supplied to an LLM.

    Attributes:
        role: Semantic role of the message in the LLM conversation.
        content: Textual content of the message.
    """

    role: LlmMessageRole
    content: str


class SystemLlmMessage(LlmMessage):
    """Instructions controlling what the model should do.

    Use this message for application-defined instructions, constraints, and
    behavioral guidance for the current LLM operation.

    In this workflow, this includes instructions for initialization, planning,
    iteration evaluation, evidence summarization, and workflow finalization.

    Attributes:
        role: Always `MessageRole.SYSTEM`.
        content: Instructions governing the current LLM operation.
    """

    role: Literal[LlmMessageRole.SYSTEM] = LlmMessageRole.SYSTEM


class UserLlmMessage(LlmMessage):
    """Information supplied to the model for it to reason about.

    Use this message for the problem and contextual information being presented
    to the model. The content does not need to have been typed directly by the
    human user.

    In this workflow, this may include the original question, workflow state,
    current iteration state, evidence, or the result of an executed action.

    Attributes:
        role: Always `MessageRole.USER`.
        content: Problem data and context the model should reason about.
    """

    role: Literal[LlmMessageRole.USER] = LlmMessageRole.USER


class AssistantLlmMessage(LlmMessage):
    """A response previously produced by the model.

    Use this message when continuing an LLM interaction, and a previous model
    response should remain part of the conversation context.

    In this workflow, this may preserve continuity between related operations
    within an iteration, such as evaluation followed by result summarization.

    Attributes:
        role: Always `MessageRole.ASSISTANT`.
        content: Content previously produced by the model.
    """

    role: Literal[LlmMessageRole.ASSISTANT] = LlmMessageRole.ASSISTANT


class ToolLlmMessage(LlmMessage):
    """Result of a native tool call requested by the model.

    Use this message only when returning the result of a native tool call from
    an assistant response. A workflow action is not automatically a tool
    message merely because its implementation invokes a tool.

    Attributes:
        role: Always `MessageRole.TOOL`.
        content: Serialized result of the native tool call.
        tool_call_id: Identifier of the native tool call being answered.
    """

    role: Literal[LlmMessageRole.TOOL] = LlmMessageRole.TOOL
    tool_call_id: str