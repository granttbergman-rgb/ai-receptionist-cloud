import os

# drop the duplicate manual getenvs if you’re importing from app.agent_env already
# import os
# ELEVEN_API_KEY = os.getenv("ELEVENLABS_API_KEY")
# ELEVEN_VOICE_ID = os.getenv("ELEVENLABS_VOICE_ID", "EXAVITQu4vr4xnSDxMaL")
# ELEVEN_MODEL = os.getenv("ELEVENLABS_MODEL_ID", "eleven_turbo_v2")
# ELEVEN_OUTPUT_FORMAT = os.getenv("ELEVENLABS_OUTPUT_FORMAT", "mp3")

from app.agent_env import (
    ELEVEN_API_KEY, ELEVEN_VOICE_ID, ELEVEN_MODEL, ELEVEN_OUTPUT_FORMAT
)

from datetime import datetime, time, timedelta   # ← add time
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field, validator
# EITHER keep pytz and add it to requirements.txt, OR use zoneinfo
import pytz
from zoneinfo import ZoneInfo

router = APIRouter()

ALLOWED = {"consultation","follow-up","onboarding","demo call"}

class AvailabilityIn(BaseModel):
    service: str = Field(...)
    date: str = Field(..., description="YYYY-MM-DD")
    duration_min: int = Field(30, ge=5, le=180)

    @validator("service", pre=True)
    def norm_service(cls, v):
        s = str(v).strip().lower()
        if s in {"consulatation","consult","consulttion"}:
            s = "consultation"
        if s not in ALLOWED:
            raise ValueError("invalid_service")
        return s

    @validator("date")
    def check_date(cls, v):
        # Expect exact YYYY-MM-DD
        try:
            datetime.fromisoformat(v)  # raises on junk like 'string'
        except Exception:
            raise ValueError("invalid_date_format")
        return v

@router.post("/check_availability")
def check_availability(payload: AvailabilityIn):
    tz = pytz.timezone("America/Chicago")
    d = datetime.fromisoformat(payload.date).date()
    base = tz.localize(datetime.combine(d, time(9, 0)))
    close = tz.localize(datetime.combine(d, time(17, 0)))

    slot = timedelta(minutes=payload.duration_min)
    slots = []
    t = base
    # TODO: subtract existing appts here if you have them
    while t + slot <= close:
        # return ISO without timezone if that's what your client expects
        start_iso = t.replace(tzinfo=None).isoformat(timespec="seconds")
        end_iso = (t + slot).replace(tzinfo=None).isoformat(timespec="seconds")
        slots.append({"start": start_iso, "end": end_iso})
        t += slot

    return {"date": payload.date, "service": payload.service, "slots": slots}

