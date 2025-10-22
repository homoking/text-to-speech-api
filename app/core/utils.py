from __future__ import annotations
import hashlib
import json
import re
import shutil
import wave
from dataclasses import dataclass
from pathlib import Path
from typing import Optional

from mutagen import File as MutagenFile  # type: ignore
from pydub import AudioSegment  # type: ignore

from .config import settings
from .logger import get_logger

log = get_logger("app.core.utils")

_WHITESPACE_RE = re.compile(r"\s+", re.MULTILINE)


@dataclass
class CacheKey:
    """
    کلید کش + مسیر فایل خروجی.
    """
    key_hex: str
    subdir: str
    filename: str
    rel_path: Path  # relative to AUDIO_DIR
    abs_path: Path  # absolute path on disk


def normalize_text(text: str) -> str:
    """
    نرمال‌سازی فاصله‌ها و شکست خط‌ها (برای حالت non-SSML)
    """
    if text is None:
        return ""
    text = text.replace("\u200c", "")  # ZWNJ
    text = _WHITESPACE_RE.sub(" ", text)
    return text.strip()


def ensure_directories() -> None:
    """
    ساخت پوشه‌ی audio در استارتاپ.
    """
    settings.AUDIO_DIR.mkdir(parents=True, exist_ok=True)


def sanitize_basename(name: str) -> str:
    """
    نام فایل-safe (بدون پسوند)
    """
    safe = re.sub(r"[^a-zA-Z0-9._-]", "-", name)
    safe = re.sub(r"-+", "-", safe).strip("-._")
    return safe or "audio"


def compute_cache_key(
    *, engine: str, voice: str, text: str, ssml: bool, rate: int, pitch: int, fmt: str
) -> CacheKey:
    """
    SHA-256 پایدار از پارامترهای تاثیرگذار در خروجی.
    مسیر: AUDIO_DIR / {first2}/{fullhex}.{ext}
    """
    payload = {
        "engine": engine,
        "voice": voice or "",
        "text": text or "",
        "ssml": bool(ssml),
        "rate": int(rate),
        "pitch": int(pitch),
        "format": fmt,
    }
    raw = json.dumps(payload, sort_keys=True, ensure_ascii=False).encode("utf-8")
    key_hex = hashlib.sha256(raw).hexdigest()
    subdir = key_hex[:2]
    filename = f"{key_hex}.{fmt}"
    rel_path = Path(subdir) / filename
    abs_path = settings.AUDIO_DIR / rel_path
    return CacheKey(key_hex=key_hex, subdir=subdir, filename=filename, rel_path=rel_path, abs_path=abs_path)


def ensure_parent_dir(path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)


def audio_url_for(rel_path: Path) -> str:
    """
    URL قابل‌مصرف توسط فرانت‌اند (نسبت به روت سرور)
    """
    return f"/static/audio/{rel_path.as_posix()}"


def probe_duration_seconds(path: Path) -> Optional[float]:
    """
    مدت زمان فایل: اول mutagen (MP3/OGG …)، اگر WAV بود از wave،
    در نهایت fallback با pydub (نیازمند ffmpeg برای بعضی فرمت‌ها).
    """
    try:
        mf = MutagenFile(path.as_posix())
        if mf is not None and mf.info is not None and getattr(mf.info, "length", None):
            return float(mf.info.length)
    except Exception as e:
        log.debug(f"mutagen probe failed for {path}: {e}")

    try:
        if path.suffix.lower() == ".wav":
            with wave.open(path.as_posix(), "rb") as w:
                frames = w.getnframes()
                rate = w.getframerate()
                if rate > 0:
                    return frames / float(rate)
    except Exception as e:
        log.debug(f"wave probe failed for {path}: {e}")

    try:
        seg = AudioSegment.from_file(path.as_posix())
        return round(len(seg) / 1000.0, 3)
    except Exception as e:
        log.warning(f"pydub probe failed for {path}: {e}")
        return None


def convert_audio(src: Path, dst: Path) -> bool:
    """
    تبدیل فرمت با pydub/ffmpeg بر اساس پسوند مقصد.
    """
    try:
        ensure_parent_dir(dst)
        audio = AudioSegment.from_file(src.as_posix())
        audio.export(dst.as_posix(), format=dst.suffix.lstrip("."))
        return True
    except Exception as e:
        log.error(f"Audio conversion failed {src} -> {dst}: {e}")
        return False


def has_ffmpeg() -> bool:
    return shutil.which("ffmpeg") is not None


def clamp(value: int, lo: int, hi: int) -> int:
    return max(lo, min(hi, value))


def validate_text_length(text: str) -> None:
    if not text or not text.strip():
        raise ValueError("Text must not be empty.")
    if len(text) > settings.MAX_CHARS:
        raise ValueError(f"Text exceeds MAX_CHARS ({settings.MAX_CHARS}).")
