from fastapi import FastAPI
from app.routers import agent

app = FastAPI(title="AI Receptionist Cloud")

# Mount under /agent so your /agent/check_availability URL actually exists
app.include_router(agent.router, prefix="/agent", tags=["agent"])
@app.get("/")
def root():
    return {"ok": True}

@app.get("/health")
def health():
    return {"status": "ok"}

