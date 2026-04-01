"""
Centralised application configuration.

Loaded once at startup via get_settings() which is cached with lru_cache.

Priority order (highest → lowest):
  1. Real environment variables (set by the OS / deployment platform)
  2. .env file in the backend directory (local development only)

Required variables — app refuses to start if missing:
  SUPABASE_URL        Supabase project URL
  SUPABASE_KEY        Supabase service-role key (bypasses RLS)

Optional variables with defaults:
  SUPABASE_STORAGE_BUCKET   default "files"
"""
from functools import lru_cache
from pathlib import Path

from pydantic import field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

# Resolve the .env path relative to this file so it works regardless of
# the working directory the process is started from.
_ENV_FILE = Path(__file__).resolve().parent.parent.parent / ".env"


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=str(_ENV_FILE),
        env_file_encoding="utf-8",
        extra="ignore",          # silently ignore unrelated env vars
        case_sensitive=True,     # SUPABASE_URL != supabase_url
    )

    # --- Supabase ---
    SUPABASE_URL: str
    SUPABASE_KEY: str
    SUPABASE_STORAGE_BUCKET: str = "files"

    @field_validator("SUPABASE_URL")
    @classmethod
    def supabase_url_must_be_https(cls, v: str) -> str:
        if not v.startswith("https://"):
            raise ValueError("SUPABASE_URL must start with https://")
        return v.rstrip("/")   # normalise: remove any trailing slash


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    """
    Return the application settings singleton.

    The first call constructs and validates the Settings object.
    Subsequent calls return the cached instance — no re-reading of env vars.

    Raises pydantic.ValidationError on startup if any required variable is
    missing or invalid, preventing the app from starting in a broken state.
    """
    return Settings()
