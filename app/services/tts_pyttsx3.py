# app/services/tts_pyttsx3.py
from __future__ import annotations
import asyncio
from pathlib import Path
from typing import List, Dict, Any, Optional

import pyttsx3  # type: ignore
from functools import lru_cache

from ..core.logger import get_logger
from ..core.utils import (
    ensure_parent_dir,
    probe_duration_seconds,
    convert_audio,
    has_ffmpeg,
)

log = get_logger("app.services.tts_pyttsx3")


class Pyttsx3Engine:
    """
    Offline TTS using system voices.
    Notes:
      - Voices are OS-dependent.
      - Pitch support is limited; we currently ignore pitch.
      - Synchronous library -> we offload blocking parts to a thread.
    """
    name = "pyttsx3"

    def __init__(self) -> None:
        self._engine = None
        self._available: bool | None = None  # None=unknown, True/False cached

    # ---- internals ----
    def _ensure_engine(self):
        if self._available is False:
            raise RuntimeError("pyttsx3 unavailable")
        if self._engine is None:
            try:
                self._engine = pyttsx3.init()
                self._available = True
            except Exception as e:
                self._available = False
                log.error(f"pyttsx3 init failed (likely missing espeak-ng): {e}")
                raise RuntimeError("pyttsx3 unavailable") from e

    def _list_voices_sync(self) -> List[Dict[str, Any]]:
        self._ensure_engine()
        voices = self._engine.getProperty("voices") or []
        result: List[Dict[str, Any]] = []
        for v in voices:
            # normalize language value (bytes on some installs)
            lang = "en-US"
            try:
                langs = getattr(v, "languages", None)
                if langs:
                    first = langs[0]
                    if isinstance(first, (bytes, bytearray)):
                        lang = first.decode("utf-8", "ignore")
                    else:
                        lang = str(first)
            except Exception:
                pass

            gender = getattr(v, "gender", "unknown")
            vid = getattr(v, "id", None) or getattr(v, "name", "default")
            result.append(
                {
                    "id": str(vid),
                    "name": getattr(v, "name", "Voice"),
                    "locale": lang,
                    "gender": str(gender).lower() if isinstance(gender, str) else "unknown",
                }
            )
        return result

    def _synthesize_sync(self, text: str, voice: str, rate_delta: int, wav_path: Path) -> Path:
        self._ensure_engine()
        eng = self._engine
        # voice selection (best-effort)
        if voice:
            try:
                eng.setProperty("voice", voice)
            except Exception as e:
                log.warning(f"pyttsx3: could not set voice '{voice}': {e}")

        # rate adjustment (additive)
        try:
            base_rate = eng.getProperty("rate")
            eng.setProperty("rate", int(base_rate) + int(rate_delta))
        except Exception as e:
            log.debug(f"pyttsx3: could not adjust rate: {e}")

        # pyttsx3 has limited/unstable pitch control across platforms -> ignored safely

        eng.save_to_file(text, str(wav_path))
        eng.runAndWait()
        return wav_path

    # ---- public API (async) ----
    async def list_voices(self) -> List[Dict[str, Any]]:
        loop = asyncio.get_running_loop()
        try:
            return await loop.run_in_executor(None, self._list_voices_sync)
        except Exception:
            # engine unavailable on this host
            return []

    async def synthesize(
        self,
        text: str,
        voice: str,
        rate: int = 0,
        pitch: int = 0,        # ignored (best-effort only)
        fmt: str = "wav",
        ssml: bool = False,    # pyttsx3 does not parse SSML; input should be plain text
        out_path: Optional[Path] = None,
    ) -> Path:
        if out_path is None:
            raise ValueError("out_path is required")
        ensure_parent_dir(out_path)

        # Always render a WAV first, then convert if needed
        wav_path = out_path if out_path.suffix.lower() == ".wav" else out_path.with_suffix(".wav")

        loop = asyncio.get_running_loop()
        try:
            await loop.run_in_executor(None, self._synthesize_sync, text, voice, rate, wav_path)
        except RuntimeError as e:
            # bubble up cleanly so router can downgrade response
            raise
        except Exception as e:
            log.error(f"pyttsx3 synthesis failed: {e}", exc_info=True)
            raise

        # Convert if requested format is not wav
        target = wav_path
        target_fmt = fmt.lower()
        if target_fmt in {"mp3", "ogg"}:
            if not has_ffmpeg():
                raise RuntimeError("ffmpeg is required to convert to the requested format.")
            target = out_path.with_suffix(f".{target_fmt}")
            if not convert_audio(wav_path, target):
                raise RuntimeError("Audio conversion failed.")

            # if conversion succeeded and the target is different, you may keep wav for cache or remove it.
            # We keep wav by default; remove if you want to save disk space:
            # try: wav_path.unlink()
            # except Exception: pass

        return target

    async def get_duration(self, path: Path) -> float:
        dur = probe_duration_seconds(path)
        return dur or 0.0
