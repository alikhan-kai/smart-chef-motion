from pydantic_settings import BaseSettings, SettingsConfigDict


class LLMSettings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    openai_api_key: str
    openai_model: str
    openai_timeout_seconds: float = 60.0
    two_step_mode: bool = False

    # Cost estimates are emitted with each Responses API usage log. These
    # defaults match GPT-5 standard pricing checked on 2026-09-30. If the app
    # changes models, set OPENAI_PRICING_MODEL and the rates together.
    openai_pricing_model: str = "gpt-5"
    openai_input_cost_per_million_usd: float = 1.25
    openai_cached_input_cost_per_million_usd: float = 0.125
    openai_output_cost_per_million_usd: float = 10.0
    openai_web_search_cost_per_call_usd: float = 0.01

    # Chat/revision settings (see llm/chat_responder.py, backend/services/chat_service.py).
    revise_model: str | None = None
    """Model used for respond_to_message(); falls back to openai_model if unset."""
    revise_use_web_search: bool = False
    revise_history_messages: int = 10
    """How many of the chat's most recent messages are sent as context."""
    revise_fallback_to_full_regeneration: bool = False
    """If true, chat_service falls back to a full regeneration (existing generator)
    when a patch still fails validation after the one model retry. Default off."""


def get_llm_settings() -> LLMSettings:
    # Required fields are read from the environment at runtime by pydantic-settings;
    # mypy can't see that, hence the ignore.
    return LLMSettings()  # type: ignore[call-arg]
