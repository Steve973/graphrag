"""LangChain model adapters for Ragas 0.4 collections metrics."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, TypeVar, cast

from langchain_core.embeddings import Embeddings
from langchain_core.language_models.chat_models import BaseChatModel
from pydantic import BaseModel
from ragas.embeddings.base import BaseRagasEmbedding
from ragas.llms import InstructorBaseRagasLLM as RagasStructuredOutputLLM


StructuredResponseT = TypeVar("StructuredResponseT", bound=BaseModel)


class LangChainRagasLLM(RagasStructuredOutputLLM):
    """Use LangChain native structured output with Ragas collections metrics.

    Ragas 0.4.3 collections metrics require its structured-output base class at
    runtime. This adapter satisfies that contract with
    ``BaseChatModel.with_structured_output``. It does not construct or call an
    Instructor or LiteLLM client.
    """

    def __init__(self, chat_model: BaseChatModel) -> None:
        self.chat_model = chat_model

    def generate(
        self,
        prompt: str,
        response_model: type[StructuredResponseT],
    ) -> StructuredResponseT:
        runnable = self.chat_model.with_structured_output(response_model)
        result = runnable.invoke(prompt)
        return self._coerce_result(result, response_model)

    async def agenerate(
        self,
        prompt: str,
        response_model: type[StructuredResponseT],
    ) -> StructuredResponseT:
        runnable = self.chat_model.with_structured_output(response_model)
        result = await runnable.ainvoke(prompt)
        return self._coerce_result(result, response_model)

    @staticmethod
    def _coerce_result(
        result: object,
        response_model: type[StructuredResponseT],
    ) -> StructuredResponseT:
        if isinstance(result, response_model):
            return result
        if isinstance(result, dict):
            return response_model.model_validate(result)
        raise TypeError(
            "LangChain structured output returned "
            f"{type(result).__name__}; expected {response_model.__name__} or dict"
        )


class LangChainRagasEmbeddings(BaseRagasEmbedding):
    """Expose a LangChain embedding model through Ragas's modern interface."""

    def __init__(self, embeddings: Embeddings) -> None:
        super().__init__()
        self.embeddings = embeddings

    def embed_text(self, text: str, **kwargs: Any) -> list[float]:
        del kwargs
        return self.embeddings.embed_query(text)

    async def aembed_text(self, text: str, **kwargs: Any) -> list[float]:
        del kwargs
        return await self.embeddings.aembed_query(text)

    def embed_texts(self, texts: list[str], **kwargs: Any) -> list[list[float]]:
        del kwargs
        return self.embeddings.embed_documents(texts)

    async def aembed_texts(
        self, texts: list[str], **kwargs: Any
    ) -> list[list[float]]:
        del kwargs
        return await self.embeddings.aembed_documents(texts)


@dataclass(frozen=True)
class LangChainRagasModels:
    """Keep the application models and their Ragas adapters together."""

    chat_model: BaseChatModel
    llm: LangChainRagasLLM
    embedding_model: Embeddings | None = None
    embeddings: LangChainRagasEmbeddings | None = None


def adapt_langchain_models(
    chat_model: BaseChatModel,
    embedding_model: Embeddings | None = None,
) -> LangChainRagasModels:
    """Adapt already-configured LangChain models without changing providers."""

    return LangChainRagasModels(
        chat_model=chat_model,
        llm=LangChainRagasLLM(chat_model),
        embedding_model=embedding_model,
        embeddings=(
            LangChainRagasEmbeddings(embedding_model)
            if embedding_model is not None
            else None
        ),
    )


def build_bedrock_converse_ragas_models(
    *,
    bedrock_runtime_client: Any,
    model: str,
    embedding_model: str | None = None,
    temperature: float = 0.0,
    max_tokens: int | None = None,
) -> LangChainRagasModels:
    """Build LangChain Bedrock models around an injected boto3 runtime client."""

    from langchain_aws import BedrockEmbeddings, ChatBedrockConverse

    chat_model = ChatBedrockConverse(
        client=bedrock_runtime_client,
        model=model,
        temperature=temperature,
        max_tokens=max_tokens,
    )
    embeddings = (
        BedrockEmbeddings(
            client=bedrock_runtime_client,
            model_id=embedding_model,
        )
        if embedding_model is not None
        else None
    )
    return adapt_langchain_models(
        cast(BaseChatModel, chat_model),
        cast(Embeddings | None, embeddings),
    )
