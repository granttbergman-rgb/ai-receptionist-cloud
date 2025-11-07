import os

ELEVEN_API_KEY = os.getenv("ELEVENLABS_API_KEY")
ELEVEN_VOICE_ID = os.getenv("ELEVENLABS_VOICE_ID", "EXAVITQu4vr4xnSDxMaL")
ELEVEN_MODEL = os.getenv("ELEVENLABS_MODEL_ID", "eleven_turbo_v2")
ELEVEN_OUTPUT_FORMAT = os.getenv("ELEVENLABS_OUTPUT_FORMAT", "mp3")
from app.agent_env import (
    ELEVEN_API_KEY, ELEVEN_VOICE_ID, ELEVEN_MODEL, ELEVEN_OUTPUT_FORMAT
)

from fastapi import APIRouter, Body
from pydantic import BaseModel
from datetime import datetime, timedelta

router = APIRouter(prefix="/agent", tags=["agent"])

class AvailabilityRequest(BaseModel):
    date: str
    service: str

@router.post("/check_availability")
def check_availability(payload: AvailabilityRequest):
    base = datetime.fromisoformat(payload.date).replace(hour=9, minute=0, 
second=0, microsecond=0)
    slots = []
    for i in range(0, 8*2):  # 9–17, every 30 minutes
        t = base + timedelta(minutes=30*i)
        if t.hour == 12:  # skip lunch
            continue
        slots.append({"start": t.isoformat(), "end": (t + 
timedelta(minutes=30)).isoformat()})
    return {"service": payload.service, "date": payload.date, "slots": 
slots}

@router.post("/handle_incoming")
def handle_incoming(from_number: str = Body(None), to_number: str = 
Body(None), speech_text: str = Body(None)):
    return {"message": "Hello from the cloud receptionist.", "caller": 
from_number, "heard": speech_text}

@router.post("/status_callback")
def status_callback():
    return {"ok": True}

@router.post("/current_date")
def get_current_date():
    tz = pytz.timezone("America/Chicago")
    now = datetime.now(tz)
    return {"current_date": now.strftime("%Y-%m-%d")}

