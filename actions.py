# actions.py
import os, httpx
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

BASE = os.getenv("INTERNAL_BASE_URL", "http://127.0.0.1:8000")
router = APIRouter(prefix="/agent", tags=["agent-actions"])

class AvailIn(BaseModel):
    service: str
    date: str
    duration_min: int = 30

class BookIn(BaseModel):
    service: str
    date: str
    start_iso: str   # YYYY-MM-DDTHH:MM:SS
    end_iso: str
    customer_name: str
    customer_phone: str

@router.post("/check_availability")
async def agent_check_availability(p: AvailIn):
    try:
        async with httpx.AsyncClient(timeout=10) as c:
            r = await c.post(f"{BASE}/tools/check_availability", 
json=p.model_dump())
        r.raise_for_status()
        return r.json()
    except Exception as e:
        raise HTTPException(400, f"availability_error: {e}")

@router.post("/create_appointment")
async def agent_create_appointment(p: BookIn):
    body = {
        "service": p.service,
        "date": p.date,
        "start": p.start_iso,
        "end": p.end_iso,
        "customer_name": p.customer_name,
        "customer_phone": p.customer_phone,
    }
    try:
        async with httpx.AsyncClient(timeout=10) as c:
            r = await c.post(f"{BASE}/tools/create_appointment", 
json=body)
        r.raise_for_status()
        return r.json()
    except Exception as e:
        raise HTTPException(400, f"booking_error: {e}")

