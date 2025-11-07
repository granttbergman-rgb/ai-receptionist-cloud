# availability.py
# Clean weekly/next-slot availability endpoints with solid syntax and safe logging.

import os
import sqlite3
import datetime as dt
from typing import Dict, List, Literal

from fastapi import APIRouter

# --- Pydantic v1/v2 compatibility -------------------------------------------
from pydantic import BaseModel, Field  # works in both
try:
    from pydantic import ConfigDict      # v2
    _PD_V2 = True
except Exception:                         # v1
    _PD_V2 = False
# --- Human date resolver (America/Chicago) -----------------------------------
from typing import Optional, Union
try:
    from zoneinfo import ZoneInfo
    _TZ = ZoneInfo("America/Chicago")
except Exception:
    _TZ = None  # fallback to server local time

def _today_chi() -> dt.date:
    if _TZ:
        return dt.datetime.now(_TZ).date()
    return dt.date.today()

_WEEKDAYS = {  # monday=0
    "monday": 0, "tuesday": 1, "wednesday": 2,
    "thursday": 3, "friday": 4, "saturday": 5, "sunday": 6
}

def _resolve_week_date(date_val: Optional[Union[str, dt.date]],
                       week_of_val: Optional[Union[str, dt.date]]) -> dt.date:
    """Return a concrete Monday-like 'week_of' date from messy inputs."""
    val = week_of_val if week_of_val is not None else date_val
    # already a date
    if isinstance(val, dt.date):
        return val
    # try to parse string patterns
    if isinstance(val, str):
        s = val.strip().lower()

        if not s or s in {"next week"}:
            return _next_monday()

        if s in {"today"}:
            return _today_chi()

        if s in {"tomorrow", "tmrw"}:
            return _today_chi() + dt.timedelta(days=1)

        # "next monday", "monday next week", "tuesday next week", "monday"
        parts = s.replace(",", " ").split()
        if "next" in parts and any(p in _WEEKDAYS for p in parts):
            # next <weekday> relative to today
            base = _today_chi()
            target = next(p for p in parts if p in _WEEKDAYS)
            target_idx = _WEEKDAYS[target]
            diff = (7 - base.weekday() + target_idx) % 7
            diff = diff or 7
            return base + dt.timedelta(days=diff)
# ISO fallback
        try:
            return dt.date.fromisoformat(s)
        except Exception:
            return _next_monday()

    # totally missing -> next Monday
    return _next_monday()


router = APIRouter(prefix="/agent")
from typing import Optional, Union
from fastapi import HTTPException
from fastapi import Query

class LegacyReq(BaseModel):
    # tolerate extra fields
    if _PD_V2:
        model_config = ConfigDict(extra="ignore")
    else:
        class Config:
            extra = "ignore"

    service: Optional[str] = None
    date: Optional[Union[str, dt.date]] = None
    week_of: Optional[Union[str, dt.date]] = None
    duration_min: int = 30

@router.post("/check_availability")
def check_availability_legacy(body: LegacyReq):
    # Resolve week date from any format
    week_date = _resolve_week_date(body.date, body.week_of)
    service = body.service or "consultation"

    days = _generate_week(service, week_date, body.duration_min)
    slots = [slot for day_slots in days.values() for slot in day_slots]
    print("[LEGACY] service={} week_of={} slots={}".format(service, week_date, len(slots)))
    return {"status": "ok", "available_slots": slots}
# === Next-week endpoint (no date guessing, no LLM prompts) ===================
@router.get("/availability/next_week")
def availability_next_week(
    service: str = Query(default="consultation"),
    duration_min: int = Query(default=30)
):
    # compute next Monday (uses your _next_monday helper if present)
    try:
        next_monday = _next_monday()
    except NameError:
        # inline fallback if helper not in this file
        base = dt.date.today()
        days = (7 - base.weekday()) or 7
        next_monday = base + dt.timedelta(days=days)

    days = _generate_week(service, next_monday, duration_min)
    print("[NEXT_WEEK] service={} week_of={} slots={}".format(
        service, next_monday, sum(len(v) for v in days.values())
    ))
    return {"status": "ok", "week_of": str(next_monday), "days": days}

# --- Config ------------------------------------------------------------------
DB_PATH = os.path.join(os.path.dirname(__file__), "data.db")
OPEN_HOUR = 9          # business open (inclusive)
CLOSE_HOUR = 17        # business close (exclusive end for slots)
STEP_MIN = 15          # step between candidate starts (minutes)

# --- DB helpers --------------------------------------------------------------
def _conn():
    con = sqlite3.connect(DB_PATH)
    con.row_factory = sqlite3.Row
    return con

def _ensure_schema():
    con = _conn()
    cur = con.cursor()
    cur.execute(
        "SELECT name FROM sqlite_master WHERE type='table' AND name='appointments'"
    )
    if not cur.fetchone():
        cur.execute("""
            CREATE TABLE appointments (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                service TEXT NOT NULL,
                customer_name TEXT,
                customer_phone TEXT,
                start TEXT NOT NULL,
                end   TEXT NOT NULL
            );
        """)
        con.commit()
    # prevent double-booking
    cur.execute("""
        CREATE UNIQUE INDEX IF NOT EXISTS uniq_appt
        ON appointments(service, start, end);
    """)
    con.commit()
    con.close()

_ensure_schema()

# --- Time helpers ------------------------------------------------------------
def _week_bounds(d: dt.date) -> tuple[dt.datetime, dt.datetime]:
    monday = d - dt.timedelta(days=d.weekday())
    start = dt.datetime.combine(monday, dt.time.min)
    end = start + dt.timedelta(days=7)
    return start, end

def _busy(service: str, start: dt.datetime, end: dt.datetime) -> List[tuple[dt.datetime, dt.datetime]]:
    con = _conn()
    cur = con.cursor()
    cur.execute(
        """
        SELECT start, end FROM appointments
        WHERE service = ?
          AND start < ?
          AND end   > ?
        """,
        (service, end.isoformat(), start.isoformat()),
    )
    rows = cur.fetchall()
    con.close()
    out: List[tuple[dt.datetime, dt.datetime]] = []
    for r in rows:
        try:
            s = dt.datetime.fromisoformat(r["start"])
            e = dt.datetime.fromisoformat(r["end"])
            out.append((s, e))
        except Exception:
            # Skip malformed rows instead of crashing
            continue
    return out

def _overlap(a: tuple[dt.datetime, dt.datetime], b: tuple[dt.datetime, 
dt.datetime]) -> bool:
    return a[0] < b[1] and a[1] > b[0]

def _generate_week(service: str, week_of: dt.date, duration_min: int) -> Dict[str, List[Dict[str, str]]]:
    wk_start, wk_end = _week_bounds(week_of)
    step = dt.timedelta(minutes=STEP_MIN)
    dur = dt.timedelta(minutes=duration_min)
    busy = _busy(service, wk_start, wk_end)

    days: Dict[str, List[Dict[str, str]]] = {}
    cur = wk_start
    while cur < wk_end:
        d = cur.date()
        # Mon..Fri only
        if d.weekday() < 5:
            open_t = dt.datetime.combine(d, dt.time(OPEN_HOUR))
            close_t = dt.datetime.combine(d, dt.time(CLOSE_HOUR))
            t = open_t
            slots: List[Dict[str, str]] = []
            while t + dur <= close_t:
                cand = (t, t + dur)
                if not any(_overlap(cand, b) for b in busy):
                    slots.append({
                        "start": t.isoformat(timespec="minutes"),
                        "end":   (t + dur).isoformat(timespec="minutes")
                    })
                t += step
            days[d.isoformat()] = slots
        # advance exactly one day
        cur = dt.datetime.combine(d + dt.timedelta(days=1), dt.time.min)
    return days

# --- Pydantic models ---------------------------------------------------------
if _PD_V2:
    class WeekReq(BaseModel):
        # ignore unexpected fields (so agents can't 422 you by accident)
        model_config = ConfigDict(extra="ignore")
        service: Literal["consultation"]
        week_of: dt.date = Field(..., description="Any date inside the target week (YYYY-MM-DD).")
        duration_min: int = 30

    class NextReq(BaseModel):
        model_config = ConfigDict(extra="ignore")
        service: Literal["consultation"]
        start_date: dt.date
        count: int = 5
        duration_min: int = 30
else:
    class WeekReq(BaseModel):
        service: Literal["consultation"]
        week_of: dt.date = Field(..., description="Any date inside the target week (YYYY-MM-DD).")
        duration_min: int = 30
        class Config:
            extra = "ignore"

    class NextReq(BaseModel):
        service: Literal["consultation"]
        start_date: dt.date
        count: int = 5
        duration_min: int = 30
        class Config:
            extra = "ignore"

class WeekRes(BaseModel):
    status: Literal["ok"]
    days: Dict[str, List[Dict[str, str]]]

# --- Endpoints ---------------------------------------------------------------
@router.post("/availability/week", response_model=WeekRes)
def availability_week(body: WeekReq):
    days = _generate_week(body.service, body.week_of, body.duration_min)
    # single-line safe logging (no f-strings, no wrap hazards)
    print("[WEEK] service={} week_of={} slots={}".format (body.service, body.week_of, sum(len(v) for v in days.values())
    ))
    return {"status": "ok", "days": days}

@router.post("/availability/next")
def availability_next(body: NextReq):
    # search across 3 weeks starting from Monday of start_date
    start, _ = _week_bounds(body.start_date)
    end = start + dt.timedelta(days=21)
    step = dt.timedelta(minutes=STEP_MIN)
    dur = dt.timedelta(minutes=body.duration_min)
    busy = _busy(body.service, start, end)

    found: List[Dict[str, str]] = []
    cur = start
    while cur < end and len(found) < body.count:
        d = cur.date()
        if d.weekday() < 5:
            open_t = dt.datetime.combine(d, dt.time(OPEN_HOUR))
            close_t = dt.datetime.combine(d, dt.time(CLOSE_HOUR))
            t = open_t
            while t + dur <= close_t and len(found) < body.count:
                cand = (t, t + dur)
                if not any(_overlap(cand, b) for b in busy):
                    found.append({
                        "start": t.isoformat(timespec="minutes"),
                        "end":   (t + dur).isoformat(timespec="minutes")
                    })
                t += step
        # advance exactly one day (outside inner loop)
        cur = dt.datetime.combine(d + dt.timedelta(days=1), dt.time.min)

    print("[NEXT] service={} start={} found={}".format(body.service, body.start_date, len(found)))
    return {"status": "ok", "slots": found}

