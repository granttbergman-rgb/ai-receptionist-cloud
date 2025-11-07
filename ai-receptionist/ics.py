from db import list_appts
from datetime import datetime

def escape(s): return (s or "").replace(",", "\\,").replace(";", "\\;")

def build_ics():
    rows = list_appts()
    out = ["BEGIN:VCALENDAR","VERSION:2.0","PRODID:-//AI 
Receptionist//EN"]
    for rid, caller, name, service, reason, starts_at, ends_at, created in 
rows:
        def fmt(ts):
            return ts.replace("-", "").replace(":", "").split(".")[0] + 
"Z"
        out += [
            "BEGIN:VEVENT",
            f"UID:appt-{rid}@airec",
            f"DTSTAMP:{datetime.utcnow().strftime('%Y%m%dT%H%M%SZ')}",
            f"DTSTART:{fmt(starts_at)}",
            f"DTEND:{fmt(ends_at)}",
            f"SUMMARY:{escape((service or '').title())}",
            f"DESCRIPTION:{escape((name or 'Caller') + ' | ' + (reason or 
''))}",
            "END:VEVENT"
        ]
    out.append("END:VCALENDAR")
    return "\r\n".join(out) + "\r\n"

