from __future__ import annotations
from pathlib import Path
from typing import Literal

from pydantic import Field, validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """
    تنظیمات اپلیکیشن از env یا .env
    """

    # Meta
    APP_NAME: str = Field(default="Text to Speech API")

    # Paths & URLs
    BASE_URL: str = Field(default="http://localhost:8000")
    AUDIO_DIR: Path = Field(default=Path("app/static/audio"))

    # Limits & defaults
    MAX_CHARS: int = Field(default=3000, ge=1)
    DEFAULT_ENGINE: Literal["edge", "pyttsx3"] = Field(default="edge")
    DEFAULT_VOICE: str = Field(default="en-US-JennyNeural")
    DEFAULT_FORMAT: Literal["mp3", "ogg", "wav"] = Field(default="mp3")
    CACHE_ENABLED: bool = Field(default=True)

    # UX knobs
    RATE_MIN: int = Field(default=-50)      # درصد
    RATE_MAX: int = Field(default=50)
    PITCH_MIN: int = Field(default=-12)     # نیم‌پرده (semitone)
    PITCH_MAX: int = Field(default=12)

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
    )

    @validator("AUDIO_DIR", pre=True)
    def _coerce_audio_dir(cls, v):
        return Path(v).resolve()


# singleton
settings = Settings()
AUDIO_DIR: Path = settings.AUDIO_DIR
