# ai_converse.py
from fastapi import APIRouter
from pydantic import BaseModel
from typing import List, Dict, Any
from booking import free_slots as check_availability, create as create_appointment

router = APIRouter()

# ---------- Schemas ----------
class CheckAvailabilityIn(BaseModel):
    service: str
    date: str            # YYYY-MM-DD
    duration_min: int

class Slot(BaseModel):
    start: str           # ISO-like "YYYY-MM-DDTHH:MM"
    end: str

class CheckAvailabilityOut(BaseModel):
    slots: List[Slot]

class CreateAppointmentIn(BaseModel):
    service: str
    start: str           # "YYYY-MM-DDTHH:MM"
    end: str             # "YYYY-MM-DDTHH:MM"
    customer_name: str
    customer_phone: str

class CreateAppointmentOut(BaseModel):
    appointment: Dict[str, Any]

# ---------- Tool endpoints ----------
@router.post("/tools/check_availability", 
response_model=CheckAvailabilityOut)
def api_check_availability(payload: CheckAvailabilityIn):
    slots = check_availability(
        service=payload.service,
        date=payload.date,
        duration_min=payload.duration_min,
    )
    return {"slots": slots}

@router.post("/tools/create_appointment", 
response_model=CreateAppointmentOut)
def api_create_appointment(payload: CreateAppointmentIn):
    appt = create_appointment(
        service=payload.service,
        start_iso=payload.start,   # <-- THIS NAME MATTERS
        end_iso=payload.end,       # <-- THIS NAME MATTERS
        customer_name=payload.customer_name,
        customer_phone=payload.customer_phone,
    )
    return {"appointment": appt}
@router.get("/tools/list_appointments")
def api_list_appointments():
    from booking import list_appointments
    appts = list_appointments()
    return {"appointments": appts}

