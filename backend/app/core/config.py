"""
Meiko Agent - Core Configuration
Loads settings from environment variables / .env file.
Users can override provider API keys at runtime via the Settings API,
which are stored encrypted in the local SQLite store (see memory/store.py).
"""
from __future__ import annotations

from functools import lru_cache
from typing import Optional

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    # --- App ---
    APP_NAME: str = "Meiko"
    ENV: str = "development"
    HOST: str = "0.0.0.0"
    PORT: int = 8000
    SECRET_KEY: str = "change-this-secret-in-production-please"
    CORS_ORIGINS: str = "*"

    # --- Auth ---
    MEIKO_API_KEY: Optional[str] = None  # if set, clients must send X-API-Key to hit /api

    # --- Default LLM provider selection ---
    # one of: nvidia, gemini, openrouter, groq, ollama, openai
    DEFAULT_PROVIDER: str = "nvidia"
    DEFAULT_MODEL: str = "meta/llama-3.3-70b-instruct"

    # --- Provider API keys (all optional; user can also set these live in Settings UI) ---
    NVIDIA_API_KEY: Optional[str] = None
    NVIDIA_BASE_URL: str = "https://integrate.api.nvidia.com/v1"

    GEMINI_API_KEY: Optional[str] = None
    GEMINI_BASE_URL: str = "https://generativelanguage.googleapis.com/v1beta"

    OPENROUTER_API_KEY: Optional[str] = None
    OPENROUTER_BASE_URL: str = "https://openrouter.ai/api/v1"

    GROQ_API_KEY: Optional[str] = None
    GROQ_BASE_URL: str = "https://api.groq.com/openai/v1"

    OPENAI_API_KEY: Optional[str] = None
    OPENAI_BASE_URL: str = "https://api.openai.com/v1"

    OLLAMA_BASE_URL: str = "http://localhost:11434"

    # --- Web search tool (optional keys, free fallback via DuckDuckGo works without keys) ---
    TAVILY_API_KEY: Optional[str] = None

    # --- Telegram ---
    TELEGRAM_BOT_TOKEN: Optional[str] = None

    # --- Storage ---
    DATA_DIR: str = "./data"
    DB_PATH: str = "./data/meiko.db"

    # --- Agent behaviour ---
    MAX_AGENT_STEPS: int = 8
    MAX_TOKENS: int = 4096
    TEMPERATURE: float = 0.7


@lru_cache
def get_settings() -> Settings:
    return Settings()
