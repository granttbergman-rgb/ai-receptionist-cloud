import re
from datetime import timedelta
from dateutil import parser as dtp
from config import SERVICES

INCREMENT_MIN = 15

KEYWORDS = {
    "book": ["book","schedule","set","make an appointment","need an 
appointment"],
    "reschedule": ["reschedule","move","change time"],
    "cancel": ["cancel","delete"],
    "hours": ["hours","open","closing"],
    "help": ["help","human","representative"]
}

def detect_intent(text: str):
    t = (text or "").lower().strip()
    for intent, kws in KEYWORDS.items():
        if any(k in t for k in kws):
            return intent
    try:
        dtp.parse(t, fuzzy=True)
        return "book"
    except Exception:
        return "smalltalk"

def extract_when(text: str, default_minutes=30):
    try:
        dt = dtp.parse(text, fuzzy=True)
        minute = (dt.minute // INCREMENT_MIN) * INCREMENT_MIN
        dt = dt.replace(minute=minute, second=0, microsecond=0)
        start = dt
        end = dt + timedelta(minutes=default_minutes)
        return start, end
    except Exception:
        return None, None

def extract_service(text: str):
    t = (text or "").lower()
    for name in SERVICES:
        if name in t:
            return name, SERVICES[name]["duration_min"]
    return "consultation", SERVICES["consultation"]["duration_min"]

def normalize_name(text: str):
    m = re.findall(r"[A-Z][a-z]+", text or "")
    if m:
        return " ".join(m[:2])
    return None

