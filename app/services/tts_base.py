from __future__ import annotations
from abc import ABC, abstractmethod
from pathlib import Path
from typing import List, Dict, Any, Optional


class TTSBase(ABC):
    """Interface base برای تمام موتورهای TTS."""

    name: str

    @abstractmethod
    async def list_voices(self) -> List[Dict[str, Any]]:
        """برگرداندن لیست صداهای پشتیبانی‌شده."""
        raise NotImplementedError

    @abstractmethod
    async def synthesize(
        self,
        text: str,
        voice: str,
        rate: int = 0,
        pitch: int = 0,
        fmt: str = "mp3",
        ssml: bool = False,
        out_path: Optional[Path] = None,
    ) -> Path:
        """تبدیل متن یا SSML به فایل صوتی."""
        raise NotImplementedError
