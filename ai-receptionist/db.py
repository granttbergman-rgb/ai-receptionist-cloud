import sqlite3, threading, datetime, os

DB_PATH = os.getenv("DB_PATH", "data.db")
_lock = threading.Lock()

def _conn():
    return sqlite3.connect(DB_PATH, check_same_thread=False)

def init():
    with _lock, _conn() as c:
        c.execute("""
            CREATE TABLE IF NOT EXISTS calls(
                id INTEGER PRIMARY KEY,
                call_sid TEXT UNIQUE,
                from_num TEXT,
                started_at TEXT
            );
        """)
        c.execute("""
            CREATE TABLE IF NOT EXISTS appointments(
                id INTEGER PRIMARY KEY,
                caller TEXT,
                name TEXT,
                service TEXT,
                reason TEXT,
                starts_at TEXT,
                ends_at TEXT,
                created_at TEXT
            );
        """)

def log_call(call_sid, from_num):
    with _lock, _conn() as c:
        c.execute(
            "INSERT OR IGNORE INTO calls(call_sid, from_num, started_at) VALUES(?,?,?)",
            (call_sid, from_num, datetime.datetime.utcnow().isoformat()),
        )

def create_appt(caller, name, service, reason, starts_at, ends_at):
    with _lock, _conn() as c:
        c.execute(
            """INSERT INTO appointments(caller,name,service,reason,starts_at,ends_at,created_at)
               VALUES(?,?,?,?,?,?,?)""",
            (caller, name, service, reason, starts_at, ends_at, datetime.datetime.utcnow().isoformat()),
        )
        return c.lastrowid

def list_appts():
    with _lock, _conn() as c:
        cur = c.execute("""
            SELECT id, caller, name, service, reason, starts_at, ends_at, created_at
            FROM appointments ORDER BY starts_at
        """)
        return cur.fetchall()

def delete_appt(appt_id):
    with _lock, _conn() as c:
        c.execute("DELETE FROM appointments WHERE id=?", (appt_id,))
