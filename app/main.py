from __future__ import annotations
import re
from pathlib import Path
from typing import Optional

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, HTMLResponse
from fastapi.staticfiles import StaticFiles

from .core.config import settings
from .core.logger import get_logger
from .core.utils import ensure_directories
from .routers.meta import router as meta_router
from .routers.tts import router as tts_router

log = get_logger("app.main")

app = FastAPI(title=settings.APP_NAME)

# (اختیاری) CORS — اگر لازم شد، دامنه‌های فرانت جدا را اضافه کنید
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # برای دپلوی واقعی محدودش کنید
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# سرو فایل‌های استاتیک
static_dir = Path(__file__).parent / "static"
app.mount("/static", StaticFiles(directory=static_dir.as_posix()), name="static")

# روترها
app.include_router(meta_router)
app.include_router(tts_router)


@app.on_event("startup")
async def on_startup():
    # ساخت دایرکتوری‌های موردنیاز
    ensure_directories()
    log.info(f"Audio dir is {settings.AUDIO_DIR}")


# صفحهٔ اصلی — همان SPA را سرو می‌کند
@app.get("/", response_class=HTMLResponse, include_in_schema=False)
async def index():
    index_path = static_dir / "index.html"
    if not index_path.exists():
        return HTMLResponse("<h1>Static UI not found</h1>", status_code=404)
    return HTMLResponse(index_path.read_text(encoding="utf-8"))


# (اختیاری) دانلود با Content-Disposition: attachment
# ورودی: شناسه‌ی فایل به صورت <sha256>.<ext>  (مثلاً 7bf2...c9.mp3)
# فایل واقعی در app/static/audio/<first2>/<sha256>.<ext> ذخیره شده است
_FILE_ID_RE = re.compile(r"^(?P<hex>[0-9a-fA-F]{64})\.(?P<ext>mp3|ogg|wav)$")


@app.get("/download/{file_id}", include_in_schema=False)
async def download(file_id: str):
    m = _FILE_ID_RE.match(file_id)
    if not m:
        raise HTTPException(status_code=400, detail="Invalid file id.")
    hex_id = m.group("hex").lower()
    ext = m.group("ext").lower()
    rel = Path(hex_id[:2]) / f"{hex_id}.{ext}"
    path = settings.AUDIO_DIR / rel
    if not path.exists():
        raise HTTPException(status_code=404, detail="File not found.")

    return FileResponse(
        path.as_posix(),
        media_type=f"audio/{'mpeg' if ext=='mp3' else ext}",
        filename=f"{hex_id}.{ext}",
        headers={"Content-Disposition": f'attachment; filename="{hex_id}.{ext}"'},
    )


# نکته: /static/audio/... به‌صورت مستقیم توسط StaticFiles سرو می‌شود،
# بنابراین کلاینت می‌تواند هم URL مستقیم داشته باشد، هم لینک دانلود اجباری از /download/...
