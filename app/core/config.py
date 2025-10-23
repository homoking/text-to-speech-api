# app/core/config.py
from __future__ import annotations
from pathlib import Path

try:
    from pydantic_settings import BaseSettings, SettingsConfigDict
except ImportError as e:
    raise RuntimeError(
        "Missing dependency 'pydantic-settings'. "
        "Install it with: pip install pydantic-settings==2.3.4"
    ) from e


class Settings(BaseSettings):
    # App meta
    APP_NAME: str = "Text to Speech API"
    BASE_URL: str = "http://localhost:8000"

    # Audio & caching
    AUDIO_DIR: Path = Path("app/static/audio")
    CACHE_ENABLED: bool = True

    # Limits & defaults
    MAX_CHARS: int = 3000
    DEFAULT_ENGINE: str = "edge"
    DEFAULT_VOICE: str = "en-US-JennyNeural"
    DEFAULT_FORMAT: str = "mp3"

    # Tuning ranges
    RATE_MIN: int = -50
    RATE_MAX: int = 50
    PITCH_MIN: int = -12
    PITCH_MAX: int = 12

    # IMPORTANT: ignore extra env vars like PYTHONUNBUFFERED, RAILWAY_* etc.
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",     # <— این خط مشکل شما را حل می‌کند
    )


settings = Settings()
