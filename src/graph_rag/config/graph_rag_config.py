"""Runtime settings and dataset-profile configuration for GraphRAG."""

from __future__ import annotations

from functools import lru_cache

from pydantic import (
    AnyHttpUrl,
    BaseModel,
    ConfigDict,
    Field,
    SecretStr,
    computed_field,
)
from pydantic_settings import (
    BaseSettings,
    PydanticBaseSettingsSource,
    SettingsConfigDict,
)

from graph_rag.model.base import NonEmptyStr


# =============================================================================
# GRAPH DATA PROFILE
#
# GraphDataProfile contains settings that describe how one graph dataset should
# be interpreted. Its computed ID is the stable value carried by workflow state
# and persisted records. Runtime endpoints and credentials remain outside this
# model so selecting a profile does not redefine infrastructure configuration.
# =============================================================================


class GraphDataProfile(BaseModel):
    """Dataset-specific configuration used while interpreting graph results.

    Attributes:
        name: Stable human-readable profile name.
        version: Profile version used to distinguish incompatible profile
            definitions.
        promote_node_properties: Node-property names that should be promoted
            into compact prompt-oriented graph representations.
        promote_edge_properties: Edge-property names that should be promoted
            into compact prompt-oriented graph representations.
    """

    model_config = ConfigDict(
        extra="forbid",
        str_strip_whitespace=True,
        validate_default=True,
    )

    name: NonEmptyStr = "default"
    version: NonEmptyStr
    promote_node_properties: list[NonEmptyStr] = Field(default_factory=list)
    promote_edge_properties: list[NonEmptyStr] = Field(default_factory=list)

    @computed_field(return_type=str)
    @property
    def id(self) -> str:
        """Return the stable profile identifier."""

        return f"{self.name}/v{self.version}"

    def __str__(self) -> str:
        """Return a concise human-readable profile representation."""

        return f"GraphDataProfile({self.id})"


# =============================================================================
# APPLICATION SETTINGS
#
# GraphRagSettings contains runtime infrastructure configuration. Values are
# resolved with explicit Spring-like override precedence:
#
#   1. Constructor arguments
#   2. Operating-system environment variables
#   3. Mounted secret files, when a configured secret directory exists
#   4. Values from the local .env file
#   5. Field defaults
#
# Earlier sources override later sources. CLI argument parsing is deliberately
# omitted so Uvicorn or other process arguments are not interpreted as
# application settings.
# =============================================================================


class GraphRagSettings(BaseSettings):
    """Runtime configuration for the GraphRAG application.

    Required values may be supplied by constructor arguments, operating-system
    environment variables, mounted secret files, or a local ``.env`` file.
    Environment variables use the ``GRAPH_RAG_`` prefix. Nested profile fields
    use ``__`` as the delimiter, such as
    ``GRAPH_RAG_DATA_PROFILE__VERSION``.

    Attributes:
        data_profile: Dataset-specific interpretation and property-promotion
            settings.
        llm_url: Base HTTP URL used for LLM requests.
        llm_api_key: Secret credential sent to the configured LLM provider.
        llm_model: Provider-specific model identifier.
        llm_provider: LiteLLM provider identifier or equivalent provider name.
        llm_temperature: Sampling temperature used for model requests.
        llm_max_tokens: Maximum number of output tokens requested from the
            model.
        graph_db_mcp_url: HTTP URL of the MCP service that exposes graph tools.
        graph_db_username: Username used when authenticating graph-tool
            requests.
        graph_db_password: Secret password used when authenticating graph-tool
            requests.
        graph_db_database: Logical graph database targeted by graph-tool
            requests.
    """

    model_config = SettingsConfigDict(
        env_prefix="GRAPH_RAG_",
        env_nested_delimiter="__",
        env_file=".env",
        env_file_encoding="utf-8",
        secrets_dir=("/run/secrets", "secrets"),
        case_sensitive=False,
        extra="ignore",
        str_strip_whitespace=True,
        validate_default=True,
    )

    data_profile: GraphDataProfile

    # LLM configuration
    llm_url: AnyHttpUrl
    llm_api_key: SecretStr
    llm_model: NonEmptyStr
    llm_provider: NonEmptyStr
    llm_temperature: float = Field(default=0.0, ge=0.0)
    llm_max_tokens: int = Field(default=4096, ge=1)

    # Graph-tool service configuration
    graph_db_mcp_url: AnyHttpUrl
    graph_db_username: NonEmptyStr
    graph_db_password: SecretStr
    graph_db_database: NonEmptyStr

    @classmethod
    def settings_customise_sources(
        cls,
        settings_cls: type[BaseSettings],
        init_settings: PydanticBaseSettingsSource,
        env_settings: PydanticBaseSettingsSource,
        dotenv_settings: PydanticBaseSettingsSource,
        file_secret_settings: PydanticBaseSettingsSource,
    ) -> tuple[PydanticBaseSettingsSource, ...]:
        """Define explicit external-configuration precedence.

        Args:
            settings_cls: Settings class being initialized.
            init_settings: Values explicitly passed to the constructor.
            env_settings: Values read from operating-system environment
                variables.
            dotenv_settings: Values read from the configured ``.env`` file.
            file_secret_settings: Values read from configured secret
                directories.

        Returns:
            Settings sources ordered from highest to lowest precedence.
        """

        del settings_cls  # Required by the Pydantic Settings override contract.
        del file_secret_settings  # Required by the Pydantic Settings override contract.

        ordered_sources: list[PydanticBaseSettingsSource] = [
            init_settings,
            env_settings,
            dotenv_settings,
        ]

        return tuple(ordered_sources)


@lru_cache
def get_graph_rag_settings() -> GraphRagSettings:
    """Load and cache application settings from configured external sources.

    Returns:
        The validated process-wide GraphRAG settings instance.

    Raises:
        pydantic.ValidationError: If required settings are absent or invalid.
    """

    return GraphRagSettings()  # type: ignore[call-arg]

