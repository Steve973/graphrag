"""Bedrock configuration for the standalone question-semantics CLI."""

from typing import Any

from pydantic import AnyHttpUrl, Field, SecretStr
from pydantic_settings import BaseSettings, SettingsConfigDict

from graphrag.llm.client import LangChainClient

from .core import Text


class LlmSettings(BaseSettings):
    model_config = SettingsConfigDict(
        env_prefix="GRAPH_RAG_",
        env_file=".env",
        env_file_encoding="utf-8",
        secrets_dir=("/run/secrets", "secrets"),
        extra="ignore",
    )

    llm_model: Text
    llm_provider: Text = "bedrock_converse"
    llm_url: AnyHttpUrl | None = None
    llm_api_key: SecretStr | None = None
    llm_region: Text | None = None
    llm_aws_profile: Text | None = None
    llm_temperature: float = Field(default=0.0, ge=0)
    llm_max_tokens: int = Field(default=4096, ge=1)
    llm_timeout_seconds: float = Field(default=60.0, gt=0)
    llm_num_retries: int = Field(default=0, ge=0)

    def __init__(self, **values: Any) -> None:
        # Required fields may come from the environment, not constructor args.
        super().__init__(**values)

    @property
    def model_name(self) -> str:
        return self.llm_model.removeprefix(f"{self.llm_provider}/")


# Reuse the application transport without requiring graph/database settings.
CliClient = LangChainClient
