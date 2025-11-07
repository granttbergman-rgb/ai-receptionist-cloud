# availability.py
import os, sqlite3, datetime as dt
from typing import List, Literal, Optional
from pydantic import BaseModel, Field
from fastapi import APIRouter

router = APIRouter(prefix="/agent")

DB_PATH = os.path.join(os.path.dirname(__file__), "data.db")
INCREMENT_MIN = 15
OPEN_HOUR, CLOSE_HOUR = 9, 17
SERVICE_DURATION_MIN = {"consultation": 30}

class CheckAvailabilityBody(BaseModel):
    week_of: Optional[dt.date] = None
    service: Literal["consultation"] = "consultation"
    days: 
Optional[List[Literal["Mon","Tue","Wed","Thu","Fri","Sat","Sun"]]] = None

class Slot(BaseModel):
    start: dt.datetime
    end: dt.datetime

def get_conn():
    conn = sqlite3.connect(DB_PATH, detect_types=sqlite3.PARSE_DECLTYPES)
    conn.row_factory = sqlite3.Row
    return conn

def ensure_schema():
    conn = get_conn()
    c = conn.cursor()
    c.execute("SELECT name FROM sqlite_master WHERE type='table' AND 
name='appointments'")
    if c.fetchone() is None:
        c.execute("""
            CREATE TABLE appointments (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                service TEXT NOT NULL,
                customer_name TEXT,
                customer_phone TEXT,
                start TEXT NOT NULL,
                end TEXT NOT NULL
            )
        """)
        conn.commit()
    conn.close()

ensure_schema()

def week_bounds(any_date: dt.date):
    monday = any_date - dt.timedelta(days=any_date.weekday())
    start = dt.datetime.combine(monday, dt.time.min)
    end = start + dt.timedelta(days=7)
    return start, end

def next_week_bounds(today: dt.date):
    this_monday = today - dt.timedelta(days=today.weekday())
    next_monday = this_monday + dt.timedelta(days=7)
    start = dt.datetime.combine(next_monday, dt.time.min)
    end = start + dt.timedelta(days=7)
    return start, end

def day_name(d: dt.date) -> str:
    return ["Mon","Tue","Wed","Thu","Fri","Sat","Sun"][d.weekday()]

def generate_candidate_slots(start_week, end_week, service, days_filter):
    duration = dt.timedelta(minutes=SERVICE_DURATION_MIN[service])
    increment = dt.timedelta(minutes=INCREMENT_MIN)
    out = []
    cur = start_week
    while cur < end_week:
        d = cur.date()
        dn = day_name(d)
        if (days_filter is None and dn in ["Mon","Tue","Wed","Thu","Fri"]) 
or (days_filter and dn in days_filter):
            day_open = dt.datetime.combine(d, dt.time(hour=OPEN_HOUR))
            day_close = dt.datetime.combine(d, dt.time(hour=CLOSE_HOUR))
            t = day_open
            while t + duration <= day_close:
                out.append((t, t + duration))
                t += increment
        cur += dt.timedelta(days=1)
        cur = dt.datetime.combine(cur.date(), dt.time.min)
    return out

def fetch_busy_intervals(service, start_week, end_week):
    conn = get_conn(); c = conn.cursor()
    c.execute("""
        SELEC
T start, end
        FROM appointments
        WHERE service = ?
          AND start < ?
          AND end > ?
    """, (service, end_week.isoformat(), start_week.isoformat()))
    rows = c.fetchall(); conn.close()
    busy = []
    for r in rows:
        try:
            s = dt.datetime.fromisoformat(r["start"])
            e = dt.datetime.fromisoformat(r["end"])
            busy.append((s, e))
        except Exception:
            continue
    return busy

def overlaps(a_start, a_end, b_start, b_end) -> bool:
    return a_start < b_end and a_end > b_start

def subtract_busy(candidates, busy):
    if not busy:
        return candidates
    free = []
    for s, e in candidates:
        if not any(overlaps(s, e, bs, be) for bs, be in busy):
            free.append((s, e))
    return free

@router.post("/check_availability")
def check_availability(body: CheckAvailabilityBody):
    today = dt.date.today()
    if body.week_of:
        wk_start, wk_end = week_bounds(body.week_of)
    else:
        wk_start, wk_end = next_week_bounds(today)

    candidates = generate_candidate_slots(wk_start, wk_end, body.service, body.days)
    busy = fetch_busy_intervals(body.service, wk_start, wk_end)
    free = subtract_busy(candidates, busy)

    return {
        "status": "ok",
        "available_slots": [
            {"start": s.isoformat(timespec="minutes"), "end": e.isoformat(timespec="minutes")}
            for s, e in free
        ]
    }

