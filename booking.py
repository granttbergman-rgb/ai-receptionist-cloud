# booking.py
import os
import sqlite3
import datetime as dt
from typing import Optional, List, Dict, Tuple

# ---- Config --------------------------------------------------------------

DB_PATH = os.path.join(os.path.dirname(__file__), "data.db")
INCREMENT = 15            # minutes between candidate starts
OPEN_HOUR, CLOSE_HOUR = 9, 17
LEAD_MIN = 120            # minimum notice before a booking (minutes)

# ---- Schema management ---------------------------------------------------

def ensure_schema() -> None:
    """Ensure appointments table exists with an autoincrement id."""
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()

    c.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='appointments'")
    exists = c.fetchone() is not None

    if not exists:
        c.execute("""
        CREATE TABLE appointments (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            service TEXT NOT NULL,
            customer_name TEXT NOT NULL,
            customer_phone TEXT NOT NULL,
            start TEXT NOT NULL,  -- ISO datetime
            end   TEXT NOT NULL   -- ISO datetime
        )
        """)
        conn.commit()
        conn.close()
        return

    # migrate legacy table missing 'id'
    c.execute("PRAGMA table_info(appointments)")
    cols = {row[1] for row in c.fetchall()}
    if "id" not in cols:
        c.execute("""
        CREATE TABLE appointments_new (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            service TEXT NOT NULL,
            customer_name TEXT NOT NULL,
            customer_phone TEXT NOT NULL,
            start TEXT NOT NULL,
            end   TEXT NOT NULL
        )
        """)
        c.execute("""
        INSERT INTO appointments_new (service, customer_name, 
customer_phone, start, end)
        SELECT service, customer_name, customer_phone, start, end FROM 
appointments
        """)
        c.execute("DROP TABLE appointments")
        c.execute("ALTER TABLE appointments_new RENAME TO appointments")
        conn.commit()
    conn.close()

# ---- Helpers -------------------------------------------------------------

def _round_up(t: dt.datetime, inc_min: int) -> dt.datetime:
    """Round up a datetime to the next inc_min boundary."""
    discard = t.minute % inc_min
    if discard:
        t = t + dt.timedelta(minutes=(inc_min - discard))
    return t.replace(second=0, microsecond=0)

def _overlaps(a_start: dt.datetime, a_end: dt.datetime,
              b_start: dt.datetime, b_end: dt.datetime) -> bool:
    """Half-open overlap: [start, end)"""
    return a_start < b_end and b_start < a_end

# ---- Public API ----------------------------------------------------------

def free_slots(service: str, date: str, duration_min: int = 30) -> List[Dict]:
    """
    Compute free time windows on a given YYYY-MM-DD date for a service.
    Returns a list of {"start": ISO, "end": ISO}.
    """
    ensure_schema()

    # bounds for the day
    day = dt.datetime.fromisoformat(f"{date}T00:00:00")
    start_of_day = day.replace(hour=OPEN_HOUR, minute=0, second=0, 
microsecond=0)
    end_of_day   = day.replace(hour=CLOSE_HOUR, minute=0, second=0, 
microsecond=0)

    # enforce lead time
    lead_cutoff = dt.datetime.now() + dt.timedelta(minutes=LEAD_MIN)
    start_of_day = max(start_of_day, _round_up(lead_cutoff, INCREMENT))

    # already booked intervals for that date
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute("SELECT start, end FROM appointments WHERE date(start)=?", 
(date,))
    booked: List[Tuple[dt.datetime, dt.datetime]] = [
        (dt.datetime.fromisoformat(s), dt.datetime.fromisoformat(e)) for 
s, e in c.fetchall()
    ]
    conn.close()

    slots: List[Dict] = []
    cur = start_of_day
    dur = dt.timedelta(minutes=duration_min)
    step = dt.timedelta(minutes=INCREMENT)

    while cur + dur <= end_of_day:
        slot_end = cur + dur
        conflict = any(_overlaps(cur, slot_end, b_start, b_end) for 
b_start, b_end in booked)
        if not conflict:
            slots.append({
                "start": cur.isoformat(timespec="minutes"),
                "end":   slot_end.isoformat(timespec="minutes"),
            })
        cur += step

    return slots

def create(customer_name: str, customer_phone: str, service: str,
           start_iso: str, end_iso: str) -> Dict:
    """
    Create an appointment; returns the full row as a dict.
    Raises ValueError if slot overlaps.
    """
    ensure_schema()

    # parse and normalize
    try:
        start_dt = dt.datetime.fromisoformat(start_iso)
        end_dt   = dt.datetime.fromisoformat(end_iso)
    except ValueError:
        raise ValueError("start/end must be ISO datetimes like 2025-11-06T10:00:00")

    if not (start_dt < end_dt):
        raise ValueError("end must be after start")

    # conflict check: half-open intervals
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute("""
        SELECT start, end FROM appointments
        WHERE date(start)=date(?) AND NOT (? <= start OR ? >= end)
    """, (start_iso, end_iso, start_iso))
    if c.fetchone():
        conn.close()
        raise ValueError("timeslot already booked")

    c.execute("""
        INSERT INTO appointments (service, customer_name, customer_phone, 
start, end)
        VALUES (?,?,?,?,?)
    """, (service, customer_name, customer_phone, start_dt.isoformat(), 
end_dt.isoformat()))
    appt_id = c.lastrowid
    conn.commit()

    row = c.execute(
        "SELECT id, service, customer_name, customer_phone, start, end FROM appointments WHERE id=?",
        (appt_id,)
    ).fetchone()
    conn.close()

    return {
        "id": row[0],
        "service": row[1],
        "customer_name": row[2],
        "customer_phone": row[3],
        "start": row[4],
        "end": row[5],
    }

