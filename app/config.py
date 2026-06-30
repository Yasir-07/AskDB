from functools import lru_cache
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    # --- AI provider ---
    llm_provider: str = "gemini"             # "gemini", "anthropic", or "openai"
    google_api_key: str = ""
    anthropic_api_key: str = ""
    openai_api_key: str = ""
    llm_model: str = "gemini-2.0-flash"      # set to a current model for your provider

    # --- Real PostgreSQL database ---
    # Example: postgresql://user:password@host:5432/dbname
    database_url: str = ""

    # How many times the agent may try to fix its own broken query
    max_retries: int = 3

    # Never return more than this many rows to the screen
    row_limit: int = 50


@lru_cache
def get_settings() -> Settings:
    return Settings()
