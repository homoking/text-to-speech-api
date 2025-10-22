# app/services/tts_edge.py
import asyncio
import json
from pathlib import Path
from typing import List, Dict, Any, Optional
import edge_tts
from aiohttp import ClientConnectorError, WSServerHandshakeError  # add

from ..core.logger import get_logger
from ..core.utils import ensure_parent_dir, probe_duration_seconds

log = get_logger("app.services.tts_edge")

class EdgeTTSEngine:
    name = "edge"

    async def list_voices(self) -> List[Dict[str, Any]]:
        try:
            voices = await edge_tts.list_voices()
            return [
                {
                    "id": v["ShortName"],
                    "name": v["FriendlyName"],
                    "locale": v["Locale"],
                    "gender": v["Gender"].lower(),
                }
                for v in voices
            ]
        except Exception as e:
            log.error(f"edge-tts voice listing failed: {e}")
            return []

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
        ensure_parent_dir(out_path)
        # overwrite if exists (avoid append)
        if out_path and out_path.exists():
            try: out_path.unlink()
            except Exception: pass

        # UA tweak to avoid some 403s (see issues)
        headers = {
            "User-Agent": (
                "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                "AppleWebKit/537.36 (KHTML, like Gecko) "
                "Chrome/124.0.0.0 Safari/537.36 Edg/124.0.0.0"
            )
        }

        try:
            rate_str = f"{rate:+d}%" if rate else "0%"
            pitch_str = f"{pitch:+d}Hz" if pitch else "0Hz"
            communicate = edge_tts.Communicate(text, voice=voice, rate=rate_str, pitch=pitch_str, headers=headers)
            async for chunk in communicate.stream():
                if chunk["type"] == "audio" and out_path:
                    with open(out_path, "ab") as f:
                        f.write(chunk["data"])
            return out_path
        except (WSServerHandshakeError, ClientConnectorError) as e:
            log.error(f"edge-tts synthesis failed: {e}")
            # rethrow so router can fallback
            raise
        except Exception as e:
            log.error(f"edge-tts synthesis failed: {e}")
            raise
