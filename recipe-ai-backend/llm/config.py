from pydantic import AliasChoices, Field, SecretStr
from pydantic_settings import BaseSettings, SettingsConfigDict


class LLMSettings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    llm_provider: str = "openai"
    """LangChain provider id passed to init_chat_model(): "openai", "anthropic",
    "google_genai", ... The matching langchain-<provider> package must be installed."""
    llm_model: str = Field(validation_alias=AliasChoices("LLM_MODEL", "OPENAI_MODEL"))
    llm_api_key: SecretStr | None = None
    """Explicit key for the selected provider. If unset, the provider integration
    reads its own env var (ANTHROPIC_API_KEY, GOOGLE_API_KEY, ...)."""
    openai_api_key: SecretStr | None = None
    """Legacy name, used only when llm_provider == "openai" and LLM_API_KEY is unset."""
    llm_timeout_seconds: float = Field(
        60.0, validation_alias=AliasChoices("LLM_TIMEOUT_SECONDS", "OPENAI_TIMEOUT_SECONDS")
    )
    two_step_mode: bool = False

    # Chat/revision settings (see llm/chat_responder.py, backend/services/chat_service.py).
    revise_model: str | None = None
    """Model used for respond_to_message(); falls back to llm_model if unset."""
    revise_use_web_search: bool = False
    revise_history_messages: int = 10
    """How many of the chat's most recent messages are sent as context."""
    revise_fallback_to_full_regeneration: bool = False
    """If true, chat_service falls back to a full regeneration (existing generator)
    when a patch still fails validation after the one model retry. Default off."""

    def provider_api_key(self) -> SecretStr | None:
        if self.llm_api_key is not None:
            return self.llm_api_key
        if self.llm_provider == "openai":
            return self.openai_api_key
        return None


def get_llm_settings() -> LLMSettings:
    # Required fields are read from the environment at runtime by pydantic-settings;
    # mypy can't see that, hence the ignore.
    return LLMSettings()  # type: ignore[call-arg]
