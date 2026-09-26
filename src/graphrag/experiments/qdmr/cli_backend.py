"""LLM-only CLI configuration; no database or workflow configuration required."""
from collections.abc import Mapping, Sequence
from typing import Any

from litellm.types.utils import ModelResponse

from pydantic import AnyHttpUrl, Field, SecretStr
from pydantic_settings import BaseSettings, SettingsConfigDict

from .core import Text


class LlmSettings(BaseSettings):
    model_config = SettingsConfigDict(
        env_prefix="GRAPH_RAG_", env_file=".env", env_file_encoding="utf-8",
        secrets_dir=("/run/secrets", "secrets"), extra="ignore",
    )
    llm_url: AnyHttpUrl
    llm_api_key: SecretStr
    llm_model: Text
    llm_provider: Text
    llm_temperature: float = Field(default=0.0, ge=0)
    llm_max_tokens: int = Field(default=4096, ge=1)
    llm_timeout_seconds: float = Field(default=60.0, gt=0)
    llm_num_retries: int = Field(default=0, ge=0)

    def __init__(self, **values: Any) -> None:
        # Required fields may come from the environment, not constructor args.
        super().__init__(**values)

    @property
    def model_name(self) -> str:
        prefix = self.llm_provider + "/"
        return self.llm_model if self.llm_model.startswith(prefix) else prefix + self.llm_model


class CliClient:
    """Implements ChatCompletionClient for the app's structured-output helper.

    The regular app can inject LiteLlmClient instead. This small transport keeps
    the standalone CLI independent of GraphRagSettings' required database fields.
    """
    def __init__(self, settings: LlmSettings):
        self.settings = settings

    async def complete(
        self,
        *,
        messages: Sequence[Mapping[str, Any]],
        tools: Sequence[Mapping[str, Any]] | None = None,
        tool_choice: str | Mapping[str, Any] | None = None,
        parallel_tool_calls: bool | None = None,
    ) -> ModelResponse:
        import litellm

        config = self.settings
        options: dict[str, Any] = {}
        if tools is not None:
            options["tools"] = list(tools)
        if tool_choice is not None:
            options["tool_choice"] = tool_choice
        if parallel_tool_calls is not None:
            options["parallel_tool_calls"] = parallel_tool_calls
        response = await litellm.acompletion(
            model=config.model_name, base_url=str(config.llm_url),
            api_key=config.llm_api_key.get_secret_value(),
            temperature=config.llm_temperature, max_tokens=config.llm_max_tokens,
            timeout=config.llm_timeout_seconds, num_retries=config.llm_num_retries,
            stream=False, drop_params=False,
            messages=[dict(message) for message in messages], **options,
        )
        if not isinstance(response, ModelResponse):
            raise TypeError(
                f"LiteLLM returned {type(response).__name__}; expected ModelResponse"
            )
        return response
