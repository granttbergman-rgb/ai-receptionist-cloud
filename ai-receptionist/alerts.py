import os
from twilio.rest import Client

SID  = os.getenv("TWILIO_ACCOUNT_SID")
AUTH = os.getenv("TWILIO_AUTH_TOKEN")
FROM = os.getenv("TWILIO_FROM", "")
TO   = os.getenv("ALERT_NUMBER", "")

def notify(text: str):
    if not (SID and AUTH and FROM and TO):
        print("[ALERT]", text)
        return
    try:
        Client(SID, AUTH).messages.create(to=TO, from_=FROM, body=text)
    except Exception as e:
        print("Twilio SMS error:", e)

