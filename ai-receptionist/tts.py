# tts.py
# ElevenLabs TTS client with streaming + sane error handling.

import os
import json
import httpx
from typing import Generator
from dotenv import load_dotenv

load_dotenv()

ELEVENLABS_API_KEY = os.getenv("ELEVENLABS_API_KEY")
DEFAULT_VOICE_ID = os.getenv("ELEVENLABS_VOICE_ID", "21m00Tcm4TlvDq8ikWAM")
DEFAULT_MODEL_ID = os.getenv("ELEVENLABS_MODEL_ID", "eleven_turbo_v2_5")

if not ELEVENLABS_API_KEY:
    raise RuntimeError("Missing ELEVENLABS_API_KEY in environment or .env")
def _headers() -> dict:
    return {
        "xi-api-key": ELEVENLABS_API_KEY,
        "accept": "audio/mpeg",
        "content-type": "application/json",
    }

def tts_stream(
    text: str,
    voice_id: str = DEFAULT_VOICE_ID,
    model_id: str = DEFAULT_MODEL_ID,
) -> Generator[bytes, None, None]:
    if not text or not text.strip():
        raise ValueError("text must be non-empty")

    url = f"https://api.elevenlabs.io/v1/text-to-speech/{voice_id}/stream"
    payload = {"text": text, "model_id": model_id}

    def gen() -> Generator[bytes, None, None]:
        with httpx.stream("POST", url, headers=_headers(), json=payload, 
timeout=60) as resp:
            ctype = resp.headers.get("content-type", "")
            if "audio" not in ctype:
                body = resp.read()
                try:
                    err = json.loads(body.decode("utf-8"))
                except Exception:
                    err = {"raw": body[:300].decode("utf-8", "ignore")}
                raise RuntimeError(f"ElevenLabs TTS error {resp.status_code}: {err}")
            for chunk in resp.iter_bytes():
                if chunk:
                    yield chunk

    return gen()

def healthcheck() -> bool:
    try:
        r = httpx.get(
            "https://api.elevenlabs.io/v1/models",
            headers={"xi-api-key": ELEVENLABS_API_KEY, "accept": "application/json"},
            timeout=10,
        )
        return r.status_code == 200
    except Exception:
        return False


