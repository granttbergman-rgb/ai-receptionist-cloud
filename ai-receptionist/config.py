import os

BUSINESS_NAME = os.getenv("BUSINESS_NAME", "Reception Demo")
BUSINESS_ID   = os.getenv("BUSINESS_ID", "demo")
TZ            = os.getenv("BUSINESS_TZ", "America/Chicago")

# Services you actually offer. Keep it tight.
SERVICES = {
    "consultation": {"duration_min": 30},
    "cleaning":     {"duration_min": 45},
    "follow up":    {"duration_min": 20},
}

# Booking rules
LEAD_MINUTES   = int(os.getenv("LEAD_MINUTES", "120"))    # minimum notice
OPEN_HOUR      = int(os.getenv("OPEN_HOUR", "9"))
CLOSE_HOUR     = int(os.getenv("CLOSE_HOUR", "17"))
INCREMENT_MIN  = 15  # round to 15 minutes

