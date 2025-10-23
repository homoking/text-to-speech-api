from __future__ import annotations
from fastapi import APIRouter, HTTPException, Query
from typing import Literal, Dict, Any

from ..core.logger import get_logger
from ..services.tts_edge import EdgeTTSEngine
from ..services.tts_pyttsx3 import Pyttsx3Engine

log = get_logger("app.routers.meta")

router = APIRouter(tags=["meta"])

# ساده‌ترین رجیستری موتورها
ENGINES: Dict[str, Any] = {
    "edge": EdgeTTSEngine(),
    "pyttsx3": Pyttsx3Engine(),
}


@router.get("/voices")
async def list_voices(engine: str = Query("edge")):
    if engine not in ENGINES:
        return {"engine": engine, "available": False, "voices": []}
    voices = await ENGINES[engine].list_voices()
    available = bool(voices) or engine == "edge"  # edge doesn't fail listing usually
    return {"engine": engine, "available": available, "voices": voices}


@router.get("/healthz")
async def healthz():
    # اگر لازم شد می‌توان سلامت وابستگی‌ها را هم چک کرد
    return {"status": "ok"}
