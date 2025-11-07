import os, json, sqlite3
from google.oauth2.credentials import Credentials
from googleapiclient.discovery import build
from google_auth_oauthlib.flow import Flow

DB = os.getenv("DB_PATH", "data.db")
CLIENT_SECRET_PATH = os.getenv("GOOGLE_CLIENT_SECRET", 
"client_secret.json")
SCOPES = ["https://www.googleapis.com/auth/calendar.events"]

def _db():
    return sqlite3.connect(DB, check_same_thread=False)

def save_token(business: str, token: dict):
    with _db() as c:
        c.execute("""CREATE TABLE IF NOT EXISTS tokens(
          id INTEGER PRIMARY KEY, business TEXT UNIQUE, token_json TEXT
        );""")
        c.execute("INSERT OR REPLACE INTO tokens(business, token_json) 
VALUES(?,?)",
                  (business, json.dumps(token)))

def load_creds(business: str):
    with _db() as c:
        row = c.execute("SELECT token_json FROM tokens WHERE business=?", 
(business,)).fetchone()
    if not row:
        return None
    token = json.loads(row[0])
    return Credentials.from_authorized_user_info(token, SCOPES)

def start_oauth(business: str, public_base: str):
    flow = Flow.from_client_secrets_file(
        CLIENT_SECRET_PATH, scopes=SCOPES,
        redirect_uri=f"{public_base}/oauth/callback"
    )
    auth_url, state = flow.authorization_url(
        access_type="offline", include_granted_scopes=True, 
prompt="consent", state=business
    )
    return auth_url

def finish_oauth(request):
    public_base = os.getenv("PUBLIC_HTTPS", "http://localhost:8000")
    flow = Flow.from_client_secrets_file(
        CLIENT_SECRET_PATH, scopes=SCOPES,
        redirect_uri=f"{public_base}/oauth/callback"
    )
    code = request.query_params.get("code")
    business = request.query_params.get("state") or "demo"
    flow.fetch_token(code=code)
    creds = flow.credentials
    token = {
        "token": creds.token, "refresh_token": creds.refresh_token,
        "token_uri": creds.token_uri, "client_id": creds.client_id,
        "client_secret": creds.client_secret, "scopes": creds.scopes,
    }
    save_token(business, token)
    return business

def _service(business: str):
    creds = load_creds(business)
    if not creds:
        raise RuntimeError("Calendar not connected.")
    return build("calendar", "v3", credentials=creds)

def has_conflict(business: str, start_iso: str, end_iso: str) -> bool:
    svc = _service(business)
    events = svc.events().list(
        calendarId="primary",
        timeMin=start_iso, timeMax=end_iso,
        singleEvents=True, orderBy="startTime"
    ).execute()
    return len(events.get("items", [])) > 0

def create_event(business: str, summary: str, description: str, start_iso: 
str, end_iso: str, timezone: str):
    svc = _service(business)
    ev = {
        "summary": summary,
        "description": description,
        "start": {"dateTime": start_iso, "timeZone": timezone},
        "end":   {"dateTime": end_iso,   "timeZone": timezone},
    }
    return svc.events().insert(calendarId="primary", body=ev).execute()


