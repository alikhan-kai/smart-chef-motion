from pydantic_settings import BaseSettings, SettingsConfigDict


class BackendSettings(BaseSettings):
    """Persistence settings for the backend layer (recipe book, recipe
    magazine). Both fields are optional: when either is unset, main.py falls
    back to in-memory repositories (this is what tests rely on)."""

    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    supabase_url: str | None = None
    supabase_service_key: str | None = None
    """Supabase *service role* key - server-side only, never the anon key
    the frontend uses. Bypasses RLS, since the backend enforces user scoping
    itself (see docs/chat_contract.md, "User scoping")."""

    yandex_alice_skill_id: str | None = None
    """Optional skill id used to reject webhook payloads for another skill."""


def get_backend_settings() -> BackendSettings:
    return BackendSettings()
