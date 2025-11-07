# app.py
"""
AI Receptionist — single-file FastAPI app

Includes:
- /tts                 ElevenLabs streaming TTS (audio/mpeg)
- /voice, /voice/process  Twilio TwiML fallback (short, barge-in)
- /agent/*             Actions the ElevenLabs Agent calls
- /tools/*             Pulled from your existing ai_converse router (if 
present)
- /static              For pre-rendered audio (greeting.mp3, etc.)
- /healthz             Health check

ENV you must set:
  PUBLIC_URL=https://<your>.ngrok-free.dev
  ELEVEN_API_KEY=sk_...
  ELEVEN_VOICE_ID=21m00Tcm4TlvDq8ikWAM   # or your custom
  ELEVEN_MODEL=eleven_turbo_v2_5
  INTERNAL_BASE_URL=http://127.0.0.1:8000   # this same app
"""

import os
from typing import Dict, Tuple, Optional
from urllib.parse import quote_plus
import sqlite3
import httpx
from fastapi import FastAPI, Form, HTTPException, APIRouter
from fastapi.responses import Response, StreamingResponse, HTMLResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel
from datetime import datetime
from fastapi import FastAPI
from availability import router as availability_router
from fastapi.responses import JSONResponse
# -------------------- App bootstrap --------------------

app = FastAPI(title="AI Receptionist")
from fastapi.middleware.cors import CORSMiddleware

app = FastAPI(title="AI Receptionist")

# CORS so your agent/webhook can hit this from anywhere
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# >>> MOUNT THE AVAILABILITY ROUTER <<<
app.include_router(availability_router)

# Debug: list routes on startup
@app.on_event("startup")
async def _show_routes():
    print("Routes:", [r.path for r in app.router.routes])

@app.get("/agent/current_date")
def get_date():
    now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    return JSONResponse({"current_date": now})
# Try to include your existing /tools router (ai_converse defines it)
try:
    from ai_converse import router as ai_router  # must expose /tools/check_availability & /tools/create_appointment
    app.include_router(ai_router)
    print("[boot] ai_converse router mounted.")
except Exception as e:
    print(f"[boot] ai_converse router NOT mounted: {e}")

# Mount /static for pre-rendered MP3s
os.makedirs("static", exist_ok=True)
app.mount("/static", StaticFiles(directory="static"), name="static")

# -------------------- Helpers & config --------------------
from pydantic import BaseModel, Field, ConfigDict
import datetime as dt
from typing import Optional, List, Literal

class CheckAvailabilityBody(BaseModel):
    model_config = ConfigDict(populate_by_name=True)
    # Accept "date" from the client, map to week_of internally
    week_of: Optional[dt.date] = Field(None, alias="date")
    service: Literal["consultation"] = "consultation"
    days: Optional[List[Literal["Mon","Tue","Wed","Thu","Fri","Sat","Sun"]]] = None

def _public_url() -> str:
    return os.getenv("PUBLIC_URL") or os.getenv("PUBLIC_HTTPS") or "http://localhost:8000"

ELEVEN_API_KEY = os.getenv("ELEVEN_API_KEY", "")
ELEVEN_VOICE_ID = os.getenv("ELEVEN_VOICE_ID", "21m00Tcm4TlvDq8ikWAM")
ELEVEN_MODEL = os.getenv("ELEVEN_MODEL", "eleven_turbo_v2_5")
INTERNAL_BASE = os.getenv("INTERNAL_BASE_URL", "http://127.0.0.1:8000")

_tts_cache: Dict[Tuple[str, str], bytes] = {}  # (CallSid, text) -> mp3 
bytes


def _eleven_stream(text: str):
    if not ELEVEN_API_KEY:
        raise HTTPException(500, "ELEVEN_API_KEY not set")
    url = f"https://api.elevenlabs.io/v1/text-to-speech/{ELEVEN_VOICE_ID}/stream?optimize_streaming_latency=3"
    headers = {
        "xi-api-key": ELEVEN_API_KEY,
        "Accept": "audio/mpeg",
        "Content-Type": "application/json",
    }
    payload = {
        "text": text,
        "model_id": ELEVEN_MODEL,
        "voice_settings": {
            "stability": 0.4, "similarity_boost": 0.8, "style": 0.2, 
"use_speaker_boost": True
        },
    }
    with httpx.stream("POST", url, headers=headers, json=payload, timeout=60) as r:
        try:
            r.raise_for_status()
        except httpx.HTTPStatusError as e:
            msg = e.response.text[:200] if e.response else str(e)
            raise HTTPException(502, f"ElevenLabs error: {msg}")
        for chunk in r.iter_bytes():
            if chunk:
                yield chunk


def _eleven_stream_cached(call_sid: Optional[str], text: str):
    if not call_sid:
        yield from _eleven_stream(text)
        return
    key = (call_sid, text)
    if key in _tts_cache:
        yield _tts_cache[key]
        return
    buf = bytearray()
    for chunk in _eleven_stream(text):
        buf.extend(chunk)
        yield chunk
    _tts_cache[key] = bytes(buf)

# -------------------- Basic routes --------------------

@app.get("/", response_class=HTMLResponse)
def home():
    return "<h3>AI Receptionist API is up.</h3>"

@app.get("/healthz")
def healthz():
    return {"status": "ok"}

@app.get("/tts")
def tts_endpoint(text: str = "Thanks for calling. The AI receptionist is alive.", sid: Optional[str] = None):
    return StreamingResponse(_eleven_stream_cached(sid, text), media_type="audio/mpeg")

# -------------------- Twilio fallback (optional) --------------------

@app.post("/voice")
async def voice(From: str = Form(None), To: str = Form(None), CallSid: str 
= Form(None)):
    public = _public_url()
    greeting = (
        f"{public}/static/greeting.mp3"
        if os.path.isfile("static/greeting.mp3")
        else f"{public}/tts?sid={CallSid}&text={quote_plus('Thanks for calling. How can I help you?')}"
    )
    twiml = f"""<?xml version="1.0" encoding="UTF-8"?>
<Response>
  <Gather input="speech"
          action="{public}/voice/process"
          method="POST"
          timeout="2"
          speechTimeout="auto"
          bargeIn="true"
          language="en-US">
    <Play>{greeting}</Play>
  </Gather>
  <Redirect method="POST">{public}/voice</Redirect>
</Response>"""
    return Response(content=twiml, media_type="text/xml")

@app.post("/voice/process")
async def voice_process(SpeechResult: str = Form(None), CallSid: str = 
Form(None)):
    public = _public_url()
    utter = (SpeechResult or "").strip().lower()
    if not utter:
        reply = "I didn't catch that. Say a date and time."
    elif any(k in utter for k in ("book", "appointment", "schedule")):
        reply = "Great. Say the date and time you want."
    elif any(k in utter for k in ("hour", "open")):
        reply = "We are open nine to five, Monday through Friday."
    else:
        reply = "I can help you book or share hours."
    play = f"{public}/tts?sid={CallSid}&text={quote_plus(reply)}"
    twiml = f"""<?xml version="1.0" encoding="UTF-8"?>
<Response>
  <Play>{play}</Play>
  <Redirect method="POST">{public}/voice</Redirect>
</Response>"""
    return Response(content=twiml, media_type="text/xml")

# -------------------- ElevenLabs Agent actions (the ones you were missing) --------------------
from datetime import datetime, timedelta, time 
import zoneinfo, requests, json

TZ = zoneinfo.ZoneInfo("America/Chicago")

def next_monday_iso(today=None):
    if not today:
        today = datetime.now(TZ).date()
    # Monday = 0
    days_until_next_mon = (7 - today.weekday()) % 7
    if days_until_next_mon == 0:
        days_until_next_mon = 7
    next_mon = today + timedelta(days=days_until_next_mon)
    return next_mon.isoformat()


agent = APIRouter(prefix="/agent", tags=["agent-actions"])

class AvailIn(BaseModel):
    service: str
    date: str
    duration_min: int = 30

class BookIn(BaseModel):
    service: str
    date: str
    start_iso: str   # YYYY-MM-DDTHH:MM:SS
    end_iso: str     # YYYY-MM-DDTHH:MM:SS
    customer_name: str
    customer_phone: str

# ---------- Helpers (safe to paste once) ----------
import os, re, sqlite3, time
from datetime import datetime, timedelta
from fastapi import Request, HTTPException

# Use your existing DB_PATH if you already have one defined.
DB_PATH = os.path.join(os.path.dirname(__file__), "data.db")

_AMPM = re.compile(r"^\s*(\d{1,2})(?::(\d{2}))?\s*(AM|PM)\s*$", re.I)

def _parse_time_24h(t: str):
    h, m = t.strip().split(":")
    return int(h), int(m)

def _parse_time_12h(t: str):
    m = _AMPM.match(t.strip())
    if not m:
        raise ValueError("bad 12h time")
    hh = int(m.group(1))
    mm = int(m.group(2) or 0)
    ap = m.group(3).upper()
    if hh == 12:
        hh = 0
    if ap == "PM":
        hh += 12
    return hh, mm

def coerce_start_end(p: dict):
    """
    Accepts one of:
      1) ISO start/end
      2) date + time (12h '9:00 AM' or 24h '09:00'), optional duration 
(min, default 30)
      3) date + time_range '9:45–10:15 AM' or '9:45-10:15 AM'
    Returns (start_iso, end_iso)
    """
    # 1) ISO
    if "start" in p and "end" in p:
        datetime.fromisoformat(p["start"].replace("Z",""))
        datetime.fromisoformat(p["end"].replace("Z",""))
        return p["start"], p["end"]

    # 2) date + time_range
    if "date" in p and "time_range" in p:
        date_str = p["date"]
        rng = p["time_range"].replace("—","-").replace("–","-")
        left, right = [s.strip() for s in rng.split("-", 1)]
        # inherit AM/PM from right if left lacks it
        if ("AM" in right.upper() or "PM" in right.upper()) and not ("AM" in left.upper() or "PM" in left.upper()):
            left = f"{left} {right.split()[-1]}"
        # parse left
        if "AM" in left.upper() or "PM" in left.upper():
            h1, m1 = _parse_time_12h(left)
        else:
            h1, m1 = _parse_time_24h(left)
        # parse right
        if "AM" in right.upper() or "PM" in right.upper():
            h2, m2 = _parse_time_12h(right)
        else:
            h2, m2 = _parse_time_24h(right)

        start_dt = datetime.fromisoformat(date_str).replace(hour=h1, minute=m1, second=0, microsecond=0)
        end_dt   = datetime.fromisoformat(date_str).replace(hour=h2, minute=m2, second=0, microsecond=0)
        return start_dt.isoformat(), end_dt.isoformat()

    # 3) date + time (+ duration)
    if "date" in p and "time" in p:
        date_str = p["date"]
        t = p["time"].strip()
        dur = int(p.get("duration", 30))
        if "AM" in t.upper() or "PM" in t.upper():
            hh, mm = _parse_time_12h(t)
        else:
            hh, mm = _parse_time_24h(t)
        start_dt = datetime.fromisoformat(date_str).replace(hour=hh, minute=mm, second=0, microsecond=0)
        end_dt   = start_dt + timedelta(minutes=dur)
        return start_dt.isoformat(), end_dt.isoformat()

    raise ValueError("Need ISO start/end, or date+time, or date+time_range")

# ---------- The ONE route you need ----------
from fastapi import Request, HTTPException
from datetime import datetime
import sqlite3, time

@app.post("/agent/create_appointment")
async def create_appointment(request: Request):
    p = await request.json()
    print(">> RAW CREATE PAYLOAD:", p)

    service = p.get("service") or "consultation"
    name    = p.get("customer_name") or p.get("name") or "Unknown"
    phone   = p.get("customer_phone") or p.get("phone") or ""

    # Parse time (your helper)
    try:
        start_iso, end_iso = coerce_start_end(p)
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"bad_time_payload: {e}")

    # Reject past starts
    start_dt = datetime.fromisoformat(start_iso.replace("Z", ""))
    now = datetime.now(tz=start_dt.tzinfo) if start_dt.tzinfo else datetime.now()
    if start_dt < now:
        raise HTTPException(status_code=400, detail="start_in_past")

    # Insert with WAL + retry; 409 on duplicate
    attempts = 3
    for i in range(attempts):
        conn = None
        try:
            conn = sqlite3.connect(DB_PATH, timeout=5)
            conn.execute("PRAGMA journal_mode=WAL;")
            conn.execute("PRAGMA busy_timeout=5000;")
            c = conn.cursor()
            c.execute("""
                INSERT INTO appointments(service, customer_name, customer_phone, start, end)
                VALUES (?, ?, ?, ?, ?)
            """, (service, name, phone, start_iso, end_iso))
            conn.commit()
            break
        except sqlite3.IntegrityError:
            if conn: conn.close()
            raise HTTPException(status_code=409, detail="Slot already booked.")
        except sqlite3.OperationalError as e:
            if conn: conn.close()
            if "locked" in str(e).lower() and i < attempts - 1:
                time.sleep(0.25 * (i + 1))
                continue
            raise HTTPException(status_code=503, detail=f"db_locked: {e}")
        except Exception as e:
            if conn: conn.close()
            raise HTTPException(status_code=400, detail=f"db_error: {e}")
        finally:
            try:
                if conn: conn.close()
            except:
                pass

    # Build ICS string (note: this is a Python f-string, triple-quoted correctly)
    ics = f"""BEGIN:VCALENDAR
VERSION:2.0
PRODID:-//greensheets//receptionist//EN
BEGIN:VEVENT
UID:{start_iso}-{name}
DTSTART:{start_iso.replace('-', '').replace(':', '')}
DTEND:{end_iso.replace('-', '').replace(':', '')}
SUMMARY:{service.title()}
END:VEVENT
END:VCALENDAR"""

    # Proper return dict — no comments inline, no stray quotes
    return {
        "ok": True,
        "service": service,
        "customer_name": name,
        "customer_phone": phone,
        "start": start_iso,
        "end": end_iso,
        "ics": ics
    }

    # --- Write to the database ---
   
    try:
        conn = sqlite3.connect(DB_PATH)
        c = conn.cursor()
        c.execute("""
            INSERT INTO appointments(service, customer_name, customer_phone, start, end)
            VALUES (?, ?, ?, ?, ?)
        """, (service, name, phone, start_iso, end_iso))
        conn.commit()
    except sqlite3.IntegrityError:
        # This means the same slot already exists (unique constraint triggered)
        raise HTTPException(status_code=409, detail="Slot already booked.")
    except Exception as e:
        print("DB insert failed:", e)
        raise HTTPException(status_code=400, detail=f"db_error: {e}")
    finally:
        conn.close()

    # --- Return confirmation ---
    return {
        "ok": True,
        "service": service,
        "customer_name": name,
        "customer_phone": phone,
        "start": start_iso,
        "end": end_iso
    }

# -------------------- Dev entrypoint --------------------

if __name__ == "__main__":
    import uvicorn
    uvicorn.run("app:app", host="0.0.0.0", port=8000, reload=True)

