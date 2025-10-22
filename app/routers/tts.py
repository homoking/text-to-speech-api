from __future__ import annotations
import tempfile
from pathlib import Path
from typing import Literal, Optional, Dict, Any

from fastapi import APIRouter, HTTPException, Request
from pydantic import BaseModel, Field

from ..core.config import settings
from ..core.logger import get_logger
from ..core.utils import (
    clamp,
    compute_cache_key,
    ensure_directories,
    normalize_text,
    audio_url_for,
    probe_duration_seconds,
    convert_audio,
    validate_text_length,
    has_ffmpeg,
)
from ..services.tts_edge import EdgeTTSEngine
from ..services.tts_pyttsx3 import Pyttsx3Engine
from aiohttp import ClientConnectorError, WSServerHandshakeError

log = get_logger("app.routers.tts")
router = APIRouter(tags=["tts"])

# رجیستری موتورها
ENGINES: Dict[str, Any] = {
    "edge": EdgeTTSEngine(),
    "pyttsx3": Pyttsx3Engine(),
}

SUPPORTED_FORMATS = {"mp3", "ogg", "wav"}


# -------------------------
# مدل‌های ورودی/خروجی
# -------------------------
class TTSRequest(BaseModel):
    text: str = Field(..., description="متن یا SSML")
    engine: Literal["edge", "pyttsx3"] = Field(default=settings.DEFAULT_ENGINE)
    voice: Optional[str] = Field(default=settings.DEFAULT_VOICE)
    rate: int = Field(default=0, description="درصد -50..+50 برای edge؛ برای pyttsx3 افزودنی روی rate پایه")
    pitch: int = Field(default=0, description="semitone برای edge به Hz نگاشت می‌شود؛ pyttsx3 محدود")
    format: Literal["mp3", "ogg", "wav"] = Field(default=settings.DEFAULT_FORMAT)
    ssml: bool = Field(default=False, description="اگر true باشد ورودی به‌عنوان SSML تفسیر می‌شود")
    normalize: bool = Field(default=True, description="نرمال‌سازی فاصله‌ها در حالت non-SSML")

    # اعتبارسنجی‌های ساده
    def prepare_text(self) -> str:
        if self.ssml:
            return self.text or ""
        return normalize_text(self.text) if self.normalize else (self.text or "")


class TTSResponse(BaseModel):
    audio_url: str
    duration: Optional[float]
    engine: str
    voice: str
    format: str
    cached: bool


# -------------------------
# ابزار ساده rate-limit در حافظه (اختیاری)
# -------------------------
from time import monotonic

_RATE_BUCKET: Dict[str, list] = {}
MAX_REQ_PER_MIN = 30
WINDOW_SEC = 60


def _rate_limit_ok(ip: str) -> bool:
    now = monotonic()
    bucket = _RATE_BUCKET.setdefault(ip, [])
    # دورریز قدیمی‌ها
    while bucket and (now - bucket[0] > WINDOW_SEC):
        bucket.pop(0)
    if len(bucket) >= MAX_REQ_PER_MIN:
        return False
    bucket.append(now)
    return True


# -------------------------
# Endpoint: POST /tts
# -------------------------
@router.post("/tts", response_model=TTSResponse)
async def tts_endpoint(req: Request, payload: TTSRequest):
    client_ip = req.client.host if req.client else "unknown"
    # Rate limit اختیاری
    if not _rate_limit_ok(client_ip):
        raise HTTPException(status_code=429, detail="Too many requests, please slow down.")

    # اعتبارسنجی پایه
    if payload.format not in SUPPORTED_FORMATS:
        raise HTTPException(status_code=400, detail="Unsupported format.")
    try:
        validate_text_length(payload.text)
    except ValueError as ve:
        raise HTTPException(status_code=400, detail=str(ve))

    engine_name = payload.engine
    if engine_name not in ENGINES:
        raise HTTPException(status_code=400, detail="Unsupported engine.")
    engine = ENGINES[engine_name]

    # clamp کردن rate/pitch به محدوده‌های پیکربندی
    rate = clamp(payload.rate, settings.RATE_MIN, settings.RATE_MAX)
    pitch = clamp(payload.pitch, settings.PITCH_MIN, settings.PITCH_MAX)
    text_for_hash = payload.text if payload.ssml else (normalize_text(payload.text) if payload.normalize else payload.text)

    # محاسبه کلید کش و مسیر خروجی
    ck = compute_cache_key(
        engine=engine_name,
        voice=payload.voice or "",
        text=text_for_hash,
        ssml=payload.ssml,
        rate=rate,
        pitch=pitch,
        fmt=payload.format,
    )

    ensure_directories()

    # اگر کش موجود است، پاسخ سریع بده
    if settings.CACHE_ENABLED and ck.abs_path.exists():
        duration = probe_duration_seconds(ck.abs_path)
        return TTSResponse(
            audio_url=audio_url_for(ck.rel_path),
            duration=duration,
            engine=engine_name,
            voice=payload.voice or "",
            format=payload.format,
            cached=True,
        )

    # تولید فایل تازه
    # edge → mp3 مستقیم؛ تبدیل به ogg/wav در صورت نیاز
    # pyttsx3 → wav مستقیم؛ تبدیل به mp3/ogg در صورت نیاز
    try:
        if engine_name == "edge":
            tmp_out = ck.abs_path if payload.format == "mp3" else ck.abs_path.with_suffix(".mp3")
            tmp_out.parent.mkdir(parents=True, exist_ok=True)
            await engine.synthesize(
                text=text_for_hash if payload.ssml else (normalize_text(payload.text) if payload.normalize else payload.text),
                voice=payload.voice or settings.DEFAULT_VOICE,
                rate=rate, pitch=pitch, fmt="mp3", ssml=payload.ssml, out_path=tmp_out,
            )
            final_path = tmp_out
            if payload.format in {"ogg", "wav"}:
                if not has_ffmpeg():
                    raise HTTPException(status_code=500, detail="ffmpeg is required to convert to requested format.")
                if not convert_audio(tmp_out, ck.abs_path):
                    raise HTTPException(status_code=500, detail="Audio conversion failed.")
                if ck.abs_path != tmp_out and tmp_out.exists():
                    try: tmp_out.unlink()
                    except Exception: pass
                final_path = ck.abs_path

        elif engine_name == "pyttsx3":
            # تولید WAV سپس تبدیل به فرمت خواسته‌شده
            tmp_wav = ck.abs_path if payload.format == "wav" else ck.abs_path.with_suffix(".wav")
            tmp_wav.parent.mkdir(parents=True, exist_ok=True)

            # برخی pyttsx3 نصب‌ها voice را قبول نمی‌کنند؛ خطا را مدیریت می‌کنیم
            await engine.synthesize(
                text=text_for_hash if payload.ssml else (normalize_text(payload.text) if payload.normalize else payload.text),
                voice=payload.voice or "",  # اگر خالی باشد، پیش‌فرض pyttsx3 استفاده می‌شود
                rate=rate,
                pitch=pitch,
                fmt="wav",
                ssml=payload.ssml,
                out_path=tmp_wav,
            )

            final_path = tmp_wav
            if payload.format in {"mp3", "ogg"}:
                if not has_ffmpeg():
                    raise HTTPException(status_code=500, detail="ffmpeg is required to convert to requested format.")
                if not convert_audio(tmp_wav, ck.abs_path):
                    raise HTTPException(status_code=500, detail="Audio conversion failed.")
                final_path = ck.abs_path
                # WAV موقت را حذف کنیم اگر مقصد متفاوت است
                if final_path != tmp_wav and tmp_wav.exists():
                    try:
                        tmp_wav.unlink()
                    except Exception:
                        pass
        else:
            raise HTTPException(status_code=400, detail="Unsupported engine.")

    except (WSServerHandshakeError, ClientConnectorError) as e:
        # Auto-fallback to offline pyttsx3
        log.error(f"edge-tts failed with network/handshake error, falling back to pyttsx3: {e}")
        engine_fallback = ENGINES["pyttsx3"]
        tmp_wav = ck.abs_path if payload.format == "wav" else ck.abs_path.with_suffix(".wav")
        tmp_wav.parent.mkdir(parents=True, exist_ok=True)
        await engine_fallback.synthesize(
            text=text_for_hash if payload.ssml else (normalize_text(payload.text) if payload.normalize else payload.text),
            voice=payload.voice or "", rate=rate, pitch=pitch, fmt="wav", ssml=payload.ssml, out_path=tmp_wav,
        )
        final_path = tmp_wav
        if payload.format in {"mp3", "ogg"}:
            if not has_ffmpeg():
                raise HTTPException(status_code=500, detail="ffmpeg is required to convert to requested format.")
            if not convert_audio(tmp_wav, ck.abs_path):
                raise HTTPException(status_code=500, detail="Audio conversion failed.")
            final_path = ck.abs_path
            if final_path != tmp_wav and tmp_wav.exists():
                try: tmp_wav.unlink()
                except Exception: pass
        # Important: reflect engine used in response
        engine_name = "pyttsx3"
        
    except HTTPException:
        raise
    except Exception as e:
        log.error(f"TTS synthesis failed: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail="Synthesis failed.")

    duration = probe_duration_seconds(final_path)
    return TTSResponse(
        audio_url=audio_url_for(final_path.relative_to(settings.AUDIO_DIR)),
        duration=duration,
        engine=engine_name,
        voice=payload.voice or "",
        format=payload.format,
        cached=False,
    )


# -------------------------
# Endpoint: POST /tts/ssml (میانبر)
# -------------------------
@router.post("/tts/ssml", response_model=TTSResponse)
async def tts_ssml(req: Request, payload: TTSRequest):
    payload.ssml = True
    payload.normalize = False
    return await tts_endpoint(req, payload)
