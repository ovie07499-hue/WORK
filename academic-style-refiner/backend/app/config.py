"""Runtime configuration, read from environment variables (or a local .env file)."""

from functools import lru_cache
from typing import Literal

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_prefix="REFINER_", extra="ignore")

    # --- LLM ---------------------------------------------------------------
    # The Anthropic API key itself is read by the SDK from ANTHROPIC_API_KEY.
    model: str = "claude-opus-5-5"
    # Effort per stage. Pass 1 does the heavy lifting; pass 2 is a lighter polish.
    pass1_effort: Literal["low", "medium", "high", "xhigh", "max"] = "medium"
    pass2_effort: Literal["low", "medium", "high", "xhigh", "max"] = "low"
    max_output_tokens: int = 8000
    # Retry a refused request server-side on Anthropic's recommended fallback model.
    enable_fallbacks: bool = True
    # Use a deterministic local transform instead of the API (dev / tests / demos).
    mock_llm: bool = False

    # --- Processing ----------------------------------------------------------
    max_words: int = 10_000
    max_upload_bytes: int = 5 * 1024 * 1024
    # Paragraphs longer than this are split at sentence boundaries before rewriting.
    max_chunk_words: int = 320
    # Parallel LLM requests per job, and jobs allowed to run at once on this server.
    chunk_concurrency: int = 4
    max_active_jobs: int = 8
    # Finished jobs (and the text they hold) are purged from memory after this many seconds.
    job_ttl_seconds: int = 1800

    # --- HTTP ----------------------------------------------------------------
    cors_origins: list[str] = ["http://localhost:5173"]
    # Directory with the built frontend; served at "/" when present.
    static_dir: str = "static"


@lru_cache
def get_settings() -> Settings:
    return Settings()
