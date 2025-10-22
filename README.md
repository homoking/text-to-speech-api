````markdown
# Text-to-Speech API

A clean, modular **Text-to-Speech (TTS)** web service built with **FastAPI** and a minimal single-page frontend (Tailwind + Vanilla JS).  
It supports multiple engines, caching, offline fallback, and ready-to-serve audio through REST endpoints.

---

## Features

- 🎤 **Engines**
  - **edge-tts** — Natural, online Microsoft Edge voices.
  - **pyttsx3** — Offline fallback using system-installed voices.

- 💾 **Caching**
  - Audio files are hashed by `(engine, voice, text/ssml, rate, pitch, format)` and reused if identical requests repeat.

- 🔊 **Audio Formats**
  - Default: `mp3`
  - Also supports `ogg` and `wav` (requires ffmpeg for conversions)

- 🌐 **Frontend**
  - Served at `/`
  - Built with Tailwind (via CDN) and vanilla JS
  - Simple, responsive, and saves user preferences in `localStorage`

- 🧩 **Endpoints**
  - `GET /voices?engine=edge|pyttsx3` → List available voices  
  - `POST /tts` → Generate or return cached audio  
  - `POST /tts/ssml` → Same as `/tts`, but forces `ssml=true`  
  - `GET /healthz` → Health check  
  - `GET /download/{id}` → Optional direct download (hashed file id)

---

## Quick Start

### 1. Setup Environment
```bash
git clone https://github.com/yourname/text-to-speech-api.git
cd text-to-speech-api
python -m venv .venv
source .venv/bin/activate  # Windows: .venv\Scripts\activate
pip install -r requirements.txt
cp .env.example .env
````

### 2. (Optional) Install ffmpeg

Required only for format conversions (`wav` ↔ `mp3/ogg`).

```bash
# macOS
brew install ffmpeg
# Debian/Ubuntu
sudo apt-get install -y ffmpeg
# Windows (Chocolatey)
choco install ffmpeg
```

### 3. Run the Server

```bash
uvicorn app.main:app --reload --port 8000
```

Then open: **[http://localhost:8000](http://localhost:8000)**

---

## Request Examples

### ➤ Get Voices

```bash
GET /voices?engine=edge
```

```json
{
  "engine": "edge",
  "voices": [
    {"id": "en-US-GuyNeural", "name": "Guy", "locale": "en-US", "gender": "male"},
    {"id": "en-US-JennyNeural", "name": "Jenny", "locale": "en-US", "gender": "female"}
  ]
}
```

### ➤ Generate Audio

```bash
POST /tts
Content-Type: application/json
```

```json
{
  "text": "Hello world",
  "engine": "edge",
  "voice": "en-US-GuyNeural",
  "rate": 0,
  "pitch": 0,
  "format": "mp3",
  "ssml": false,
  "normalize": true
}
```

**Response**

```json
{
  "audio_url": "/static/audio/7b/7bf2a3...c.mp3",
  "duration": 3.42,
  "engine": "edge",
  "voice": "en-US-GuyNeural",
  "format": "mp3",
  "cached": true
}
```

---

## Configuration

Defined in `.env` or environment variables:

| Variable         | Default                 | Description                 |
| ---------------- | ----------------------- | --------------------------- |
| `APP_NAME`       | `Text to Speech API`    | Application title           |
| `BASE_URL`       | `http://localhost:8000` | Public base URL             |
| `AUDIO_DIR`      | `app/static/audio`      | Output directory            |
| `CACHE_ENABLED`  | `true`                  | Enable or disable caching   |
| `MAX_CHARS`      | `3000`                  | Max text length per request |
| `DEFAULT_ENGINE` | `edge`                  | Default TTS engine          |
| `DEFAULT_VOICE`  | `en-US-JennyNeural`     | Default voice               |
| `DEFAULT_FORMAT` | `mp3`                   | Default output format       |

---

## Notes

* **edge-tts 403 errors:** If Edge voices fail due to Microsoft endpoint issues, the system automatically falls back to `pyttsx3`.
* **pyttsx3:** Works entirely offline but depends on your OS voices.
* **Rate & Pitch:**

  * Rate: `-50..+50` → percentage change.
  * Pitch: `-12..+12` → semitone shift (Edge only).
* **Caching:** Two-level directory structure under `/static/audio/`.

---

## Author

**Hossein Mohammadi Kia**
[github.com/homoking](https://github.com/homoking)

```
```
